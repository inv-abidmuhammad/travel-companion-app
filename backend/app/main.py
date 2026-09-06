"""
FastAPI entrypoint.

    uvicorn app.main:app --reload

Endpoints:
  GET  /health              liveness check
  POST /chat                 send one message, get the agent's reply
  GET  /debug/state/{id}     inspect a conversation's raw graph state

`thread_id` is the conversation id LangGraph's checkpointer uses to
resume state between calls — pass the same one back on every message
in a conversation to keep memory. Phase 3 replaces MemorySaver with a
Postgres checkpointer so this survives a restart.
"""
from fastapi import FastAPI
from langchain_core.messages import HumanMessage
from langgraph.types import Command
from pydantic import BaseModel

from app.graph.graph import adventure_graph

app = FastAPI(title="AI Adventure Companion")


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

    `snapshot.next` being non-empty means the graph stopped mid-run
    rather than reaching END — for this graph, the only way that
    happens is human_input_node's interrupt(). If your graph later
    gains other reasons to pause (or fail) mid-run, this check would
    need to distinguish those cases; it's a fine simplification for
    now since interrupt() is the only pause point that exists.
    """
    config = {"configurable": {"thread_id": req.thread_id}}
    snapshot = adventure_graph.get_state(config)

    if snapshot.next:
        # Paused, waiting on human_input_node's interrupt() — the
        # incoming message is the answer to that question, not a new
        # conversational turn. Command(resume=...) picks execution
        # back up exactly inside interrupt(), returning this value.
        result = adventure_graph.invoke(Command(resume=req.message), config=config)
    else:
        result = adventure_graph.invoke(
            {"messages": [HumanMessage(content=req.message)], "user_id": req.user_id},
            config=config,
        )

    if "__interrupt__" in result:
        # The graph paused again (or for the first time) — surface the
        # question as the reply, and flag it so the client knows the
        # next message should answer it, not start a new topic.
        question = result["__interrupt__"][0].value.get("question", "Please respond.")
        return ChatResponse(reply=question, thread_id=req.thread_id, awaiting_confirmation=True)

    return ChatResponse(reply=result["final_response"], thread_id=req.thread_id)


@app.get("/debug/state/{thread_id}")
def debug_state(thread_id: str) -> dict:
    """Inspect a conversation's raw graph state — this is the actual
    proof for things like "did validate_node loop back to agent?" or
    "is this thread currently paused on an interrupt?", rather than
    guessing from the reply's wording. Reads whatever MemorySaver has
    snapshotted for this thread_id; returns nothing useful if the
    server has restarted since, since MemorySaver is in-process only
    until Phase 3.
    """
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
