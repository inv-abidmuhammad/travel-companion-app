"""
FastAPI entrypoint.

    uvicorn app.main:app --reload

Endpoints:
  GET  /health                    liveness check
  POST /chat                       send one message, get the agent's reply
  GET  /debug/state/{id}           inspect a conversation's raw graph state
  POST /trips                      create a durable trip record
  GET  /trips/{trip_id}            fetch one trip
  GET  /users/{user_id}/trips      list a user's trips
  GET  /trips/{trip_id}/resume     trip metadata + its conversation state

`thread_id` is the conversation id LangGraph's checkpointer uses to
resume state between calls. As of Phase 3, that checkpointer is
Postgres-backed (see app/db/checkpointer.py) - conversations survive
a server restart, unlike Phase 1/2's in-process MemorySaver.

`Trip` rows (app/db/models.py) are separate, durable business data -
budget, origin, destination, status - linked to a conversation only
by `thread_id`. The checkpointer owns "what was said"; the database
owns "what trip this is." /trips/{trip_id}/resume is the join point:
given a trip, load its conversation state to continue chatting.
"""
from contextlib import asynccontextmanager
import uuid

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import HumanMessage, ToolMessage
from langgraph.types import Command
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import crud
from app.db.checkpointer import build_postgres_checkpointer
from app.db.session import get_db, init_db
from app.graph.graph import build_graph
from app.graph.utils import get_user_facing_messages, normalize_message
from app.graph.extraction import extract_trip_from_conversation

from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.trips import TripCreate, TripUpdate, TripOut



@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run startup I/O only when the server actually boots — not at import
    time — so tests that import from main.py don't require a live database."""
    _settings = get_settings()
    init_db()  # create users/trips tables if they don't exist yet
    checkpointer, pool = build_postgres_checkpointer(_settings.database_url)
    app.state.graph = build_graph(checkpointer=checkpointer)
    yield
    pool.close()  # release Postgres connections cleanly on shutdown


