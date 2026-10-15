"""Checks on a single model reading. A reading with problems gets ONE retry on the escalation model.

These checks never use the ground truth: they only test whether a reading is complete and
internally plausible — the same thing we could check in production.
"""

from app.ingestion.schemas import ChartReading, FloorPlanReading, TextExtraction

PLAUSIBLE_PRICE_PER_M2 = (500, 50_000)


def check_text(reading: TextExtraction) -> list[str]:
    problems = []
    if not reading.title.value:
        problems.append("no listing title found")
    if not reading.price_usd.value:
        problems.append("no price found")
    return problems


def check_document_photo(reading: TextExtraction) -> list[str]:
    problems = []
    if not reading.title.value:
        problems.append("no listing title found")
    numbers = [reading.price_usd, reading.condo_fee_usd, reading.property_tax_usd, reading.area_m2]
    if not any(fact.value for fact in numbers):
        problems.append("no prices or fees could be read")
    return problems


def check_floor_plan(reading: FloorPlanReading) -> list[str]:
    problems = []
    if not reading.title:
        problems.append("no unit title on the plan")
    if not reading.rooms:
        return problems + ["no rooms found"]

    room_area = sum((r.width_m or 0) * (r.length_m or 0) for r in reading.rooms)
    if reading.total_area_m2 and room_area and abs(room_area - reading.total_area_m2) / reading.total_area_m2 > 0.2:
        problems.append(
            f"room sizes add up to {room_area:.0f} m² but the plan says {reading.total_area_m2:.0f} m²"
        )
    return problems


def check_chart(reading: ChartReading) -> list[str]:
    problems = []
    years = [point.year for point in reading.points]
    if len(years) < 3:
        problems.append(f"only {len(years)} data points read")
    if len(set(years)) != len(years):
        problems.append("duplicate years")
    low, high = PLAUSIBLE_PRICE_PER_M2
    if any(not low <= point.value <= high for point in reading.points):
        problems.append("values outside a plausible price-per-m² range")
    return problems
