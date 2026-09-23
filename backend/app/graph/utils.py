from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
import re


_SYNTHETIC_PATTERNS = [
    re.compile(r"^\[validation check\]", re.IGNORECASE),
    # add other internal-injection prefixes here as they show up, e.g.
    # re.compile(r"^\[internal retry\]", re.IGNORECASE),
]

def extract_text(content) -> str:
    """Providers don't agree on message content shape. Some (older
    Anthropic-style APIs, some Gemini responses) return `content` as a
    plain string. Others return a list of content blocks, e.g.:

        [{"type": "text", "text": "...", "extras": {...}}]

    Without this, str(content) on a list just gives you the raw
    Python repr — which is exactly a real bug this project hit: that
    repr showed up verbatim in the API's `reply` field.
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
        return "\n".join(p for p in parts if p)
    return str(content)


def is_synthetic(text: str) -> bool:
    return any(p.match(text) for p in _SYNTHETIC_PATTERNS)


def normalize_message(msg) -> dict:
    if isinstance(msg, HumanMessage):
        role = "user"
    elif isinstance(msg, AIMessage):
        role = "assistant"
    else:
        role = "unknown"

    text = extract_text(msg.content)
    synthetic = role == "user" and is_synthetic(text)
    if synthetic:
        role = "internal"

    normalized = {
        "id": msg.id,
        "role": role,
        "text": text,
    }
    if synthetic:
        normalized["synthetic"] = True

    if role == "user" and text.startswith("[human decision]"):
        normalized["text"] = text[len("[human decision]") :].strip()

    tool_calls = getattr(msg, "tool_calls", None) or []
    if tool_calls:
        normalized["tool_calls"] = [
            {"name": tc["name"], "args": tc["args"]} for tc in tool_calls
        ]

    return normalized


def is_user_facing_ai_message(messages: list, index: int) -> bool:
    """Return True only if the AIMessage at messages[index] was actually
    presented to the user — meaning:

    1. It has no tool_calls (intermediate planner decisions, never shown to the user).
    2. It has non-empty text content.
    3. It is NOT followed by an internal [validation check] injection before the next
       real HumanMessage (if it is, it was a failed draft that the graph retried
       internally — the user only ever saw the final corrected version).
    """
    m = messages[index]
    if getattr(m, "tool_calls", None):
        return False

    text = extract_text(getattr(m, "content", ""))
    if not text.strip():
        return False

    for j in range(index + 1, len(messages)):
        nxt = messages[j]
        if isinstance(nxt, ToolMessage):
            continue
        if isinstance(nxt, HumanMessage):
            nxt_text = extract_text(nxt.content)
            if is_synthetic(nxt_text):
                return False
            else:
                return True

    return True


def get_user_facing_messages(messages: list) -> list[dict]:
    """Filter and normalize messages from graph state to include only the messages
    the user actually saw in the conversation (excluding ToolMessages, internal
    validation checks, and failed AI drafts that were retried)."""
    user_facing = []
    for i, m in enumerate(messages):
        if isinstance(m, ToolMessage):
            continue

        if isinstance(m, HumanMessage):
            text = extract_text(m.content)
            if is_synthetic(text):
                continue
            normalized = normalize_message(m)
            user_facing.append(normalized)

        elif isinstance(m, AIMessage):
            if is_user_facing_ai_message(messages, i):
                normalized = normalize_message(m)
                user_facing.append(normalized)

    return user_facing