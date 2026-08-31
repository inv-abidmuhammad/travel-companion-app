"""
Structural tests: verify the graph is wired the way the diagram says,
without needing a live ANTHROPIC_API_KEY. Once you're past Phase 1,
add a happy-path test that mocks agent_node's LLM call to return a
canned AIMessage and asserts the full run reaches `respond`.
"""
from app.graph.graph import build_graph


def test_graph_compiles():
    graph = build_graph()
    assert graph is not None


def test_graph_has_expected_nodes():
    graph = build_graph()
    node_names = set(graph.get_graph().nodes.keys())
    assert {"agent", "tools", "respond"}.issubset(node_names)


def test_tool_node_routes_from_agent():
    graph = build_graph()
    edges = graph.get_graph().edges
    sources_from_agent = {e.source for e in edges if e.target == "tools"}
    assert "agent" in sources_from_agent
    sources_from_tools = {e.target for e in edges if e.source == "tools"}
    assert "agent" in sources_from_tools
