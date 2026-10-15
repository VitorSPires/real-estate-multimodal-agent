import json

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as client:
        client.post("/api/reset")
        yield client


def read_events(client: TestClient, run_id: str, last_event_id: int = 0) -> list[dict]:
    events = []
    headers = {"Last-Event-ID": str(last_event_id)} if last_event_id else {}
    with client.stream("GET", f"/api/ingestions/{run_id}/events", headers=headers) as response:
        for line in response.iter_lines():
            if line.startswith("data:"):
                events.append(json.loads(line.removeprefix("data:")))
    return events


@pytest.fixture(scope="module")
def sample_run(client) -> tuple[str, list[dict]]:
    run_id = client.post("/api/ingestions/sample").json()["run_id"]
    return run_id, read_events(client, run_id)


def test_sample_run_streams_until_the_end(sample_run) -> None:
    _, events = sample_run
    assert events[-1]["type"] == "end"
    assert any(e["type"] == "listing" for e in events)
    assert events[-2]["level"] == "success"


def test_run_status_and_listings(client, sample_run) -> None:
    run_id, _ = sample_run
    assert client.get(f"/api/ingestions/{run_id}").json()["status"] == "done"
    listings = client.get("/api/listings").json()
    assert [listing["id"] for listing in listings] == ["cedar-lofts-5b", "harbor-view-1104", "linden-park-7", "maple-court-302"]
    assert client.get("/api/listings/harbor-view-1104").json()["amenities"]["bbq_grill"]["value"] is True


def test_reconnect_replays_only_newer_events(client, sample_run) -> None:
    run_id, events = sample_run
    with_ids = [e for e in events if "id" in e]
    replayed = read_events(client, run_id, last_event_id=with_ids[-3]["id"])
    assert [e.get("id") for e in replayed[:-1]] == [e["id"] for e in with_ids[-2:]]


def test_evidence_images_are_served(client) -> None:
    listing = client.get("/api/listings/harbor-view-1104").json()
    path = listing["fields"]["price_usd"]["evidence"][0]["image_path"]
    response = client.get(f"/api/files/{path}")
    assert response.status_code == 200 and response.headers["content-type"] == "image/png"


def test_files_outside_the_data_dir_are_refused(client) -> None:
    assert client.get("/api/files/..%2F..%2Fapp%2Fconfig.py").status_code == 404


def test_upload_runs_the_same_pipeline(client) -> None:
    from pathlib import Path

    floorplan = Path(__file__).resolve().parents[2] / "dataset/listings/listing-d/cedar-lofts-5b-floorplan.png"
    response = client.post("/api/ingestions", files=[("files", (floorplan.name, floorplan.read_bytes(), "image/png"))])
    assert response.status_code == 202
    events = read_events(client, response.json()["run_id"])
    assert any("floor plan" in e.get("text", "") for e in events)


def test_unknown_run_is_404(client) -> None:
    assert client.get("/api/ingestions/nope/events").status_code == 404
