from app.ingestion import verify
from app.ingestion.schemas import ChartPoint, ChartReading, FloorPlanReading, FloorPlanRoom, IntFact, TextExtraction, TextFact


def test_chart_with_too_few_points_needs_a_retry() -> None:
    reading = ChartReading(points=[ChartPoint(year=2021, value=5400), ChartPoint(year=2022, value=5750)])
    assert verify.check_chart(reading) == ["only 2 data points read"]


def test_chart_with_implausible_values() -> None:
    points = [ChartPoint(year=y, value=v) for y, v in [(2021, 5.4), (2022, 5.7), (2023, 6.0)]]  # read as thousands
    assert "values outside a plausible price-per-m² range" in verify.check_chart(ChartReading(points=points))


def test_floor_plan_whose_rooms_dont_add_up() -> None:
    reading = FloorPlanReading(
        title="X", total_area_m2=84, rooms=[FloorPlanRoom(label="BR", kind="bedroom", width_m=3, length_m=3)],
    )
    assert "room sizes add up to 9 m² but the plan says 84 m²" in verify.check_floor_plan(reading)


def test_good_floor_plan_has_no_problems() -> None:
    rooms = [FloorPlanRoom(label="LIV", kind="living", width_m=7, length_m=6)]
    assert verify.check_floor_plan(FloorPlanReading(title="X", total_area_m2=45, rooms=rooms)) == []


def test_text_without_title_or_price() -> None:
    assert verify.check_text(TextExtraction()) == ["no listing title found", "no price found"]
    ok = TextExtraction(title=TextFact(value="X"), price_usd=IntFact(value=1))
    assert verify.check_text(ok) == []
