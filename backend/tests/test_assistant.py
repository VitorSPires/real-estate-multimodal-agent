"""Conversation tools and the offline chat agent, over listings ingested from the dataset."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.assistant.offline import offline_reply
from app.assistant.tools import TOOLS, chat_completions_definitions, responses_api_definitions, run_tool
from app.config import settings
from app.db import SessionLocal, init_db
from app.ingestion.llm import FakeLLMClient
from app.ingestion.runner import run_ingestion
from app.main import app
from app.models import IngestionRun
from app.store import SqlListingStore, reset

DATASET = Path(__file__).resolve().parents[2] / "dataset" / "listings"


@pytest.fixture(scope="module", autouse=True)
async def listings(tmp_path_factory):
    init_db()
    with SessionLocal.begin() as session:
        reset(session)
        session.add(IngestionRun(id="assistant-run"))
    work = tmp_path_factory.mktemp("assistant")
    paths = sorted(p for p in DATASET.rglob("*") if p.suffix in {".pdf", ".png", ".jpg"})
    await run_ingestion(paths, llm=FakeLLMClient.from_file(settings.fake_responses), work_dir=work, data_dir=work,
                        store=SqlListingStore(SessionLocal, "assistant-run"))


def test_filter_combines_requirements() -> None:
    result = run_tool("filter_listings", {"min_bedrooms": 2, "required_amenities": ["bbq_grill"]})
    assert [m["id"] for m in result["matches"]] == ["harbor-view-1104"]
    why = {e["id"]: e["why_not"] for e in result["excluded"]}
    assert why["cedar-lofts-5b"] == ["1 bedroom(s)"]
    assert why["linden-park-7"] == ["no bbq grill mentioned"]


def test_listing_can_be_named_loosely() -> None:
    assert run_tool("get_listing", {"listing": "Harbor View"})["id"] == "harbor-view-1104"
    assert "error" in run_tool("get_listing", {"listing": "nowhere"})


def test_show_evidence_points_to_the_floor_plan_for_the_grill() -> None:
    result = run_tool("show_evidence", {"listing": "harbor-view-1104", "field": "bbq_grill"})
    assert result["found"] and result["evidence"][0]["document"] == "harbor-view-1104-floorplan.png"


def test_neighborhood_check_uses_another_listings_chart() -> None:
    result = run_tool("neighborhood_price_check", {"listing": "cedar-lofts-5b"})  # Old Port, chart is in Harbor View
    assert result["available"] and result["neighborhood"] == "Old Port"
    assert result["difference_pct"] > 0  # 6,622/m² vs ~6,511 average


def test_bad_arguments_become_an_error_result() -> None:
    assert "error" in run_tool("get_listing", {"wrong": 1})
    assert "error" in run_tool("no_such_tool", {})


def test_tool_definitions_in_both_formats() -> None:
    assert [d["name"] for d in responses_api_definitions()] == [t.name for t in TOOLS]
    assert [d["function"]["name"] for d in chat_completions_definitions()] == [t.name for t in TOOLS]


def test_offline_agent_handles_the_demo_conversation() -> None:
    history: list[dict] = []
    tools_per_turn = []
    for text in ["Hi! Can you help me pick one?", "I need at least two bedrooms.",
                 "And I really want a barbecue grill.", "Is it a good price for the area?"]:
        history.append({"role": "user", "content": text})
        reply, steps = offline_reply(history)
        history.append({"role": "assistant", "content": reply})
        tools_per_turn.append([s["tool"] for s in steps])

    assert tools_per_turn == [["list_listings"], ["filter_listings"], ["filter_listings", "show_evidence"],
                              ["neighborhood_price_check"]]
    assert "Harbor View 1104" in history[5]["content"] and "office" in history[5]["content"]
    assert "below the Old Port average" in history[7]["content"]


def test_chat_endpoint() -> None:
    with TestClient(app) as client:
        response = client.post("/api/chat", json={"messages": [{"role": "user", "content": "compare them"}]})
    body = response.json()
    assert response.status_code == 200 and body["offline"] is True
    assert [s["tool"] for s in body["steps"]] == ["list_listings", "compare_listings"]
