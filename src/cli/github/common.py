from __future__ import annotations

from src.integrations.github.issues import resolve_token

OUTPUT_TEXT = "text"
OUTPUT_JSON = "json"
OUTPUT_NUMBER = "number"
DEFAULT_READY_LABEL = "ready-for-copilot"


def resolve_agent_token(explicit_token: str | None) -> str:
    """Prefer an explicit token, then fall back to the environment."""
    if explicit_token:
        return explicit_token
    return resolve_token(None)
