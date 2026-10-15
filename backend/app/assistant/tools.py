"""Conversation tools: what the assistant can look up while talking to the buyer.

Plain, deterministic functions over the stored listings — no model calls — so answers are fast
(voice can't wait for a vision model) and only ever come from verified, evidence-backed data.
The same tools serve the text chat and the voice session.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.db import SessionLocal
from app.ingestion.merge import listing_key
from app.ingestion.schemas import AMENITIES, ListingRecord
from app.store import list_listings as load_listings

LOW_CONFIDENCE = 0.7
AMENITY_PARAM = {"type": "array", "items": {"type": "string", "enum": list(AMENITIES)}}
LISTING_PARAM = {"type": "string", "description": "Listing id or title, e.g. 'harbor-view-1104'."}


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    parameters: dict
    run: Callable[..., dict]


# --- Tool implementations ------------------------------------------------------------------------


def list_listings() -> dict:
    return {"listings": [_summary(listing) for listing in _listings()]}


def filter_listings(
    min_bedrooms: int | None = None,
    max_price_usd: int | None = None,
    min_area_m2: int | None = None,
    required_amenities: list[str] | None = None,
    neighborhood: str | None = None,
) -> dict:
    matches, excluded = [], []
    for listing in _listings():
        reasons = _mismatches(listing, min_bedrooms, max_price_usd, min_area_m2, required_amenities or [], neighborhood)
        if reasons:
            excluded.append({"id": listing.id, "title": listing.title, "why_not": reasons})
        else:
            matches.append(_summary(listing))
    return {"matches": matches, "excluded": excluded}


def get_listing(listing: str) -> dict:
    record = _find(listing)
    return {
        "id": record.id,
        "title": record.title,
        "documents": record.documents,
        "fields": {name: _field(value) for name, value in record.fields.items()},
        "amenities": [name for name, value in record.amenities.items() if value.value],
        "price_trend": record.price_trend.value if record.price_trend else None,
        "warnings": record.warnings,
    }


def compare_listings(listings: list[str]) -> dict:
    rows = []
    for item in listings:
        record = _find(item)
        rows.append({
            **_summary(record),
            "condo_fee_usd": _value(record, "condo_fee_usd"),
            "property_tax_usd": _value(record, "property_tax_usd"),
            "parking_spots": _value(record, "parking_spots"),
            "floor": _value(record, "floor"),
        })
    return {"comparison": rows}


def neighborhood_price_check(listing: str) -> dict:
    """Compare a listing's price per m² with the latest neighborhood average from any brochure chart."""
    record = _find(listing)
    neighborhood = _value(record, "neighborhood")
    trend = next(
        (other.price_trend.value for other in _listings()
         if other.price_trend and _value(other, "neighborhood") == neighborhood),
        None,
    )
    price_per_m2 = _value(record, "price_per_m2")
    if not trend or not price_per_m2:
        return {"listing": record.title, "available": False,
                "reason": f"No neighborhood price data for {neighborhood} in the documents."}
    latest = trend[-1]
    return {
        "listing": record.title,
        "available": True,
        "neighborhood": neighborhood,
        "listing_price_per_m2": price_per_m2,
        "neighborhood_avg_price_per_m2": latest["price_per_m2"],
        "year": latest["year"],
        "difference_pct": round((price_per_m2 - latest["price_per_m2"]) / latest["price_per_m2"] * 100, 1),
        "trend_since_first_year_pct": round((latest["price_per_m2"] - trend[0]["price_per_m2"]) / trend[0]["price_per_m2"] * 100, 1),
    }


def show_evidence(listing: str, field: str) -> dict:
    """Where a fact came from. The UI reacts to this tool by opening the evidence viewer."""
    record = _find(listing)
    key = field.removeprefix("amenity.")
    value = record.amenities.get(key) if key in record.amenities else record.fields.get(field)
    if field == "price_trend":
        value = record.price_trend
    if value is None:
        return {"listing_id": record.id, "field": field, "found": False}
    return {
        "listing_id": record.id,
        "title": record.title,
        "field": field,
        "found": True,
        "value": value.value,
        "evidence": [e.model_dump(mode="json") for e in value.evidence],
        "conflicts": [{"value": a.value, "note": a.note} for a in value.conflict],
    }


