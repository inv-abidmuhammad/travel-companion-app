"""
Plain functions over a Session — no repository classes, no ORM magic
beyond what SQLAlchemy itself gives you. Each function does exactly
one thing so it's easy to test and easy to call from an endpoint or
(later) from a graph node.
"""
from sqlalchemy.orm import Session

from app.db.models import Trip, User


def get_or_create_user(db: Session, user_id: str) -> User:
    user = db.get(User, user_id)
    if user is None:
        user = User(id=user_id)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def create_trip(
    db: Session,
    user_id: str,
    thread_id: str,
    origin: str | None = None,
    destination: str | None = None,
    budget: float | None = None,
    duration_days: int | None = None,
) -> Trip:
    get_or_create_user(db, user_id)  # ensure the FK target exists
    trip = Trip(
        user_id=user_id,
        thread_id=thread_id,
        origin=origin,
        destination=destination,
        budget=budget,
        duration_days=duration_days,
    )
    db.add(trip)
    db.commit()
    db.refresh(trip)
    return trip


def get_trip(db: Session, trip_id: str) -> Trip | None:
    return db.get(Trip, trip_id)


def list_trips_for_user(db: Session, user_id: str) -> list[Trip]:
    return list(
        db.query(Trip).filter(Trip.user_id == user_id).order_by(Trip.created_at.desc())
    )


def update_trip(db: Session, trip_id: str, **fields) -> Trip | None:
    trip = db.get(Trip, trip_id)
    if trip is None:
        return None
    for key, value in fields.items():
        setattr(trip, key, value)
    db.commit()
    db.refresh(trip)
    return trip
