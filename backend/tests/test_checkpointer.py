"""
Requires a real Postgres - skipped if DATABASE_URL isn't reachable.
Confirms build_postgres_checkpointer produces a working checkpointer
(not just that it doesn't raise), and that state genuinely persists
across two separate checkpointer instances pointed at the same
database - the actual point of Phase 3.
"""
import pytest
from langchain_core.messages import HumanMessage

from app.config import get_settings
from app.db.checkpointer import build_postgres_checkpointer
from app.graph.graph import build_graph

_settings = get_settings()

try:
    import psycopg
    _conn = psycopg.connect(_settings.database_url)
    _conn.close()
    _DB_AVAILABLE = True
except Exception:
    _DB_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not _DB_AVAILABLE,
    reason="No Postgres reachable at DATABASE_URL - run `docker compose up -d` first.",
)


def test_checkpointer_setup_is_idempotent():
    checkpointer1, pool1 = build_postgres_checkpointer(_settings.database_url)
    pool1.close()
    # Calling setup() again (a second app start against the same DB)
    # must not raise - this is exactly what happens every time uvicorn
    # restarts against an already-initialized database.
    checkpointer2, pool2 = build_postgres_checkpointer(_settings.database_url)
    pool2.close()


def test_state_survives_a_fresh_checkpointer_instance():
    """The actual point of Phase 3: build a graph, run one turn, throw
    away that checkpointer/pool entirely, build a brand new one against
    the same database, and confirm the conversation is still there -
    simulating what a server restart looks like."""
    from unittest.mock import MagicMock, patch
    from langchain_core.messages import AIMessage

    thread_id = "test-persistence-across-restart"
    config = {"configurable": {"thread_id": thread_id}}

    checkpointer1, pool1 = build_postgres_checkpointer(_settings.database_url)
    with patch("app.graph.nodes._get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = AIMessage(content="Sounds like a great trip!")
        mock_get_llm.return_value = mock_llm

        graph1 = build_graph(checkpointer=checkpointer1)
        graph1.invoke(
            {"messages": [HumanMessage(content="Plan a trip to Munnar")], "user_id": "test"},
            config=config,
        )
    pool1.close()  # simulate the server process ending entirely

    # Fresh checkpointer, fresh pool, fresh compiled graph - nothing
    # in memory is shared with the run above except the database.
    checkpointer2, pool2 = build_postgres_checkpointer(_settings.database_url)
    graph2 = build_graph(checkpointer=checkpointer2)
    snapshot = graph2.get_state(config)
    pool2.close()

    assert snapshot.values.get("final_response") == "Sounds like a great trip!"
    message_types = [type(m).__name__ for m in snapshot.values.get("messages", [])]
    assert "HumanMessage" in message_types
    assert "AIMessage" in message_types