TOOLS: list[Tool] = [
    Tool("list_listings", "Short summary of every apartment the user has uploaded.",
         {"type": "object", "properties": {}, "additionalProperties": False}, list_listings),
    Tool("filter_listings", "Find apartments that meet ALL the user's requirements so far. "
         "Returns matches and, for the others, why they don't match.",
         {"type": "object", "properties": {
             "min_bedrooms": {"type": "integer"},
             "max_price_usd": {"type": "integer"},
             "min_area_m2": {"type": "integer"},
             "required_amenities": AMENITY_PARAM,
             "neighborhood": {"type": "string"},
         }, "additionalProperties": False}, filter_listings),
    Tool("get_listing", "All extracted facts of one apartment, with confidence and conflicts between documents.",
         {"type": "object", "properties": {"listing": LISTING_PARAM}, "required": ["listing"],
          "additionalProperties": False}, get_listing),
    Tool("compare_listings", "Side-by-side comparison of two or more apartments, including fees.",
         {"type": "object", "properties": {"listings": {"type": "array", "items": LISTING_PARAM}},
          "required": ["listings"], "additionalProperties": False}, compare_listings),
    Tool("neighborhood_price_check", "Is the apartment's price per m² above or below its neighborhood "
         "average? Uses price charts found in the brochures.",
         {"type": "object", "properties": {"listing": LISTING_PARAM}, "required": ["listing"],
          "additionalProperties": False}, neighborhood_price_check),
    Tool("show_evidence", "Show the user the document region a fact came from (opens it on screen). "
         "field: a field name like 'bedrooms' or 'price_usd', an amenity like 'bbq_grill', or 'price_trend'.",
         {"type": "object", "properties": {"listing": LISTING_PARAM, "field": {"type": "string"}},
          "required": ["listing", "field"], "additionalProperties": False}, show_evidence),
]
TOOLS_BY_NAME = {tool.name: tool for tool in TOOLS}


def run_tool(name: str, arguments: dict[str, Any]) -> dict:
    """Execute a tool by name. Errors become results, so the model can recover and say so."""
    tool = TOOLS_BY_NAME.get(name)
    if tool is None:
        return {"error": f"Unknown tool: {name}"}
    try:
        return tool.run(**arguments)
    except LookupError as error:
        return {"error": str(error)}
    except TypeError as error:
        return {"error": f"Bad arguments for {name}: {error}"}


def responses_api_definitions() -> list[dict]:
    """Format used by GPT-Live delegation (Responses API): flat function objects."""
    return [{"type": "function", "name": t.name, "description": t.description, "parameters": t.parameters} for t in TOOLS]


def chat_completions_definitions() -> list[dict]:
    """Format used by Chat Completions (text chat): nested under "function"."""
    return [{"type": "function", "function": {"name": t.name, "description": t.description, "parameters": t.parameters}}
            for t in TOOLS]


# --- Helpers -------------------------------------------------------------------------------------


def _listings() -> list[ListingRecord]:
    with SessionLocal() as session:
        return load_listings(session)


def _find(listing: str) -> ListingRecord:
    """Accepts an id ('harbor-view-1104'), a title, or an unambiguous part of one ('harbor view')."""
    key = listing_key(listing)
    records = _listings()
    exact = [r for r in records if r.id == key]
    partial = [r for r in records if key and key in r.id]
    if exact or len(partial) == 1:
        return (exact or partial)[0]
    raise LookupError(f"No single listing matches '{listing}'. Known: {', '.join(r.id for r in records)}")


def _value(record: ListingRecord, field: str) -> Any:
    value = record.fields.get(field)
    return value.value if value else None


def _summary(record: ListingRecord) -> dict:
    return {
        "id": record.id,
        "title": record.title,
        "neighborhood": _value(record, "neighborhood"),
        "price_usd": _value(record, "price_usd"),
        "area_m2": _value(record, "area_m2"),
        "bedrooms": _value(record, "bedrooms"),
        "bathrooms": _value(record, "bathrooms"),
        "price_per_m2": _value(record, "price_per_m2"),
        "amenities": [name for name, value in record.amenities.items() if value.value],
        "conflicts": [
            f"{name}: {alt.note}" for name, value in record.fields.items() for alt in value.conflict if alt.note
        ],
    }


def _field(value) -> dict:
    result: dict[str, Any] = {"value": value.value}
    if value.confidence < LOW_CONFIDENCE:
        result["low_confidence"] = True
    if value.conflict:
        result["conflicts"] = [{"value": a.value, "note": a.note} for a in value.conflict]
    return result


def _mismatches(record, min_bedrooms, max_price, min_area, amenities, neighborhood) -> list[str]:
    reasons = []
    bedrooms, price, area = _value(record, "bedrooms"), _value(record, "price_usd"), _value(record, "area_m2")
    if min_bedrooms is not None and (bedrooms or 0) < min_bedrooms:
        reasons.append(f"{bedrooms} bedroom(s)")
    if max_price is not None and price and price > max_price:
        reasons.append(f"costs USD {price:,}")
    if min_area is not None and (area or 0) < min_area:
        reasons.append(f"{area} m²")
    for amenity in amenities:
        if not (record.amenities.get(amenity) and record.amenities[amenity].value):
            reasons.append(f"no {amenity.replace('_', ' ')} mentioned")
    if neighborhood and listing_key(neighborhood) != listing_key(_value(record, "neighborhood") or ""):
        reasons.append(f"in {_value(record, 'neighborhood')}")
    return reasons