app = FastAPI(title="AI Adventure Companion", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_adventure_graph(request: Request):
    """FastAPI dependency: injects the compiled LangGraph instance that was
    built during lifespan startup. Endpoints that need the graph declare
    `graph = Depends(get_adventure_graph)` instead of reaching for a global."""
    return request.app.state.graph


@app.get("/health")
def health() -> dict:
    """Liveness check endpoint. Returns 200 OK if the server is running."""
    return {"status": "ok"}



# Trip fields that also live in graph state (see AdventureState) and can be
# carried over when a conversation is resumed on a fresh graph checkpoint.
_RESUMABLE_TRIP_FIELDS = (
    "origin", "destination", "departure_date", "duration_days", "budget", "itinerary_text",
)

# The subset of the above that record_trip_detail actually writes into
# graph state with real validation — these are read straight from state
# on sync rather than re-derived from prose. itinerary_text is excluded:
# nothing writes it into state, so it's still sourced from the
# conversation itself (see extraction.py).
_STATE_SOURCED_TRIP_FIELDS = tuple(f for f in _RESUMABLE_TRIP_FIELDS if f != "itinerary_text")


def _backfill_state_from_trip(graph, config: dict, state_values: dict, trip) -> None:
    """Fill gaps in graph state from the trip row — never overwrite.

    Only ever writes a field that is currently unset in graph state, so
    this is safe to call on every turn: it can't clobber a value the
    agent set this session but that hasn't been PATCHed back to the
    trip row yet, and it's what makes resuming an older conversation
    (or one that predates these state fields existing at all) not lose
    already-known trip details.
    """
    updates = {
        field: getattr(trip, field)
        for field in _RESUMABLE_TRIP_FIELDS
        if state_values.get(field) is None and getattr(trip, field, None) is not None
    }
    if updates:
        graph.update_state(config, updates)


def _sync_trip_row_from_state(graph, config: dict, db: Session, trip_id: str) -> None:
    """Helper to auto-persist known trip fields from graph state into the durable database row."""
    try:
        snap = graph.get_state(config)
        vals = snap.values
        fields = {
            field: vals[field]
            for field in _STATE_SOURCED_TRIP_FIELDS
            if vals.get(field) is not None
        }
        messages = vals.get("messages", [])
        try:
            extracted = extract_trip_from_conversation(messages)
            if extracted.itinerary_text is not None:
                fields["itinerary_text"] = extracted.itinerary_text
        except Exception:
            pass
        if fields:
            crud.update_trip(db, trip_id, **fields)
    except Exception:
        pass


@app.post("/chat", response_model=ChatResponse)
def chat(
    req: ChatRequest,
    graph=Depends(get_adventure_graph),
    db: Session = Depends(get_db),
) -> ChatResponse:
    """One endpoint handles both starting a new turn and answering a
    pending interrupt() question, based on whether the graph is
    currently paused for this thread_id.

    A trip row is created automatically on the first message for a
    thread_id — the client never needs to call POST /trips separately.
    The trip_id is returned in every response so the client can call
    PATCH /trips/{trip_id}?sync_from_conversation=true at any time.
    """
    trip = None
    if req.trip_id:
        trip = crud.get_trip(db, req.trip_id)
        if trip:
            req.thread_id = trip.thread_id

    if req.thread_id is None or req.thread_id.strip() == "":
        req.thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": req.thread_id}}
    snapshot = graph.get_state(config)

    if trip is None:
        trip = crud.get_trip_by_thread_id(db, req.thread_id)
    if trip is None:
        trip = crud.create_trip(db, user_id=req.user_id, thread_id=req.thread_id)
    else:
        _backfill_state_from_trip(graph, config, snapshot.values, trip)

    if snapshot.next:
        result = graph.invoke(Command(resume=req.message), config=config)
    else:
        result = graph.invoke(
            {"messages": [HumanMessage(content=req.message)], "user_id": req.user_id},
            config=config,
        )

    _sync_trip_row_from_state(graph, config, db, trip.trip_id)

    if "__interrupt__" in result:
        question = result["__interrupt__"][0].value.get("question", "Please respond.")
        return ChatResponse(
            reply=question,
            thread_id=req.thread_id,
            trip_id=trip.trip_id,
            awaiting_confirmation=True,
        )

    return ChatResponse(
        reply=result["final_response"],
        thread_id=req.thread_id,
        trip_id=trip.trip_id,
    )



@app.get("/debug/state/{thread_id}")
def debug_state(thread_id: str, graph=Depends(get_adventure_graph)) -> dict:
    """Inspect a conversation's raw graph state. Now reads from
    Postgres - try this, restart uvicorn, and call it again with the
    same thread_id to see the state survive the restart."""
    config = {"configurable": {"thread_id": thread_id}}
    snapshot = graph.get_state(config)
    values = snapshot.values
    return {
        "message_count": len(values.get("messages", [])),
        "message_types": [type(m).__name__ for m in values.get("messages", [])],
        "validation_attempts": values.get("validation_attempts", 0),
        "validation_errors": values.get("validation_errors", []),
        "paused_at": list(snapshot.next),
        "origin": values.get("origin"),
        "destination": values.get("destination"),
        "departure_date": values.get("deaparture_date"),
        "duration_days": values.get("duration_days"),
        "budget": values.get("budget"),
        "weather_data": values.get("weather_data", {}),
        "departure_date": values.get("departure_date")
    }


@app.post("/trips", response_model=TripOut)
def create_trip(payload: TripCreate, db: Session = Depends(get_db)) -> TripOut:
    """Create a new trip row in the database. Returns the trip's durable id and trip details.
    If the client doesn't provide a thread_id, one is generated automatically."""
    if payload.thread_id is None or payload.thread_id.strip() == "":
        # If the client didn't provide a thread_id, generate one for them.
        # This is the common case: a new trip starts a new conversation.
        payload.thread_id = str(uuid.uuid4())
    trip = crud.create_trip(
        db,
        user_id=payload.user_id,
        thread_id=payload.thread_id,
        origin=payload.origin,
        destination=payload.destination,
        departure_date=payload.departure_date,
        budget=payload.budget,
        duration_days=payload.duration_days,
    )
    return TripOut.model_validate(trip)


@app.get("/trips/{trip_id}", response_model=TripOut)
def get_trip(trip_id: str, db: Session = Depends(get_db)) -> TripOut:
    """Fetch a trip row by its durable id. Returns 404 if not found."""
    trip = crud.get_trip(db, trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail="Trip not found")
    return TripOut.model_validate(trip)


@app.patch("/trips/{trip_id}", response_model=TripOut)
def patch_trip(
    trip_id: str,
    payload: TripUpdate,
    sync_from_conversation: bool = Query(
        False,
        description=(
            "When true, ignores the request body and instead reads the trip's "
            "conversation thread to extract update fields automatically."
        ),
    ),
    db: Session = Depends(get_db),
    graph=Depends(get_adventure_graph),
) -> TripOut:
    """Update a trip row by its durable id, syncing via conversation
    or by manual update. Returns 404 if not found."""
    if sync_from_conversation:
        trip = crud.get_trip(db, trip_id)
        if trip is None:
            raise HTTPException(status_code=404, detail="Trip not found")
        config = {"configurable": {"thread_id": trip.thread_id}}
        snapshot = graph.get_state(config)
        values = snapshot.values

        # origin/destination/departure_date/duration_days/budget are
        # ground truth the moment record_trip_detail validates and
        # writes them — read straight from graph state instead of
        # re-deriving them from prose, which can only lose information
        # (e.g. a date the agent resolved internally but only ever
        # paraphrased back to the user, like "mid-October").
        fields = {
            field: values[field]
            for field in _STATE_SOURCED_TRIP_FIELDS
            if values.get(field) is not None
        }

        # itinerary_text has no dedicated tool/state slot, so it's the
        # one field that still has to come from the conversation itself.
        messages = values.get("messages", [])
        extracted = extract_trip_from_conversation(messages)
        if extracted.itinerary_text is not None:
            fields["itinerary_text"] = extracted.itinerary_text
    else:
        fields = {k: v for k, v in payload.model_dump().items() if v is not None}

    trip = crud.update_trip(db, trip_id, **fields)
    if trip is None:
        raise HTTPException(status_code=404, detail="Trip not found")
    return TripOut.model_validate(trip)


@app.get("/users/{user_id}/trips", response_model=list[TripOut])
def list_trips(user_id: str, db: Session = Depends(get_db), graph=Depends(get_adventure_graph)) -> list[TripOut]:
    """List all trips for a given user_id. Returns an empty list if none found."""
    trips = crud.list_trips_for_user(db, user_id)
    for t in trips:
        if t.destination is None and t.thread_id:
            try:
                config = {"configurable": {"thread_id": t.thread_id}}
                _sync_trip_row_from_state(graph, config, db, t.trip_id)
            except Exception:
                pass
    trips = crud.list_trips_for_user(db, user_id)
    return [TripOut.model_validate(t) for t in trips]



@app.get("/trips/{trip_id}/resume")
def resume_trip(trip_id: str, db: Session = Depends(get_db), graph=Depends(get_adventure_graph)) -> dict:
    """The actual "resume an existing trip" feature from the
    blueprint: given a trip's durable id, look up which conversation
    thread it's tied to and return that conversation's current state,
    so a client can keep chatting on that thread_id via /chat without
    already knowing it."""
    trip = crud.get_trip(db, trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail="Trip not found")

    config = {"configurable": {"thread_id": trip.thread_id}}
    snapshot = graph.get_state(config)
    values = snapshot.values

    raw_messages = values.get("messages", [])
    messages = get_user_facing_messages(raw_messages)

    return {
        "trip_id": trip.trip_id,
        "thread_id": trip.thread_id,
        "status": trip.status,
        "origin": trip.origin,
        "destination": trip.destination,
        "departure_date": trip.departure_date,
        "budget": trip.budget,
        "duration_days": trip.duration_days,
        "messages": messages,
        "message_count": len(messages),
        "final_response": values.get("final_response"),
    }


@app.get("/trips/{trip_id}/messages")
def list_trip_messages(trip_id: str, db: Session = Depends(get_db), graph=Depends(get_adventure_graph)) -> dict:
    """Given a trip's durable id, look up which conversation
    thread it's tied to and return that conversation's entire message history."""
    trip = crud.get_trip(db, trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail="Trip not found")

    config = {"configurable": {"thread_id": trip.thread_id}}
    snapshot = graph.get_state(config)
    messages = snapshot.values["messages"] if "messages" in snapshot.values else []
    messages = [normalize_message(m) for m in messages if not isinstance(m, ToolMessage)]

    return {
        "trip_id": trip.trip_id,
        "message_count": len(messages),
        "messages": messages,
    }