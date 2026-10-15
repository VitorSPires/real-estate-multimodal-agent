"""GPT-Live-1 voice sessions.

The browser never talks to OpenAI with a key. It sends its WebRTC offer (SDP) here; we create the
Live session server-side and return OpenAI's answer. From then on audio flows browser ↔ OpenAI
directly, and events (transcripts, tool calls) travel over the WebRTC data channel.

Who does what:
- gpt-live-1 listens, speaks and handles interruptions (`VOICE_INSTRUCTIONS`).
- A Responses model (delegation) decides which tool to call (`ASSISTANT_INSTRUCTIONS` + tools).
- Our tools run in this backend; the browser relays each call to `POST /api/live/tools`.
"""

from openai import AsyncOpenAI

from app.assistant.instructions import ASSISTANT_INSTRUCTIONS
from app.assistant.tools import responses_api_definitions
from app.config import Settings

VOICE_INSTRUCTIONS = """\
You are ListingLens, a friendly voice assistant helping someone choose an apartment from the
documents their broker sent. Speak English, naturally and briefly — one or two sentences per turn.
Delegate every question about the apartments, the documents or prices to the backend; never state
a fact about a listing yourself. While the backend works, a short filler is fine ("Let me check.").
If the user interrupts, stop and listen.
"""


class VoiceUnavailable(RuntimeError):
    """Voice needs an OpenAI key: GPT-Live is only on OpenAI's API (not on OpenRouter)."""


def session_config(settings: Settings) -> dict:
    return {
        "model": "gpt-live-1",
        "instructions": VOICE_INSTRUCTIONS,
        "audio": {"output": {"voice": settings.voice_name}},
        "delegation": {
            "type": "responses",
            "responses": {
                "model": settings.voice_backend_model,
                "instructions": ASSISTANT_INSTRUCTIONS,
                "tools": responses_api_definitions(),
                "tool_choice": "auto",
                "parallel_tool_calls": False,
                "max_output_tokens": 800,
            },
        },
    }


async def create_session(sdp_offer: str, settings: Settings) -> str:
    """Create a Live session for the browser's SDP offer; returns OpenAI's SDP answer."""
    if not settings.openai_api_key:
        raise VoiceUnavailable("Voice needs a valid OPENAI_API_KEY in backend/.env (GPT-Live is OpenAI-only).")
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    response = await client.live.create(
        session=session_config(settings), transport={"type": "webrtc", "sdp": sdp_offer},
    )
    return response.transport.sdp
