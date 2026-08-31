"""
Graph nodes.

Six functions, all written by hand — no `ToolNode`, no `tools_condition`.
Seeing the mechanics once makes it much easier to know what to change
later (e.g. per-tool retry logic, or parallel tool execution).

  agent_node          the LLM, bound to tools, decides what to do next
  tools_node          runs whatever tools the agent asked for
  route_after_agent   decides: loop back to tools, or move to validate
  validate_node       catches unverified weather/budget claims
  route_after_validate  decides: loop back to agent for a fix, or respond
  respond_node         turns the agent's final AIMessage into final_response
"""
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from app.config import get_settings
from app.graph.state import AdventureState
from app.tools.calculator import calculator
from app.tools.weather import get_weather

SYSTEM_PROMPT = """You are the AI Adventure Companion, a conversational \
travel and adventure planning partner. You help turn vague trip ideas \
into concrete plans: destination, route, day-by-day itinerary, budget.

Ask only for essential missing information (starting point, rough \
budget, duration, interests) before proposing options. Use the \
calculator tool for any budget math instead of estimating in your head. \
Use the get_weather tool to check conditions for mountain driving or \
outdoor activity days before recommending them — don't guess at \
weather. Explain trade-offs conversationally rather than dumping a \
bare list."""

TOOLS = [calculator, get_weather]

# name -> callable tool, so tools_node can look up whatever the LLM asks for
TOOLS_BY_NAME = {t.name: t for t in TOOLS}


def _get_llm():
    settings = get_settings()
    return ChatGoogleGenerativeAI(
        model=settings.model_name,
        google_api_key=settings.google_api_key,
        temperature=0.4,
    ).bind_tools(TOOLS)


def agent_node(state: AdventureState) -> dict:
    """The router+planner, merged: one LLM call that sees full history
    and either calls a tool, asks a clarifying question, or gives a
    final answer. Looping back here after `tools` lets it chain
    multiple tool calls across turns without new graph edges."""
    llm = _get_llm()
    messages = state["messages"]
    if not messages or not isinstance(messages[0], SystemMessage):
        messages = [SystemMessage(content=SYSTEM_PROMPT), *messages]
    response: AIMessage = llm.invoke(messages)
    return {"messages": [response]}


def tools_node(state: AdventureState) -> dict:
    """Manual stand-in for LangGraph's prebuilt ToolNode.

    The agent's last AIMessage carries `.tool_calls`: a list of dicts
    like {"name": "calculator", "args": {"expression": "25000/4"},
    "id": "call_abc123"}. For each one, look up the matching Python
    tool by name, call it with the args the LLM generated, and wrap
    the result in a ToolMessage.

    The `tool_call_id` on each ToolMessage matters: it's how the LLM,
    reading the message list again next turn, matches a result back
    to the specific call it made — this is required by every provider
    when there's more than one call in flight at once.
    """
    last_message: AIMessage = state["messages"][-1]
    results = []
    for call in last_message.tool_calls:
        tool_fn = TOOLS_BY_NAME.get(call["name"])
        if tool_fn is None:
            output = f"Error: no tool registered with name '{call['name']}'"
        else:
            try:
                output = tool_fn.invoke(call["args"])
            except Exception as exc:  # noqa: BLE001 — reported back to the agent, not raised
                output = f"Error running {call['name']}: {exc}"
        results.append(
            ToolMessage(content=str(output), tool_call_id=call["id"], name=call["name"])
        )
    return {"messages": results}


def route_after_agent(state: AdventureState) -> str:
    """Manual stand-in for LangGraph's prebuilt tools_condition.

    Just checks: did the agent's last message ask for any tools? If
    so, go run them. If not, the agent thinks it's done, so move on
    to validate — not straight to respond, since "the agent stopped
    calling tools" isn't the same as "the agent's claims are actually
    backed by tool results." This return value is matched against the
    dict passed to add_conditional_edges in graph.py.
    """
    last_message: AIMessage = state["messages"][-1]
    if getattr(last_message, "tool_calls", None):
        return "tools"
    return "done"


def _extract_text(content) -> str:
    """Providers don't agree on message content shape. Some (older
    Anthropic-style APIs, some Gemini responses) return `content` as a
    plain string. Others return a list of content blocks, e.g.:

        [{"type": "text", "text": "...", "extras": {...}}]

    Without this, str(content) on a list just gives you the raw
    Python repr — which is exactly the bug that motivated writing
    this function: it's what showed up in the `reply` field.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts)
    return str(content)


def respond_node(state: AdventureState) -> dict:
    """Extract the agent's final text once it stops calling tools."""
    last = state["messages"][-1]
    return {"final_response": _extract_text(last.content)}


# Phrases that only make sense if the corresponding tool actually ran.
# This is deliberately a narrow, literal check — not an LLM judging
# an LLM — so its behavior is predictable and easy to unit test.
_WEATHER_CLAIM_MARKERS = ["°c", "rain probability", "forecast", "weather"]
_BUDGET_CLAIM_MARKERS = ["₹", "per day", "per-day", "budget is"]

MAX_VALIDATION_RETRIES = 2


def validate_node(state: AdventureState) -> dict:
    """Guardrail node: catch the agent stating weather- or budget-
    specific claims that no tool call actually produced this
    conversation, per the blueprint's guardrail — "Never invent
    real-time weather, prices, availability... when a live tool is
    required." Structural contradiction/missing-data checks (e.g.
    itinerary day count vs. requested duration) belong here too once
    Phase 2's structured itinerary output exists — this starts with
    the check that matters most with only two tools in play.

    If it finds a problem, it appends a corrective HumanMessage and
    signals `needs_revision` so route_after_validate sends control
    back to `agent` — capped at MAX_VALIDATION_RETRIES so a model that
    keeps failing the check can't loop forever.
    """
    messages = state["messages"]
    last = messages[-1]
    text = _extract_text(last.content).lower()

    tools_used = {m.name for m in messages if isinstance(m, ToolMessage)}

    errors = []
    if any(marker in text for marker in _WEATHER_CLAIM_MARKERS) and "get_weather" not in tools_used:
        errors.append("Response describes specific weather conditions without calling get_weather.")
    if any(marker in text for marker in _BUDGET_CLAIM_MARKERS) and "calculator" not in tools_used:
        errors.append("Response states specific budget figures without calling calculator.")

    attempts = state.get("validation_attempts", 0)

    if errors and attempts < MAX_VALIDATION_RETRIES:
        nudge = HumanMessage(
            content=(
                "[validation check] Your last answer had unverified claims: "
                + "; ".join(errors)
                + ". Call the appropriate tool(s), then give a corrected answer."
            )
        )
        return {
            "messages": [nudge],
            "validation_errors": errors,
            "validation_attempts": attempts + 1,
            "needs_revision": True,
        }

    # Either no problems, or we've retried enough — move on. Errors are
    # kept in state either way so they're visible for debugging/logging.
    return {"validation_errors": errors, "needs_revision": False}


def route_after_validate(state: AdventureState) -> str:
    """Straight read of the flag validate_node just set — no guessing
    from message content, no re-deriving anything. If validate_node
    decided a revision is needed, loop back to agent; otherwise move
    on to respond."""
    return "agent" if state.get("needs_revision") else "respond"
