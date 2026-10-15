"""Data shapes of the ingestion pipeline.

Three layers, from raw to final:
1. LLM outputs  — what we ask models to return (`TextExtraction`, `FloorPlanReading`, ...).
2. Observations — one fact from one place in one document, with its evidence.
3. ListingRecord — all observations of a listing merged, with confidence and conflicts.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field

AmenityKey = Literal["bbq_grill", "pool", "gym", "gourmet_balcony", "pet_friendly", "elevator", "doorman"]
AMENITIES: tuple[str, ...] = AmenityKey.__args__

Method = Literal["native_text", "vision", "computed"]


# --- 1. LLM outputs -----------------------------------------------------------------------------


class IntFact(BaseModel):
    value: int | None = None
    quote: str | None = Field(None, description="Exact text the value was read from.")


class TextFact(BaseModel):
    value: str | None = None
    quote: str | None = Field(None, description="Exact text the value was read from.")


class AmenityMention(BaseModel):
    amenity: AmenityKey
    quote: str = Field(description="Exact text or label that mentions the amenity.")


class TextExtraction(BaseModel):
    """Listing facts read from text: a brochure's text layer, or a photo of a printed page."""

    title: TextFact = TextFact()
    neighborhood: TextFact = TextFact()
    price_usd: IntFact = IntFact()
    area_m2: IntFact = IntFact()
    bedrooms: IntFact = IntFact()
    suites: IntFact = IntFact()
    bathrooms: IntFact = IntFact()
    parking_spots: IntFact = IntFact()
    floor: IntFact = IntFact()
    condo_fee_usd: IntFact = Field(default_factory=IntFact, description="Monthly condo / HOA fee.")
    property_tax_usd: IntFact = Field(default_factory=IntFact, description="Yearly property tax.")
    stated_price_per_m2: IntFact = Field(
        default_factory=IntFact, description="Price per m² only if the document explicitly states it."
    )
    amenities: list[AmenityMention] = []


RegionKind = Literal["floor_plan", "chart", "document_photo", "property_photo", "other"]


class RegionTriage(BaseModel):
    kind: RegionKind
    reason: str = Field(description="One short sentence.")


class FloorPlanRoom(BaseModel):
    label: str = Field(description="Label exactly as printed, e.g. 'MBR', 'BR 2', 'OFFICE'.")
    kind: Literal["bedroom", "office", "bathroom", "kitchen", "living", "balcony", "laundry", "other"]
    width_m: float | None = None
    length_m: float | None = None


class FloorPlanReading(BaseModel):
    title: str | None = Field(None, description="Unit / building name printed on the plan.")
    total_area_m2: float | None = None
    rooms: list[FloorPlanRoom] = []
    amenities: list[AmenityMention] = []


class ChartPoint(BaseModel):
    year: int
    value: float


class ChartReading(BaseModel):
    title: str | None = None
    neighborhood: str | None = None
    metric: str | None = Field(None, description="What the y axis measures, e.g. 'price per m² (USD)'.")
    points: list[ChartPoint] = []


# --- 2. Observations ----------------------------------------------------------------------------


class Evidence(BaseModel):
    """Where a fact came from. `bbox` is normalized to 0–1 of the page/image (x0, y0, x1, y1)."""

    document: str
    page: int | None = None
    bbox: tuple[float, float, float, float] | None = None
    quote: str | None = None
    method: Method
    model: str | None = None
    image_path: str | None = Field(None, description="Page render or image to show, relative to the data dir.")


class Observation(BaseModel):
    """One fact, e.g. field='bedrooms' value=2, or field='amenity.bbq_grill' value=True."""

    field: str
    value: Any
    evidence: Evidence


# --- 3. Merged listing --------------------------------------------------------------------------


class Alternative(BaseModel):
    value: Any
    evidence: list[Evidence]
    note: str | None = None


class FieldValue(BaseModel):
    value: Any
    confidence: float
    evidence: list[Evidence] = []
    conflict: list[Alternative] = Field(default_factory=list, description="Competing values, if sources disagree.")


class ListingRecord(BaseModel):
    id: str = Field(description="Stable key derived from the title, e.g. 'harbor-view-1104'.")
    title: str
    documents: list[str]
    fields: dict[str, FieldValue]
    amenities: dict[str, FieldValue]
    price_trend: FieldValue | None = None
    warnings: list[str] = []
