"""One small interface for every model call: "give me JSON matching this schema".

Implementations:
- `OpenAICompatibleClient` — OpenRouter (any provider, one key) or OpenAI directly. Both speak the
  OpenAI Chat Completions API, so only the base URL and the model names differ.
- `FakeLLMClient` — returns canned responses from a JSON file. Used by tests and by the offline
  dev mode (`LLM_PROVIDER=fake`) so the pipeline and UI can run without API keys.
"""

import base64
import json
import mimetypes
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from openai import AsyncOpenAI
from pydantic import BaseModel, ValidationError

# USD per 1M tokens (input, output), from the OpenRouter catalog (Oct 2026). Only used when the
# provider doesn't report cost itself (OpenAI direct). OpenRouter returns exact cost per call.
PRICES: dict[str, tuple[float, float]] = {
    "anthropic/claude-haiku-5.5": (0.10, 0.50),
    "anthropic/claude-sonnet-5.5": (2.0, 10.0),
    "openai/gpt-6-luna": (0.10, 0.50),
    "openai/gpt-6.1-sol": (2.0, 10.0),
    "openai/gpt-6.1-sol-pro": (2.0, 10.0),
    "google/gemini-3.8-flash": (0.75, 3.75),
    "google/gemini-4-argon": (2.0, 10.0),
}


class LLMError(RuntimeError):
    """A model call failed or returned something we couldn't parse."""


@dataclass
class LLMResult[T: BaseModel]:
    parsed: T
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float | None
    latency_ms: int


class LLMClient(Protocol):
    provider: str

    async def complete_json[T: BaseModel](
        self,
        *,
        model: str,
        system: str,
        user_text: str,
        schema: type[T],
        images: list[Path] = (),
        call_key: str = "",
    ) -> LLMResult[T]:
        """Ask `model` for an answer matching `schema`. `call_key` names the call (logs, fakes)."""
        ...


class OpenAICompatibleClient:
    def __init__(self, provider: str, api_key: str):
        self.provider = provider
        base_url = "https://openrouter.ai/api/v1" if provider == "openrouter" else None
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url, max_retries=2, timeout=90)

    async def complete_json[T: BaseModel](
        self,
        *,
        model: str,
        system: str,
        user_text: str,
        schema: type[T],
        images: list[Path] = (),
        call_key: str = "",
    ) -> LLMResult[T]:
        content = [{"type": "text", "text": user_text}]
        content += [{"type": "image_url", "image_url": {"url": _data_url(path)}} for path in images]

        started = time.perf_counter()
        response = await self._client.chat.completions.create(
            model=self._model_name(model),
            messages=[{"role": "system", "content": system}, {"role": "user", "content": content}],
            response_format={
                "type": "json_schema",
                "json_schema": {"name": schema.__name__, "schema": schema.model_json_schema()},
            },
            temperature=0,
            # OpenRouter adds the exact cost of the call to `usage` when asked.
            extra_body={"usage": {"include": True}} if self.provider == "openrouter" else None,
        )
        latency_ms = int((time.perf_counter() - started) * 1000)

        text = response.choices[0].message.content or ""
        usage = response.usage
        input_tokens = usage.prompt_tokens if usage else 0
        output_tokens = usage.completion_tokens if usage else 0
        return LLMResult(
            parsed=parse_json_output(text, schema, call_key),
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=_reported_cost(usage) or estimate_cost(model, input_tokens, output_tokens),
            latency_ms=latency_ms,
        )

    def _model_name(self, model: str) -> str:
        """Routing uses OpenRouter ids ('openai/gpt-6-luna'); OpenAI direct wants 'gpt-6-luna'."""
        if self.provider == "openrouter":
            return model
        if not model.startswith("openai/"):
            raise LLMError(f"{model} needs OPENROUTER_API_KEY (only openai/* models work with OpenAI direct)")
        return model.removeprefix("openai/")


class FakeLLMClient:
    """Answers from a dict {call_key: response}. A response may hold per-model overrides:
    {"default": {...}, "by_model": {"openai/gpt-6.1-sol": {...}}} — used to test escalation."""

    provider = "fake"

    def __init__(self, responses: dict[str, dict]):
        self.responses = responses
        self.calls: list[tuple[str, str]] = []  # (call_key, model), for assertions in tests

    @classmethod
    def from_file(cls, path: Path) -> "FakeLLMClient":
        return cls(json.loads(path.read_text(encoding="utf-8")))

    async def complete_json[T: BaseModel](
        self,
        *,
        model: str,
        system: str,
        user_text: str,
        schema: type[T],
        images: list[Path] = (),
        call_key: str = "",
    ) -> LLMResult[T]:
        self.calls.append((call_key, model))
        if call_key not in self.responses:
            raise LLMError(f"FakeLLMClient has no response for {call_key!r}")
        entry = self.responses[call_key]
        answer = entry.get("by_model", {}).get(model, entry.get("default", entry))
        return LLMResult(
            parsed=parse_json_output(json.dumps(answer), schema, call_key),
            model=model,
            input_tokens=0,
            output_tokens=0,
            cost_usd=0.0,
            latency_ms=0,
        )


def parse_json_output[T: BaseModel](text: str, schema: type[T], call_key: str) -> T:
    """Validate the model's JSON. Tolerates a ```json fence or prose around the object."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise LLMError(f"{call_key}: no JSON object in model output")
    try:
        return schema.model_validate_json(match.group(0))
    except ValidationError as error:
        raise LLMError(f"{call_key}: output doesn't match {schema.__name__}: {error}") from error


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float | None:
    if model not in PRICES:
        return None
    price_in, price_out = PRICES[model]
    return (input_tokens * price_in + output_tokens * price_out) / 1_000_000


def _reported_cost(usage) -> float | None:
    cost = getattr(usage, "cost", None) if usage else None
    if cost is None and usage is not None:
        cost = (getattr(usage, "model_extra", None) or {}).get("cost")
    return float(cost) if cost is not None else None


def _data_url(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"
