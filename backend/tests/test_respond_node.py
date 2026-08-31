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
    assert result["final_response"] == "Part one. Part two."
