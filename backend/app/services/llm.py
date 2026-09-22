from __future__ import annotations

import base64
import hashlib
import re
from datetime import datetime, timezone
from typing import Literal

import httpx
from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException, status

from app.config import get_settings
from app.limits import MAX_LUNA_QUERY_CHARS

LlmProvider = Literal["openai", "claude", "grok"]

PROVIDERS: dict[str, dict[str, str]] = {
    "openai": {
        "kind": "openai",
        "base": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
    },
    "grok": {
        "kind": "openai",
        "base": "https://api.x.ai/v1",
        "model": "grok-3-mini",
    },
    "claude": {
        "kind": "anthropic",
        "base": "https://api.anthropic.com",
        "model": "claude-sonnet-4-5",
    },
}

MAX_HTML_CHARS = 400_000
API_KEY_MIN_LEN = 12
API_KEY_MAX_LEN = 256

STAGE_INSTRUCTIONS = """
LEVEL PROGRESS CONTRACT (required — the host records Level done/total from these calls):

The platform injects ./learnplay-i18n.js and ./learnplay-sdk.js. Do NOT redefine LearnPlay.
Do NOT load remote scripts, fonts, or iframes. Inline CSS and JS only.

Let TOTAL be the number of levels in this game. TOTAL must never change.

After the learner finishes level k (1-indexed), call:
  LearnPlay.stage(k, TOTAL, { label: "<level name>", id: "level-k", points: 10, correct: true });

If they get a level wrong, still keep the same structure:
  LearnPlay.stage(k - 1, TOTAL, { label: "<level name>", id: "level-k", correct: false });

When they successfully finish the last level, return the SAME structure with complete:
  LearnPlay.stage(TOTAL, TOTAL, { complete: true, score: <points>, label: "Complete", id: "done" });

If they fail the final attempt, do NOT mark the game solved:
  LearnPlay.stage(done, TOTAL, { complete: false, label: "Try again" });
  // never call LearnPlay.complete() on failure

Always pass the same TOTAL. The host must still show Level done/TOTAL when the run ends.
You may also use LearnPlay.score and LearnPlay.answer; stage() already covers progress.
""".strip()


def hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.strip().encode("utf-8")).hexdigest()


def api_key_hint(api_key: str) -> str:
    cleaned = api_key.strip()
    if len(cleaned) < 4:
        return "****"
    return cleaned[-4:]


def normalize_provider(provider: str) -> str:
    value = (provider or "").strip().lower()
    if value not in PROVIDERS:
        raise HTTPException(status_code=400, detail="provider must be openai, claude, or grok")
    return value


def require_api_key(api_key: str) -> str:
    key = (api_key or "").strip()
    if len(key) < API_KEY_MIN_LEN or len(key) > API_KEY_MAX_LEN:
        raise HTTPException(
            status_code=400,
            detail=f"API key must be {API_KEY_MIN_LEN}–{API_KEY_MAX_LEN} characters",
        )
    if any(ch.isspace() for ch in key):
        raise HTTPException(status_code=400, detail="API key must not contain whitespace")
    return key


def store_llm_key(user, provider: str, api_key: str) -> None:
    key = require_api_key(api_key)
    user.llm_provider = normalize_provider(provider)
    user.llm_api_key_hash = hash_api_key(key)
    user.llm_api_key_hint = api_key_hint(key)


