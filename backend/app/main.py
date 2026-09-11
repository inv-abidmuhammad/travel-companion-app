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

from fastapi import Depends, FastAPI, HTTPException
from langchain_core.messages import HumanMessage
from langgraph.types import Command
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import crud
from app.db.checkpointer import build_postgres_checkpointer
from app.db.session import get_db, init_db
from app.graph.graph import build_graph

settings = get_settings()
init_db()  # create users/trips tables if they don't exist yet

_pg_checkpointer, _pg_pool = build_postgres_checkpointer(settings.database_url)
adventure_graph = build_graph(checkpointer=_pg_checkpointer)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    _pg_pool.close()  # release Postgres connections cleanly on shutdown


app = FastAPI(title="AI Adventure Companion", lifespan=lifespan)


class ChatRequest(BaseModel):
    message: str
    thread_id: str = "default"
    user_id: str = "anonymous"


class ChatResponse(BaseModel):
    reply: str
    thread_id: str
    awaiting_confirmation: bool = False


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    """One endpoint handles both starting a new turn and answering a
    pending interrupt() question, based on whether the graph is
    currently paused for this thread_id.
    """
    config = {"configurable": {"thread_id": req.thread_id}}
    snapshot = adventure_graph.get_state(config)

    if snapshot.next:
        result = adventure_graph.invoke(Command(resume=req.message), config=config)
    else:
        result = adventure_graph.invoke(
            {"messages": [HumanMessage(content=req.message)], "user_id": req.user_id},
            config=config,
        )

    if "__interrupt__" in result:
        question = result["__interrupt__"][0].value.get("question", "Please respond.")
        return ChatResponse(reply=question, thread_id=req.thread_id, awaiting_confirmation=True)

    return ChatResponse(reply=result["final_response"], thread_id=req.thread_id)


@app.get("/debug/state/{thread_id}")
def debug_state(thread_id: str) -> dict:
    """Inspect a conversation's raw graph state. Now reads from
    Postgres - try this, restart uvicorn, and call it again with the
    same thread_id to see the state survive the restart."""
    config = {"configurable": {"thread_id": thread_id}}
    snapshot = adventure_graph.get_state(config)
    values = snapshot.values
    return {
        "message_count": len(values.get("messages", [])),
        "message_types": [type(m).__name__ for m in values.get("messages", [])],
        "validation_attempts": values.get("validation_attempts", 0),
        "validation_errors": values.get("validation_errors", []),
        "paused_at": list(snapshot.next),
    }


class TripCreate(BaseModel):
    user_id: str
    thread_id: str | None = None
    origin: str | None = None
    destination: str | None = None
    budget: float | None = None
    duration_days: int | None = None


class TripUpdate(BaseModel):
    origin: str | None = None
    destination: str | None = None
    budget: float | None = None
    duration_days: int | None = None
    status: str | None = None
    itinerary_text: str | None = None


class TripOut(BaseModel):
    id: str
    user_id: str
    thread_id: str
    origin: str | None = None
    destination: str | None = None
    budget: float | None = None
    duration_days: int | None = None
    status: str
    itinerary_text: str | None = None

    model_config = {"from_attributes": True}


@app.post("/trips", response_model=TripOut)
def create_trip(payload: TripCreate, db: Session = Depends(get_db)) -> TripOut:

    if payload.thread_id is None:
        # If the client didn't provide a thread_id, generate one for them.
        # This is the common case: a new trip starts a new conversation.
        payload.thread_id = str(uuid.uuid4())
    trip = crud.create_trip(
        db,
        user_id=payload.user_id,
        thread_id=payload.thread_id,
        origin=payload.origin,
        destination=payload.destination,
        budget=payload.budget,
        duration_days=payload.duration_days,
    )
    return TripOut.model_validate(trip)


@app.get("/trips/{trip_id}", response_model=TripOut)
def get_trip(trip_id: str, db: Session = Depends(get_db)) -> TripOut:
    trip = crud.get_trip(db, trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail="Trip not found")
    return TripOut.model_validate(trip)


@app.patch("/trips/{trip_id}", response_model=TripOut)
def patch_trip(trip_id: str, payload: TripUpdate, db: Session = Depends(get_db)) -> TripOut:
    fields = {k: v for k, v in payload.model_dump().items() if v is not None}
    trip = crud.update_trip(db, trip_id, **fields)
    if trip is None:
        raise HTTPException(status_code=404, detail="Trip not found")
    return TripOut.model_validate(trip)


@app.get("/users/{user_id}/trips", response_model=list[TripOut])
def list_trips(user_id: str, db: Session = Depends(get_db)) -> list[TripOut]:
    trips = crud.list_trips_for_user(db, user_id)
    return [TripOut.model_validate(t) for t in trips]


@app.get("/trips/{trip_id}/resume")
def resume_trip(trip_id: str, db: Session = Depends(get_db)) -> dict:
    """The actual "resume an existing trip" feature from the
    blueprint: given a trip's durable id, look up which conversation
    thread it's tied to and return that conversation's current state,
    so a client can keep chatting on that thread_id via /chat without
    already knowing it."""
    trip = crud.get_trip(db, trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail="Trip not found")

    config = {"configurable": {"thread_id": trip.thread_id}}
    snapshot = adventure_graph.get_state(config)
    values = snapshot.values

    return {
        "trip_id": trip.id,
        "thread_id": trip.thread_id,
        "status": trip.status,
        "origin": trip.origin,
        "destination": trip.destination,
        "budget": trip.budget,
        "duration_days": trip.duration_days,
        "message_count": len(values.get("messages", [])),
        "final_response": values.get("final_response"),
    }


@app.get("/trips/{trip_id}/messages")
def list_trip_messages(trip_id: str, db: Session = Depends(get_db)) -> dict:
    """Given a trip's durable id, look up which conversation
    thread it's tied to and return that conversation's entire message history."""
    trip = crud.get_trip(db, trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail="Trip not found")

    config = {"configurable": {"thread_id": trip.thread_id}}
    snapshot = adventure_graph.get_state(config)
    messages = snapshot.values["messages"] if "messages" in snapshot.values else []

    return {
        "trip_id": trip.id,
        "message_count": len(messages),
        "messages": messages,
    }
