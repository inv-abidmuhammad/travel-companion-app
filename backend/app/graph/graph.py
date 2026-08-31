"""
Graph assembly.

    START -> agent --(tool_calls present)--> tools -> agent (loop)
             agent --(no tool_calls)-------> respond -> END

Routing is done by `route_after_agent`, a plain function in nodes.py —
no prebuilt `tools_condition`. `tools` is `tools_node`, also hand
written — no prebuilt `ToolNode`. See nodes.py for what each one
actually does; this file is purely the wiring diagram.

Phase 2 adds: a `validate` node between the loop exit and `respond`,
and a `human_input` node reached via `interrupt()` when the agent
flags missing essential constraints.
"""
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from app.graph.nodes import agent_node, respond_node, route_after_agent, tools_node
from app.graph.state import AdventureState


def build_graph():
    graph = StateGraph(AdventureState)

    graph.add_node("agent", agent_node)
    graph.add_node("tools", tools_node)
    graph.add_node("respond", respond_node)

    graph.set_entry_point("agent")

    graph.add_conditional_edges(
        "agent",
        route_after_agent,
        {"tools": "tools", "respond": "respond"},
    )
    graph.add_edge("tools", "agent")
    graph.add_edge("respond", END)

    # MemorySaver keeps conversation state in-process, keyed by thread_id.
    # Swap for a Postgres-backed checkpointer in Phase 3.
    checkpointer = MemorySaver()
    return graph.compile(checkpointer=checkpointer)


# Compiled once at import time; reused across requests.
adventure_graph = build_graph()
