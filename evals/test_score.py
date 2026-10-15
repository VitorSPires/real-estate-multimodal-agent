"""Scorer tests. Run from the repo root:  backend/.venv/Scripts/python -m pytest evals"""

import copy
import json
from pathlib import Path

from evals.score import accuracy, score_listing

TRUTH = json.loads((Path(__file__).parent.parent / "dataset/listings/listing-b/ground_truth.json").read_text("utf-8"))


def perfect_record(truth: dict) -> dict:
    fields = {name: {"value": value, "conflict": []} for name, value in truth["fields"].items()
              if name not in ("amenities", "price_trend")}
    for conflict in truth["expected_conflicts"]:
        others = [v for v in conflict["values"] if v != fields[conflict["field"]]["value"]]
        fields[conflict["field"]]["conflict"] = [{"value": v} for v in others]
    return {
        "fields": fields,
        "amenities": {name: {"value": value} for name, value in truth["fields"]["amenities"].items()},
        "price_trend": {"value": truth["fields"]["price_trend"]},
    }


def test_perfect_record_scores_100() -> None:
    assert accuracy(score_listing(TRUTH, perfect_record(TRUTH))) == 1.0


def test_missing_listing_scores_0() -> None:
    checks = score_listing(TRUTH, None)
    assert accuracy(checks) < 0.4  # only "absent amenity == None" style checks could pass
    assert not any(c.ok for c in checks if c.category == "brochure_text")


def test_chart_within_tolerance_passes_and_outside_fails() -> None:
    record = perfect_record(TRUTH)
    record["price_trend"]["value"] = [{**p, "price_per_m2": round(p["price_per_m2"] * 1.02)} for p in TRUTH["fields"]["price_trend"]]
    assert all(c.ok for c in score_listing(TRUTH, record) if c.category == "chart")

    record["price_trend"]["value"][0]["price_per_m2"] *= 1.2
    assert not any(c.ok for c in score_listing(TRUTH, record) if c.category == "chart")


def test_missed_conflict_is_a_failure() -> None:
    record = perfect_record(TRUTH)
    record["fields"]["bedrooms"]["conflict"] = []
    [check] = [c for c in score_listing(TRUTH, record) if c.category == "conflict"]
    assert not check.ok


def test_amenity_categories_follow_the_source() -> None:
    record = copy.deepcopy(perfect_record(TRUTH))
    record["amenities"]["bbq_grill"]["value"] = False  # B's grill is only on the floor plan
    failed = [c for c in score_listing(TRUTH, record) if not c.ok]
    assert [(c.category, c.name) for c in failed] == [("amenity_from_floorplan", "amenity.bbq_grill")]
