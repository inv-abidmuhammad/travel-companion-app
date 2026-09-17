"""
These require a real Postgres - the whole module is skipped if
DATABASE_URL isn't reachable (e.g. `docker compose up -d` hasn't been
run yet), so `pytest` still works out of the box for anyone who
hasn't set up the database.

Each test runs inside a savepoint that's rolled back afterward, so
running this file never leaves rows behind in your dev database -
even though crud.py itself calls session.commit() internally.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session as SASession

from app.config import get_settings
from app.db import crud
from app.db.models import Base

_settings = get_settings()

try:
    _test_engine = create_engine(_settings.sqlalchemy_database_url)
    with _test_engine.connect():
        pass
    _DB_AVAILABLE = True
except Exception:
    _DB_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not _DB_AVAILABLE,
    reason="No Postgres reachable at DATABASE_URL - run `docker compose up -d` first.",
)


@pytest.fixture
def db_session():
    Base.metadata.create_all(bind=_test_engine)
    connection = _test_engine.connect()
    transaction = connection.begin()
    # join_transaction_mode="create_savepoint" means crud.py's internal
    # session.commit() calls only commit a SAVEPOINT, not the real
    # transaction - so the outer transaction.rollback() below discards
    # everything this test did, regardless of how many commits happened.
    session = SASession(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


def test_get_or_create_user_is_idempotent(db_session):
    user1 = crud.get_or_create_user(db_session, "user-abc")
    user2 = crud.get_or_create_user(db_session, "user-abc")
    assert user1.id == user2.id == "user-abc"


def test_create_and_get_trip(db_session):
    trip = crud.create_trip(
        db_session, user_id="u1", thread_id="t1",
        origin="Kochi", budget=25000, duration_days=4,
    )
    fetched = crud.get_trip(db_session, trip.id)
    assert fetched is not None
    assert fetched.origin == "Kochi"
    assert fetched.budget == 25000
    assert fetched.status == "draft"  # default


def test_get_trip_returns_none_for_unknown_id(db_session):
    assert crud.get_trip(db_session, "does-not-exist") is None


def test_list_trips_for_user_orders_newest_first(db_session):
    older = crud.create_trip(db_session, user_id="u2", thread_id="t2a")
    newer = crud.create_trip(db_session, user_id="u2", thread_id="t2b")
    trips = crud.list_trips_for_user(db_session, "u2")
    assert [t.id for t in trips] == [newer.id, older.id]


def test_list_trips_for_user_is_scoped_to_that_user(db_session):
    crud.create_trip(db_session, user_id="u3", thread_id="t3")
    crud.create_trip(db_session, user_id="u4", thread_id="t4")
    trips_for_u3 = crud.list_trips_for_user(db_session, "u3")
    assert len(trips_for_u3) == 1
    assert trips_for_u3[0].user_id == "u3"


def test_update_trip_changes_only_given_fields(db_session):
    trip = crud.create_trip(db_session, user_id="u5", thread_id="t5", budget=25000)
    updated = crud.update_trip(db_session, trip.id, budget=15000, status="confirmed")
    assert updated.budget == 15000
    assert updated.status == "confirmed"
    assert updated.thread_id == "t5"  # untouched field preserved


def test_update_trip_returns_none_for_unknown_id(db_session):
    assert crud.update_trip(db_session, "does-not-exist", budget=1) is None


def test_get_trip_by_thread_id_returns_matching_trip(db_session):
    trip = crud.create_trip(db_session, user_id="u6", thread_id="thread-abc")
    found = crud.get_trip_by_thread_id(db_session, "thread-abc")
    assert found is not None
    assert found.id == trip.id


def test_get_trip_by_thread_id_returns_none_for_unknown_thread(db_session):
    assert crud.get_trip_by_thread_id(db_session, "no-such-thread") is None
