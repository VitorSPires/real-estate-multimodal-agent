"""Write the canned answers used by FakeLLMClient (tests + offline dev mode, LLM_PROVIDER=fake).

They are what a model that reads every document correctly would return, built from spec.py —
with ONE deliberate mistake: the first reading of Harbor View's chart comes back with only two
points, so the pipeline's verify → escalate path runs. The escalation model then reads it well,
with small estimation errors, like a real model reading values off a plot.

This is a test double, not an extraction result: real numbers come from evals with real models.

Usage (repo root):  backend/.venv/Scripts/python -m dataset.make_fake_llm
"""

import json
from pathlib import Path

from dataset.spec import AMENITY_NAMES, LISTINGS, Listing

OUT = Path(__file__).parent.parent / "backend" / "app" / "ingestion" / "fakes" / "dataset_responses.json"
ESCALATION_MODEL = "openai/gpt-6.1-sol"  # Routing().escalation

ROOM_KINDS = {"bedroom": "bedroom", "office": "office", "bath": "bathroom", "kitchen": "kitchen",
              "living": "living", "balcony": "balcony", "laundry": "laundry"}


def fact(value, quote):
    return {"value": value, "quote": quote}


def text_extraction(listing: Listing) -> dict:
    answer = {
        "title": fact(listing.title, listing.title),
        "neighborhood": fact(listing.neighborhood, listing.neighborhood),
        "price_usd": fact(listing.price_usd, f"USD {listing.price_usd:,}"),
        "area_m2": fact(listing.area_m2, f"{listing.area_m2} m²"),
        "bedrooms": fact(listing.bedrooms, f"Bedrooms {listing.bedrooms}"),
        "suites": fact(listing.suites, f"Suites {listing.suites}"),
        "bathrooms": fact(listing.bathrooms, f"Bathrooms {listing.bathrooms}"),
        "parking_spots": fact(listing.parking_spots, "Parking"),
        "floor": fact(listing.floor, f"Floor {listing.floor}"),
        "amenities": [{"amenity": a, "quote": AMENITY_NAMES[a]} for a in sorted(listing.brochure_amenities)]
        + [{"amenity": a, "quote": listing.photo_caption} for a in sorted(listing.caption_amenities)],
    }
    if listing.fees_in_brochure:
        answer["condo_fee_usd"] = fact(listing.condo_fee_usd, f"USD {listing.condo_fee_usd:,} / month")
        answer["property_tax_usd"] = fact(listing.property_tax_usd, f"USD {listing.property_tax_usd:,} / year")
    if listing.stated_price_per_m2:
        answer["stated_price_per_m2"] = fact(listing.stated_price_per_m2, f"USD {listing.stated_price_per_m2:,}")
    return answer


def floor_plan(listing: Listing) -> dict:
    return {
        "title": listing.title.upper(),
        "total_area_m2": listing.area_m2,
        "rooms": [
            {"label": r.label, "kind": ROOM_KINDS[r.kind], "width_m": r.w, "length_m": r.h} for r in listing.rooms
        ],
        "amenities": [
            {"amenity": a, "quote": "BBQ" if a == "bbq_grill" else "GOURMET BALC."}
            for a in sorted(listing.floorplan_amenities)
        ],
    }


def chart(listing: Listing) -> dict:
    estimate = [round(v * (1.008 if i % 2 else 0.994)) for i, (_, v) in enumerate(listing.price_trend)]
    good = {
        "title": f"{listing.neighborhood}: average price per m² (USD)",
        "neighborhood": listing.neighborhood,
        "metric": "average price per m² (USD)",
        "points": [{"year": y, "value": v} for (y, _), v in zip(listing.price_trend, estimate)],
    }
    flawed = {**good, "points": good["points"][:2]}
    return {"default": flawed, "by_model": {ESCALATION_MODEL: good}}


def price_sheet(listing: Listing) -> dict:
    return {
        "title": fact(listing.title, f"{listing.title} · {listing.neighborhood}"),
        "neighborhood": fact(listing.neighborhood, listing.neighborhood),
        "price_usd": fact(listing.price_usd, f"USD {listing.price_usd:,}"),
        "condo_fee_usd": fact(listing.condo_fee_usd, f"Condo fee (monthly) USD {listing.condo_fee_usd:,}"),
        "property_tax_usd": fact(listing.property_tax_usd, f"Property tax (yearly) USD {listing.property_tax_usd:,}"),
        "parking_spots": fact(listing.parking_spots, f"{listing.parking_spots} spots included"),
    }


def build() -> dict:
    responses = {}
    for listing in LISTINGS:
        names = listing.document_names
        brochure, plan = names["brochure"], names["floorplan"]

        responses[f"text:{brochure}#text"] = text_extraction(listing)
        responses[f"triage:{brochure}#p1-img1"] = {"kind": "property_photo", "reason": "Photo of buildings."}
        if listing.price_trend:
            responses[f"triage:{brochure}#p2-img1"] = {"kind": "chart", "reason": "Line chart of prices."}
            responses[f"chart:{brochure}#p2-img1"] = chart(listing)
        responses[f"triage:{plan}"] = {"kind": "floor_plan", "reason": "Architectural drawing of rooms."}
        responses[f"floor_plan:{plan}"] = floor_plan(listing)
        if "price_sheet" in names:
            sheet = names["price_sheet"]
            responses[f"triage:{sheet}"] = {"kind": "document_photo", "reason": "Photo of a printed price sheet."}
            responses[f"document_photo:{sheet}"] = price_sheet(listing)
    return responses


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(build(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
