"""
Conversation-to-trip extraction.

`extract_trip_from_conversation(messages)` reads the full message list
for a conversation thread and uses an LLM with structured output to pull
out whatever trip planning data has been settled on so far.

Design choices:
- The function takes a plain message list, not a thread_id, so it stays
  pure and easy to unit test without a running database or graph.
- The caller (the PATCH endpoint) is responsible for fetching the messages
  and writing the result back to the trip row.
- Every field is Optional — the function returns only what it can
  determine with confidence from the *latest state* of the conversation.
  Fields that were mentioned but later retracted without replacement come
  back as None rather than the stale value.
"""
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from pydantic import BaseModel, Field

from .llm import llm
from .prompts import EXTRACTION_SYSTEM_PROMPT
from .utils import extract_text, is_synthetic


class ExtractedTripFields(BaseModel):
    """The structured shape the LLM fills in.

    Kept separate from TripUpdate intentionally: TripUpdate includes
    `status`, which is a business/workflow field — not something to
    infer from conversation. This schema covers only the planning data
    that naturally emerges from a chat session. The field descriptions
    here are also extraction-oriented ("if clearly stated and not
    retracted") rather than PATCH-oriented ("updated value of X").
    """

    origin: str | None = Field(
        None,
        description=(
            "Starting location of the trip, if the user clearly stated it "
            "and did not later retract it. Null otherwise."
        ),
    )
    destination: str | None = Field(
        None,
        description=(
            "Trip destination, if agreed upon and not retracted. "
            "Use the most specific place name mentioned (e.g. 'Manali' not 'the mountains'). "
            "Null if not finalized."
        ),
    )
    departure_date: str | None = Field(
        None,
        description=(
            "Planned departure date as YYYY-MM-DD, if clearly stated and not retracted. "
            "Null otherwise."
        ),
    )
    budget: float | None = Field(
        None,
        description=(
            "Total trip budget as a plain number (no currency symbols). "
            "Null if not stated or retracted."
        ),
    )
    duration_days: int | None = Field(
        None,
        description=(
            "Trip duration in whole days as an integer "
            "(e.g. 7 for 'a week', 3 for 'a long weekend'). "
            "Null if not stated."
        ),
    )
    itinerary_text: str | None = Field(
        None,
        description=(
            "Full or partial itinerary from the conversation, written out clearly "
            "with day-by-day or activity-level detail. Include everything that was "
            "discussed and not later removed. "
            "Null only if no concrete itinerary planning happened at all."
        ),
    )
    retracted_fields: list[str] = Field(
        default_factory=list,
        description="Names of fields the user explicitly retracted without a replacement (e.g. ['destination']). Do not include fields that were simply never mentioned."
    )


def _is_user_facing_ai_message(messages: list, index: int) -> bool:
    """Return True only if the AIMessage at messages[index] was actually
    presented to the user — meaning:

    1. It has no tool_calls (those are intermediate planner decisions, never
       shown to the user).
    2. It is NOT followed by a [validation check] injection before the next
       real HumanMessage (if it is, it was a failed draft that the graph
       retried internally — the user only ever saw the final passing version).
    """
    m = messages[index]
    if getattr(m, "tool_calls", None):
        return False

    for j in range(index + 1, len(messages)):
        nxt = messages[j]
        if isinstance(nxt, ToolMessage):
            continue
        if isinstance(nxt, HumanMessage):
            nxt_text = extract_text(nxt.content)
            if is_synthetic(nxt_text):
                return False
            elif nxt_text.lower().startswith("[human decision]"):
                return False
            else:
                return True

    return True


def _format_conversation(messages: list) -> str:
    """Build a clean User / Assistant transcript for the extraction prompt.

    Included:
    - Real HumanMessages typed by the user
    - AIMessages that were actually shown to the user (user-facing responses)

    Excluded:
    - ToolMessages (raw JSON tool results — internal graph mechanics)
    - [validation check] HumanMessages (internal nudges to the agent)
    - [human decision] HumanMessages (resume payloads after an interrupt —
      already reflected in the subsequent AI response)
    - AIMessages with tool_calls (intermediate planner decisions)
    - AIMessages that preceded a validation failure (failed drafts the user
      never saw)
    """
    lines = []
    for i, m in enumerate(messages):
        if isinstance(m, ToolMessage):
            continue

        if isinstance(m, HumanMessage):
            text = extract_text(m.content)
            if is_synthetic(text) or text.lower().startswith("[human decision]"):
                continue
            lines.append(f"User: {text}")

        elif isinstance(m, AIMessage):
            if not _is_user_facing_ai_message(messages, i):
                continue
            text = extract_text(m.content)
            lines.append(f"Assistant: {text}")

    return "\n\n".join(lines)


def extract_trip_from_conversation(messages: list) -> ExtractedTripFields:
    """Given the LangChain message list for a thread, extract whatever
    trip planning fields can be determined from the conversation.

    Returns an ExtractedTripFields instance. Fields that couldn't be
    determined (or were retracted without replacement) are None — callers
    should filter those out before writing to the database so that a
    partial extraction doesn't accidentally overwrite previously saved data.

    Returns an empty ExtractedTripFields (all None) if there are no
    messages or no meaningful conversation yet.
    """
    if not messages:
        return ExtractedTripFields()

    conversation = _format_conversation(messages)
    if not conversation.strip():
        return ExtractedTripFields()

    extractor = llm.with_structured_output(ExtractedTripFields)
    return extractor.invoke(f"{EXTRACTION_SYSTEM_PROMPT}\n\nConversation:\n{conversation}")