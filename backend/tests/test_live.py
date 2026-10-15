"""Voice endpoints, without calling OpenAI: the SDK call is replaced by a stub."""

from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.config import settings
from app.live import session
from app.main import app

OFFER = "v=0\r\no=- 1 2 IN IP4 127.0.0.1\r\ns=-\r\n"


def test_session_config_delegates_to_responses_with_our_tools() -> None:
    config = session.session_config(settings)
    assert config["model"] == "gpt-live-1"
    delegation = config["delegation"]
    assert delegation["type"] == "responses"
    assert {tool["name"] for tool in delegation["responses"]["tools"]} >= {"filter_listings", "show_evidence"}
    assert all(tool["type"] == "function" for tool in delegation["responses"]["tools"])


def test_session_exchanges_sdp_server_side(monkeypatch) -> None:
    sent = {}

    class FakeLive:
        async def create(self, *, session, transport):
            sent.update(session=session, transport=transport)
            return SimpleNamespace(transport=SimpleNamespace(sdp="v=0 answer"))

    monkeypatch.setattr(settings, "openai_api_key", "sk-test")
    monkeypatch.setattr(session, "AsyncOpenAI", lambda api_key: SimpleNamespace(live=FakeLive()))
    with TestClient(app) as client:
        response = client.post("/api/live/session", json={"sdp": OFFER})

    assert response.json() == {"sdp": "v=0 answer"}
    assert sent["transport"] == {"type": "webrtc", "sdp": OFFER}


def test_session_without_key_is_a_clear_503(monkeypatch) -> None:
    monkeypatch.setattr(settings, "openai_api_key", "")
    with TestClient(app) as client:
        response = client.post("/api/live/session", json={"sdp": OFFER})
    assert response.status_code == 503 and "OPENAI_API_KEY" in response.json()["detail"]


def test_tool_relay_runs_known_tools_only() -> None:
    with TestClient(app) as client:
        assert "listings" in client.post("/api/live/tools", json={"name": "list_listings"}).json()
        assert client.post("/api/live/tools", json={"name": "rm_rf"}).status_code == 404
