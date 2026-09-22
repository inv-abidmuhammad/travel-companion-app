"""
LLM client and tool registry — built once at import time.

All LLM variants live here so the rest of the graph just imports what
it needs:

  llm_with_tools   — the planner, bound to the travel tools
  llm              — base client; use for .with_structured_output()
                     when extraction or structured planning is added

"""
from langchain_google_genai import ChatGoogleGenerativeAI

from app.config import get_settings
from app.tools.calculator import calculator
from app.tools.current_date import get_current_date
from app.tools.places import search_place_info
from app.tools.trip_details import record_trip_detail
from app.tools.weather import get_weather

_settings = get_settings()

TOOLS = [calculator, get_weather, get_current_date, record_trip_detail, search_place_info]
TOOLS_BY_NAME = {t.name: t for t in TOOLS}

llm = ChatGoogleGenerativeAI(
    model=_settings.model_name,
    google_api_key=_settings.google_api_key,
    temperature=0.4,
)

llm_with_tools = llm.bind_tools(TOOLS)