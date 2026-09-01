"""Canonical game topics and AI focus labels."""

from __future__ import annotations

TOPICS = ("AI", "Physics", "Math")

AI_FOCUS_LABELS = (
    "Computer Vision",
    "Large Language Models",
    "Transformers",
    "Privacy",
    "Cybersecurity",
    "Trustworthiness of AI",
)

# Legacy topic aliases normalized on read/write
_TOPIC_ALIASES = {"ML": "AI", "ml": "AI", "Ai": "AI"}

_MATH_HINTS = (
    "math",
    "volume",
    "perimeter",
    "food",
    "estimation",
    "embedding",
    "word_map",
    "word map",
)
_PHYSICS_HINTS = (
    "physics",
    "world_model",
    "world-model",
    "world model",
    "planning",
    "red_dot",
    "red dot",
    "obstacle",
    "furniture",
    "perception",
)

_FOCUS_HINTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "Computer Vision",
        (
            "computer-vision",
            "computer vision",
            "cnn",
            "whiskers",
            "cat or not",
            "feature map",
            "pixels",
            "mood",
            "vision",
        ),
    ),
    (
        "Large Language Models",
        (
            "embedding",
            "word map",
            "word_map",
            "llm",
            "language model",
            "tokenizer",
            "tokenization",
            "nlp",
        ),
    ),
    (
        "Transformers",
        ("transformer", "attention", "self-attention"),
    ),
    (
        "Privacy",
        ("privacy", "secret", "secrets safe", "personal data"),
    ),
    (
        "Cybersecurity",
        ("cyber", "security", "crypto", "encryption", "secrets safe"),
    ),
    (
        "Trustworthiness of AI",
        (
            "trust",
            "knn",
            "neuron",
            "neural",
            "backprop",
            "mlp",
            "classification",
            "jei tai",
            "friends",
        ),
    ),
)


def normalize_topic(value: str | None) -> str | None:
    if not value:
        return None
    return _TOPIC_ALIASES.get(value, value)


def infer_topic(*parts: str) -> str:
    blob = " ".join(p.lower().replace("-", "_") for p in parts if p)
    mathish = any(h.replace("-", "_") in blob or h in blob for h in _MATH_HINTS)
    physicsish = any(h.replace("-", "_") in blob or h in blob for h in _PHYSICS_HINTS)
    if mathish and not any(
        h in blob for h in ("world_model", "world model", "planning", "furniture", "obstacle")
    ):
        if any(
            h in blob
            for h in ("math", "volume", "perimeter", "food", "estimation", "word_map", "word map", "embedding")
        ):
            return "Math"
    if physicsish:
        return "Physics"
    if mathish:
        return "Math"
    return "AI"


def infer_ai_focus_labels(*parts: str) -> list[str]:
    blob = " ".join(p.lower() for p in parts if p)
    found: list[str] = []
    for label, hints in _FOCUS_HINTS:
        if any(h in blob for h in hints):
            found.append(label)
    return found


def ensure_topic_tag(tags: list[str] | None, *infer_parts: str) -> list[str]:
    raw = list(tags or [])
    normalized = []
    for t in raw:
        n = normalize_topic(t)
        if n and n not in normalized:
            normalized.append(n)

    existing = next((t for t in normalized if t in TOPICS), None)
    topic = existing or infer_topic(*infer_parts, *normalized)

    focus_existing = [t for t in normalized if t in AI_FOCUS_LABELS]
    other = [t for t in normalized if t not in TOPICS and t not in AI_FOCUS_LABELS]

    focus = focus_existing or infer_ai_focus_labels(*infer_parts, *normalized, *other)
    # Keep stable order from AI_FOCUS_LABELS
    focus_ordered = [lab for lab in AI_FOCUS_LABELS if lab in focus]

    return [topic, *focus_ordered, *other]
