"""Starting ingestion runs from the API: save the files, record the run, run the graph in the
background, and publish every event (database + live subscribers)."""

import asyncio
import shutil
from pathlib import Path

from fastapi import UploadFile
from openai import AuthenticationError

from app.config import settings
from app.db import SessionLocal
from app.events import run_events
from app.ingestion.runner import build_llm, run_ingestion
from app.models import Document, IngestionRun
from app.store import SqlListingStore, add_event

DATASET = Path(__file__).resolve().parents[2] / "dataset" / "listings"
_background: set[asyncio.Task] = set()  # keep references so tasks aren't garbage-collected mid-run


def run_dir(run_id: str) -> Path:
    return settings.data_dir / "runs" / run_id


async def start_from_uploads(files: list[UploadFile]) -> str:
    run_id = _create_run()
    uploads = run_dir(run_id) / "uploads"
    uploads.mkdir(parents=True, exist_ok=True)
    paths = []
    for file in files:
        target = uploads / Path(file.filename or "upload").name  # never trust client paths
        target.write_bytes(await file.read())
        paths.append(target)
    return _start(run_id, paths)


def start_from_samples() -> str:
    """Ingest the bundled synthetic dataset — the 'try it' button for people without documents."""
    run_id = _create_run()
    uploads = run_dir(run_id) / "uploads"
    uploads.mkdir(parents=True, exist_ok=True)
    paths = []
    for source in sorted(p for p in DATASET.rglob("*") if p.suffix in {".pdf", ".png", ".jpg"}):
        target = uploads / source.name
        shutil.copyfile(source, target)
        paths.append(target)
    return _start(run_id, paths)


def _create_run() -> str:
    with SessionLocal.begin() as session:
        run = IngestionRun()
        session.add(run)
        session.flush()
        return run.id


def _start(run_id: str, paths: list[Path]) -> str:
    with SessionLocal.begin() as session:
        for path in paths:
            relative = path.relative_to(settings.data_dir).as_posix()
            session.add(Document(run_id=run_id, filename=path.name, path=relative))
    task = asyncio.create_task(_run(run_id, paths))
    _background.add(task)
    task.add_done_callback(_background.discard)
    return run_id


async def _run(run_id: str, paths: list[Path]) -> None:
    def emit(event: dict) -> None:
        event_id = add_event(SessionLocal, run_id, event)
        run_events.publish(run_id, {**event, "id": event_id})

    status, error = "done", None
    try:
        await run_ingestion(
            paths, llm=build_llm(settings), work_dir=run_dir(run_id), data_dir=settings.data_dir,
            store=SqlListingStore(SessionLocal, run_id), on_event=emit,
        )
    except AuthenticationError:
        status, error = "failed", "The model provider rejected the API key. Check backend/.env."
    except Exception as exc:  # the run must always end with a status the UI can show
        status, error = "failed", f"{type(exc).__name__}: {exc}"[:300]

    if error:
        emit({"type": "narration", "level": "error", "text": error})
    with SessionLocal.begin() as session:
        run = session.get(IngestionRun, run_id)
        run.status, run.error = status, error
    run_events.finish(run_id)
