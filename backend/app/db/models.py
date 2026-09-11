"""
Durable application data — separate from LangGraph's own checkpoint
tables (checkpoints, checkpoint_writes, checkpoint_blobs), which store
conversation/graph state and are managed entirely by
langgraph-checkpoint-postgres, not by anything here.

This is deliberately a small slice of the blueprint's full data model
(User, Trip, TripPreference, ItineraryDay, Place, Conversation,
Message, ToolExecution): only User and Trip exist right now, because
the agent doesn't yet extract structured itinerary data from
conversation — adding ItineraryDay/Place tables with nothing to
populate them would be scaffolding ahead of actual capability. A Trip
links to a conversation via `thread_id`, which is the join point
between "durable business data" (this file) and "conversation memory"
(the checkpointer) — see /trips/{trip_id}/resume in main.py.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    trips: Mapped[list["Trip"]] = relationship(back_populates="user")


class Trip(Base):
    __tablename__ = "trips"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)

    # The join point to LangGraph's checkpointed conversation state —
    # see adventure_graph.get_state({"configurable": {"thread_id": ...}})
    thread_id: Mapped[str] = mapped_column(String, index=True)

    origin: Mapped[str | None] = mapped_column(String, nullable=True)
    destination: Mapped[str | None] = mapped_column(String, nullable=True)
    budget: Mapped[float | None] = mapped_column(Float, nullable=True)
    duration_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String, default="draft")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    user: Mapped["User"] = relationship(back_populates="trips")

    itinerary_text: Mapped[str | None] = mapped_column(String, nullable=True)
