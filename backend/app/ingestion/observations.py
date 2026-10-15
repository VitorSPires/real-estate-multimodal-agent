"""Model outputs → observations (one fact + where it came from).

After this step nothing downstream cares which model or document type produced a fact: verify
and merge only see `Observation`s.
"""

from pathlib import Path

from app.ingestion.documents import Region, locate_quote
from app.ingestion.schemas import ChartReading, Evidence, FloorPlanReading, IntFact, Observation, TextExtraction, TextFact

TEXT_FIELDS = (
    "title", "neighborhood", "price_usd", "area_m2", "bedrooms", "suites", "bathrooms",
    "parking_spots", "floor", "condo_fee_usd", "property_tax_usd", "stated_price_per_m2",
)


def from_text(
    reading: TextExtraction, region: Region, model: str, data_dir: Path, pdf_path: Path | None
) -> list[Observation]:
    """Facts from a brochure's text layer (pdf_path given) or from a photo of a printed page."""
    observations = []
    for field in TEXT_FIELDS:
        fact: IntFact | TextFact = getattr(reading, field)
        if fact.value is not None:
            observations.append(Observation(field=field, value=fact.value, evidence=_text_evidence(
                fact.quote, region, model, data_dir, pdf_path,
            )))
    for mention in reading.amenities:
        observations.append(Observation(field=f"amenity.{mention.amenity}", value=True, evidence=_text_evidence(
            mention.quote, region, model, data_dir, pdf_path,
        )))
    return observations


def from_floor_plan(reading: FloorPlanReading, region: Region, model: str, data_dir: Path) -> list[Observation]:
    """The plan is a second source for room counts and area — used to cross-check the brochure."""
    kinds = [room.kind for room in reading.rooms]
    labels = ", ".join(room.label for room in reading.rooms)
    evidence = _image_evidence(region, model, data_dir, quote=labels)

    observations = [
        Observation(field="floorplan.bedrooms", value=kinds.count("bedroom"), evidence=evidence),
        Observation(field="floorplan.offices", value=kinds.count("office"), evidence=evidence),
        Observation(field="floorplan.bathrooms", value=kinds.count("bathroom"), evidence=evidence),
    ]
    if reading.title:
        observations.append(Observation(field="title", value=reading.title, evidence=evidence))
    if reading.total_area_m2:
        observations.append(Observation(field="floorplan.area_m2", value=reading.total_area_m2, evidence=evidence))
    for mention in reading.amenities:
        observations.append(Observation(
            field=f"amenity.{mention.amenity}", value=True,
            evidence=_image_evidence(region, model, data_dir, quote=mention.quote),
        ))
    return observations


def from_chart(reading: ChartReading, region: Region, model: str, data_dir: Path) -> list[Observation]:
    points = sorted(reading.points, key=lambda point: point.year)
    trend = [{"year": point.year, "price_per_m2": round(point.value)} for point in points]
    quote = reading.title or reading.metric
    return [Observation(field="price_trend", value=trend, evidence=_image_evidence(region, model, data_dir, quote))]


def _text_evidence(quote, region: Region, model, data_dir: Path, pdf_path: Path | None) -> Evidence:
    if pdf_path is None:  # photo of a page: the whole image is the evidence
        return _image_evidence(region, model, data_dir, quote)

    found = locate_quote(pdf_path, quote) if quote else None
    page, bbox = found if found else (None, None)
    page_render = region.evidence_image.with_name(f"{region.document}-p{page or 1}.png")
    return Evidence(
        document=region.document, page=page, bbox=bbox, quote=quote, method="native_text", model=model,
        image_path=_relative(page_render, data_dir),
    )


def _image_evidence(region: Region, model: str, data_dir: Path, quote: str | None = None) -> Evidence:
    return Evidence(
        document=region.document, page=region.page, bbox=region.bbox, quote=quote, method="vision", model=model,
        image_path=_relative(region.evidence_image, data_dir),
    )


def _relative(path: Path | None, data_dir: Path) -> str | None:
    if path is None:
        return None
    try:
        return path.resolve().relative_to(data_dir.resolve()).as_posix()
    except ValueError:  # outside the data dir (e.g. CLI runs on the dataset folder)
        return path.as_posix()
