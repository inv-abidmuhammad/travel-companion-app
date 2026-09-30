"""
Tests for graph/utils.py: extract_text, is_synthetic, normalize_message.

These functions sit beneath every node and every message-formatting step,
so bugs here would silently affect everything above them.
"""
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.graph.utils import (
    extract_text,
    is_synthetic,
    normalize_message,
    is_user_facing_ai_message,
    get_user_facing_messages,
)



# ---------------------------------------------------------------------------
# extract_text
# ---------------------------------------------------------------------------

def test_extract_text_returns_plain_string_unchanged():
    assert extract_text("Hello world") == "Hello world"


def test_extract_text_joins_text_blocks_with_newline():
    blocks = [{"type": "text", "text": "Part one."}, {"type": "text", "text": "Part two."}]
    assert extract_text(blocks) == "Part one.\nPart two."


def test_extract_text_skips_non_text_blocks():
    blocks = [{"type": "image_url", "url": "http://example.com"}, {"type": "text", "text": "Hi"}]
    assert extract_text(blocks) == "Hi"


def test_extract_text_skips_empty_text_values():
    blocks = [{"type": "text", "text": ""}, {"type": "text", "text": "Real content"}]
    assert extract_text(blocks) == "Real content"


def test_extract_text_handles_empty_list():
    assert extract_text([]) == ""


def test_extract_text_handles_list_of_plain_strings():
    assert extract_text(["Hello", " world"]) == "Hello\n world"


def test_extract_text_falls_back_to_str_for_unknown_type():
    assert extract_text(42) == "42"


# ---------------------------------------------------------------------------
# is_synthetic
# ---------------------------------------------------------------------------

def test_is_synthetic_matches_validation_check_prefix():
    assert is_synthetic("[validation check] your last answer was wrong") is True


def test_is_synthetic_is_case_insensitive():
    assert is_synthetic("[VALIDATION CHECK] retry please") is True


def test_is_synthetic_returns_false_for_normal_user_message():
    assert is_synthetic("I want to visit Manali for 5 days.") is False


def test_is_synthetic_returns_false_for_human_decision():
    # [human decision] is NOT a synthetic validation nudge — it's a
    # resume payload from the user and is handled separately.
    assert is_synthetic("[human decision] proceed") is False


# ---------------------------------------------------------------------------
# normalize_message
# ---------------------------------------------------------------------------

def test_normalize_message_user_role_and_text():
    msg = HumanMessage(content="I want to go to Goa", id="m1")
    result = normalize_message(msg)
    assert result["role"] == "user"
    assert result["text"] == "I want to go to Goa"
    assert result["id"] == "m1"


def test_normalize_message_assistant_role():
    msg = AIMessage(content="Great choice!", id="m2")
    result = normalize_message(msg)
    assert result["role"] == "assistant"
    assert result["text"] == "Great choice!"


def test_normalize_message_synthetic_validation_check_becomes_internal():
    msg = HumanMessage(content="[validation check] call get_weather first", id="m3")
    result = normalize_message(msg)
    assert result["role"] == "internal"
    assert result.get("synthetic") is True


def test_normalize_message_human_decision_strips_prefix():
    msg = HumanMessage(content="[human decision] proceed", id="m4")
    result = normalize_message(msg)
    assert result["role"] == "user"
    assert result["text"] == "proceed"


def test_normalize_message_includes_tool_calls_for_ai_messages():
    msg = AIMessage(
        content="",
        tool_calls=[{"name": "calculator", "args": {"expression": "100/4"}, "id": "c1", "type": "tool_call"}],
        id="m5",
    )
    result = normalize_message(msg)
    assert "tool_calls" in result
    assert result["tool_calls"][0]["name"] == "calculator"
    assert result["tool_calls"][0]["args"] == {"expression": "100/4"}


def test_normalize_message_no_tool_calls_key_for_plain_ai_message():
    msg = AIMessage(content="Here's your plan.", id="m6")
    result = normalize_message(msg)
    assert "tool_calls" not in result


# ---------------------------------------------------------------------------
# get_user_facing_messages
# ---------------------------------------------------------------------------

def test_get_user_facing_messages_excludes_failed_validation_drafts():
    messages = [
        HumanMessage(content="Trip to China for 7 days with 50000 budget", id="m1"),
        AIMessage(content="That's a great start! Budget of 50,000 rupees...", id="m2"),
        HumanMessage(content="[validation check] unverified claims", id="m3"),
        AIMessage(content="", tool_calls=[{"name": "calculator", "args": {"expression": "50000/7"}, "id": "c1"}], id="m4"),
        ToolMessage(content="7142.85", tool_call_id="c1", name="calculator", id="m5"),
        AIMessage(content="With 50,000 for 7 days, you have ~7,143 per day.", id="m6"),
    ]
    result = get_user_facing_messages(messages)
    assert len(result) == 2
    assert result[0]["role"] == "user"
    assert result[0]["text"] == "Trip to China for 7 days with 50000 budget"
    assert result[1]["role"] == "assistant"
    assert result[1]["text"] == "With 50,000 for 7 days, you have ~7,143 per day."

