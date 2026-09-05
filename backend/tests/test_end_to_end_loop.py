"""
End-to-end proof that validate_node's retry loop actually changes
graph behavior — not just that each node works in isolation. Stubs
out the LLM (via _get_llm) so this needs no live API key: turn 1
guesses a weather claim with no tool call, turn 2 (after validate's
nudge) calls get_weather, turn 3 gives a clean final answer.
"""
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage

from app.graph.graph import build_graph


def test_full_graph_loops_through_validate_when_agent_guesses():
    scripted_responses = [
        AIMessage(content="It will be sunny and 24°C in Kerala."),
        AIMessage(
            content="",
            tool_calls=[{
                "name": "get_weather",
                "args": {"location": "Kerala", "date": "September"},
                "id": "call_1",
                "type": "tool_call",
            }],
        ),
        AIMessage(content="Based on the forecast, expect 24°C and partly cloudy skies."),
    ]
    call_index = {"n": 0}

    def fake_invoke(_messages):
        response = scripted_responses[call_index["n"]]
        call_index["n"] += 1
        return response

    with patch("app.graph.nodes._get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = fake_invoke
        mock_get_llm.return_value = mock_llm

        graph = build_graph()
        config = {"configurable": {"thread_id": "test-full-loop"}}
        result = graph.invoke(
            {"messages": [HumanMessage(content="weather in Kerala?")], "user_id": "test"},
            config=config,
        )

        assert result["final_response"] == "Based on the forecast, expect 24°C and partly cloudy skies."
        assert result["validation_attempts"] == 1
        assert result["validation_errors"] == []  # clean on the retry

        # The message trace should show the full loop happened, not
        # just that we ended up with the right final_response.
        types = [type(m).__name__ for m in result["messages"]]
        assert types == [
            "HumanMessage",   # the user's question
            "AIMessage",      # first guess, no tool call
            "HumanMessage",   # validate_node's corrective nudge
            "AIMessage",      # now calling get_weather
            "ToolMessage",    # the tool's result
            "AIMessage",      # corrected final answer
        ]
        assert call_index["n"] == 3  # LLM was actually called three times
