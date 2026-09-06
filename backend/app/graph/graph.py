"""
Graph assembly.

    START -> agent --(tool_calls present)--> tools -> agent   (loop)
             agent --(none)-----------------> validate
    validate --(unverified claims, retries left)--> agent      (loop)
             --(retries exhausted, still unresolved)--> human_input
             --(clean)---------------------------------> respond -> END
    human_input --(person says "retry")--> agent
                --(otherwise)------------> respond -> END

Routing is done by plain functions in nodes.py — no prebuilt
`tools_condition`. `tools` (tools_node), `validate` (validate_node),
and `human_input` (human_input_node) are all hand written too. See
nodes.py for what each one actually does; this file is purely the
wiring diagram.

`human_input` is the edge the original blueprint's graph was missing:
its router could reach human_input, but validation had no path there
at all — a person only ever got looped in for missing info the router
already knew was missing, never for something validation caught
downstream. Here, validate's automatic retries handle the common
case, and a person only gets interrupted when those retries fail.
"""
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from app.graph.nodes import (
    agent_node,
    human_input_node,
    respond_node,
    route_after_agent,
    route_after_human_input,
    route_after_validate,
    tools_node,
    validate_node,
)
from app.graph.state import AdventureState


def build_graph():
    graph = StateGraph(AdventureState)

    graph.add_node("agent", agent_node)
    graph.add_node("tools", tools_node)
    graph.add_node("validate", validate_node)
    graph.add_node("human_input", human_input_node)
    graph.add_node("respond", respond_node)

    graph.set_entry_point("agent")

    graph.add_conditional_edges(
        "agent",
        route_after_agent,
        {"tools": "tools", "done": "validate"},
    )
    graph.add_edge("tools", "agent")

    graph.add_conditional_edges(
        "validate",
        route_after_validate,
        {"agent": "agent", "human_input": "human_input", "respond": "respond"},
    )

    graph.add_conditional_edges(
        "human_input",
        route_after_human_input,
        {"agent": "agent", "respond": "respond"},
    )

    graph.add_edge("respond", END)

    # MemorySaver keeps conversation state in-process, keyed by thread_id.
    # A checkpointer isn't optional here the way it was in Phase 1 —
    # interrupt() requires one to persist state across the pause, even
    # within a single process. Swap for Postgres in Phase 3.
    checkpointer = MemorySaver()
    return graph.compile(checkpointer=checkpointer)


# Compiled once at import time; reused across requests.
adventure_graph = build_graph()
