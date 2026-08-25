from __future__ import annotations

import json
import re
from pathlib import Path

import httpx
from bs4 import BeautifulSoup, NavigableString, Comment
from langdetect import DetectorFactory, LangDetectException, detect

from app.config import get_settings

DetectorFactory.seed = 0

SUPPORTED_LANGS = {
    "en": "English",
    "lt": "Lietuvių",
    "de": "Deutsch",
    "es": "Español",
    "fr": "Français",
    "pl": "Polski",
}

_LT_MARKERS = (
    " ir ",
    " yra ",
    " kad ",
    " tai ",
    " žaid",
    "pasirink",
    "teising",
    "neteising",
    "klausim",
    "atsakym",
    "pradėti",
    "toliau",
    "taškai",
)
_SKIP_TAGS = {"script", "style", "code", "pre", "noscript", "svg", "path"}


def detect_language(*texts: str) -> str:
    blob = " ".join(t for t in texts if t).strip()
    if not blob:
        return "en"
    lower = blob.lower()
    lt_hits = sum(1 for m in _LT_MARKERS if m in lower)
    if lt_hits >= 2 or re.search(r"[ąčęėįšųūž]", lower):
        return "lt"
    sample = blob[:4000]
    try:
        code = detect(sample)
    except LangDetectException:
        return "en"
    if code not in SUPPORTED_LANGS:
        return "en"
    return code


def extract_visible_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(_SKIP_TAGS):
        tag.decompose()
    return " ".join(soup.stripped_strings)


def _collect_nodes(soup: BeautifulSoup) -> list[tuple[str, object, str]]:
    """Return list of (kind, target, text). kind is 'text' or attr name."""
    items: list[tuple[str, object, str]] = []
    for node in soup.descendants:
        if isinstance(node, Comment):
            continue
        if isinstance(node, NavigableString):
            parent = node.parent
            if parent is None or parent.name in _SKIP_TAGS:
                continue
            text = str(node)
            if text.strip() and not text.isspace():
                items.append(("text", node, text))
        elif getattr(node, "name", None) and node.name not in _SKIP_TAGS:
            for attr in ("title", "alt", "placeholder", "aria-label"):
                val = node.get(attr)
                if val and str(val).strip():
                    items.append((attr, node, str(val)))
            if node.name in {"button", "option"} and node.get("value") and str(node.get("value")).strip():
                # only when value looks like human text
                val = str(node.get("value"))
                if re.search(r"[A-Za-zĄ-ž]", val):
                    items.append(("value", node, val))
    return items


async def translate_strings(strings: list[str], source: str, target: str) -> dict[str, str]:
    unique = []
    seen = set()
    for s in strings:
        key = s.strip()
        if not key or key in seen:
            continue
        # skip pure numbers / punctuation
        if re.fullmatch(r"[\d\s\-–—./:+%]+", key):
            continue
        seen.add(key)
        unique.append(s if s.strip() == key else s)

    # Use stripped keys for translation map
    keys = list(dict.fromkeys(s.strip() for s in unique))
    if not keys or source == target:
        return {k: k for k in keys}

    settings = get_settings()
    if settings.openai_api_key:
        return await _translate_openai(keys, source, target)
    return await _translate_mymemory(keys, source, target)


async def _translate_openai(keys: list[str], source: str, target: str) -> dict[str, str]:
    settings = get_settings()
    mapping: dict[str, str] = {}
    # chunk to keep prompts small
    chunk_size = 40
    async with httpx.AsyncClient(timeout=90.0) as client:
        for i in range(0, len(keys), chunk_size):
            chunk = keys[i : i + chunk_size]
            payload = {
                "model": settings.openai_model,
                "temperature": 0.1,
                "response_format": {"type": "json_object"},
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You translate UI strings for educational games. "
                            "Return JSON object {\"items\":[{\"src\":\"...\",\"dst\":\"...\"}]}. "
                            "Preserve numbers, formulas, code identifiers, and names like Liucian/Lucian. "
                            "Do not add explanations."
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "source_lang": source,
                                "target_lang": target,
                                "strings": chunk,
                            }
                        ),
                    },
                ],
            }
            resp = await client.post(
                f"{settings.openai_base_url.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.openai_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            if resp.status_code >= 400:
                # fall back for this chunk
                partial = await _translate_mymemory(chunk, source, target)
                mapping.update(partial)
                continue
            data = resp.json()
            try:
                raw = json.loads(data["choices"][0]["message"]["content"])
                items = raw.get("items") or []
                if isinstance(raw, dict) and not items:
                    # maybe direct map
                    for k, v in raw.items():
                        if k != "items" and isinstance(v, str):
                            mapping[k] = v
                for item in items:
                    src = item.get("src")
                    dst = item.get("dst")
                    if src and dst:
                        mapping[src] = dst
            except (KeyError, IndexError, json.JSONDecodeError, TypeError):
                partial = await _translate_mymemory(chunk, source, target)
                mapping.update(partial)
    for k in keys:
        mapping.setdefault(k, k)
    return mapping


async def _translate_mymemory(keys: list[str], source: str, target: str) -> dict[str, str]:
    mapping: dict[str, str] = {}
    async with httpx.AsyncClient(timeout=30.0) as client:
        for key in keys:
            try:
                resp = await client.get(
                    "https://api.mymemory.translated.net/get",
                    params={"q": key[:450], "langpair": f"{source}|{target}"},
                )
                if resp.status_code >= 400:
                    mapping[key] = key
                    continue
                data = resp.json()
                translated = (
                    data.get("responseData", {}).get("translatedText")
                    or key
                )
                # MyMemory sometimes returns identical or error strings
                if "MYMEMORY WARNING" in translated.upper():
                    mapping[key] = key
                else:
                    mapping[key] = translated
            except Exception:
                mapping[key] = key
    return mapping


def apply_translations(html: str, mapping: dict[str, str]) -> str:
    if not mapping:
        return html
    soup = BeautifulSoup(html, "lxml")
    for kind, target, text in _collect_nodes(soup):
        stripped = text.strip()
        translated = mapping.get(stripped)
        if not translated or translated == stripped:
            continue
        if kind == "text":
            # preserve surrounding whitespace
            leading = text[: len(text) - len(text.lstrip())]
            trailing = text[len(text.rstrip()) :]
            target.replace_with(NavigableString(f"{leading}{translated}{trailing}"))
        else:
            target[kind] = translated
    # BeautifulSoup may wrap with html/body; prefer original structure
    body = soup.body
    if body and soup.html:
        # reconstruct roughly
        head = soup.head
        head_html = "".join(str(x) for x in head.contents) if head else ""
        body_html = "".join(str(x) for x in body.contents)
        doctype = "<!DOCTYPE html>\n"
        return f"{doctype}<html lang=\"{soup.html.get('lang') or ''}\"><head>{head_html}</head><body>{body_html}</body></html>"
    return str(soup)


async def translate_html(html: str, source: str, target: str) -> str:
    if source == target:
        return html
    nodes = _collect_nodes(BeautifulSoup(html, "lxml"))
    strings = [text for _, _, text in nodes]
    mapping = await translate_strings(strings, source, target)
    return apply_translations(html, mapping)


async def translate_plain(text: str, source: str, target: str) -> str:
    if not text or source == target:
        return text
    mapping = await translate_strings([text], source, target)
    return mapping.get(text.strip(), text)


def i18n_cache_path(game_dir: Path, lang: str, entry_path: str) -> Path:
    return game_dir / "i18n" / lang / entry_path
