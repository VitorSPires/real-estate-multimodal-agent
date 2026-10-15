"""The nodes of the ingestion graph. Each node reads the state, does one job, narrates it, and
returns only the keys it changed. The heavy lifting lives in documents / observations / verify /
merge; nodes are the glue.
"""

import asyncio
import operator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Any, Protocol, TypedDict

from langgraph.config import get_stream_writer
from langgraph.runtime import Runtime
from openai import AuthenticationError, OpenAIError
from pydantic import BaseModel

from app.ingestion import documents as docs
from app.ingestion import observations as obs
from app.ingestion import verify
from app.ingestion.documents import Region, SourceDocument
from app.ingestion.llm import LLMClient, LLMError
from app.ingestion.merge import DocumentObservations, merge
from app.ingestion.routing import Routing
from app.ingestion.schemas import (
    ChartReading, FloorPlanReading, ListingRecord, Observation, RegionTriage, TextExtraction,
)

PROMPTS = Path(__file__).parent / "prompts"
VISUAL_TASKS = ("floor_plan", "chart", "document_photo")


# --- State and context ---------------------------------------------------------------------------


@dataclass
class Extraction:
    """One model reading of one region (the latest attempt)."""

    region_key: str
    document: str
    task: str
    model: str
    observations: list[Observation] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    escalated: bool = False


class ListingStore(Protocol):
    def save(self, listings: list[ListingRecord], state: "IngestionState") -> None: ...


@dataclass
class IngestionContext:
    """Dependencies, injected at run time (not part of the state)."""

    llm: LLMClient
    routing: Routing
    work_dir: Path  # where page renders and crops of this run go
    data_dir: Path  # evidence paths are stored relative to this
    store: ListingStore | None = None
    max_concurrency: int = 6


def _merge_dicts(left: dict, right: dict) -> dict:
    return {**left, **right}


class IngestionState(TypedDict, total=False):
    paths: list[Path]
    documents: list[SourceDocument]
    regions: Annotated[list[Region], operator.add]  # written by parse_pdf AND prepare_image
    triage: dict[str, str]  # region key -> RegionKind
    extractions: Annotated[dict[str, Extraction], _merge_dicts]  # keyed by region key
    model_calls: Annotated[list[dict], operator.add]
    listings: list[ListingRecord]
    unassigned: list[str]


# --- Narration -----------------------------------------------------------------------------------


def say(text: str, level: str = "info", **data: Any) -> None:
    """Stream a human-readable progress line to whoever runs the graph (CLI, SSE, UI)."""
    get_stream_writer()({"type": "narration", "text": text, "level": level, **data})


def short(model: str) -> str:
    return model.split("/")[-1]


# --- Nodes ---------------------------------------------------------------------------------------


async def classify(state: IngestionState) -> dict:
    documents = [docs.classify(path) for path in state["paths"]]
    pdfs = sum(d.kind == "pdf" for d in documents)
    say(f"Received {len(documents)} documents: {pdfs} PDF(s), {len(documents) - pdfs} image(s).")
    for d in documents:
        if d.kind == "pdf" and not d.has_text_layer:
            say(f"{d.name}: no text layer (scanned) — pages will go to a vision model.", "warn")
    return {"documents": documents}


async def parse_pdf(state: IngestionState, runtime: Runtime[IngestionContext]) -> dict:
    regions = []
    for document in (d for d in state["documents"] if d.kind == "pdf"):
        found = await asyncio.to_thread(docs.parse_pdf, document, runtime.context.work_dir)
        images = sum(r.kind == "image" for r in found)
        layer = "native text layer read for free" if document.has_text_layer else "scanned"
        say(f"{document.name}: {document.pages} page(s), {layer}, {images} image(s) to inspect.", document=document.name)
        regions += found
    return {"regions": regions}


async def prepare_image(state: IngestionState, runtime: Runtime[IngestionContext]) -> dict:
    regions = []
    for document in (d for d in state["documents"] if d.kind == "image"):
        regions.append(await asyncio.to_thread(docs.prepare_image, document, runtime.context.work_dir))
    return {"regions": regions}


async def extract_text(state: IngestionState, runtime: Runtime[IngestionContext]) -> dict:
    ctx = runtime.context
    text_regions = [r for r in state["regions"] if r.kind == "pdf_text"]
    results = await _gather(ctx, [_read(r, "text", ctx.routing.text, ctx, state) for r in text_regions])
    return _collect(results)


