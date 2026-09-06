"""
Builds a Postgres-backed checkpointer for LangGraph, replacing
MemorySaver so conversation state survives a server restart.

Two things worth knowing, both confirmed against a real Postgres
instance rather than assumed from docs:

1. PostgresSaver.from_conn_string(...) is a context manager — it's
   meant for short-lived scripts, not something you can hold open for
   an app's entire lifetime. Passing a psycopg_pool.ConnectionPool
   directly to PostgresSaver(pool) instead works fine with no context
   manager needed, which is what a long-running FastAPI app wants.

2. This pool wants the BARE psycopg-style DSN
   ("postgresql://user:pass@host:port/db") — no "+psycopg" dialect
   suffix. Giving it a SQLAlchemy-style URL fails with a connection
   string parse error. SQLAlchemy, conversely, needs that suffix to
   pick psycopg3 over psycopg2. See Settings.sqlalchemy_database_url
   in config.py for where that split is handled.
"""
from psycopg_pool import ConnectionPool
from langgraph.checkpoint.postgres import PostgresSaver


def build_postgres_checkpointer(conn_string: str) -> tuple[PostgresSaver, ConnectionPool]:
    """Returns (checkpointer, pool). Hold onto the pool and call
    pool.close() on app shutdown — see the lifespan handler in
    main.py."""
    pool = ConnectionPool(conn_string, max_size=10, kwargs={"autocommit": True}, open=True)
    checkpointer = PostgresSaver(pool)
    checkpointer.setup()  # idempotent — creates tables only if missing
    return checkpointer, pool
