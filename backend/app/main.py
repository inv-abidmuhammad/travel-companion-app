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


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    config = {"configurable": {"thread_id": req.thread_id}}
    result = adventure_graph.invoke(
        {"messages": [HumanMessage(content=req.message)], "user_id": req.user_id},
        config=config,
    )
    return ChatResponse(reply=result["final_response"], thread_id=req.thread_id)


@app.get("/debug/state/{thread_id}")
def debug_state(thread_id: str) -> dict:
    """Inspect a conversation's raw graph state — this is the actual
    proof for things like "did validate_node loop back to agent?",
    rather than guessing from the reply's wording. Reads whatever
    MemorySaver has snapshotted for this thread_id; returns nothing
    useful if the server has restarted since, since MemorySaver is
    in-process only until Phase 3.
    """
    config = {"configurable": {"thread_id": thread_id}}
    snapshot = adventure_graph.get_state(config)
    values = snapshot.values
    return {
        "message_count": len(values.get("messages", [])),
        "message_types": [type(m).__name__ for m in values.get("messages", [])],
        "validation_attempts": values.get("validation_attempts", 0),
        "validation_errors": values.get("validation_errors", []),
    }
