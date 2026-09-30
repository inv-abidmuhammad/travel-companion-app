from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.graph.nodes import MAX_VALIDATION_RETRIES, route_after_validate, validate_node


def test_passes_clean_response_with_no_claims():
    state = {"messages": [AIMessage(content="What dates were you thinking?")]}
    result = validate_node(state)
    assert result["validation_errors"] == []
    assert result["needs_revision"] is False


def test_passes_weather_claim_when_get_weather_was_called():
    state = {
        "messages": [
            ToolMessage(content="...", tool_call_id="c1", name="get_weather"),
            AIMessage(content="Expect 22°C and light rain in Munnar."),
        ]
    }
    result = validate_node(state)
    assert result["validation_errors"] == []
    assert result["needs_revision"] is False


def test_flags_weather_claim_without_a_tool_call():
    state = {"messages": [AIMessage(content="It'll be a sunny 24°C in Munnar.")]}
    result = validate_node(state)
    assert result["needs_revision"] is True
    assert any("get_weather" in e for e in result["validation_errors"])
    # A corrective nudge should have been appended for the agent to see.
    assert any(isinstance(m, HumanMessage) for m in result["messages"])


def test_flags_budget_claim_without_a_tool_call():
    state = {"messages": [AIMessage(content="Your per-day budget is ₹6,250.")]}
    result = validate_node(state)
    assert result["needs_revision"] is True
    assert any("calculator" in e for e in result["validation_errors"])


def test_stops_retrying_once_max_attempts_reached():
    state = {
        "messages": [AIMessage(content="It'll be 24°C and sunny.")],
        "validation_attempts": MAX_VALIDATION_RETRIES,
    }
    result = validate_node(state)
    # Still flags the problem for visibility...
    assert result["validation_errors"] != []
    # ...but gives up looping rather than retrying forever.
    assert result["needs_revision"] is False


def test_route_after_validate_reads_the_flags_directly():
    assert route_after_validate({"needs_revision": True}) == "agent"
    assert route_after_validate({"needs_revision": False, "validation_errors": ["x"]}) == "human_input"
    assert route_after_validate({"needs_revision": False, "validation_errors": []}) == "respond"
    assert route_after_validate({}) == "respond"


def test_flags_itinerary_when_weather_null_and_all_fields_set():
    state = {
        "destination": "China",
        "departure_date": "2026-10-01",
        "duration_days": 10,
        "weather_data": None,
        "messages": [
            HumanMessage(content="change days to 10"),
            AIMessage(content="Here is your 10-day itinerary:\nDay 1: Arrival in Beijing\nDay 2: Forbidden City"),
        ],
    }
    result = validate_node(state)
    assert result["needs_revision"] is True
    assert any("weather_data is null" in e for e in result["validation_errors"])
    assert any(isinstance(m, HumanMessage) for m in result["messages"])


def test_passes_itinerary_when_weather_data_is_present():
    state = {
        "destination": "China",
        "departure_date": "2026-10-01",
        "duration_days": 10,
        "weather_data": {"condition": "Sunny", "temp_c": 20},
        "messages": [
            HumanMessage(content="Plan my trip"),
            ToolMessage(content="Sunny 20C", tool_call_id="c1", name="get_weather"),
            AIMessage(content="Here is your 10-day itinerary:\nDay 1: Arrival in Beijing\nDay 2: Forbidden City"),
        ],
    }
    result = validate_node(state)
    assert result["needs_revision"] is False
    assert result["validation_errors"] == []


def test_flags_itinerary_when_required_fields_missing():
    state = {
        "destination": "China",
        "departure_date": None,
        "duration_days": 10,
        "weather_data": None,
        "messages": [
            HumanMessage(content="change days to 10"),
            AIMessage(content="Here is your 10-day itinerary:\nDay 1: Arrival in Beijing\nDay 2: Forbidden City"),
        ],
    }
    result = validate_node(state)
    assert result["needs_revision"] is True
    assert any("before required trip details" in e for e in result["validation_errors"])


def test_flags_weather_not_called_when_field_modified_this_turn():
    state = {
        "destination": "China",
        "departure_date": "2026-10-01",
        "duration_days": 10,
        "weather_data": None,
        "messages": [
            HumanMessage(content="change days to 10"),
            AIMessage(
                content="",
                tool_calls=[{"name": "record_trip_detail", "args": {"field": "duration_days", "value": 10}, "id": "c1"}],
            ),
            ToolMessage(content="{'field': 'duration_days', 'value': 10}", tool_call_id="c1", name="record_trip_detail"),
            AIMessage(content="I've updated your trip to 10 days! Let me know what you want to do."),
        ],
    }
    result = validate_node(state)
    assert result["needs_revision"] is True
    assert any("get_weather was not called" in e for e in result["validation_errors"])


def test_passes_when_missing_field_and_agent_asks_for_it():
    state = {
        "destination": "China",
        "departure_date": None,
        "duration_days": 10,
        "weather_data": None,
        "messages": [
            HumanMessage(content="change days to 10"),
            AIMessage(
                content="",
                tool_calls=[{"name": "record_trip_detail", "args": {"field": "duration_days", "value": 10}, "id": "c1"}],
            ),
            ToolMessage(content="{'field': 'duration_days', 'value': 10}", tool_call_id="c1", name="record_trip_detail"),
            AIMessage(content="I've updated your trip to 10 days! When are you planning to depart?"),
        ],
    }
    result = validate_node(state)
    assert result["needs_revision"] is False
    assert result["validation_errors"] == []

