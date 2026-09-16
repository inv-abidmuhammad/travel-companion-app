"""
LLM client and tool registry — built once at import time.

All LLM variants live here so the rest of the graph just imports what
it needs:

  llm_with_tools   — the planner, bound to the travel tools
  llm              — base client; use for .with_structured_output()
                     when extraction or structured planning is added

Adding a new variant (e.g. for itinerary extraction in Phase 5) is a
one-liner here — nodes.py and graph.py stay unchanged.
"""
from langchain_google_genai import ChatGoogleGenerativeAI

from app.config import get_settings
from app.tools.calculator import calculator
from app.tools.weather import get_weather

_settings = get_settings()

# All tools the planner can call.
TOOLS = [calculator, get_weather]

# name → callable, so tools_node can dispatch whatever the LLM requested.
TOOLS_BY_NAME = {t.name: t for t in TOOLS}

# Base LLM — keep a reference so callers can do llm.with_structured_output()
# for extraction tasks without re-instantiating the client.
llm = ChatGoogleGenerativeAI(
    model=_settings.model_name,
    google_api_key=_settings.google_api_key,
    temperature=0.4,
)

# The planner LLM — pre-bound to the travel tool set.
llm_with_tools = llm.bind_tools(TOOLS)
