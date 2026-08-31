"""
Graph state for the AI Adventure Companion.

Keep this typed and intentional: only what nodes need to make decisions
lives here. Durable application data (users, trips, saved itineraries)
belongs in the database once Phase 3 adds persistence — this is
short-lived, per-conversation working memory that LangGraph's
checkpointer snapshots between turns.

Phase 1 uses: messages, user_id, trip_id, final_response.
Everything else is defined now so later phases are additive, not
a state-shape rewrite.
"""
from typing import Annotated, Any, TypedDict

from langgraph.graph.message import add_messages


class AdventureState(TypedDict, total=False):
    # Phase 1 — core conversation loop
    messages: Annotated[list, add_messages]
    user_id: str
    trip_id: str | None
    final_response: str | None

    # Phase 2 — tool-using planner
    intent: str | None
    user_preferences: dict[str, Any]
    constraints: dict[str, Any]
    destination_candidates: list[Any]
    selected_destination: dict[str, Any] | None
    itinerary: list[Any]
    tool_results: dict[str, Any]
    validation_errors: list[str]

    # Phase 4 — human-in-the-loop / re-planning
    pending_questions: list[str]
    needs_human_input: bool
    current_step: str | None
