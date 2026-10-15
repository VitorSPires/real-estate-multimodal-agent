"""The whole graph over the committed dataset, with canned model answers (FakeLLMClient).

This checks the pipeline's logic — routing, escalation, evidence, merging, conflicts — not model
quality. Model quality is what evals/ measures with real models.
"""

from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.db import Base
from app.ingestion.llm import FakeLLMClient
from app.ingestion.routing import Routing
from app.ingestion.runner import run_ingestion
from app.models import IngestionRun, ModelCall
from app.store import SqlListingStore, list_listings

DATASET = Path(__file__).resolve().parents[2] / "dataset" / "listings"


@pytest.fixture(scope="module")
async def run(tmp_path_factory):
    fake = FakeLLMClient.from_file(settings.fake_responses)
    work = tmp_path_factory.mktemp("run")
    engine = create_engine(f"sqlite:///{work / 'test.db'}")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    with session_factory.begin() as session:
        session.add(IngestionRun(id="run-1"))

    events: list[dict] = []
    paths = sorted(p for p in DATASET.rglob("*") if p.suffix in {".pdf", ".png", ".jpg"})
    state = await run_ingestion(
        paths, llm=fake, routing=Routing(), work_dir=work, data_dir=work,
        store=SqlListingStore(session_factory, "run-1"), on_event=events.append,
    )
    return {"state": state, "fake": fake, "events": events, "session_factory": session_factory}


def listing(run, listing_id):
    return next(item for item in run["state"]["listings"] if item.id == listing_id)


async def test_all_documents_end_up_in_four_listings(run) -> None:
    listings = run["state"]["listings"]
    assert [item.id for item in listings] == ["cedar-lofts-5b", "harbor-view-1104", "linden-park-7", "maple-court-302"]
    assert run["state"]["unassigned"] == []
    assert len(listing(run, "linden-park-7").documents) == 3  # brochure + plan + photo


async def test_property_photos_never_reach_an_extraction_model(run) -> None:
    keys = [key for key, _ in run["fake"].calls]
    assert "triage:maple-court-302-brochure.pdf#p1-img1" in keys
    assert not any(key.startswith(("floor_plan:", "chart:")) and "#p1-img1" in key for key in keys)


async def test_flawed_chart_reading_is_escalated_once(run) -> None:
    chart_calls = [model for key, model in run["fake"].calls if key.startswith("chart:")]
    assert chart_calls == [Routing().chart, Routing().escalation]
    trend = listing(run, "harbor-view-1104").price_trend
    assert len(trend.value) == 5


async def test_designed_conflicts_are_recorded(run) -> None:
    bedrooms = listing(run, "harbor-view-1104").fields["bedrooms"]
    assert bedrooms.value == 2 and [alt.value for alt in bedrooms.conflict] == [3]
    price_per_m2 = listing(run, "cedar-lofts-5b").fields["price_per_m2"]
    assert price_per_m2.value == 6_622 and [alt.value for alt in price_per_m2.conflict] == [5_900]


async def test_facts_hidden_in_images_are_found(run) -> None:
    harbor = listing(run, "harbor-view-1104")
    assert harbor.amenities["bbq_grill"].value is True
    assert harbor.amenities["bbq_grill"].evidence[0].document == "harbor-view-1104-floorplan.png"
    fee = listing(run, "linden-park-7").fields["condo_fee_usd"]
    assert fee.value == 980 and fee.evidence[0].method == "vision"


async def test_native_text_evidence_points_at_the_page(run) -> None:
    price = listing(run, "harbor-view-1104").fields["price_usd"]
    evidence = price.evidence[0]
    assert evidence.page == 1 and evidence.bbox is not None
    assert evidence.image_path == "pages/harbor-view-1104-brochure.pdf-p1.png"


async def test_narration_and_live_listing_events_are_streamed(run) -> None:
    types = {event["type"] for event in run["events"]}
    assert {"narration", "facts", "listing"} <= types
    assert run["events"][-1]["level"] == "success"


async def test_results_are_persisted(run) -> None:
    with run["session_factory"]() as session:
        assert len(list_listings(session)) == 4
        assert len(session.scalars(select(ModelCall)).all()) == len(run["state"]["model_calls"])
