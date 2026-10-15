"""Checks that the spec is internally consistent and the rendered documents have the traps we
designed. Run from the repo root:  backend/.venv/Scripts/python -m pytest dataset
"""

from pathlib import Path

import pymupdf
import pytest

from dataset.generate import generate, ground_truth
from dataset.spec import LISTINGS, Listing

BY_SLUG = {listing.slug: listing for listing in LISTINGS}


@pytest.mark.parametrize("listing", LISTINGS, ids=lambda listing: listing.slug)
def test_floor_plan_matches_the_facts(listing: Listing) -> None:
    kinds = [room.kind for room in listing.rooms]
    assert kinds.count("bedroom") == listing.bedrooms
    assert kinds.count("bath") == listing.bathrooms
    plan_area = sum(room.area for room in listing.rooms)
    assert abs(plan_area - listing.area_m2) / listing.area_m2 < 0.05


def test_demo_query_has_exactly_one_answer() -> None:
    """'At least two bedrooms' + 'BBQ grill' must narrow down to a single listing."""
    matches = [
        listing.slug for listing in LISTINGS
        if listing.bedrooms >= 2 and "bbq_grill" in listing.amenities
    ]
    assert matches == ["listing-b"]


@pytest.fixture(scope="module")
def dataset_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("listings")
    generate(out)
    return out


def test_brochures_have_a_native_text_layer(dataset_dir: Path) -> None:
    for listing in LISTINGS:
        with pymupdf.open(dataset_dir / listing.slug / listing.document_names["brochure"]) as pdf:
            text = "".join(page.get_text() for page in pdf)
        assert listing.title in text
        assert f"USD {listing.price_usd:,}" in text


def test_traps_are_where_we_put_them(dataset_dir: Path) -> None:
    def brochure_text(slug: str) -> str:
        brochure = BY_SLUG[slug].document_names["brochure"]
        with pymupdf.open(dataset_dir / slug / brochure) as pdf:
            return "".join(page.get_text() for page in pdf)

    # B: the BBQ grill is only on the floor plan, never in the brochure text.
    assert "BBQ" not in brochure_text("listing-b")
    # C: fees only in the phone photo.
    assert "Condo fee" not in brochure_text("listing-c")
    assert (dataset_dir / "listing-c" / "linden-park-7-price-sheet.jpg").exists()
    # D: the brochure states a price per m² that disagrees with price / area.
    assert "USD 5,900" in brochure_text("listing-d")
    assert BY_SLUG["listing-d"].price_per_m2 == 6_622


def test_ground_truth_lists_existing_documents(dataset_dir: Path) -> None:
    for listing in LISTINGS:
        files = {p.name for p in (dataset_dir / listing.slug).iterdir()} - {"ground_truth.json"}
        assert set(ground_truth(listing)["documents"]) == files


def test_generation_is_deterministic(dataset_dir: Path, tmp_path: Path) -> None:
    """Same spec -> byte-identical files, so regenerating never creates noisy git diffs."""
    generate(tmp_path)
    for first in dataset_dir.rglob("*.*"):
        second = tmp_path / first.relative_to(dataset_dir)
        assert first.read_bytes() == second.read_bytes(), first.name
