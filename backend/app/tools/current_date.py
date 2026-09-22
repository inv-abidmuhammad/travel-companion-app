"""
get_current_date tool.

Models don't reliably know what day it is. This gives the agent a
grounded "today" so it can resolve relative dates the user gives
("next Friday", "in two weeks") into an absolute YYYY-MM-DD before
calling record_trip_detail or get_weather. Note this is for the
agent's own reasoning only — get_weather's forecast-vs-estimate
cutoff computes datetime.now() itself, deterministically, rather
than depending on the agent having called this first.
"""
from datetime import datetime, timezone

from langchain_core.tools import tool


@tool
def get_current_date() -> dict:
    """Return today's date and weekday. Use this whenever the user
    gives a relative date (e.g. 'next Friday', 'in two weeks', 'this
    weekend') so you can resolve it to an absolute YYYY-MM-DD date
    before recording it or checking weather for it.
    """
    now = datetime.now(timezone.utc)
    return {"date": now.strftime("%Y-%m-%d"), "weekday": now.strftime("%A")}