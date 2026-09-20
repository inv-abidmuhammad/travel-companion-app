"""
Conversation-to-itinerary extraction.

`extract_trip_from_conversation(messages)` reads the full message list
for a conversation thread and uses an LLM with structured output to pull
out the itinerary that's been discussed so far.

origin/destination/departure_date/duration_days/budget are deliberately
NOT extracted here — those are recorded directly by the
record_trip_detail tool (see trip_details.py) the moment the user
confirms them, with real type/format validation and an error path back
to the agent on a bad value. That's ground truth; re-deriving it from
prose after the fact can only lose information (e.g. a date the agent
resolved internally but only ever paraphrased back to the user, like
"mid-October" instead of the literal 2026-10-15). Callers should read
those five fields straight from graph state instead — see PATCH
/trips/{trip_id} in main.py.

itinerary_text is the one exception: there's no tool that writes it
into state, so it only ever exists in the conversation's prose, which
is what this function is for.

Design choices:
- The function takes a plain message list, not a thread_id, so it stays
  pure and easy to unit test without a running database or graph.
- The caller (the PATCH endpoint) is responsible for fetching the messages
  and writing the result back to the trip row.
- itinerary_text reflects only the *latest state* of the conversation —
  if part of it was discussed and later changed or dropped, only the
  final version should come back.
"""
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from pydantic import BaseModel, Field

from .llm import llm
from .prompts import EXTRACTION_SYSTEM_PROMPT
from .utils import extract_text, is_synthetic


class ExtractedTripFields(BaseModel):
    """The structured shape the LLM fills in.

    Just one field: see the module docstring for why the other trip
    fields aren't extracted here anymore.
    """

    itinerary_text: str | None = Field(
        None,
        description=(
            "Full or partial itinerary from the conversation, written out clearly "
            "with day-by-day or activity-level detail. Include everything that was "
            "discussed and not later removed. "
            "Null only if no concrete itinerary planning happened at all."
        ),
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
    """Given the LangChain message list for a thread, extract the
    itinerary discussed so far.

    Returns an ExtractedTripFields instance. itinerary_text is None if
    it couldn't be determined — callers should treat that as "leave
    the existing value alone," not "clear it."

    Returns an empty ExtractedTripFields (itinerary_text=None) if there
    are no messages or no meaningful conversation yet.
    """
    if not messages:
        return ExtractedTripFields()

    conversation = _format_conversation(messages)
    if not conversation.strip():
        return ExtractedTripFields()

    extractor = llm.with_structured_output(ExtractedTripFields)
    return extractor.invoke(f"{EXTRACTION_SYSTEM_PROMPT}\n\nConversation:\n{conversation}")