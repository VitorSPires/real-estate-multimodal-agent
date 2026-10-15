"""The four fictional listings: the single source of truth for documents AND ground truth.

Every document is rendered from these objects, and ground_truth.json is derived from the same
objects, so the two can't drift apart. The traps are explicit fields, not accidents:

- `brochure_amenities` / `caption_amenities` / `floorplan_amenities` control WHERE each amenity
  is mentioned (e.g. a BBQ grill that only appears as a floor-plan label).
- `fees_in_brochure=False` means condo fee and property tax only appear in the phone photo.
- `stated_price_per_m2` is what the brochure prints, which may disagree with price / area.
- `expected_conflicts` lists what a good pipeline should flag instead of silently picking one.
"""

from dataclasses import dataclass, field

AMENITY_NAMES = {
    "bbq_grill": "BBQ grill",
    "pool": "Swimming pool",
    "gym": "Gym",
    "gourmet_balcony": "Gourmet balcony",
    "pet_friendly": "Pet friendly",
    "elevator": "Elevator",
    "doorman": "24h doorman",
}


@dataclass(frozen=True)
class Room:
    """A rectangle on the floor plan, in meters. `label` is what's printed on the drawing."""

    label: str
    kind: str  # bedroom | office | living | kitchen | bath | laundry | balcony
    x: float
    y: float
    w: float
    h: float
    furniture: tuple[str, ...] = ()  # "bed", "desk", "bbq"

    @property
    def area(self) -> float:
        return self.w * self.h


@dataclass(frozen=True)
class Listing:
    slug: str
    title: str
    neighborhood: str
    price_usd: int
    area_m2: int
    bedrooms: int
    suites: int
    bathrooms: int
    parking_spots: int
    floor: int
    condo_fee_usd: int  # monthly
    property_tax_usd: int  # yearly
    description: str
    rooms: tuple[Room, ...]
    brochure_amenities: frozenset[str]
    caption_amenities: frozenset[str] = frozenset()
    floorplan_amenities: frozenset[str] = frozenset()
    photo_caption: str = ""
    fees_in_brochure: bool = True
    stated_price_per_m2: int | None = None
    price_trend: tuple[tuple[int, int], ...] = ()  # (year, avg USD per m2 in the neighborhood)
    expected_conflicts: tuple[dict, ...] = field(default_factory=tuple)
    seed: int = 0

    @property
    def amenities(self) -> frozenset[str]:
        return self.brochure_amenities | self.caption_amenities | self.floorplan_amenities

    @property
    def price_per_m2(self) -> int:
        return round(self.price_usd / self.area_m2)


