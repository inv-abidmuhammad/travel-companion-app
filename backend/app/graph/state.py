"""
Graph state for the AI Adventure Companion.

TypedDict with total=False: nodes return partial dicts and LangGraph
merges them into state, so every field is implicitly optional with no
default needed. Pydantic BaseModel is the right choice for external API
schemas (see app/schemas/); TypedDict is the conventional fit here.
"""
from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages


class AdventureState(TypedDict, total=False):
    # ── core conversation ────────────────────────────────────────────────────
    messages: Annotated[list, add_messages]  # append-only via add_messages reducer
    user_id: str                             # carried from the initial /chat request
    final_response: str | None              # set by respond_node, read by main.py

    # ── validation guardrail ─────────────────────────────────────────────────
    # validate_node writes these; route_after_validate and respond_node read them.
    validation_errors: list[str]
    validation_attempts: int
    needs_revision: bool

    # ── human-in-the-loop ────────────────────────────────────────────────────
    # human_input_node writes this; route_after_human_input and respond_node read it.
    user_wants_retry: bool

    # ── trip slots ────────────────────────────────────────────────────────────
    # Written by tools_node whenever the agent calls record_trip_detail;
    # read by the (Phase 2) missing-fields router and the itinerary builder.
    # None means "not yet confirmed by the user" — never inferred from raw
    # text, only ever set via the tool call, same reasoning as validate_node
    # checking tool calls rather than guessing from phrasing.
    origin: str | None
    destination: str | None
    departure_date: str | None  # YYYY-MM-DD
    duration_days: int | None
    budget: float | None

    # ── itinerary ─────────────────────────────────────────────────────────────
    itinerary_text: str | None
    itinerary_confirmed: bool