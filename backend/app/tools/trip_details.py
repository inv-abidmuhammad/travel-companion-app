"""
record_trip_detail tool.

The agent's only way to write a trip slot (origin, destination,
departure_date, duration_days, budget) into graph state. Deliberately
mirrors calculator's shape: validate/coerce, return an error dict
rather than raising, and never guess — this only records what the
user has actually confirmed, one call per detail.

tools_node is what actually merges a successful call's output into
state (see nodes.py) — this function stays pure so it's easy to unit
test without a graph.
"""
from datetime import datetime

from langchain_core.tools import tool

ALLOWED_FIELDS = {"origin", "destination", "departure_date", "duration_days", "budget"}


@tool
def record_trip_detail(field: str, value: str) -> dict:
    """Record a trip detail the user has confirmed. Call this once for
    each of: origin, destination, departure_date, duration_days,
    budget — every time the user states or changes one, so the
    conversation can track what's still missing.

    field must be exactly one of: 'origin', 'destination',
    'departure_date', 'duration_days', 'budget'.
    - departure_date must be an absolute YYYY-MM-DD date — resolve
      relative dates with get_current_date first.
    - duration_days must be a whole number of days.
    - budget must be a plain number, no currency symbol.
    Only call this for values the user has actually settled on —
    not tentative options still being discussed.
    """
    if field not in ALLOWED_FIELDS:
        return {
            "field": field,
            "value": None,
            "error": f"Unknown field '{field}'. Must be one of {sorted(ALLOWED_FIELDS)}.",
        }

    if field == "duration_days":
        try:
            coerced: object = int(value)
        except (TypeError, ValueError):
            return {"field": field, "value": None, "error": f"'{value}' is not a whole number of days."}
    elif field == "budget":
        try:
            coerced = float(value)
        except (TypeError, ValueError):
            return {"field": field, "value": None, "error": f"'{value}' is not a valid number."}
    elif field == "departure_date":
        try:
            departure_datetime = datetime.strptime(value, "%Y-%m-%d")
        except (TypeError, ValueError):
            return {"field": field, "value": None, "error": f"'{value}' is not in YYYY-MM-DD format."}
        # if date is in the past, we reject it as well
        if departure_datetime.date() < datetime.now().date():
            return {"field": field, "value": None, "error": f"'{value}' is in the past."}
        coerced = value
    else:  # origin, destination
        coerced = value

    return {"field": field, "value": coerced, "error": None}