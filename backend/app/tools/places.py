"""
search_place_info tool.

Descriptive info about a destination — what it's like, notable
places, and anything currently happening there that could affect
travel — via web search rather than the model's own (possibly stale
or wrong) knowledge. Deliberately returns raw search results for the
agent to read and summarize itself, rather than this tool doing its
own LLM summarization pass — keeps the tool a single deterministic
API call, same reasoning as the other tools here.

ASSUMPTION: settings.search_api_key is a Tavily API key
(https://tavily.com) — the common default for LangChain-style agent
search. If that's not the provider in use, only _run_search and the
request/response shape below need to change; get_settings() and the
tool's signature stay the same.
"""
import requests
from langchain_core.tools import tool

from app.config import get_settings

SEARCH_URL = "https://api.tavily.com/search"
REQUEST_TIMEOUT_SECONDS = 10


def _run_search(query: str, api_key: str, max_results: int = 5) -> list[dict]:
    resp = requests.post(
        SEARCH_URL,
        json={
            "api_key": api_key,
            "query": query,
            "search_depth": "basic",
            "max_results": max_results,
            "include_answer": False,
        },
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    return resp.json().get("results", [])


@tool
def search_place_info(location: str) -> dict:
    """Search the web for general information about a travel
    destination: what it's known for, notable places to visit, and
    any current or seasonal events, closures, or conditions that
    could affect a trip there. Use this once the destination is
    confirmed, before describing the place to the user or building an
    itinerary around it. This is descriptive/informational only — it
    does not check live weather (use get_weather for that) or real
    hotel/flight prices.
    """
    settings = get_settings()
    api_key = getattr(settings, "search_api_key", None)
    if not api_key:
        return {"location": location, "results": [], "error": "Search API key is not configured."}

    try:
        results = _run_search(f"{location} travel guide notable places current events", api_key)
    except requests.RequestException as exc:
        return {"location": location, "results": [], "error": f"Search request failed: {exc}"}

    return {
        "location": location,
        "results": [
            {"title": r.get("title"), "url": r.get("url"), "snippet": r.get("content")}
            for r in results
        ],
        "error": None,
    }