def _fernet() -> Fernet:
    digest = hashlib.sha256(get_settings().jwt_secret.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_api_key(api_key: str) -> str:
    return _fernet().encrypt(api_key.encode("utf-8")).decode("ascii")


def decrypt_api_key(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail="Saved API key could not be read. Save the key again.",
        ) from exc


def upsert_llm_key(db, user, provider: str, api_key: str) -> None:
    from app.models import UserLlmKey

    key = require_api_key(api_key)
    chosen = normalize_provider(provider)
    store_llm_key(user, chosen, key)
    row = (
        db.query(UserLlmKey)
        .filter(UserLlmKey.user_id == user.id, UserLlmKey.provider == chosen)
        .first()
    )
    now = datetime.now(timezone.utc)
    if row is None:
        row = UserLlmKey(user_id=user.id, provider=chosen)
        db.add(row)
    row.key_ciphertext = encrypt_api_key(key)
    row.key_hash = hash_api_key(key)
    row.key_hint = api_key_hint(key)
    row.updated_at = now
    db.add(user)


def delete_llm_key(db, user, provider: str | None = None) -> None:
    from app.models import UserLlmKey

    q = db.query(UserLlmKey).filter(UserLlmKey.user_id == user.id)
    if provider:
        q = q.filter(UserLlmKey.provider == normalize_provider(provider))
    q.delete(synchronize_session=False)
    remaining = (
        db.query(UserLlmKey)
        .filter(UserLlmKey.user_id == user.id)
        .order_by(UserLlmKey.updated_at.desc())
        .first()
    )
    if remaining is None:
        user.llm_provider = None
        user.llm_api_key_hash = None
        user.llm_api_key_hint = None
    else:
        user.llm_provider = remaining.provider
        user.llm_api_key_hash = remaining.key_hash
        user.llm_api_key_hint = remaining.key_hint
    db.add(user)


def list_llm_keys(db, user) -> list[dict[str, str | None]]:
    from app.models import UserLlmKey

    rows = (
        db.query(UserLlmKey)
        .filter(UserLlmKey.user_id == user.id)
        .order_by(UserLlmKey.provider.asc())
        .all()
    )
    return [{"provider": row.provider, "hint": row.key_hint} for row in rows]


def resolve_llm_key(db, user, provider: str | None, api_key: str | None) -> tuple[str, str]:
    chosen = normalize_provider(provider or getattr(user, "llm_provider", None) or "openai")
    raw = (api_key or "").strip()
    if raw:
        key = require_api_key(raw)
        upsert_llm_key(db, user, chosen, key)
        return chosen, key
    from app.models import UserLlmKey

    row = (
        db.query(UserLlmKey)
        .filter(UserLlmKey.user_id == user.id, UserLlmKey.provider == chosen)
        .first()
    )
    if row is None or not (row.key_ciphertext or "").strip():
        raise HTTPException(
            status_code=400,
            detail=f"No saved API key for {chosen}. Save one in Settings, or paste a key.",
        )
    key = decrypt_api_key(row.key_ciphertext)
    store_llm_key(user, chosen, key)
    db.add(user)
    return chosen, key


def assert_html_safe(html: str) -> str:
    if len(html) > MAX_HTML_CHARS:
        raise HTTPException(status_code=502, detail="Generated HTML is too large")
    lower = html.lower()
    if "<html" not in lower:
        raise HTTPException(status_code=502, detail="LLM did not return an HTML document")
    if re.search(r"<script[^>]+src=['\"]https?://", html, flags=re.I):
        raise HTTPException(status_code=502, detail="Generated game must not load remote scripts")
    if re.search(r"<iframe\b", html, flags=re.I):
        raise HTTPException(status_code=502, detail="Generated game must not embed iframes")
    return html


def html_contract_warnings(html: str, total_levels: int) -> list[str]:
    warnings: list[str] = []
    if "LearnPlay.stage" not in html:
        warnings.append("Missing LearnPlay.stage level markers")
    if "complete:" not in html and "complete :" not in html:
        warnings.append("Missing a completion marker on the final level")
    if str(total_levels) not in html:
        warnings.append("Does not use the requested level total")
    interactive = any(
        marker in html.lower()
        for marker in ("<input", "<select", "<textarea", "data-", "option", "choice", "quiz", "match")
    )
    if not interactive:
        warnings.append("Levels look like placeholders. Ask for real questions, matches, or typed answers.")
    return warnings


def extract_html(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        raise HTTPException(status_code=502, detail="LLM returned empty content")
    fence = re.match(r"^```(?:html|HTML)?\s*\n([\s\S]*?)\n```\s*$", text)
    if fence:
        text = fence.group(1).strip()
    elif text.startswith("```"):
        text = re.sub(r"^```(?:html|HTML)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text).strip()
    if text.startswith("{") and '"html"' in text[:200]:
        import json

        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict) and parsed.get("html"):
                text = str(parsed["html"]).strip()
        except json.JSONDecodeError:
            pass
    lower = text.lower()
    start = lower.find("<!doctype html")
    if start < 0:
        start = lower.find("<html")
    if start > 0:
        text = text[start:]
    end = text.lower().rfind("</html>")
    if end >= 0:
        text = text[: end + len("</html>")]
    return text.strip()


def validate_generated_html(html: str, total_levels: int) -> str:
    html = assert_html_safe(html)
    warnings = html_contract_warnings(html, total_levels)
    if warnings:
        raise HTTPException(status_code=502, detail=warnings[0])
    return html


def _chat_messages(user: str, history: list[dict[str, str]] | None) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    for item in history or []:
        role = (item.get("role") or "").strip()
        content = (item.get("content") or "").strip()
        if role in {"user", "assistant"} and content:
            messages.append({"role": role, "content": content[:MAX_LUNA_QUERY_CHARS]})
    messages.append({"role": "user", "content": user})
    return messages[-12:]


MAX_OUTPUT_TOKENS = 8192
MAX_REASONING_OUTPUT_TOKENS = 16384


def uses_max_completion_tokens(model: str) -> bool:
    """Newer OpenAI chat models reject max_tokens in favor of max_completion_tokens."""
    name = (model or "").strip().lower()
    return name.startswith(("o1", "o3", "o4", "gpt-5", "gpt-4.1"))


def openai_chat_payload(
    *,
    model: str,
    system: str,
    messages: list[dict[str, str]],
    json_mode: bool = False,
) -> dict:
    payload: dict = {
        "model": model,
        "messages": [{"role": "system", "content": system}, *messages],
    }
    if uses_max_completion_tokens(model):
        payload["max_completion_tokens"] = MAX_REASONING_OUTPUT_TOKENS
    else:
        payload["max_tokens"] = MAX_OUTPUT_TOKENS
        payload["temperature"] = 0.4
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    return payload


def _retarget_token_limit(payload: dict) -> dict:
    next_payload = dict(payload)
    if "max_tokens" in next_payload:
        next_payload["max_completion_tokens"] = max(
            int(next_payload.pop("max_tokens") or MAX_OUTPUT_TOKENS),
            MAX_REASONING_OUTPUT_TOKENS,
        )
        next_payload.pop("temperature", None)
    return next_payload


def _should_swap_max_tokens(status_code: int, body: str) -> bool:
    if status_code != 400:
        return False
    text = (body or "").lower()
    return "max_tokens" in text and "max_completion_tokens" in text


async def chat_complete(
    *,
    provider: str,
    api_key: str,
    system: str,
    user: str,
    model: str | None = None,
    json_mode: bool = False,
    timeout: float = 180.0,
    history: list[dict[str, str]] | None = None,
) -> str:
    spec = PROVIDERS[normalize_provider(provider)]
    key = require_api_key(api_key)
    chosen = (model or "").strip() or spec["model"]
    convo = _chat_messages(user, history)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            if spec["kind"] == "anthropic":
                resp = await client.post(
                    f"{spec['base'].rstrip('/')}/v1/messages",
                    headers={
                        "x-api-key": key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": chosen,
                        "max_tokens": MAX_OUTPUT_TOKENS,
                        "system": system,
                        "messages": convo,
                    },
                )
            else:
                url = f"{spec['base'].rstrip('/')}/chat/completions"
                headers = {
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                }
                payload = openai_chat_payload(
                    model=chosen,
                    system=system,
                    messages=convo,
                    json_mode=json_mode,
                )
                resp = await client.post(url, headers=headers, json=payload)
                if _should_swap_max_tokens(resp.status_code, resp.text):
                    resp = await client.post(
                        url,
                        headers=headers,
                        json=_retarget_token_limit(payload),
                    )
    except httpx.TimeoutException as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="LLM request timed out",
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="LLM request failed",
        ) from exc

    if resp.status_code == 401 or resp.status_code == 403:
        raise HTTPException(status_code=400, detail="LLM API key was rejected")
    if resp.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM request failed: {resp.status_code} {resp.text[:300]}",
        )

    data = resp.json()
    try:
        if spec["kind"] == "anthropic":
            blocks = data.get("content") or []
            parts = [b.get("text", "") for b in blocks if isinstance(b, dict)]
            text = "".join(parts).strip()
        else:
            text = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise HTTPException(status_code=502, detail="LLM returned an unexpected payload") from exc
    if not text or not str(text).strip():
        raise HTTPException(status_code=502, detail="LLM returned empty content")
    return str(text)
