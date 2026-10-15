from typing import Any

from fastapi import APIRouter, HTTPException
from openai import AuthenticationError, OpenAIError
from pydantic import BaseModel, Field

from app.assistant.tools import TOOLS_BY_NAME, run_tool
from app.config import settings
from app.live.session import VoiceUnavailable, create_session

router = APIRouter(prefix="/live", tags=["voice"])


class SessionRequest(BaseModel):
    sdp: str = Field(min_length=10, max_length=20_000)


class ToolCall(BaseModel):
    name: str
    arguments: dict[str, Any] = {}


@router.post("/session")
async def start_session(request: SessionRequest) -> dict:
    """Exchange the browser's WebRTC offer for GPT-Live's answer (the API key stays here)."""
    try:
        return {"sdp": await create_session(request.sdp, settings)}
    except VoiceUnavailable as error:
        raise HTTPException(503, str(error)) from error
    except AuthenticationError as error:
        raise HTTPException(502, "OpenAI rejected the API key. Check OPENAI_API_KEY in backend/.env.") from error
    except OpenAIError as error:
        raise HTTPException(502, f"Couldn't start the voice session ({type(error).__name__}).") from error


@router.post("/tools")
def call_tool(call: ToolCall) -> dict:
    """Run a tool the voice session's backend model asked for (relayed by the browser)."""
    if call.name not in TOOLS_BY_NAME:
        raise HTTPException(404, f"Unknown tool: {call.name}")
    return run_tool(call.name, call.arguments)
