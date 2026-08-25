"""Canonical game topics used for filtering."""

TOPICS = ("ML", "Physics", "Math")

_MATH_HINTS = (
    "math",
    "volume",
    "perimeter",
    "food",
    "estimation",
    "embedding",
    "word_map",
)
_PHYSICS_HINTS = (
    "physics",
    "world_model",
    "world-model",
    "planning",
    "red_dot",
    "obstacle",
    "furniture",
    "perception",
    "volume_box",  # spatial / physical volume intuition
)


def infer_topic(*parts: str) -> str:
    blob = " ".join(p.lower().replace("-", "_") for p in parts if p)
    if any(h in blob for h in _MATH_HINTS) and "world_model" not in blob and "planning" not in blob:
        # math wins for pure math unless it's clearly planning/world-model
        if any(h in blob for h in ("math", "volume", "perimeter", "food", "estimation", "word_map", "embedding")):
            if not any(h in blob for h in _PHYSICS_HINTS if h not in ("volume_box",)):
                return "Math"
    if any(h in blob for h in _PHYSICS_HINTS):
        return "Physics"
    if any(h in blob for h in _MATH_HINTS):
        return "Math"
    return "ML"


def ensure_topic_tag(tags: list[str] | None, *infer_parts: str) -> list[str]:
    tags = list(tags or [])
    existing = next((t for t in tags if t in TOPICS), None)
    topic = existing or infer_topic(*infer_parts, *tags)
    rest = [t for t in tags if t not in TOPICS]
    return [topic, *rest]
