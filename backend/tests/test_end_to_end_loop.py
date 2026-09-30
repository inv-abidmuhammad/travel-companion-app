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

    with patch("app.graph.nodes.llm_with_tools") as mock_llm:
        mock_llm.invoke.side_effect = fake_invoke

        graph = build_graph()
        config = {"configurable": {"thread_id": "test-full-loop"}}
        result = graph.invoke(
            {"messages": [HumanMessage(content="weather in Kerala?")], "user_id": "test"},
            config=config,
        )

        assert result["final_response"] == "Based on the forecast, expect 24°C and partly cloudy skies."
        # respond_node resets per-turn validation bookkeeping once a
        # turn concludes cleanly — so the retry count itself isn't
        # visible in the final result. The message trace below is the
        # real proof that the loop happened.
        assert result["validation_attempts"] == 0
        assert result["validation_errors"] == []

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


def test_changing_duration_clears_weather_and_calls_weather_before_itinerary():
    """Simulate the user's flow:
    - User has destination, departure_date, duration_days, and existing weather.
    - User changes duration to 10 days.
    - Turn 1: agent calls record_trip_detail(duration_days=10), which invalidates weather_data.
    - Turn 2: agent calls get_weather before generating itinerary.
    - Turn 3: agent generates updated 10-day itinerary grounded in weather.
    """
    scripted_responses = [
        AIMessage(
            content="",
            tool_calls=[{
                "name": "record_trip_detail",
                "args": {"field": "duration_days", "value": 10},
                "id": "call_record",
                "type": "tool_call",
            }],
        ),
        AIMessage(
            content="",
            tool_calls=[{
                "name": "get_weather",
                "args": {"location": "China", "date": "2026-10-01"},
                "id": "call_weather",
                "type": "tool_call",
            }],
        ),
        AIMessage(
            content="Here is your updated 10-day itinerary for China:\nDay 1: Arrival in Beijing\nDay 2: Forbidden City\nDay 10: Departure",
        ),
    ]
    call_index = {"n": 0}

    def fake_invoke(_messages):
        response = scripted_responses[call_index["n"]]
        call_index["n"] += 1
        return response

    with patch("app.graph.nodes.llm_with_tools") as mock_llm:
        mock_llm.invoke.side_effect = fake_invoke

        graph = build_graph()
        config = {"configurable": {"thread_id": "test-duration-weather-itinerary"}}

        # Start with confirmed destination, departure_date, duration 7, and previous weather
        initial_state = {
            "messages": [HumanMessage(content="change my days duration to 10")],
            "destination": "China",
            "departure_date": "2026-10-01",
            "duration_days": 7,
            "weather_data": {"location": "China", "condition": "Old Forecast", "temp_c": 15},
            "user_id": "test_user",
        }
        result = graph.invoke(initial_state, config=config)

        assert result["duration_days"] == 10
        assert result["weather_data"] is not None
        assert "Day 1: Arrival in Beijing" in result["final_response"]
        assert call_index["n"] == 3


def test_changing_duration_with_missing_field_asks_for_field_without_calling_weather():
    """Simulate missing field flow:
    - User has destination and duration, but departure_date is missing.
    - User changes duration to 10 days.
    - Turn 1: agent calls record_trip_detail(duration_days=10).
    - Turn 2: agent asks for departure date instead of calling get_weather or generating itinerary.
    """
    scripted_responses = [
        AIMessage(
            content="",
            tool_calls=[{
                "name": "record_trip_detail",
                "args": {"field": "duration_days", "value": 10},
                "id": "call_record",
                "type": "tool_call",
            }],
        ),
        AIMessage(
            content="I've updated your trip to 10 days! When are you planning to go?",
        ),
    ]
    call_index = {"n": 0}

    def fake_invoke(_messages):
        response = scripted_responses[call_index["n"]]
        call_index["n"] += 1
        return response

    with patch("app.graph.nodes.llm_with_tools") as mock_llm:
        mock_llm.invoke.side_effect = fake_invoke

        graph = build_graph()
        config = {"configurable": {"thread_id": "test-duration-missing-fields"}}

        initial_state = {
            "messages": [HumanMessage(content="change my days duration to 10")],
            "destination": "China",
            "departure_date": None,
            "duration_days": 7,
            "weather_data": None,
            "user_id": "test_user",
        }
        result = graph.invoke(initial_state, config=config)

        assert result["duration_days"] == 10
        assert result["weather_data"] is None
        assert "When are you planning to go?" in result["final_response"]
        assert call_index["n"] == 2

