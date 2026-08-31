# AI Adventure Companion

A stateful, tool-using LangGraph agent that turns vague trip ideas into
personalized plans and adapts them as constraints change.

This is **Phase 0 + Phase 1** of the project blueprint: repo
foundation, a typed graph state, one working agent↔tools loop, one
real tool (calculator), and a FastAPI endpoint to talk to it.

## Graph

```
START -> agent --(tool call)--> tools -> agent   (loops until done)
         agent --(no tool call)--------> respond -> END
```

`agent` is a single LLM call bound to the tool list — it decides
whether it needs a tool, needs more info from the user, or is ready to
answer. This merges what the original blueprint called `router_node`
and `planner_node` into one node, which is the standard LangGraph
ReAct-style pattern. See `app/graph/graph.py` for the reasoning.

## Setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp ../.env.example ../.env
# edit ../.env and set ANTHROPIC_API_KEY
```

## Run

```bash
uvicorn app.main:app --reload
```

```bash
curl http://localhost:8000/health

curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "I want a 4-day road trip from Kochi, budget around 25k, mountains and mythology.", "thread_id": "demo-1"}'
```

Send another message with the same `thread_id` and the agent will
remember the conversation (in-memory only for now — restarting the
server clears it; Phase 3 swaps in a Postgres checkpointer).

## Test

```bash
cd backend
pytest
```

Tests cover the calculator tool and the graph's wiring (node presence,
routing edges). They don't call the live Anthropic API, so they run
without a key. Once you're comfortable, add a test that mocks
`agent_node`'s LLM call to exercise a full happy-path run.

## What's next (per the blueprint)

- **Phase 2**: add place search / weather / route tools (mocked first),
  a `validate` node before `respond`, and an `interrupt()`-based
  `human_input` path for missing essential constraints.
- **Phase 3**: swap `MemorySaver` for a Postgres checkpointer; add the
  User/Trip/Message tables from the blueprint.
- **Phase 4**: re-planning is mostly free with this graph shape — a
  "make it cheaper" message just re-enters `agent` with existing state
  already loaded.

## Repo layout

```
backend/
  app/
    main.py            FastAPI app (/health, /chat)
    config.py           env-based settings
    graph/
      state.py           AdventureState TypedDict
      nodes.py           agent_node, respond_node
      graph.py           StateGraph assembly
    tools/
      calculator.py      Phase 1's one tool
  tests/
.env.example
```
