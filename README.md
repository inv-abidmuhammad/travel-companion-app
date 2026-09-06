# AI Adventure Companion

A stateful, tool-using LangGraph agent that turns vague trip ideas into
personalized plans and adapts them as constraints change.

This covers **Phase 0, 1, 2, and most of Phase 3** of the project
blueprint: repo foundation, typed graph state, an agent↔tools loop
with two tools (calculator, mocked weather), a validate node that
catches unverified claims, an interrupt()-based human-in-the-loop
path, and now — Postgres-backed persistence, so conversations survive
a server restart, plus durable `User`/`Trip` records separate from
the conversation checkpointer.

## Graph

```
START -> agent --(tool call)--> tools -> agent   (loops until done)
         agent --(no tool call)--------> validate
validate --(unverified claims, retries left)--> agent   (loops, capped)
         --(retries exhausted, still unresolved)--> human_input
         --(clean)-----------------------------------> respond -> END
human_input --("retry")--> agent
            --(otherwise)--> respond -> END
```

`agent` is a single LLM call bound to the tool list — it decides
whether it needs a tool, needs more info from the user, or is ready to
answer. This merges what the original blueprint called `router_node`
and `planner_node` into one node, the standard LangGraph ReAct-style
pattern.

`tools`, the routing between `agent`/`tools`/`validate`/`human_input`,
`validate`, and `human_input` itself are all written by hand in
`app/graph/nodes.py` — deliberately not using LangGraph's prebuilt
`ToolNode` / `tools_condition`, so every step is visible and editable.

`validate_node` checks the agent's final answer for weather- or
budget-specific language (e.g. "°C", "₹", "per day") and confirms the
matching tool actually ran this conversation, per the blueprint's
guardrail: *"Never invent real-time weather, prices, availability...
when a live tool is required."* If it catches a mismatch, it appends a
corrective message and loops the agent back — capped at
`MAX_VALIDATION_RETRIES` so it can't loop forever.

`human_input_node` is reached only when those automatic retries are
exhausted and the concern is still unresolved — the edge the
*original* blueprint's graph was missing entirely. It uses LangGraph's
real `interrupt()`: the graph genuinely pauses mid-run, and resuming
(even from a fresh process, since state lives in Postgres now) picks
up exactly inside the paused function via `Command(resume=<answer>)`.

## Persistence (Phase 3)

Two separate things now persist to Postgres, for two separate reasons:

1. **Conversation state** — `app/db/checkpointer.py` builds a
   `PostgresSaver`-backed checkpointer instead of the in-process
   `MemorySaver` from Phase 1/2. Every message, tool call, and
   validation counter for a `thread_id` survives a server restart.
   This uses LangGraph's own tables (`checkpoints`,
   `checkpoint_writes`, `checkpoint_blobs`) — nothing here manages
   those directly.

2. **Durable business data** — `app/db/models.py` defines `User` and
   `Trip` tables via SQLAlchemy: budget, origin, destination, status.
   This is deliberately a small slice of the blueprint's full model
   (no `ItineraryDay`/`Place` tables yet — the agent doesn't extract
   structured itinerary data from conversation yet, so those tables
   would have nothing to populate them). A `Trip` links to a
   conversation only by `thread_id` — see `/trips/{trip_id}/resume`,
   the actual "resume an existing trip" feature from the blueprint.

`app/graph/graph.py`'s `build_graph()` takes an optional checkpointer
so the module stays testable without a running database — tests get
an in-memory `MemorySaver`. The real app (`main.py`) builds its own
Postgres-backed instance instead.

## Setup

```bash
# Start Postgres
docker compose up -d

cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp ../.env.example .env
# edit .env and set GOOGLE_API_KEY (get one at aistudio.google.com/apikey)
# DATABASE_URL already matches docker-compose.yml's defaults
```

## Run

```bash
uvicorn app.main:app --reload
```

Tables (both LangGraph's checkpoint tables and the app's `users`/
`trips` tables) are created automatically on startup if they don't
exist yet — no separate migration step needed at this stage.

```bash
curl http://localhost:8000/health

curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "I want a 4-day road trip from Kochi, budget around 25k, mountains and mythology.", "thread_id": "demo-1", "user_id": "alice"}'

# Save it as a durable trip, separate from the conversation itself
curl -X POST http://localhost:8000/trips \
  -H "Content-Type: application/json" \
  -d '{"user_id": "alice", "thread_id": "demo-1", "origin": "Kochi", "budget": 25000, "duration_days": 4}'

# Later — resume it (works even after restarting uvicorn, or on a
# different machine pointed at the same database)
curl http://localhost:8000/trips/<trip_id>/resume

curl http://localhost:8000/debug/state/demo-1
```

Restart `uvicorn` between the first `/chat` call and the `/debug/state`
call to see conversation memory actually survive the restart — this
is the concrete proof Phase 3 changed anything, versus just trusting
that it did.

## Test

```bash
cd backend
pytest
```

Tests don't call the live Gemini API — `_get_llm` is stubbed where
needed (see `test_end_to_end_loop.py` and
`test_end_to_end_human_input.py`). `test_db.py` and
`test_checkpointer.py` need a real Postgres and are automatically
skipped if `DATABASE_URL` isn't reachable (e.g. you haven't run
`docker compose up -d` yet) — everything else runs regardless.
`test_checkpointer.py::test_state_survives_a_fresh_checkpointer_instance`
is the direct proof of Phase 3's core claim: it builds a graph, runs
one turn, discards that checkpointer and pool entirely, builds a
brand new one against the same database, and confirms the
conversation is still there.

## What's next (per the blueprint)

Phases 0–2 are complete. Phase 3's core persistence is done; the full
blueprint data model (`ItineraryDay`, `Place`, `ToolExecution` tables)
is deferred until the agent actually produces structured itinerary
output worth persisting that way.

- **Phase 4**: re-planning is mostly free with this graph shape — a
  "make it cheaper" message just re-enters `agent` with existing state
  already loaded. Structured itinerary output would be a natural
  precursor, to give `validate_node` and the database something more
  concrete to check and store.

## Repo layout

```
docker-compose.yml     Postgres service for local dev
backend/
  app/
    main.py            FastAPI app: /chat, /debug/state, /trips/*
    config.py           env-based settings (anchored .env path)
    graph/
      state.py           AdventureState TypedDict
      nodes.py           all eight node/routing functions
      graph.py           StateGraph assembly (injectable checkpointer)
    tools/
      calculator.py      safe arithmetic tool
      weather.py         mocked weather tool
    db/
      models.py          SQLAlchemy User/Trip models
      session.py          engine, SessionLocal, get_db dependency
      crud.py             plain functions over a Session
      checkpointer.py      Postgres-backed LangGraph checkpointer factory
  tests/
.env.example
```
