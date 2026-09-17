"""
Regression test for a real bug: Gemini returns AIMessage.content as a
list of content blocks (not a plain string), and the original
respond_node fell back to str(content) for anything non-string — which
produced the raw Python repr of that list as the user-facing reply,
e.g. "[{'type': 'text', 'text': 'Sounds great...', 'extras': {...}}]"
showing up verbatim in the API response.
"""
from langchain_core.messages import AIMessage

from app.graph.nodes import respond_node


def test_respond_node_handles_plain_string_content():
    state = {"messages": [AIMessage(content="Here's your itinerary.")]}
    result = respond_node(state)
    assert result["final_response"] == "Here's your itinerary."


def test_respond_node_handles_gemini_style_block_list_content():
    # Shape actually returned by ChatGoogleGenerativeAI.
    state = {
        "messages": [
            AIMessage(
                content=[
                    {
                        "type": "text",
                        "text": "Sounds like a fantastic trip!",
                        "extras": {"signature": "abc123"},
                    }
                ]
            )
        ]
    }
    result = respond_node(state)
    assert result["final_response"] == "Sounds like a fantastic trip!"
    # The old bug: this must NOT contain the raw block repr.
    assert "'type'" not in result["final_response"]
    assert "extras" not in result["final_response"]


def test_respond_node_joins_multiple_text_blocks():
    state = {
        "messages": [
            AIMessage(
                content=[
                    {"type": "text", "text": "Part one. "},
                    {"type": "text", "text": "Part two."},
                ]
            )
        ]
    }
    result = respond_node(state)
    assert result["final_response"] == "Part one. \nPart two."


def test_respond_node_appends_caveat_when_user_proceeded_despite_errors():
    """When the user said 'proceed' after validation retries were exhausted,
    user_wants_retry is False and validation_errors is non-empty — respond_node
    should append the unverified-claim disclaimer."""
    state = {
        "messages": [AIMessage(content="It'll be sunny and 24°C.")],
        "user_wants_retry": False,
        "validation_errors": ["Response describes specific weather conditions without calling get_weather."],
    }
    result = respond_node(state)
    assert "wasn't independently verified" in result["final_response"]
    assert "24°C" in result["final_response"]
    # Bookkeeping must be cleared for the next turn.
    assert result["user_wants_retry"] is False
    assert result["validation_errors"] == []


def test_respond_node_no_caveat_when_retry_succeeded():
    """When user_wants_retry was True the agent got another chance and
    succeeded cleanly — by the time respond_node runs, validation_errors
    should be empty and no caveat should appear."""
    state = {
        "messages": [AIMessage(content="Based on the forecast, expect 24°C.")],
        "user_wants_retry": False,
        "validation_errors": [],   # cleared by validate_node on clean pass
    }
    result = respond_node(state)
    assert "wasn't independently verified" not in result["final_response"]
