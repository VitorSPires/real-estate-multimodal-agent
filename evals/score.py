"""Compare merged listings to ground truth, one check per fact.

Every check belongs to a *category* named after where the fact had to be read from, so the report
can say "vision on floor plans is the weak spot" instead of just "87% accurate".
"""

from dataclasses import dataclass

TEXT_FIELDS = ("neighborhood", "price_usd", "area_m2", "bedrooms", "suites", "bathrooms", "parking_spots", "floor")

# Category → the routing task that reads it (so results can recommend a model per task).
CATEGORY_TASK = {
    "brochure_text": "text",
    "fees": "text",
    "fees_from_photo": "document_photo",
    "amenity_from_text": "text",
    "amenity_from_floorplan": "floor_plan",
    "chart": "chart",
    "conflict": "floor_plan",
}


@dataclass
class Check:
    listing: str
    category: str
    name: str
    expected: object
    actual: object
    ok: bool


def score_listing(truth: dict, record: dict | None) -> list[Check]:
    """`truth` is a ground_truth.json; `record` the matching ListingRecord as a dict (None = missing)."""
    slug = truth["slug"]
    expected = truth["fields"]
    fields = (record or {}).get("fields", {})
    amenities = (record or {}).get("amenities", {})
    checks: list[Check] = []

    def add(category, name, want, got, ok=None):
        checks.append(Check(slug, category, name, want, got, (want == got) if ok is None else ok))

    for name in TEXT_FIELDS:
        add("brochure_text", name, expected[name], _value(fields, name))

    fee_category = "fees" if truth["sources"]["fees"].endswith(".pdf") else "fees_from_photo"
    for name in ("condo_fee_usd", "property_tax_usd"):
        add(fee_category, name, expected[name], _value(fields, name))

    sources = truth["sources"]["amenities"]
    for amenity, want in expected["amenities"].items():
        got = amenities.get(amenity, {}).get("value")
        source = sources.get(amenity, "brochure_text")
        category = "amenity_from_floorplan" if source == "floorplan" else "amenity_from_text"
        add(category, f"amenity.{amenity}", want, got)

    if expected["price_trend"]:
        got = (record or {}).get("price_trend") or {}
        add("chart", "price_trend", expected["price_trend"], got.get("value"),
            ok=_trend_close(expected["price_trend"], got.get("value"), truth["tolerances"]["price_trend"]))

    for conflict in truth["expected_conflicts"]:
        field = fields.get(conflict["field"], {})
        found = {field.get("value"), *(alt["value"] for alt in field.get("conflict", []))}
        add("conflict", f"conflict.{conflict['field']}", sorted(conflict["values"]), sorted(v for v in found if v is not None),
            ok=set(conflict["values"]) <= found)
    return checks


def _value(fields: dict, name: str):
    return fields.get(name, {}).get("value")


def _trend_close(expected: list[dict], actual: list[dict] | None, tolerance: float) -> bool:
    if not actual or len(actual) != len(expected):
        return False
    for want, got in zip(expected, actual):
        if want["year"] != got["year"]:
            return False
        if abs(got["price_per_m2"] - want["price_per_m2"]) / want["price_per_m2"] > tolerance:
            return False
    return True


def accuracy(checks: list[Check]) -> float:
    return sum(c.ok for c in checks) / len(checks) if checks else 0.0
