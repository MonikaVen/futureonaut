from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import PlatformSettings, User

DEFAULT_STYLE_GUIDELINES = """\
Futureonaut style (default):
Visual: space-inspired educational UI. Dark theme uses navy backgrounds (#050810 to #0d2137), cyan accent (#00d4ff), violet highlight (#7b5cff), high-contrast text, rounded cards, generous spacing. Light theme (html[data-lp-theme="light"]) uses pale surfaces, dark text, and the same accent. No neon glow overload, no cluttered panels.
Motion: short, calm transitions only. No flashing, shake, or seizure-risk effects.
Voice: clear, encouraging, age-appropriate. Short instructions. Immediate on-page feedback (correct / try again). No slang that hides the learning goal.
Layout: one task in view; title + one-line mission; obvious primary control. Keyboard accessible. Do not use alert(), prompt(), or confirm().
Brand: a small “Futureonaut” wordmark in a corner is optional. Do not copy the marketing banner or load remote images.
""".strip()

DEFAULT_GENERATION_SYSTEM_PROMPT = (
    "You are a senior educational game engineer for Futureonaut. "
    "Return one complete, self-contained HTML5 document (no markdown). "
    "The game must run in a sandboxed iframe with no network except relative files. "
    "Follow style_guidelines in the user message for visual design, voice, and layout."
)

DEFAULT_REVISE_SYSTEM_PROMPT = (
    "You are editing an existing self-contained HTML5 educational game for Futureonaut. "
    "Return one complete HTML5 document (no markdown). "
    "Keep the game playable in a sandboxed iframe with no network except relative files. "
    "Follow style_guidelines in the user message for visual design, voice, and layout."
)

STYLE_SOURCE_DEFAULT = "futureonaut"
STYLE_SOURCE_CUSTOM = "custom"
VALID_STYLE_SOURCES = {STYLE_SOURCE_DEFAULT, STYLE_SOURCE_CUSTOM}


def get_or_create_platform_settings(db: Session) -> PlatformSettings:
    row = db.query(PlatformSettings).first()
    if row is not None:
        if not (row.style_guidelines or "").strip():
            row.style_guidelines = DEFAULT_STYLE_GUIDELINES
        if not (row.generation_system_prompt or "").strip():
            row.generation_system_prompt = DEFAULT_GENERATION_SYSTEM_PROMPT
        if not (row.revise_system_prompt or "").strip():
            row.revise_system_prompt = DEFAULT_REVISE_SYSTEM_PROMPT
        return row
    row = PlatformSettings(
        id=1,
        style_guidelines=DEFAULT_STYLE_GUIDELINES,
        generation_system_prompt=DEFAULT_GENERATION_SYSTEM_PROMPT,
        revise_system_prompt=DEFAULT_REVISE_SYSTEM_PROMPT,
        catalog_assigned=False,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def normalize_style_source(value: str | None) -> str:
    raw = (value or "").strip().lower()
    return raw if raw in VALID_STYLE_SOURCES else STYLE_SOURCE_DEFAULT


def resolve_style_guidelines(settings: PlatformSettings, user: User | None) -> str:
    default = (settings.style_guidelines or "").strip() or DEFAULT_STYLE_GUIDELINES
    if user is None:
        return default
    if normalize_style_source(getattr(user, "style_source", None)) != STYLE_SOURCE_CUSTOM:
        return default
    custom = (getattr(user, "style_guidelines", None) or "").strip()
    return custom or default


def generation_context(db: Session, user: User | None) -> tuple[str, str, str]:
    settings = get_or_create_platform_settings(db)
    return (
        (settings.generation_system_prompt or DEFAULT_GENERATION_SYSTEM_PROMPT).strip(),
        (settings.revise_system_prompt or DEFAULT_REVISE_SYSTEM_PROMPT).strip(),
        resolve_style_guidelines(settings, user),
    )
