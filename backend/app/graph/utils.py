from langchain_core.messages import HumanMessage, AIMessage
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