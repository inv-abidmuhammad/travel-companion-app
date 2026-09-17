"""
Tests for graph/extraction.py.

Covers three layers:
1. _is_user_facing_ai_message — the helper that decides which AIMessages
   were actually shown to the user vs. intermediate retry drafts.
2. _format_conversation — the transcript builder that feeds the LLM.
3. extract_trip_from_conversation — the public API (LLM call mocked).

The LLM call itself is not tested here — these tests verify the
conversation pre-processing and the plumbing around the structured
output call, not the model's extraction quality.
"""
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.graph.extraction import (
    ExtractedTripFields,
    _format_conversation,
    _is_user_facing_ai_message,
    extract_trip_from_conversation,
)


# ---------------------------------------------------------------------------
# _is_user_facing_ai_message
# ---------------------------------------------------------------------------

def test_ai_message_with_tool_calls_is_not_user_facing():
    """Tool-calling AIMessages are planner decisions, never shown to the user."""
    messages = [
        AIMessage(
            content="",
            tool_calls=[{"name": "get_weather", "args": {}, "id": "c1", "type": "tool_call"}],
        ),
    ]
    assert _is_user_facing_ai_message(messages, 0) is False


def test_ai_message_followed_by_validation_check_is_not_user_facing():
    """A [validation check] injection after an AIMessage means it was a
    failed draft — the user only sees the corrected version that followed."""
    messages = [
        AIMessage(content="It'll be 24°C."),
        HumanMessage(content="[validation check] call get_weather first"),
    ]
    assert _is_user_facing_ai_message(messages, 0) is False


def test_ai_message_followed_by_real_user_message_is_user_facing():
    messages = [
        AIMessage(content="Here's your itinerary."),
        HumanMessage(content="Sounds great, thanks!"),
    ]
    assert _is_user_facing_ai_message(messages, 0) is True


def test_ai_message_at_end_of_conversation_is_user_facing():
    """The most recent response in the conversation is always user-facing."""
    messages = [
        HumanMessage(content="Plan a trip to Goa."),
        AIMessage(content="Sure! Here's a 5-day plan."),
    ]
    assert _is_user_facing_ai_message(messages, 1) is True


def test_tool_messages_between_ai_and_next_human_are_skipped_in_scan():
    """ToolMessages sitting between an AIMessage and the next real
    HumanMessage should not cause the AIMessage to be excluded."""
    messages = [
        AIMessage(content="Based on results, expect sunshine."),
        ToolMessage(content="...", tool_call_id="c1", name="get_weather"),
        HumanMessage(content="Perfect, book it!"),
    ]
    assert _is_user_facing_ai_message(messages, 0) is True


def test_human_decision_message_does_not_mark_preceding_ai_as_failed():
    """[human decision] is a resume payload injected after an interrupt —
    the AIMessage before it was genuinely shown to the user (it's the
    one that triggered the interrupt question)."""
    messages = [
        AIMessage(content="I couldn't verify the weather; proceed or retry?"),
        HumanMessage(content="[human decision] proceed"),
    ]
    assert _is_user_facing_ai_message(messages, 0) is True


# ---------------------------------------------------------------------------
# _format_conversation
# ---------------------------------------------------------------------------

def test_format_includes_user_and_assistant_messages():
    messages = [
        HumanMessage(content="I want to go from Mumbai to Manali."),
        AIMessage(content="Great choice! Here's a plan."),
    ]
    result = _format_conversation(messages)
    assert "User: I want to go from Mumbai to Manali." in result
    assert "Assistant: Great choice! Here's a plan." in result


def test_format_excludes_tool_messages():
    messages = [ToolMessage(content='{"temp": 24}', tool_call_id="c1", name="get_weather")]
    assert _format_conversation(messages) == ""


def test_format_excludes_validation_check_human_messages():
    messages = [HumanMessage(content="[validation check] call get_weather first")]
    assert _format_conversation(messages) == ""


def test_format_excludes_human_decision_messages():
    messages = [HumanMessage(content="[human decision] proceed")]
    assert _format_conversation(messages) == ""


def test_format_excludes_ai_messages_with_tool_calls():
    messages = [
        AIMessage(
            content="",
            tool_calls=[{"name": "calculator", "args": {}, "id": "c1", "type": "tool_call"}],
        )
    ]
    assert _format_conversation(messages) == ""


def test_format_excludes_failed_ai_draft_but_keeps_passing_response():
    """The draft that triggered a [validation check] must be hidden;
    the corrected response that followed must be visible."""
    messages = [
        HumanMessage(content="What's the weather in Goa?"),
        AIMessage(content="It'll be sunny and 28°C."),             # failed draft
        HumanMessage(content="[validation check] call get_weather"),
        ToolMessage(content="...", tool_call_id="c1", name="get_weather"),
        AIMessage(content="Based on the forecast, expect 28°C."),  # user-facing
    ]
    result = _format_conversation(messages)
    assert "It'll be sunny and 28°C." not in result
    assert "Based on the forecast, expect 28°C." in result


def test_format_full_clean_conversation():
    """A normal turn with no validation loops — everything visible to the
    user should appear, tool mechanics should not."""
    messages = [
        HumanMessage(content="Plan Manali, 5 days, budget ₹30000."),
        AIMessage(
            content="",
            tool_calls=[{"name": "calculator", "args": {"expression": "30000/5"}, "id": "c1", "type": "tool_call"}],
        ),
        ToolMessage(content='{"result": 6000}', tool_call_id="c1", name="calculator"),
        AIMessage(content="Your daily budget is ₹6,000. Here's your 5-day plan."),
    ]
    result = _format_conversation(messages)
    assert "User: Plan Manali" in result
    assert "Assistant: Your daily budget" in result
    # Intermediate tool-calling AIMessage and ToolMessage must be absent.
    assert '{"result": 6000}' not in result
    assert result.count("Assistant:") == 1


# ---------------------------------------------------------------------------
# extract_trip_from_conversation
# ---------------------------------------------------------------------------

def test_extract_returns_empty_fields_for_no_messages():
    result = extract_trip_from_conversation([])
    assert result == ExtractedTripFields()


def test_extract_returns_empty_fields_when_only_tool_messages():
    """Only ToolMessages produce an empty transcript — no LLM call should
    be made and the result should be all-None."""
    messages = [ToolMessage(content="...", tool_call_id="c1", name="calculator")]
    result = extract_trip_from_conversation(messages)
    assert result == ExtractedTripFields()


def test_extract_calls_structured_output_and_returns_result():
    """The function should call llm.with_structured_output(ExtractedTripFields),
    invoke it with the formatted transcript, and return the result."""
    messages = [
        HumanMessage(content="I want to go from Mumbai to Manali for 7 days, budget 28000."),
        AIMessage(content="Here's a 7-day plan from Mumbai to Manali within ₹28,000."),
    ]
    expected = ExtractedTripFields(
        origin="Mumbai", destination="Manali", duration_days=7, budget=28000.0
    )

    with patch("app.graph.extraction.llm") as mock_llm:
        mock_extractor = MagicMock()
        mock_extractor.invoke.return_value = expected
        mock_llm.with_structured_output.return_value = mock_extractor

        result = extract_trip_from_conversation(messages)

    assert result.origin == "Mumbai"
    assert result.destination == "Manali"
    assert result.duration_days == 7
    assert result.budget == 28000.0
    mock_llm.with_structured_output.assert_called_once_with(ExtractedTripFields)
    # The formatted transcript must have been passed to the extractor.
    call_args = mock_extractor.invoke.call_args[0][0]
    assert "Mumbai" in call_args
    assert "Manali" in call_args
