import asyncio
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile
from fastapi.sse import EventSourceResponse, ServerSentEvent
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import ingestion_service
from app.db import SessionLocal, get_session
from app.events import run_events
from app.models import Event, IngestionRun

router = APIRouter(prefix="/ingestions", tags=["ingestions"])

MAX_FILES = 30
MAX_BYTES = 20 * 1024 * 1024


@router.post("", status_code=202)
async def upload(files: list[UploadFile] = File(...)) -> dict:
    """Start an ingestion run for the uploaded files. Progress streams from /events."""
    if not 0 < len(files) <= MAX_FILES:
        raise HTTPException(400, f"Upload between 1 and {MAX_FILES} files.")
    if any((f.size or 0) > MAX_BYTES for f in files):
        raise HTTPException(413, "Each file must be 20 MB or less.")
    return {"run_id": await ingestion_service.start_from_uploads(files)}


@router.post("/sample", status_code=202)
async def sample() -> dict:
    """Start an ingestion run on the bundled synthetic documents."""
    return {"run_id": ingestion_service.start_from_samples()}


@router.get("/{run_id}")
def get_run(run_id: str, session: Session = Depends(get_session)) -> dict:
    run = session.get(IngestionRun, run_id)
    if run is None:
        raise HTTPException(404, "Run not found")
    return {"id": run.id, "status": run.status, "error": run.error, "cost_usd": run.cost_usd}


def existing_run(run_id: str, session: Session = Depends(get_session)) -> str:
    """Checked before the stream starts: once an SSE response begins, it can't become a 404."""
    if session.get(IngestionRun, run_id) is None:
        raise HTTPException(404, "Run not found")
    return run_id


@router.get("/{run_id}/events", response_class=EventSourceResponse)
async def events(run_id: str = Depends(existing_run), last_event_id: int = Header(0)) -> AsyncIterator[ServerSentEvent]:
    """Replay stored events, then follow the live run. Reconnecting browsers send Last-Event-ID."""
    queue = run_events.subscribe(run_id)  # subscribe BEFORE replaying, so nothing falls in the gap
    try:
        with SessionLocal() as session:
            stored = session.scalars(
                select(Event).where(Event.run_id == run_id, Event.id > last_event_id).order_by(Event.id)
            ).all()
            replay = [{**event.payload, "id": event.id} for event in stored]
            finished = session.get(IngestionRun, run_id).status != "running"

        last_sent = last_event_id
        for event in replay:
            last_sent = event["id"]
            yield ServerSentEvent(data=event, id=str(event["id"]))
        if finished:
            yield ServerSentEvent(data={"type": "end"}, event="end")
            return

        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=15)
            except TimeoutError:
                yield ServerSentEvent(comment="keep-alive")
                continue
            if event["type"] == "end":
                yield ServerSentEvent(data=event, event="end")
                return
            if event["id"] > last_sent:
                last_sent = event["id"]
                yield ServerSentEvent(data=event, id=str(event["id"]))
    finally:
        run_events.unsubscribe(run_id, queue)
