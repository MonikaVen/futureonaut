from __future__ import annotations

import json
from typing import Any

from fastapi import HTTPException, status
from pydantic import ValidationError

from app.config import get_settings
from app.schemas import DragMatchContent, QuizContent, TimedChallengeContent
from app.services.llm import (
    STAGE_INSTRUCTIONS,
    chat_complete,
    extract_html,
    normalize_provider,
    require_api_key,
    validate_generated_html,
)

TEMPLATE_SCHEMAS = {
    "quiz": QuizContent,
    "drag_match": DragMatchContent,
    "timed_challenge": TimedChallengeContent,
}


def validate_template_content(template_type: str, content: dict[str, Any]) -> dict[str, Any]:
    schema = TEMPLATE_SCHEMAS.get(template_type)
    if schema is None:
        raise HTTPException(status_code=400, detail=f"Unknown template_type: {template_type}")
    try:
        return schema.model_validate(content).model_dump()
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.errors()) from exc


def _resolve_openai_fallback(api_key: str | None, provider: str | None) -> tuple[str, str]:
    settings = get_settings()
    chosen_provider = normalize_provider(provider or "openai") if provider else "openai"
    if api_key:
        return chosen_provider, require_api_key(api_key)
    if chosen_provider == "openai" and settings.openai_api_key:
        return "openai", settings.openai_api_key.strip()
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Enter an API key for the selected provider",
    )


async def generate_ai_content(
    *,
    topic: str,
    difficulty: int,
    template_type: str,
    description: str,
    question_count: int,
    api_key: str | None = None,
    provider: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    if template_type not in TEMPLATE_SCHEMAS:
        raise HTTPException(status_code=400, detail=f"Unknown template_type: {template_type}")

    chosen_provider, key = _resolve_openai_fallback(api_key, provider)
    schema_hint = TEMPLATE_SCHEMAS[template_type].model_json_schema()
    system = (
        "You generate educational mini-game content as strict JSON only. "
        "No markdown fences. Match the provided JSON schema shape."
    )
    user = {
        "topic": topic,
        "difficulty": difficulty,
        "template_type": template_type,
        "description": description,
        "item_count": question_count,
        "json_schema": schema_hint,
        "rules": [
            "Use clear learner-friendly language",
            "Include topic_tags related to the topic",
            "difficulty must match the requested difficulty",
            "For quiz, exactly one option per question should be correct",
            "For timed_challenge, answers should be short strings",
        ],
    }
    raw = await chat_complete(
        provider=chosen_provider,
        api_key=key,
        system=system,
        user=json.dumps(user),
        model=model,
        json_mode=chosen_provider != "claude",
    )
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail="LLM returned invalid JSON") from exc

    validated = validate_template_content(template_type, parsed)
    validated["difficulty"] = difficulty
    if topic.lower() not in " ".join(validated.get("topic_tags", [])).lower():
        tags = list(validated.get("topic_tags") or [])
        tags.insert(0, topic.lower().replace(" ", "-")[:40])
        validated["topic_tags"] = tags[:8]
    if description and not validated.get("description"):
        validated["description"] = description
    return validated


def html_game_prompt(
    *,
    title: str,
    topic: str,
    difficulty: int,
    level_count: int,
    levels_brief: str,
    language: str,
) -> tuple[str, str]:
    system = (
        "You are a senior educational game engineer. "
        "Return one complete, self-contained HTML5 document (no markdown). "
        "The game must run in a sandboxed iframe with no network except relative files. "
        + STAGE_INSTRUCTIONS
    )
    user = json.dumps(
        {
            "title": title,
            "topic": topic,
            "difficulty": difficulty,
            "language": language or "en",
            "level_count": level_count,
            "levels": levels_brief,
            "ui": {
                "use_css_variables": True,
                "variables": ["--bg", "--text", "--card", "--accent", "--muted", "--border", "--good", "--bad"],
                "self_contained": True,
            },
            "requirements": [
                f"Build exactly {level_count} playable levels matching the teacher's description.",
                f"Use TOTAL = {level_count} in every LearnPlay.stage(done, TOTAL, extra) call.",
                f"On success call LearnPlay.stage({level_count}, {level_count}, {{ complete: true, score, label: 'Complete' }}).",
                "Keep the same (done, TOTAL) structure when the learner is done — do not switch to a different event shape.",
                "Show a short title, instructions, and a Next or Check control on each level.",
                "No remote scripts, fonts, images, or iframes. Inline CSS and JavaScript only.",
                "Do not include <script src> except optionally ./learnplay-sdk.js (the host injects the SDK).",
                "Do not invent a LearnPlay global. Call window.LearnPlay when it exists.",
                "Keep the game keyboard accessible and readable in light and dark (html[data-lp-theme]).",
            ],
        }
    )
    return system, user


async def generate_html_game(
    *,
    title: str,
    topic: str,
    difficulty: int,
    level_count: int,
    levels_brief: str,
    language: str,
    api_key: str,
    provider: str,
    model: str | None = None,
) -> str:
    system, user = html_game_prompt(
        title=title,
        topic=topic,
        difficulty=difficulty,
        level_count=level_count,
        levels_brief=levels_brief,
        language=language,
    )
    raw = await chat_complete(
        provider=provider,
        api_key=api_key,
        system=system,
        user=user,
        model=model,
        json_mode=False,
    )
    html = extract_html(raw)
    return validate_generated_html(html, level_count)
