"""Reads and writes of ingestion results. The graph's `persist` node calls `SqlListingStore.save`."""

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, sessionmaker

from app.ingestion.schemas import ListingRecord
from app.models import Document, Event, IngestionRun, Listing, ModelCall


class SqlListingStore:
    def __init__(self, session_factory: sessionmaker, run_id: str):
        self.session_factory = session_factory
        self.run_id = run_id

    def save(self, listings: list[ListingRecord], state: dict) -> None:
        with self.session_factory.begin() as session:
            for record in listings:
                session.merge(Listing(
                    id=record.id, title=record.title, run_id=self.run_id, record=record.model_dump(mode="json"),
                ))
                session.execute(
                    Document.__table__.update()
                    .where(Document.run_id == self.run_id, Document.filename.in_(record.documents))
                    .values(listing_id=record.id)
                )
            calls = state.get("model_calls", [])
            session.add_all(ModelCall(run_id=self.run_id, **call) for call in calls)
            run = session.get(IngestionRun, self.run_id)
            run.cost_usd = sum(call["cost_usd"] or 0 for call in calls)


def add_event(session_factory: sessionmaker, run_id: str, payload: dict) -> int:
    with session_factory.begin() as session:
        event = Event(run_id=run_id, payload=payload)
        session.add(event)
        session.flush()
        return event.id


def list_listings(session: Session) -> list[ListingRecord]:
    rows = session.scalars(select(Listing).order_by(Listing.id))
    return [ListingRecord.model_validate(row.record) for row in rows]


def get_listing(session: Session, listing_id: str) -> ListingRecord | None:
    row = session.get(Listing, listing_id)
    return ListingRecord.model_validate(row.record) if row else None


def reset(session: Session) -> None:
    """Forget every run (demo reset). Files on disk are removed by the caller."""
    for table in (Event, ModelCall, Listing, Document, IngestionRun):
        session.execute(delete(table))
