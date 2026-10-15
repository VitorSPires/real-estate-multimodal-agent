"""Database tables. Listings store the merged record as JSON: it is always read and written whole,
so splitting it into columns would add joins without adding queries we need."""

from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from uuid6 import uuid7

from app.db import Base


def new_id() -> str:
    return str(uuid7())


def now() -> datetime:
    return datetime.now(UTC)


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    status: Mapped[str] = mapped_column(String, default="running")  # running | done | failed
    error: Mapped[str | None] = mapped_column(String, nullable=True)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(ForeignKey("ingestion_runs.id"))
    filename: Mapped[str] = mapped_column(String)
    path: Mapped[str] = mapped_column(String)  # relative to the data dir
    listing_id: Mapped[str | None] = mapped_column(String, nullable=True)


class Listing(Base):
    __tablename__ = "listings"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # e.g. "harbor-view-1104"
    title: Mapped[str] = mapped_column(String)
    run_id: Mapped[str] = mapped_column(ForeignKey("ingestion_runs.id"))
    record: Mapped[dict] = mapped_column(JSON)  # ListingRecord.model_dump(mode="json")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class ModelCall(Base):
    __tablename__ = "model_calls"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(ForeignKey("ingestion_runs.id"))
    region: Mapped[str] = mapped_column(String)
    task: Mapped[str] = mapped_column(String)
    model: Mapped[str] = mapped_column(String)
    escalated: Mapped[bool] = mapped_column(default=False)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)


class Event(Base):
    """Every narration / facts / listing event of a run, so the UI can replay it after a reload."""

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("ingestion_runs.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    payload: Mapped[dict] = mapped_column(JSON)