async def triage_images(state: IngestionState, runtime: Runtime[IngestionContext]) -> dict:
    """A cheap vision call decides what each image is, so expensive models only see what matters."""
    ctx = runtime.context
    images = [r for r in state["regions"] if r.kind == "image"]

    async def triage(region: Region) -> tuple[str, str, dict | None]:
        try:
            result = await ctx.llm.complete_json(
                model=ctx.routing.triage, system=_prompt("triage"), user_text=f"Image from {region.document}.",
                schema=RegionTriage, images=[region.image_path], call_key=f"triage:{region.key}",
            )
        except AuthenticationError:
            raise  # a rejected key fails every call: stop the run instead of retrying
        except (LLMError, OpenAIError) as error:
            say(f"{region.key}: triage failed ({_describe(error)}); skipping.", "warn", document=region.document)
            return region.key, "other", None
        kind = result.parsed.kind
        target = getattr(ctx.routing, kind, None)
        action = f"→ {short(target)}" if kind in VISUAL_TASKS else "skipped (nothing to extract)"
        say(f"{region.key}: {kind.replace('_', ' ')} {action}", document=region.document)
        return region.key, kind, _call_record(result, region.key, "triage")

    outcomes = await _gather(ctx, [triage(r) for r in images])
    return {
        "triage": {key: kind for key, kind, _ in outcomes},
        "model_calls": [call for _, _, call in outcomes if call],
    }


async def extract_visual(state: IngestionState, runtime: Runtime[IngestionContext]) -> dict:
    ctx = runtime.context
    jobs = [
        _read(region, state["triage"][region.key], getattr(ctx.routing, state["triage"][region.key]), ctx, state)
        for region in state["regions"]
        if state.get("triage", {}).get(region.key) in VISUAL_TASKS
    ]
    return _collect(await _gather(ctx, jobs))


async def verify_readings(state: IngestionState) -> dict:
    for extraction in state.get("extractions", {}).values():
        if extraction.problems and not extraction.escalated:
            say(f"{extraction.region_key}: {'; '.join(extraction.problems)} — will retry with a stronger model.",
                "warn", document=extraction.document)
        elif extraction.problems:
            say(f"{extraction.region_key}: still {'; '.join(extraction.problems)} after retry — "
                "keeping it with low confidence.", "warn", document=extraction.document)
    return {}


def needs_escalation(state: IngestionState) -> str:
    pending = [e for e in state.get("extractions", {}).values() if e.problems and not e.escalated]
    return "escalate" if pending else "merge"


async def escalate(state: IngestionState, runtime: Runtime[IngestionContext]) -> dict:
    ctx = runtime.context
    regions = {r.key: r for r in state["regions"]}
    pending = [e for e in state["extractions"].values() if e.problems and not e.escalated]
    jobs = [_read(regions[e.region_key], e.task, ctx.routing.escalation, ctx, state, escalated=True) for e in pending]
    return _collect(await _gather(ctx, jobs))


async def merge_listings(state: IngestionState) -> dict:
    by_document: dict[str, DocumentObservations] = {}
    for extraction in state.get("extractions", {}).values():
        entry = by_document.setdefault(extraction.document, DocumentObservations(extraction.document, [], []))
        entry.observations += extraction.observations
        entry.unresolved_problems += extraction.problems

    listings, unassigned = merge(list(by_document.values()))
    for listing in listings:
        for name, value in {**listing.fields, **({"price_trend": listing.price_trend} if listing.price_trend else {})}.items():
            for alternative in value.conflict:
                say(f"⚠ {listing.title}: {name} — {alternative.note}. Recorded both values.", "warn", listing=listing.id)
        get_stream_writer()({"type": "listing", "listing": listing.model_dump(mode="json")})
    for name in unassigned:
        say(f"{name}: couldn't tell which listing this belongs to (no title found).", "warn", document=name)
    return {"listings": listings, "unassigned": unassigned}


async def persist(state: IngestionState, runtime: Runtime[IngestionContext]) -> dict:
    calls = state.get("model_calls", [])
    cost = sum(c["cost_usd"] or 0 for c in calls)
    if runtime.context.store is not None:
        await asyncio.to_thread(runtime.context.store.save, state["listings"], state)
    say(f"Done: {len(state['listings'])} listing(s) from {len(state['documents'])} documents · "
        f"{len(calls)} model calls · ${cost:.4f}.", "success", cost_usd=round(cost, 6))
    return {}


# --- Helpers -------------------------------------------------------------------------------------