LISTINGS: tuple[Listing, ...] = (
    Listing(
        slug="listing-a",
        title="Maple Court 302",
        neighborhood="Riverside",
        price_usd=412_000,
        area_m2=68,
        bedrooms=2,
        suites=1,
        bathrooms=2,
        parking_spots=1,
        floor=3,
        condo_fee_usd=520,
        property_tax_usd=4_100,
        description=(
            "A quiet two-bedroom home a short walk from the river park. The master bedroom has "
            "its own bathroom, and the open living and dining area gets morning sun."
        ),
        rooms=(
            Room("LIV / DIN", "living", 0, 0, 5.5, 4.2),
            Room("KIT", "kitchen", 0, 4.2, 3.2, 2.8),
            Room("WC", "bath", 3.2, 4.2, 2.3, 2.8),
            Room("BR 2", "bedroom", 5.5, 0, 4.5, 3.2, ("bed",)),
            Room("MBR", "bedroom", 5.5, 3.2, 3.0, 3.8, ("bed",)),
            Room("WC", "bath", 8.5, 3.2, 1.5, 3.8),
        ),
        brochure_amenities=frozenset({"pool", "elevator"}),
        caption_amenities=frozenset({"gym"}),  # trap: gym only in the photo caption
        photo_caption="Front of the building. Residents' gym on the ground floor.",
        seed=11,
    ),
    Listing(
        slug="listing-b",
        title="Harbor View 1104",
        neighborhood="Old Port",
        price_usd=538_000,
        area_m2=84,
        bedrooms=2,
        suites=1,
        bathrooms=2,
        parking_spots=2,
        floor=11,
        condo_fee_usd=690,
        property_tax_usd=5_300,
        description=(
            "Bright corner unit on the 11th floor with open views over the old harbor. "
            "Two bedrooms, a flexible extra room and two parking spots."
        ),
        rooms=(
            Room("GOURMET BALC.", "balcony", 0, 0, 5.5, 1.6, ("bbq",)),
            Room("LIV / DIN", "living", 0, 1.6, 5.5, 3.4),
            Room("KIT", "kitchen", 0, 5.0, 3.0, 2.0),
            Room("WC", "bath", 3.0, 5.0, 2.5, 2.0),
            Room("OFFICE", "office", 5.5, 0, 2.6, 2.8, ("desk",)),
            Room("BR 2", "bedroom", 8.1, 0, 3.9, 2.8, ("bed",)),
            Room("MBR", "bedroom", 5.5, 2.8, 4.5, 4.2, ("bed",)),
            Room("WC", "bath", 10.0, 2.8, 2.0, 4.2),
        ),
        brochure_amenities=frozenset({"elevator", "pet_friendly"}),
        # trap: balcony + BBQ grill only appear on the floor plan
        floorplan_amenities=frozenset({"gourmet_balcony", "bbq_grill"}),
        photo_caption="View from the living room over the old harbor.",
        price_trend=((2021, 5_400), (2022, 5_750), (2023, 6_050), (2024, 6_300), (2025, 6_550)),
        expected_conflicts=(
            {
                "field": "bedrooms",
                "values": [2, 3],
                "why": "Brochure advertises 2 bedrooms; floor plan shows 2 bedrooms plus a room "
                "labeled OFFICE that could be used as a third.",
            },
        ),
        seed=22,
    ),
    Listing(
        slug="listing-c",
        title="Linden Park 7",
        neighborhood="Green Hills",
        price_usd=720_000,
        area_m2=112,
        bedrooms=3,
        suites=2,
        bathrooms=3,
        parking_spots=2,
        floor=7,
        condo_fee_usd=980,
        property_tax_usd=6_840,
        description=(
            "Spacious three-bedroom family apartment facing Linden Park, with two en-suite "
            "bedrooms, a full-service building and room for a home office."
        ),
        rooms=(
            Room("LIV / DIN", "living", 0, 0, 6.0, 5.0),
            Room("KIT", "kitchen", 0, 5.0, 3.5, 3.0),
            Room("WC", "bath", 3.5, 5.0, 2.5, 3.0),
            Room("BR 3", "bedroom", 6.0, 0, 3.5, 3.5, ("bed",)),
            Room("MBR", "bedroom", 9.5, 0, 3.0, 3.5, ("bed",)),
            Room("WC", "bath", 12.5, 0, 1.5, 3.5),
            Room("BR 2 (EN-SUITE)", "bedroom", 6.0, 3.5, 3.5, 4.5, ("bed",)),
            Room("WC", "bath", 9.5, 3.5, 1.5, 4.5),
            Room("LDY / STOR.", "laundry", 11.0, 3.5, 3.0, 4.5),
        ),
        brochure_amenities=frozenset({"pool", "doorman", "elevator", "gym"}),
        photo_caption="Linden Park seen from the building entrance.",
        fees_in_brochure=False,  # trap: condo fee + property tax only in the phone photo
        seed=33,
    ),
    Listing(
        slug="listing-d",
        title="Cedar Lofts 5B",
        neighborhood="Old Port",
        price_usd=298_000,
        area_m2=45,
        bedrooms=1,
        suites=0,
        bathrooms=1,
        parking_spots=0,
        floor=5,
        condo_fee_usd=410,
        property_tax_usd=2_900,
        description=(
            "Compact one-bedroom loft in a converted warehouse, steps from the Old Port "
            "restaurants. Shared rooftop terrace with a BBQ grill."
        ),
        rooms=(
            Room("LIV / KIT", "living", 0, 0, 4.5, 6.0),
            Room("BR", "bedroom", 4.5, 0, 3.0, 3.5, ("bed",)),
            Room("WC", "bath", 4.5, 3.5, 3.0, 2.5),
        ),
        brochure_amenities=frozenset({"bbq_grill", "elevator", "pet_friendly"}),
        photo_caption="Rooftop terrace at sunset.",
        stated_price_per_m2=5_900,  # trap: real value is 298,000 / 45 = 6,622
        expected_conflicts=(
            {
                "field": "price_per_m2",
                "values": [5_900, 6_622],
                "why": "Brochure states USD 5,900/m2, but price / area = 6,622.",
            },
        ),
        seed=44,
    ),
)
