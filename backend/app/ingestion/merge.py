"""Observations from many documents → one ListingRecord per apartment.

Three jobs:
1. Group: which documents describe the same apartment? (match on the printed title)
2. Choose: when several sources give a field, which value wins? (native text > vision)
3. Cross-check: when sources disagree, keep the winner but record the alternative as a conflict.
"""

import re
from collections import defaultdict
from dataclasses import dataclass

from app.ingestion.schemas import AMENITIES, Alternative, Evidence, FieldValue, ListingRecord, Observation

CONFIDENCE = {"native_text": 0.95, "vision": 0.85}
CONFLICT_PENALTY = 0.7
SIMPLE_FIELDS = (
    "neighborhood", "price_usd", "area_m2", "bedrooms", "suites", "bathrooms",
    "parking_spots", "floor", "condo_fee_usd", "property_tax_usd",
)


@dataclass
class DocumentObservations:
    document: str
    observations: list[Observation]
    unresolved_problems: list[str]


def listing_key(title: str) -> str:
    """'HARBOR VIEW 1104' and 'Harbor View 1104' → 'harbor-view-1104'."""
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")


def merge(documents: list[DocumentObservations]) -> tuple[list[ListingRecord], list[str]]:
    """Returns the merged listings and the names of documents we couldn't assign to any listing."""
    groups: dict[str, list[DocumentObservations]] = defaultdict(list)
    titles: dict[str, str] = {}
    unassigned = []

    for doc in documents:
        title = _document_title(doc)
        if title is None:
            unassigned.append(doc.document)
            continue
        key = listing_key(title)
        groups[key].append(doc)
        # Prefer the brochure's casing ("Harbor View 1104") over the plan's ("HARBOR VIEW 1104").
        if key not in titles or titles[key].isupper():
            titles[key] = title

    records = [_merge_listing(key, titles[key], docs) for key, docs in groups.items()]
    return sorted(records, key=lambda record: record.id), unassigned


def _document_title(doc: DocumentObservations) -> str | None:
    titles = [o for o in doc.observations if o.field == "title"]
    titles.sort(key=lambda o: o.evidence.method != "native_text")
    return str(titles[0].value) if titles else None


def _merge_listing(key: str, title: str, docs: list[DocumentObservations]) -> ListingRecord:
    by_field: dict[str, list[Observation]] = defaultdict(list)
    for doc in docs:
        for observation in doc.observations:
            by_field[observation.field].append(observation)

    fields = {name: _choose(by_field[name]) for name in SIMPLE_FIELDS if by_field[name]}
    _fill_from_floor_plan(fields, by_field)
    _cross_check_bedrooms(fields, by_field)
    _cross_check_number(fields, by_field, "bathrooms", "floorplan.bathrooms", tolerance=0)
    _cross_check_number(fields, by_field, "area_m2", "floorplan.area_m2", tolerance=0.05)
    _price_per_m2(fields, by_field)

    warnings = [f"{doc.document}: {problem}" for doc in docs for problem in doc.unresolved_problems]
    return ListingRecord(
        id=key,
        title=title,
        documents=sorted({doc.document for doc in docs}),
        fields=fields,
        amenities={amenity: _amenity(by_field[f"amenity.{amenity}"]) for amenity in AMENITIES},
        price_trend=_choose(by_field["price_trend"]) if by_field["price_trend"] else None,
        warnings=warnings,
    )


def _choose(observations: list[Observation]) -> FieldValue:
    """Native text beats vision; disagreeing values become conflict alternatives."""
    ranked = sorted(observations, key=lambda o: o.evidence.method != "native_text")
    winner = ranked[0]
    agreeing = [o.evidence for o in ranked if o.value == winner.value]
    alternatives = _group_alternatives([o for o in ranked if o.value != winner.value])
    confidence = CONFIDENCE.get(winner.evidence.method, 0.8)
    return FieldValue(
        value=winner.value,
        confidence=round(confidence * (CONFLICT_PENALTY if alternatives else 1), 2),
        evidence=agreeing,
        conflict=alternatives,
    )


