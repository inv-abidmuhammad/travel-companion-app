"""
Graph assembly.

    START -> check_stale_details -> agent --(tool_calls present)--> tools -> agent   (loop)
                                     agent --(none)-----------------> validate
    validate --(unverified claims, retries left)--> agent      (loop)
             --(retries exhausted, still unresolved)--> human_input
             --(clean)---------------------------------> respond -> END
    human_input --(person says "retry")--> agent
                --(otherwise)------------> respond -> END

check_stale_details is the entry point rather than agent directly so
it runs once on every genuinely fresh turn — a stored departure_date
that's since slipped into the past gets cleared before the agent ever
sees it. Command(resume=...), used to answer an interrupt(), re-enters
the graph exactly where human_input_node paused, not through the entry
point — so interrupt resumes correctly skip this check; it only fires
on a new incoming HumanMessage.

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

`build_graph` takes an optional checkpointer so this module stays
DB-agnostic and testable without a running Postgres — tests (and the
default `adventure_graph` below) get an in-process MemorySaver. The
actual running app builds its own Postgres-backed checkpointer in
main.py and passes it in instead, so real conversations survive a
server restart.
"""
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from .nodes import (
    agent_node,
    check_stale_details_node,
    human_input_node,
    respond_node,
    route_after_agent,
    route_after_human_input,
    route_after_validate,
    tools_node,
    validate_node,
)
from .state import AdventureState


def build_graph(checkpointer: BaseCheckpointSaver | None = None):
    graph = StateGraph(AdventureState)

    graph.add_node("check_stale_details", check_stale_details_node)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tools_node)
    graph.add_node("validate", validate_node)
    graph.add_node("human_input", human_input_node)
    graph.add_node("respond", respond_node)

    graph.set_entry_point("check_stale_details")
    graph.add_edge("check_stale_details", "agent")

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

    if checkpointer is None:
        # In-process only — fine for tests and quick scripts, but
        # state disappears on restart. The real app never hits this
        # branch; see adventure_graph construction in main.py.
        checkpointer = MemorySaver()
    return graph.compile(checkpointer=checkpointer)


# Default, in-memory instance — used by tests and anything that just
# needs a working graph without setting up a database. The FastAPI
# app builds its own Postgres-backed instance instead (see main.py).
adventure_graph = build_graph()