TASKS: dict[str, tuple[type[BaseModel], str, Any]] = {
    "text": (TextExtraction, "text_extraction", verify.check_text),
    "floor_plan": (FloorPlanReading, "floor_plan", verify.check_floor_plan),
    "chart": (ChartReading, "chart", verify.check_chart),
    "document_photo": (TextExtraction, "text_extraction", verify.check_document_photo),
}


async def _read(
    region: Region, task: str, model: str, ctx: IngestionContext, state: IngestionState, escalated: bool = False
) -> tuple[Extraction, dict | None]:
    """Run one model reading of one region and turn it into observations + problems."""
    schema, prompt, check = TASKS[task]
    images = [] if task == "text" else [region.image_path]
    user_text = f"Document: {region.document}\n\n{region.text}" if task == "text" else f"Image from {region.document}."
    if task == "document_photo":
        user_text += " It is a photo of a printed page: read it like a document."

    try:
        result = await ctx.llm.complete_json(
            model=model, system=_prompt(prompt), user_text=user_text, schema=schema, images=images,
            call_key=f"{task}:{region.key}",
        )
    except AuthenticationError:
        raise
    except (LLMError, OpenAIError) as error:
        say(f"{region.key}: {short(model)} failed ({_describe(error)}).", "warn", document=region.document)
        return Extraction(region.key, region.document, task, model,
                          problems=[f"model call failed ({_describe(error)})"], escalated=escalated), None

    reading = result.parsed
    observations = _observations(task, reading, region, model, ctx, state)
    problems = check(reading)
    _narrate_reading(task, region, model, observations, result.cost_usd, escalated)
    get_stream_writer()({"type": "facts", "document": region.document, "facts": _facts_preview(observations)})
    return (
        Extraction(region.key, region.document, task, model, observations, problems, escalated),
        _call_record(result, region.key, task, escalated),
    )


def _observations(task, reading, region: Region, model: str, ctx: IngestionContext, state) -> list[Observation]:
    if task == "text":
        pdf_path = next(d.path for d in state["documents"] if d.name == region.document)
        return obs.from_text(reading, region, model, ctx.data_dir, pdf_path)
    if task == "document_photo":
        return obs.from_text(reading, region, model, ctx.data_dir, pdf_path=None)
    if task == "floor_plan":
        return obs.from_floor_plan(reading, region, model, ctx.data_dir)
    return obs.from_chart(reading, region, model, ctx.data_dir)


def _narrate_reading(task, region: Region, model, observations: list[Observation], cost, escalated) -> None:
    preview = _facts_preview(observations)
    highlights = ", ".join(f"{k.replace('_', ' ')}: {v}" for k, v in list(preview.items())[:5])
    how = "native text" if task == "text" else task.replace("_", " ")
    retry = " (retry)" if escalated else ""
    price = f" · ${cost:.4f}" if cost else ""
    say(f"{region.key}: read {how} with {short(model)}{retry} — {highlights or 'nothing found'}{price}",
        document=region.document)


def _facts_preview(observations: list[Observation]) -> dict[str, Any]:
    preview: dict[str, Any] = {}
    for o in observations:
        if o.field.startswith("amenity."):
            preview.setdefault("amenities", []).append(o.field.removeprefix("amenity."))
        elif o.field == "price_trend":
            preview["price_trend"] = f"{len(o.value)} points"
        else:
            preview.setdefault(o.field, o.value)
    return preview


def _collect(results: list[tuple[Extraction, dict | None]]) -> dict:
    return {
        "extractions": {extraction.region_key: extraction for extraction, _ in results},
        "model_calls": [call for _, call in results if call],
    }


def _call_record(result, region_key: str, task: str, escalated: bool = False) -> dict:
    return {
        "region": region_key, "task": task, "model": result.model, "escalated": escalated,
        "input_tokens": result.input_tokens, "output_tokens": result.output_tokens,
        "cost_usd": result.cost_usd, "latency_ms": result.latency_ms,
    }


async def _gather(ctx: IngestionContext, jobs: list) -> list:
    """Run model calls concurrently, at most `max_concurrency` at a time."""
    semaphore = asyncio.Semaphore(ctx.max_concurrency)

    async def limited(job):
        async with semaphore:
            return await job

    return await asyncio.gather(*(limited(job) for job in jobs))


def _describe(error: Exception) -> str:
    """Short, key-free description of a failed call (API errors can echo request details)."""
    if isinstance(error, LLMError):
        return str(error)[:200]
    status = getattr(error, "status_code", None)
    return f"{type(error).__name__}{f' {status}' if status else ''}"


def _prompt(name: str) -> str:
    return (PROMPTS / f"{name}.md").read_text(encoding="utf-8")
