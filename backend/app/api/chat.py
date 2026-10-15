from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.assistant.chat import chat
from app.config import settings

router = APIRouter(tags=["chat"])


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=50)


@router.post("/chat")
async def post_chat(request: ChatRequest) -> dict:
    """One assistant turn. Returns the reply plus every tool call made (the UI renders them)."""
    turn = await chat([m.model_dump() for m in request.messages], settings)
    return {"reply": turn.reply, "steps": turn.steps, "offline": turn.offline}
