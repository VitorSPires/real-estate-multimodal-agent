from app.ingestion.merge import DocumentObservations, listing_key, merge
from app.ingestion.schemas import Evidence, Observation


def obs(field, value, method="native_text", document="brochure.pdf"):
    return Observation(field=field, value=value, evidence=Evidence(document=document, method=method))


def doc(name, *observations, problems=()):
    return DocumentObservations(name, list(observations), list(problems))


def test_documents_are_grouped_by_title_ignoring_case() -> None:
    listings, unassigned = merge([
        doc("b.pdf", obs("title", "Harbor View 1104"), obs("price_usd", 538_000)),
        doc("plan.png", obs("title", "HARBOR VIEW 1104", "vision", "plan.png"), obs("floorplan.bedrooms", 2, "vision")),
    ])
    assert [listing.id for listing in listings] == ["harbor-view-1104"]
    assert listings[0].title == "Harbor View 1104"  # brochure casing wins over the plan's
    assert listings[0].documents == ["b.pdf", "plan.png"]
    assert unassigned == []


def test_document_without_title_is_unassigned() -> None:
    _, unassigned = merge([doc("mystery.png", obs("price_usd", 1, "vision"))])
    assert unassigned == ["mystery.png"]


def test_native_text_beats_vision_and_the_loser_becomes_a_conflict() -> None:
    [listing], _ = merge([doc(
        "b.pdf", obs("title", "X"), obs("condo_fee_usd", 690), obs("condo_fee_usd", 960, "vision"),
    )])
    fee = listing.fields["condo_fee_usd"]
    assert fee.value == 690
    assert [alt.value for alt in fee.conflict] == [960]
    assert fee.confidence < 0.95


def test_office_on_the_plan_is_a_bedroom_conflict() -> None:
    [listing], _ = merge([doc(
        "b.pdf", obs("title", "X"), obs("bedrooms", 2),
        obs("floorplan.bedrooms", 2, "vision"), obs("floorplan.offices", 1, "vision"),
    )])
    bedrooms = listing.fields["bedrooms"]
    assert bedrooms.value == 2
    assert [alt.value for alt in bedrooms.conflict] == [3]
    assert "office" in bedrooms.conflict[0].note


def test_price_per_m2_is_computed_and_a_wrong_stated_value_is_flagged() -> None:
    [listing], _ = merge([doc(
        "b.pdf", obs("title", "X"), obs("price_usd", 298_000), obs("area_m2", 45), obs("stated_price_per_m2", 5_900),
    )])
    price_per_m2 = listing.fields["price_per_m2"]
    assert price_per_m2.value == 6_622
    assert price_per_m2.evidence[0].method == "computed"
    assert [alt.value for alt in price_per_m2.conflict] == [5_900]


def test_floor_plan_fills_missing_counts() -> None:
    [listing], _ = merge([doc("p.png", obs("title", "X", "vision"), obs("floorplan.bedrooms", 3, "vision"))])
    assert listing.fields["bedrooms"].value == 3


def test_amenities_are_true_if_any_source_mentions_them() -> None:
    [listing], _ = merge([
        doc("b.pdf", obs("title", "X"), obs("amenity.elevator", True)),
        doc("p.png", obs("title", "X", "vision", "p.png"), obs("amenity.bbq_grill", True, "vision", "p.png")),
    ])
    assert listing.amenities["bbq_grill"].value is True
    assert listing.amenities["bbq_grill"].evidence[0].document == "p.png"
    assert listing.amenities["pool"].value is False


def test_unresolved_problems_become_warnings() -> None:
    [listing], _ = merge([doc("b.pdf", obs("title", "X"), problems=["no price found"])])
    assert listing.warnings == ["b.pdf: no price found"]


def test_listing_key() -> None:
    assert listing_key("Cedar Lofts 5B") == listing_key("CEDAR LOFTS 5B") == "cedar-lofts-5b"
