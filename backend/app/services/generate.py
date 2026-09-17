from __future__ import annotations

import json
import re
from typing import Any

from fastapi import HTTPException
from pydantic import ValidationError

from app.schemas import DragMatchContent, QuizContent, TimedChallengeContent
from app.services.llm import (
    STAGE_INSTRUCTIONS,
    assert_html_safe,
    chat_complete,
    extract_html,
    html_contract_warnings,
    normalize_provider,
    require_api_key,
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


def _require_caller_llm_key(api_key: str | None, provider: str | None) -> tuple[str, str]:
    chosen_provider = normalize_provider(provider or "openai")
    return chosen_provider, require_api_key(api_key or "")


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
    style_guidelines: str = "",
) -> dict[str, Any]:
    if template_type not in TEMPLATE_SCHEMAS:
        raise HTTPException(status_code=400, detail=f"Unknown template_type: {template_type}")

    chosen_provider, key = _require_caller_llm_key(api_key, provider)
    schema_hint = TEMPLATE_SCHEMAS[template_type].model_json_schema()
    system = (
        "You generate educational mini-game content as strict JSON only. "
        "No markdown fences. Match the provided JSON schema shape. "
        "Follow style_guidelines for voice and difficulty of language."
    )
    user = {
        "topic": topic,
        "difficulty": difficulty,
        "template_type": template_type,
        "description": description,
        "item_count": question_count,
        "json_schema": schema_hint,
        "style_guidelines": (style_guidelines or "").strip(),
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
    style_guidelines: str = "",
    system_prompt: str | None = None,
) -> tuple[str, str]:
    from app.services.prompts import DEFAULT_GENERATION_SYSTEM_PROMPT

    system = (system_prompt or DEFAULT_GENERATION_SYSTEM_PROMPT).strip()
    if STAGE_INSTRUCTIONS not in system:
        system = f"{system}\n\n{STAGE_INSTRUCTIONS}"
    style = (style_guidelines or "").strip()
    user = json.dumps(
        {
            "title": title,
            "topic": topic,
            "difficulty": difficulty,
            "language": language or "en",
            "level_count": level_count,
            "levels": levels_brief,
            "style_guidelines": style,
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
                "Each level MUST be a real graded task: multiple-choice, matching pairs, or a typed answer. Include the actual items, options, and Check control in the HTML.",
                "Never ship a lone Next/Finish button that always succeeds. Grade the learner's answer before calling LearnPlay.stage.",
                "Show a short title, instructions, and feedback (correct/try again) on each level.",
                "No remote scripts, fonts, images, or iframes. Inline CSS and JavaScript only.",
                "Do not include <script src> except optionally ./learnplay-sdk.js (the host injects the SDK).",
                "Do not invent a LearnPlay global. Call window.LearnPlay when it exists.",
                "Keep the game keyboard accessible and readable in light and dark (html[data-lp-theme]).",
                "Do not use alert(), prompt(), or confirm(). Keep feedback on the page.",
                "Apply style_guidelines for colors, typography, layout, and voice.",
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
    style_guidelines: str = "",
    system_prompt: str | None = None,
) -> tuple[str, list[str]]:
    system, user = html_game_prompt(
        title=title,
        topic=topic,
        difficulty=difficulty,
        level_count=level_count,
        levels_brief=levels_brief,
        language=language,
        style_guidelines=style_guidelines,
        system_prompt=system_prompt,
    )
    raw = await chat_complete(
        provider=provider,
        api_key=api_key,
        system=system,
        user=user,
        model=model,
        json_mode=False,
    )
    html = assert_html_safe(extract_html(raw))
    return html, html_contract_warnings(html, level_count)


def html_revise_prompt(
    *,
    html: str,
    message: str,
    level_count: int,
    title: str,
    style_guidelines: str = "",
    system_prompt: str | None = None,
) -> tuple[str, str]:
    from app.services.prompts import DEFAULT_REVISE_SYSTEM_PROMPT

    system = (system_prompt or DEFAULT_REVISE_SYSTEM_PROMPT).strip()
    if STAGE_INSTRUCTIONS not in system:
        system = f"{system}\n\n{STAGE_INSTRUCTIONS}"
    user = json.dumps(
        {
            "title": title,
            "level_count": level_count,
            "teacher_request": message,
            "style_guidelines": (style_guidelines or "").strip(),
            "requirements": [
                "Apply the teacher's request to the current HTML.",
                "Return the FULL updated document, not a diff.",
                f"Keep exactly {level_count} playable levels unless the teacher asks to change that.",
                f"Use TOTAL = {level_count} in every LearnPlay.stage(done, TOTAL, extra) call.",
                f"On success call LearnPlay.stage({level_count}, {level_count}, {{ complete: true, score, label: 'Complete' }}).",
                "Each level must stay a real graded task with options or inputs — never a lone Next button that always succeeds.",
                "No remote scripts, fonts, images, or iframes. Inline CSS and JavaScript only.",
                "Do not invent a LearnPlay global. Call window.LearnPlay when it exists.",
                "Do not use alert(), prompt(), or confirm().",
                "Apply style_guidelines for colors, typography, layout, and voice.",
            ],
            "current_html": html,
        }
    )
    return system, user


async def revise_html_game(
    *,
    html: str,
    message: str,
    level_count: int,
    title: str,
    api_key: str,
    provider: str,
    model: str | None = None,
    history: list[dict[str, str]] | None = None,
    style_guidelines: str = "",
    system_prompt: str | None = None,
) -> tuple[str, list[str]]:
    system, user = html_revise_prompt(
        html=html,
        message=message,
        level_count=level_count,
        title=title,
        style_guidelines=style_guidelines,
        system_prompt=system_prompt,
    )
    prior = [
        item
        for item in (history or [])
        if item.get("role") == "user" and (item.get("content") or "").strip()
    ][-6:]
    raw = await chat_complete(
        provider=provider,
        api_key=api_key,
        system=system,
        user=user,
        model=model,
        json_mode=False,
        history=prior,
    )
    next_html = assert_html_safe(extract_html(raw))
    return next_html, html_contract_warnings(next_html, level_count)


def infer_level_count(text: str) -> int:
    match = re.search(r"\b([2-9]|1[0-2])\s*-?\s*(?:levels?|lyg)", text, re.I)
    if match:
        return int(match.group(1))
    return 4


def infer_title_from_html(html: str, fallback: str) -> str:
    title = re.search(r"<title[^>]*>([^<]+)</title>", html, flags=re.I)
    if title and title.group(1).strip():
        return title.group(1).strip()[:200]
    heading = re.search(r"<h1[^>]*>([^<]+)</h1>", html, flags=re.I)
    if heading and heading.group(1).strip():
        return heading.group(1).strip()[:200]
    line = (fallback or "").strip().splitlines()[0].strip()
    return (line or "Class game")[:80]


async def generate_html_from_chat(
    *,
    message: str,
    language: str,
    api_key: str,
    provider: str,
    model: str | None = None,
    style_guidelines: str = "",
    system_prompt: str | None = None,
) -> tuple[str, list[str], str, int]:
    level_count = infer_level_count(message)
    seed_title = infer_title_from_html("", message)
    html, warnings = await generate_html_game(
        title=seed_title,
        topic=seed_title,
        difficulty=2,
        level_count=level_count,
        levels_brief=message,
        language=language,
        api_key=api_key,
        provider=provider,
        model=model,
        style_guidelines=style_guidelines,
        system_prompt=system_prompt,
    )
    title = infer_title_from_html(html, seed_title)
    return html, warnings, title, level_count
