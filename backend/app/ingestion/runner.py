"""One entry point to run the ingestion graph, shared by the CLI, the API and the evals."""

from collections.abc import Callable
from pathlib import Path

from app.config import Settings
from app.ingestion.graph import ingestion_graph
from app.ingestion.llm import FakeLLMClient, LLMClient, OpenAICompatibleClient
from app.ingestion.nodes import IngestionContext, IngestionState, ListingStore
from app.ingestion.routing import Routing, default_routing


def build_llm(settings: Settings, provider: str | None = None) -> LLMClient:
    provider = provider or settings.resolved_llm_provider
    if provider == "fake":
        return FakeLLMClient.from_file(settings.fake_responses)
    key = settings.openrouter_api_key if provider == "openrouter" else settings.openai_api_key
    if not key:
        raise RuntimeError(f"LLM provider '{provider}' needs its API key in backend/.env")
    return OpenAICompatibleClient(provider, key)


async def run_ingestion(
    paths: list[Path],
    *,
    llm: LLMClient,
    work_dir: Path,
    data_dir: Path,
    routing: Routing | None = None,
    store: ListingStore | None = None,
    on_event: Callable[[dict], None] | None = None,
) -> IngestionState:
    """Run the graph to completion, forwarding every streamed event to `on_event`."""
    context = IngestionContext(
        llm=llm, routing=routing or default_routing(llm.provider), work_dir=work_dir, data_dir=data_dir, store=store,
    )
    if llm.provider == "fake" and on_event:
        on_event({"type": "narration", "level": "warn",
                  "text": "Offline mode: model answers are canned test fixtures, not real model calls."})

    final: IngestionState = {}
    async for mode, chunk in ingestion_graph.astream(
        {"paths": paths}, context=context, stream_mode=["custom", "values"]
    ):
        if mode == "custom" and on_event:
            on_event(chunk)
        elif mode == "values":
            final = chunk
    return final
