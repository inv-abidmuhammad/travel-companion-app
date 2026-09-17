"""
End-to-end proof of the interrupt()-based human_input path: validate
exhausts its automatic retries (agent keeps making an unverified claim
without calling the tool), the graph genuinely pauses, and a
Command(resume=...) call picks execution back up — either accepting
the answer with a caveat ("proceed") or giving the agent a fresh shot
("retry").
"""
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.types import Command

from app.graph.graph import build_graph
from app.graph.nodes import MAX_VALIDATION_RETRIES


def _bad_weather_claim() -> AIMessage:
    return AIMessage(content="It'll be sunny and 24°C, no need to check.")


def test_proceed_after_exhausting_retries_returns_answer_with_caveat():
    # MAX_VALIDATION_RETRIES + 1 identical bad guesses before the
    # graph gives up looping automatically and asks a human.
    scripted = [_bad_weather_claim() for _ in range(MAX_VALIDATION_RETRIES + 1)]
    call_index = {"n": 0}

    def fake_invoke(_messages):
        response = scripted[call_index["n"]]
        call_index["n"] += 1
        return response

    with patch("app.graph.nodes.llm_with_tools") as mock_llm:
        mock_llm.invoke.side_effect = fake_invoke

        graph = build_graph()
        config = {"configurable": {"thread_id": "test-proceed"}}

        first = graph.invoke(
            {"messages": [HumanMessage(content="weather in Kerala?")], "user_id": "test"},
            config=config,
        )
        # Graph genuinely paused — did not run to completion.
        assert "__interrupt__" in first
        question = first["__interrupt__"][0].value["question"]
        assert "couldn't automatically verify" in question

        snapshot = graph.get_state(config)
        assert snapshot.next == ("human_input",)

        second = graph.invoke(Command(resume="proceed"), config=config)
        assert "__interrupt__" not in second
        assert "24°C" in second["final_response"]
        # The caveat should be visible in the final answer.
        assert "wasn't independently verified" in second["final_response"]
        # And bookkeeping should be clean for the next turn.
        assert second["validation_attempts"] == 0
        assert second["validation_errors"] == []


def test_retry_after_exhausting_retries_gives_the_agent_another_shot():
    scripted = [
        *[_bad_weather_claim() for _ in range(MAX_VALIDATION_RETRIES + 1)],
        # After "retry", the agent finally calls the tool...
        AIMessage(
            content="",
            tool_calls=[{
                "name": "get_weather",
                "args": {"location": "Kerala", "date": "September"},
                "id": "call_1",
                "type": "tool_call",
            }],
        ),
        # ...and gives a clean, tool-backed final answer.
        AIMessage(content="Based on the forecast, expect 24°C and partly cloudy skies."),
    ]
    call_index = {"n": 0}

    def fake_invoke(_messages):
        response = scripted[call_index["n"]]
        call_index["n"] += 1
        return response

    with patch("app.graph.nodes.llm_with_tools") as mock_llm:
        mock_llm.invoke.side_effect = fake_invoke

        graph = build_graph()
        config = {"configurable": {"thread_id": "test-retry"}}

        first = graph.invoke(
            {"messages": [HumanMessage(content="weather in Kerala?")], "user_id": "test"},
            config=config,
        )
        assert "__interrupt__" in first

        second = graph.invoke(Command(resume="retry"), config=config)
        assert "__interrupt__" not in second
        assert second["final_response"] == "Based on the forecast, expect 24°C and partly cloudy skies."
        # Clean pass this time — no caveat needed.
        assert "wasn't independently verified" not in second["final_response"]
        assert call_index["n"] == len(scripted)  # every scripted response was consumed
