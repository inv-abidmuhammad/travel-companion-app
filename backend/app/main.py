"""
FastAPI entrypoint.

    uvicorn app.main:app --reload

Two endpoints for Phase 1:
  GET  /health        liveness check
  POST /chat           send one message, get the agent's reply

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
