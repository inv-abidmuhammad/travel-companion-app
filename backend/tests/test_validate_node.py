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


def test_route_after_validate_reads_the_flag_directly():
    assert route_after_validate({"needs_revision": True}) == "agent"
    assert route_after_validate({"needs_revision": False}) == "respond"
    assert route_after_validate({}) == "respond"
