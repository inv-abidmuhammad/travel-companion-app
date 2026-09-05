"""
Structural tests: verify the graph is wired the way the diagram says,
without needing a live GOOGLE_API_KEY.
"""
from app.graph.graph import build_graph


def test_graph_compiles():
    graph = build_graph()
    assert graph is not None


def test_graph_has_expected_nodes():
    graph = build_graph()
    node_names = set(graph.get_graph().nodes.keys())
    assert {"agent", "tools", "validate", "respond"}.issubset(node_names)


def test_tool_node_routes_from_agent():
    graph = build_graph()
    edges = graph.get_graph().edges
    sources_from_agent = {e.source for e in edges if e.target == "tools"}
    assert "agent" in sources_from_agent
    sources_from_tools = {e.target for e in edges if e.source == "tools"}
    assert "agent" in sources_from_tools


def test_agent_routes_to_validate_not_directly_to_respond():
    graph = build_graph()
    edges = graph.get_graph().edges
    targets_from_agent = {e.target for e in edges if e.source == "agent"}
    assert "validate" in targets_from_agent
    assert "respond" not in targets_from_agent


def test_validate_can_loop_back_to_agent_and_can_reach_respond():
    graph = build_graph()
    edges = graph.get_graph().edges
    targets_from_validate = {e.target for e in edges if e.source == "validate"}
    assert "agent" in targets_from_validate
    assert "respond" in targets_from_validate
