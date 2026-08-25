from __future__ import annotations

import json
from typing import Any

import httpx
from fastapi import HTTPException, status
from pydantic import ValidationError

from app.config import get_settings
from app.schemas import DragMatchContent, QuizContent, TimedChallengeContent

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


async def generate_ai_content(
    *,
    topic: str,
    difficulty: int,
    template_type: str,
    description: str,
    question_count: int,
) -> dict[str, Any]:
    settings = get_settings()
    if not settings.openai_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OPENAI_API_KEY is not configured",
        )
    if template_type not in TEMPLATE_SCHEMAS:
        raise HTTPException(status_code=400, detail=f"Unknown template_type: {template_type}")

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

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{settings.openai_base_url.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.openai_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.openai_model,
                "temperature": 0.4,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": json.dumps(user)},
                ],
            },
        )
    if resp.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM request failed: {resp.status_code} {resp.text[:300]}",
        )
    data = resp.json()
    try:
        raw = data["choices"][0]["message"]["content"]
        parsed = json.loads(raw)
    except (KeyError, IndexError, json.JSONDecodeError) as exc:
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
