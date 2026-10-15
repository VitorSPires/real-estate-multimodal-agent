import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app import store
from app.config import settings
from app.db import get_session
from app.ingestion.schemas import ListingRecord

router = APIRouter(tags=["listings"])


@router.get("/listings")
def list_listings(session: Session = Depends(get_session)) -> list[ListingRecord]:
    return store.list_listings(session)


@router.get("/listings/{listing_id}")
def get_listing(listing_id: str, session: Session = Depends(get_session)) -> ListingRecord:
    listing = store.get_listing(session, listing_id)
    if listing is None:
        raise HTTPException(404, "Listing not found")
    return listing


@router.get("/files/{path:path}")
def get_file(path: str) -> FileResponse:
    """Page renders, crops and uploads referenced by evidence (`image_path`)."""
    data_dir = settings.data_dir.resolve()
    target = (data_dir / path).resolve()
    if not target.is_relative_to(data_dir) or not target.is_file():  # blocks ../ traversal
        raise HTTPException(404, "File not found")
    return FileResponse(target)


@router.post("/reset", status_code=204)
def reset(session: Session = Depends(get_session)) -> None:
    """Forget all runs and listings (demo reset)."""
    store.reset(session)
    session.commit()
    shutil.rmtree(Path(settings.data_dir) / "runs", ignore_errors=True)
