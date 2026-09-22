from __future__ import annotations

from typing import Any

MAX_GAME_LEVEL = 50
MAX_EVENT_PAYLOAD_BYTES = 4096
MAX_EVENT_PAYLOAD_KEYS = 32
MAX_EVENT_PAYLOAD_KEY_LEN = 64
MAX_SCORE_DELTA = 1_000_000
MAX_DURATION_MS = 24 * 60 * 60 * 1000
MAX_TASK_ID_LEN = 64
MAX_INT_DIGITS = 10

# Match Luna / platform prompt input size for game-generation queries.
MAX_LUNA_QUERY_CHARS = 12_000

_LEVEL_KEYS = ("level", "totalLevels", "total_levels", "levelsCompleted", "levels_completed")
_DURATION_KEYS = ("durationMs", "duration_ms")
_DELTA_KEYS = ("delta",)


def bounded_int(value: Any, *, default: int = 0, lo: int = 0, hi: int) -> int:
    if value is None or isinstance(value, bool):
        return default
    if isinstance(value, str):
        text = value.strip()
        if not text or len(text) > MAX_INT_DIGITS:
            return default
        value = text
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return max(lo, min(hi, number))


def cap_event_payload(payload: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in payload.items():
        if key in _LEVEL_KEYS:
            cleaned[key] = bounded_int(value, hi=MAX_GAME_LEVEL)
        elif key in _DURATION_KEYS:
            cleaned[key] = bounded_int(value, hi=MAX_DURATION_MS)
        elif key in _DELTA_KEYS:
            cleaned[key] = bounded_int(value, lo=-MAX_SCORE_DELTA, hi=MAX_SCORE_DELTA)
        elif key in {"taskId", "task_id"} and isinstance(value, str):
            cleaned[key] = value[:MAX_TASK_ID_LEN]
        else:
            cleaned[key] = value
    return cleaned
