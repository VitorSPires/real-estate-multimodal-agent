"""Build the synthetic dataset: documents + ground truth for every listing in spec.py.

Usage (from the repo root, with the backend venv):
    backend/.venv/Scripts/python -m dataset.generate            # Windows
    backend/.venv/bin/python -m dataset.generate                # macOS / Linux
"""

import argparse
import json
from pathlib import Path

from dataset.brochure import render_brochure
from dataset.images import render_floor_plan, render_hero_photo, render_price_chart
from dataset.phone_photo import render_price_sheet_photo
from dataset.spec import AMENITY_NAMES, LISTINGS, Listing

DEFAULT_OUT = Path(__file__).parent / "listings"


def generate(out_dir: Path = DEFAULT_OUT) -> list[Path]:
    """Render every listing into out_dir/<slug>/ and return the listing folders."""
    folders = []
    for listing in LISTINGS:
        folder = out_dir / listing.slug
        folder.mkdir(parents=True, exist_ok=True)
        _render_documents(listing, folder)
        _write_ground_truth(listing, folder)
        folders.append(folder)
    return folders


def _render_documents(listing: Listing, folder: Path) -> None:
    # Hero photo and chart stay in memory: they only exist to be embedded in the PDF.
    # (Temp files would also make the PDF non-deterministic: reportlab names embedded
    # images after their file path.)
    names = listing.document_names
    hero = render_hero_photo(listing)
    chart = render_price_chart(listing) if listing.price_trend else None
    render_brochure(listing, hero, chart, folder / names["brochure"])
    render_floor_plan(listing, folder / names["floorplan"])
    if "price_sheet" in names:
        render_price_sheet_photo(listing, folder / names["price_sheet"])


def ground_truth(listing: Listing) -> dict:
    """What a perfect extraction of this listing's documents should produce."""
    return {
        "slug": listing.slug,
        "documents": sorted(listing.document_names.values()),
        "fields": {
            "title": listing.title,
            "neighborhood": listing.neighborhood,
            "price_usd": listing.price_usd,
            "area_m2": listing.area_m2,
            "price_per_m2": listing.price_per_m2,
            "bedrooms": listing.bedrooms,
            "suites": listing.suites,
            "bathrooms": listing.bathrooms,
            "parking_spots": listing.parking_spots,
            "floor": listing.floor,
            "condo_fee_usd": listing.condo_fee_usd,
            "property_tax_usd": listing.property_tax_usd,
            "amenities": {key: key in listing.amenities for key in AMENITY_NAMES},
            "price_trend": [{"year": y, "price_per_m2": v} for y, v in listing.price_trend] or None,
        },
        # Where the harder facts live, so the eval can report accuracy per source type.
        "sources": {
            "fees": listing.document_names["price_sheet" if "price_sheet" in listing.document_names else "brochure"],
            "amenities": {
                **{a: "brochure_text" for a in sorted(listing.brochure_amenities)},
                **{a: "photo_caption" for a in sorted(listing.caption_amenities)},
                **{a: "floorplan" for a in sorted(listing.floorplan_amenities)},
            },
        },
        "expected_conflicts": list(listing.expected_conflicts),
        # Chart values are read off a plot, so exact matches aren't expected.
        "tolerances": {"price_trend": 0.03},
    }


def _write_ground_truth(listing: Listing, folder: Path) -> None:
    text = json.dumps(ground_truth(listing), indent=2, sort_keys=False)
    (folder / "ground_truth.json").write_text(text + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="output folder")
    args = parser.parse_args()

    for folder in generate(args.out):
        files = ", ".join(sorted(p.name for p in folder.iterdir()))
        print(f"{folder.name}: {files}")


if __name__ == "__main__":
    main()
