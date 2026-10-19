"""Text chat: a classic tool-calling loop over the conversation tools.

The model may call tools several times (filter, then show evidence, ...) before answering. Each
tool call is returned as a step so the UI can render it — and react to `show_evidence`.

Two transports for the same loop:
- OpenAI → Responses API (gpt-6 models only accept function tools there; it's also the format the
  voice session's delegation uses, so text and voice share tool definitions).
- OpenRouter → Chat Completions (the API every provider behind it supports).
"""

import json
from dataclasses import dataclass, field

from openai import AsyncOpenAI

from app.assistant.instructions import ASSISTANT_INSTRUCTIONS
from app.assistant.offline import offline_reply
from app.assistant.tools import chat_completions_definitions, responses_api_definitions, run_tool
from app.config import Settings

MAX_TOOL_ROUNDS = 5
# Cheap, fast models: the chat only picks tools and phrases short answers. Measured with OpenAI:
# gpt-6-luna answers the demo conversation correctly in 4–6 s vs 8–15 s for gpt-6.1-sol.
CHAT_MODELS = {"openrouter": "anthropic/claude-haiku-5.5", "openai": "gpt-6-luna"}
GAVE_UP = "Sorry, I couldn't finish looking that up. Could you rephrase?"


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

    model = settings.chat_model or CHAT_MODELS[provider]
    if provider == "openai":
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        return await _responses_loop(client, model, messages)
    client = AsyncOpenAI(api_key=settings.openrouter_api_key, base_url="https://openrouter.ai/api/v1")
    return await _chat_completions_loop(client, model, messages)


def _run(name: str, raw_arguments: str | None, steps: list[dict]) -> str:
    """Execute one tool call, record it as a step, return the result as JSON for the model."""
    arguments = json.loads(raw_arguments or "{}")
    result = run_tool(name, arguments)
    steps.append({"tool": name, "arguments": arguments, "result": result})
    return json.dumps(result)


async def _responses_loop(client: AsyncOpenAI, model: str, messages: list[dict]) -> ChatTurn:
    inputs: list = list(messages)
    steps: list[dict] = []
    for _ in range(MAX_TOOL_ROUNDS):
        response = await client.responses.create(
            model=model, instructions=ASSISTANT_INSTRUCTIONS, input=inputs, tools=responses_api_definitions(),
        )
        calls = [item for item in response.output if item.type == "function_call"]
        if not calls:
            return ChatTurn(response.output_text, steps)

        inputs += response.output  # the model's own items (reasoning, calls) go back as context
        for call in calls:
            output = _run(call.name, call.arguments, steps)
            inputs.append({"type": "function_call_output", "call_id": call.call_id, "output": output})
    return ChatTurn(GAVE_UP, steps)


async def _chat_completions_loop(client: AsyncOpenAI, model: str, messages: list[dict]) -> ChatTurn:
    history: list[dict] = [{"role": "system", "content": ASSISTANT_INSTRUCTIONS}, *messages]
    steps: list[dict] = []
    for _ in range(MAX_TOOL_ROUNDS):
        response = await client.chat.completions.create(model=model, messages=history, tools=chat_completions_definitions())
        message = response.choices[0].message
        if not message.tool_calls:
            return ChatTurn(message.content or "", steps)

        history.append(message.model_dump(exclude_none=True))
        for call in message.tool_calls:
            output = _run(call.function.name, call.function.arguments, steps)
            history.append({"role": "tool", "tool_call_id": call.id, "content": output})
    return ChatTurn(GAVE_UP, steps)
