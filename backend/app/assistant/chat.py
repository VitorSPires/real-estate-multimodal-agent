"""Text chat: a classic tool-calling loop over the conversation tools.

The model may call tools several times (filter, then show evidence, ...) before answering. Each
tool call is returned as a step so the UI can render it — and react to `show_evidence`.
"""

import json
from dataclasses import dataclass, field

from openai import AsyncOpenAI

from app.assistant.instructions import ASSISTANT_INSTRUCTIONS
from app.assistant.offline import offline_reply
from app.assistant.tools import chat_completions_definitions, run_tool
from app.config import Settings

MAX_TOOL_ROUNDS = 5
CHAT_MODELS = {"openrouter": "anthropic/claude-sonnet-5.5", "openai": "gpt-6.1-sol"}


@dataclass
class ChatTurn:
    reply: str
    steps: list[dict] = field(default_factory=list)  # [{"tool", "arguments", "result"}]
    offline: bool = False


async def chat(messages: list[dict], settings: Settings) -> ChatTurn:
    """`messages`: the conversation so far, [{"role": "user" | "assistant", "content": str}]."""
    provider = settings.resolved_llm_provider
    if provider == "fake":
        reply, steps = offline_reply(messages)
        return ChatTurn(reply, steps, offline=True)

    key = settings.openrouter_api_key if provider == "openrouter" else settings.openai_api_key
    client = AsyncOpenAI(api_key=key, base_url="https://openrouter.ai/api/v1" if provider == "openrouter" else None)
    model = settings.chat_model or CHAT_MODELS[provider]

    history: list[dict] = [{"role": "system", "content": ASSISTANT_INSTRUCTIONS}, *messages]
    steps: list[dict] = []
    for _ in range(MAX_TOOL_ROUNDS):
        response = await client.chat.completions.create(
            model=model, messages=history, tools=chat_completions_definitions(),
        )
        message = response.choices[0].message
        if not message.tool_calls:
            return ChatTurn(message.content or "", steps)

        history.append(message.model_dump(exclude_none=True))
        for call in message.tool_calls:
            arguments = json.loads(call.function.arguments or "{}")
            result = run_tool(call.function.name, arguments)
            steps.append({"tool": call.function.name, "arguments": arguments, "result": result})
            history.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(result)})

    return ChatTurn("Sorry, I couldn't finish looking that up. Could you rephrase?", steps)
