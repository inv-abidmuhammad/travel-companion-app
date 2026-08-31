"""
These test tools_node and route_after_agent directly, by handing them
a fake AIMessage with tool_calls already attached — as if the LLM had
just responded. No live API call needed, and it proves the manual
replacements for ToolNode/tools_condition behave the same way.
"""
from langchain_core.messages import AIMessage, ToolMessage

from app.graph.nodes import route_after_agent, tools_node


def _ai_message_with_tool_call(name: str, args: dict, call_id: str = "call_1") -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[{"name": name, "args": args, "id": call_id, "type": "tool_call"}],
    )


def test_route_after_agent_goes_to_tools_when_tool_calls_present():
    state = {"messages": [_ai_message_with_tool_call("calculator", {"expression": "1+1"})]}
    assert route_after_agent(state) == "tools"


def test_route_after_agent_goes_to_done_when_no_tool_calls():
    state = {"messages": [AIMessage(content="Here's your itinerary.")]}
    assert route_after_agent(state) == "done"


def test_tools_node_runs_the_matching_tool_and_tags_the_call_id():
    state = {
        "messages": [_ai_message_with_tool_call("calculator", {"expression": "25000/4"}, "call_42")]
    }
    result = tools_node(state)
    messages = result["messages"]
    assert len(messages) == 1
    assert isinstance(messages[0], ToolMessage)
    assert messages[0].tool_call_id == "call_42"
    assert "6250" in messages[0].content


def test_tools_node_reports_unknown_tool_without_raising():
    state = {"messages": [_ai_message_with_tool_call("not_a_real_tool", {}, "call_99")]}
    result = tools_node(state)
    messages = result["messages"]
    assert len(messages) == 1
    assert "not_a_real_tool" in messages[0].content
    assert messages[0].tool_call_id == "call_99"


def test_tools_node_handles_multiple_tool_calls_in_one_turn():
    """Now that there are two tools, the agent can plausibly ask for
    both at once (e.g. budget math AND weather for the same message).
    tools_node must run each and tag each result with its own id."""
    last_message = AIMessage(
        content="",
        tool_calls=[
            {"name": "calculator", "args": {"expression": "25000/4"}, "id": "call_a", "type": "tool_call"},
            {"name": "get_weather", "args": {"location": "Munnar", "date": "day 2"}, "id": "call_b", "type": "tool_call"},
        ],
    )
    result = tools_node({"messages": [last_message]})
    messages = result["messages"]
    assert len(messages) == 2
    by_id = {m.tool_call_id: m for m in messages}
    assert "6250" in by_id["call_a"].content
    assert "Munnar" in by_id["call_b"].content