def _group_alternatives(observations: list[Observation], note: str | None = None) -> list[Alternative]:
    grouped: dict[str, Alternative] = {}
    for o in observations:
        key = repr(o.value)
        grouped.setdefault(key, Alternative(value=o.value, evidence=[], note=note)).evidence.append(o.evidence)
    return list(grouped.values())


def _fill_from_floor_plan(fields: dict[str, FieldValue], by_field) -> None:
    """If the brochure doesn't state bedrooms/bathrooms/area, the floor plan can."""
    for field, plan_field in (("bedrooms", "floorplan.bedrooms"), ("bathrooms", "floorplan.bathrooms"),
                              ("area_m2", "floorplan.area_m2")):
        if field not in fields and by_field[plan_field]:
            fields[field] = _choose(by_field[plan_field])


def _cross_check_bedrooms(fields: dict[str, FieldValue], by_field) -> None:
    """A room labeled OFFICE is the classic 'is it a bedroom?' ambiguity: keep the advertised
    count, but surface bedrooms + offices as an alternative the buyer should know about."""
    if "bedrooms" not in fields or not by_field["floorplan.bedrooms"]:
        return
    advertised = fields["bedrooms"]
    plan_bedrooms = by_field["floorplan.bedrooms"][0]
    offices = by_field["floorplan.offices"][0] if by_field["floorplan.offices"] else None

    if plan_bedrooms.value != advertised.value:
        _add_conflict(advertised, plan_bedrooms.value, plan_bedrooms.evidence,
                      f"the floor plan shows {plan_bedrooms.value} bedrooms")
    if offices and offices.value:
        _add_conflict(advertised, plan_bedrooms.value + offices.value, offices.evidence,
                      f"the floor plan shows {plan_bedrooms.value} bedrooms plus {offices.value} "
                      "room(s) labeled as office, which could be used as a bedroom")


def _cross_check_number(fields, by_field, field: str, plan_field: str, tolerance: float) -> None:
    if field not in fields or not by_field[plan_field]:
        return
    plan = by_field[plan_field][0]
    value = fields[field].value
    if value and abs(plan.value - value) / value > tolerance:
        _add_conflict(fields[field], plan.value, plan.evidence, f"the floor plan says {plan.value}")


def _price_per_m2(fields: dict[str, FieldValue], by_field) -> None:
    """Always computed from price and area; a stated value that disagrees becomes a conflict."""
    if "price_usd" not in fields or "area_m2" not in fields:
        return
    price, area = fields["price_usd"], fields["area_m2"]
    computed = FieldValue(
        value=round(price.value / area.value),
        confidence=min(price.confidence, area.confidence),
        evidence=[*price.evidence[:1], *area.evidence[:1]],
    )
    computed.evidence = [e.model_copy(update={"method": "computed"}) for e in computed.evidence]
    for stated in by_field["stated_price_per_m2"]:
        if abs(stated.value - computed.value) / computed.value > 0.03:
            _add_conflict(computed, stated.value, stated.evidence,
                          f"the document states {stated.value:,}, but price / area = {computed.value:,}")
    fields["price_per_m2"] = computed


def _amenity(observations: list[Observation]) -> FieldValue:
    if not observations:  # not mentioned anywhere: probably absent, but absence is weak evidence
        return FieldValue(value=False, confidence=0.6)
    best = max(CONFIDENCE.get(o.evidence.method, 0.8) for o in observations)
    return FieldValue(value=True, confidence=best, evidence=[o.evidence for o in observations])


def _add_conflict(target: FieldValue, value, evidence: Evidence, note: str) -> None:
    target.conflict.append(Alternative(value=value, evidence=[evidence], note=note))
    target.confidence = round(min(target.confidence, max(CONFIDENCE.values()) * CONFLICT_PENALTY), 2)
