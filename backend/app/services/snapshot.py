from __future__ import annotations

import io
import json
import logging
import re
from pathlib import Path
from uuid import UUID

from PIL import Image, ImageDraw, ImageFont

from app.config import get_settings
from app.services.storage import game_dir
from app.services.topics import normalize_topic

logger = logging.getLogger(__name__)

PREVIEW_FILENAME = "preview-v2.png"
ICON_FILENAME = "icon.png"
OG_SIZE = (1200, 630)
MAX_ICON_BYTES = 8 * 1024 * 1024
_ICON_CANDIDATES = (
    ICON_FILENAME,
    "icon.jpg",
    "icon.jpeg",
    "icon.webp",
    "icon.gif",
    "poster.png",
    "poster.jpg",
    "poster.jpeg",
    "poster.webp",
    "cover.png",
    "cover.jpg",
    "cover.jpeg",
    "cover.webp",
    "logo.png",
    "logo.jpg",
    "logo.jpeg",
    "logo.webp",
)

_TOPIC_ACCENT = {
    "AI": (62, 200, 232),
    "Physics": (159, 107, 255),
    "Math": (61, 186, 122),
}

_HEX = re.compile(r"#([0-9a-fA-F]{3,8})\b")
_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def preview_path(game_id: UUID) -> Path:
    return game_dir(game_id) / PREVIEW_FILENAME


def screenshot_file(game_id: UUID) -> Path:
    return Path(get_settings().games_dir) / str(game_id) / ICON_FILENAME


def has_game_screenshot(game_id: UUID) -> bool:
    path = screenshot_file(game_id)
    try:
        return path.is_file() and path.stat().st_size > 32
    except OSError:
        return False


def write_game_preview(game) -> Path | None:
    try:
        path = preview_path(game.id)
        path.write_bytes(render_preview_png(game))
        return path
    except Exception:
        logger.exception("Failed to write preview for game %s", getattr(game, "id", "?"))
        return None


def ensure_game_preview(game) -> Path:
    path = preview_path(game.id)
    if path.is_file() and path.stat().st_size > 800:
        return path
    written = write_game_preview(game)
    if written is None or not written.is_file():
        raise FileNotFoundError("Could not build game preview")
    return written


def cover_crop(image: Image.Image, size: tuple[int, int] = OG_SIZE) -> Image.Image:
    target_w, target_h = size
    src = image.convert("RGB")
    src_w, src_h = src.size
    if src_w < 1 or src_h < 1:
        raise ValueError("Invalid image")
    scale = max(target_w / src_w, target_h / src_h)
    new_w = max(target_w, round(src_w * scale))
    new_h = max(target_h, round(src_h * scale))
    resized = src.resize((new_w, new_h), Image.Resampling.LANCZOS)
    left = max(0, (new_w - target_w) // 2)
    top = max(0, (new_h - target_h) // 2)
    return resized.crop((left, top, left + target_w, top + target_h))


def save_game_icon(dest: Path, data: bytes) -> Path:
    if len(data) > MAX_ICON_BYTES:
        raise ValueError("Icon is too large (max 8MB)")
    if len(data) < 32:
        raise ValueError("Icon file is empty")
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
    except Exception as exc:
        raise ValueError("Icon must be a PNG, JPEG, WebP, or GIF image") from exc
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / ICON_FILENAME
    cover_crop(image).save(path, format="PNG", optimize=True)
    return path


def promote_pack_icon(dest: Path) -> Path | None:
    seen: list[Path] = []
    names = {name.lower() for name in _ICON_CANDIDATES}
    for name in _ICON_CANDIDATES:
        path = dest / name
        if path.is_file():
            seen.append(path)
    if not seen:
        for path in dest.rglob("*"):
            if path.is_file() and path.name.lower() in names:
                seen.append(path)
    skip = {PREVIEW_FILENAME.lower(), "preview.png"}
    for path in seen:
        if path.name.lower() in skip:
            continue
        try:
            return save_game_icon(dest, path.read_bytes())
        except (OSError, ValueError):
            continue
    return None


def render_preview_png(game) -> bytes:
    dest = game_dir(game.id)
    palette = _palette(game, dest)
    img = Image.new("RGB", OG_SIZE, palette["bg"])
    draw = ImageDraw.Draw(img)
    photo = _embedded_photo(dest)
    if photo is not None:
        img.paste(cover_crop(photo), (0, 0))
    else:
        _paint_stage(draw, palette)
        content = _content_json(dest)
        kind = (getattr(game, "template_type", None) or "").strip()
        if kind == "quiz" or (content and content.get("questions")):
            _paint_quiz(draw, game, content or {}, palette)
        elif kind == "drag_match" or (content and content.get("pairs")):
            _paint_match(draw, game, content or {}, palette)
        elif kind == "timed_challenge" or (content and content.get("items")):
            _paint_timed(draw, game, content or {}, palette)
        else:
            _paint_html_game(draw, game, dest, palette)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _font(size: int, *, bold: bool = False) -> ImageFont.ImageFont:
    filename = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    for root in (
        Path("/usr/share/fonts/truetype/dejavu"),
        Path("/usr/share/fonts/truetype/liberation"),
        Path("/usr/share/fonts/truetype/freefont"),
    ):
        path = root / filename
        if path.is_file():
            try:
                return ImageFont.truetype(str(path), size)
            except OSError:
                continue
        fallback = root / "DejaVuSans.ttf"
        if fallback.is_file():
            try:
                return ImageFont.truetype(str(fallback), size)
            except OSError:
                continue
    return ImageFont.load_default()


def _hex_to_rgb(value: str, fallback: tuple[int, int, int]) -> tuple[int, int, int]:
    raw = value.strip().lstrip("#")
    if len(raw) == 3:
        raw = "".join(ch * 2 for ch in raw)
    if len(raw) not in {6, 8}:
        return fallback
    try:
        return int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)
    except ValueError:
        return fallback


def _plain(text: str, limit: int = 160) -> str:
    cleaned = _WS.sub(" ", _TAG.sub(" ", text or "")).replace("&nbsp;", " ").strip()
    cleaned = "".join(
        ch
        for ch in cleaned
        if ch.isprintable() and (ch.isalnum() or ch.isspace() or ch in ".,;:!?-'’“”()[]&/%+#·")
    )
    cleaned = _WS.sub(" ", cleaned).strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "…"


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: int, max_lines: int = 3) -> list[str]:
    words = _plain(text, 400).split()
    if not words:
        return []
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        trial = f"{current} {word}"
        if draw.textlength(trial, font=font) <= max_width:
            current = trial
            continue
        lines.append(current)
        current = word
        if len(lines) >= max_lines:
            return lines[:max_lines]
    if len(lines) < max_lines:
        lines.append(current)
    return lines[:max_lines]


def _topic(game) -> str:
    for tag in getattr(game, "topic_tags", None) or []:
        normalized = normalize_topic(tag)
        if normalized in _TOPIC_ACCENT:
            return normalized
    return "AI"


def _content_json(dest: Path) -> dict | None:
    path = dest / "content.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _css_vars(html: str) -> dict[str, str]:
    found: dict[str, str] = {}
    for match in re.finditer(r"--([a-zA-Z0-9-]+)\s*:\s*([^;]+);", html):
        found[match.group(1).lower()] = match.group(2).strip()
    return found


def _luma(rgb: tuple[int, int, int]) -> float:
    return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]


def _palette(game, dest: Path) -> dict[str, tuple[int, int, int]]:
    accent = _TOPIC_ACCENT[_topic(game)]
    palette = {
        "bg": (12, 18, 32),
        "ink": (238, 244, 251),
        "muted": (154, 171, 196),
        "card": (18, 26, 44),
        "line": (40, 64, 92),
        "accent": accent,
        "chrome": (8, 12, 22),
    }
    html_path = dest / (getattr(game, "entry_path", None) or "index.html")
    if html_path.is_file():
        html = html_path.read_text(encoding="utf-8", errors="replace")[:80_000]
        vars_map = _css_vars(html)
        aliases = {
            "bg": "bg",
            "ink": "ink",
            "text": "ink",
            "muted": "muted",
            "card": "card",
            "accent": "accent",
            "border": "line",
        }
        for src, dest_key in aliases.items():
            value = vars_map.get(src, "")
            if value.startswith("#"):
                palette[dest_key] = _hex_to_rgb(value, palette[dest_key])
        body_bg = re.search(r"body\s*\{[^}]*background(?:-color)?:\s*([^;]+)", html, re.I)
        if body_bg:
            hexes = _HEX.findall(body_bg.group(1))
            if hexes:
                palette["bg"] = _hex_to_rgb(hexes[0], palette["bg"])
    if _luma(palette["bg"]) >= 150:
        if _luma(palette["ink"]) >= 140:
            palette["ink"] = (31, 41, 55)
        if _luma(palette["muted"]) >= 150:
            palette["muted"] = (107, 114, 128)
        if _luma(palette["line"]) >= 200:
            palette["line"] = (209, 213, 219)
        if _luma(palette["card"]) >= 230:
            palette["card"] = (255, 255, 255)
        palette["chrome"] = (18, 24, 36)
    elif _luma(palette["ink"]) < 90:
        palette["ink"] = (238, 244, 251)
    return palette


def _embedded_photo(dest: Path) -> Image.Image | None:
    skip = {PREVIEW_FILENAME.lower(), "preview.png"}
    for name in (ICON_FILENAME, "snapshot.png", "screenshot.png", "poster.png", "cover.png", "og.png"):
        path = dest / name
        if not path.is_file() or path.name.lower() in skip:
            continue
        try:
            return Image.open(path).convert("RGB")
        except OSError:
            continue
    images: list[Path] = []
    for pattern in ("*.png", "*.jpg", "*.jpeg", "*.webp"):
        images.extend(p for p in dest.glob(pattern) if p.name.lower() not in skip)
    images.sort(key=lambda p: p.stat().st_size, reverse=True)
    for path in images[:6]:
        if path.stat().st_size < 8_000:
            continue
        try:
            return Image.open(path).convert("RGB")
        except OSError:
            continue
    return None


def _paint_stage(draw: ImageDraw.ImageDraw, palette: dict) -> None:
    draw.rectangle((0, 0, 1200, 630), fill=palette["bg"])
    draw.ellipse((860, -140, 1380, 380), fill=tuple(min(255, c + 18) for c in palette["bg"]))
    draw.ellipse((-160, 360, 360, 860), fill=tuple(max(0, c - 10) for c in palette["bg"]))
    draw.rounded_rectangle((36, 28, 1164, 602), 28, fill=palette["chrome"])
    draw.rounded_rectangle((48, 64, 1152, 590), 22, fill=palette["bg"])


def _paint_chrome(draw: ImageDraw.ImageDraw, game, palette: dict) -> None:
    title_font = _font(22, bold=True)
    brand_font = _font(16, bold=True)
    draw.ellipse((72, 40, 88, 56), fill=(255, 95, 86))
    draw.ellipse((98, 40, 114, 56), fill=(255, 189, 46))
    draw.ellipse((124, 40, 140, 56), fill=(39, 201, 64))
    draw.text((168, 38), "FUTUREONAUT", font=brand_font, fill=palette["muted"])
    title = _plain(getattr(game, "title", "") or "Game", 48)
    draw.text((72, 548), title, font=title_font, fill=palette["ink"])
    chip = f"{_topic(game)}  ·  LV {getattr(game, 'difficulty', 1)}"
    chip_font = _font(16, bold=True)
    width = int(draw.textlength(chip, font=chip_font)) + 28
    draw.rounded_rectangle((72, 500, 72 + width, 534), 14, fill=palette["accent"])
    draw.text((86, 506), chip, font=chip_font, fill=(8, 12, 20))


def _paint_quiz(draw: ImageDraw.ImageDraw, game, content: dict, palette: dict) -> None:
    title_font = _font(34, bold=True)
    body_font = _font(22)
    opt_font = _font(20)
    title = _plain(content.get("title") or getattr(game, "title", "") or "Quiz", 50)
    draw.text((88, 92), title, font=title_font, fill=palette["ink"])
    questions = content.get("questions") or []
    prompt = "Choose the best answer"
    options = ["Option A", "Option B", "Option C", "Option D"]
    if questions and isinstance(questions[0], dict):
        prompt = str(questions[0].get("prompt") or prompt)
        parsed = []
        for opt in (questions[0].get("options") or [])[:4]:
            if isinstance(opt, dict):
                parsed.append(str(opt.get("text") or opt.get("label") or ""))
            else:
                parsed.append(str(opt))
        if parsed:
            options = parsed
    y = 148
    for line in _wrap(draw, prompt, body_font, 1000, 2):
        draw.text((88, y), line, font=body_font, fill=palette["muted"])
        y += 34
    top = max(y + 16, 220)
    for i, option in enumerate(options[:4]):
        yy = top + i * 68
        draw.rounded_rectangle((88, yy, 1112, yy + 56), 14, outline=palette["line"], width=2, fill=palette["card"])
        draw.text((112, yy + 14), _plain(option, 70), font=opt_font, fill=palette["ink"])


def _paint_match(draw: ImageDraw.ImageDraw, game, content: dict, palette: dict) -> None:
    title_font = _font(34, bold=True)
    label_font = _font(18, bold=True)
    item_font = _font(20)
    draw.text(
        (88, 92),
        _plain(content.get("title") or getattr(game, "title", "") or "Match", 50),
        font=title_font,
        fill=palette["ink"],
    )
    pairs = content.get("pairs") or []
    lefts: list[str] = []
    rights: list[str] = []
    for pair in pairs[:4]:
        if isinstance(pair, dict):
            lefts.append(str(pair.get("left") or ""))
            rights.append(str(pair.get("right") or ""))
    if not lefts:
        lefts, rights = ["Term"], ["Meaning"]
    draw.rounded_rectangle((88, 168, 572, 470), 18, fill=palette["card"], outline=palette["line"], width=2)
    draw.rounded_rectangle((628, 168, 1112, 470), 18, fill=palette["card"], outline=palette["line"], width=2)
    draw.text((112, 186), "TERMS", font=label_font, fill=palette["accent"])
    draw.text((652, 186), "MEANINGS", font=label_font, fill=palette["accent"])
    for i, (left, right) in enumerate(zip(lefts, rights)):
        y = 236 + i * 54
        draw.rounded_rectangle((108, y, 552, y + 44), 12, fill=palette["bg"], outline=palette["line"])
        draw.rounded_rectangle((648, y, 1092, y + 44), 12, fill=palette["bg"], outline=palette["line"])
        draw.text((124, y + 10), _plain(left, 28), font=item_font, fill=palette["ink"])
        draw.text((664, y + 10), _plain(right, 28), font=item_font, fill=palette["ink"])


def _paint_timed(draw: ImageDraw.ImageDraw, game, content: dict, palette: dict) -> None:
    title_font = _font(34, bold=True)
    body_font = _font(22)
    draw.text(
        (88, 92),
        _plain(content.get("title") or getattr(game, "title", "") or "Timed challenge", 50),
        font=title_font,
        fill=palette["ink"],
    )
    items = content.get("items") or []
    prompt = "Beat the clock"
    if items and isinstance(items[0], dict):
        prompt = str(items[0].get("prompt") or items[0].get("question") or prompt)
    elif items:
        prompt = str(items[0])
    draw.ellipse((980, 96, 1110, 226), outline=palette["accent"], width=10)
    draw.text((1012, 140), "30s", font=_font(28, bold=True), fill=palette["accent"])
    y = 180
    for line in _wrap(draw, prompt, body_font, 820, 3):
        draw.text((88, y), line, font=body_font, fill=palette["ink"])
        y += 36
    draw.rounded_rectangle((88, 340, 900, 410), 14, fill=palette["card"], outline=palette["line"], width=2)
    draw.text((112, 360), "Type your answer…", font=body_font, fill=palette["muted"])
    draw.rounded_rectangle((88, 434, 280, 492), 14, fill=palette["accent"])
    draw.text((118, 448), "Submit", font=_font(22, bold=True), fill=(8, 12, 20))


def _paint_html_game(draw: ImageDraw.ImageDraw, game, dest: Path, palette: dict) -> None:
    html_path = dest / (getattr(game, "entry_path", None) or "index.html")
    html = html_path.read_text(encoding="utf-8", errors="replace")[:80_000] if html_path.is_file() else ""
    title_font = _font(30, bold=True)
    body_font = _font(20)
    brand_match = re.search(r'class="brand"[^>]*>(.*?)</div>', html, re.I | re.S)
    brand = _plain(brand_match.group(1) if brand_match else (getattr(game, "title", "") or "Game"), 28)
    draw.rounded_rectangle((88, 92, 360, 470), 18, fill=tuple(max(0, c - 12) for c in palette["card"]))
    by = 118
    for line in brand.replace("<br>", "\n").split("\n")[:3]:
        text = _plain(line, 18)
        if not text:
            continue
        draw.text((112, by), text, font=_font(20, bold=True), fill=palette["ink"])
        by += 28
    draw.ellipse((150, 220, 298, 368), fill=palette["accent"])
    draw.text((188, 268), "▶", font=_font(42, bold=True), fill=(8, 12, 20))
    heading = _plain(getattr(game, "title", "") or "Play", 42)
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.I | re.S)
    if h1:
        heading = _plain(h1.group(1), 42) or heading
    draw.text((396, 108), heading, font=title_font, fill=palette["ink"])
    blurb = _plain(getattr(game, "description", "") or "", 140)
    speech = re.search(r'id="(?:sideSpeech|missionText)"[^>]*>(.*?)<', html, re.I | re.S)
    if speech:
        blurb = _plain(speech.group(1), 140) or blurb
    y = 160
    for line in _wrap(draw, blurb or "Interactive learning game", body_font, 720, 3):
        draw.text((396, y), line, font=body_font, fill=palette["muted"])
        y += 32
    buttons = [_plain(match, 28) for match in re.findall(r"<button[^>]*>(.*?)</button>", html, re.I | re.S)[:4]]
    choices = [
        _plain(match, 28)
        for match in re.findall(r'class="(?:choice|token|item|opt)[^"]*"[^>]*>(.*?)<', html, re.I | re.S)[:4]
    ]
    labels = [item for item in (choices or buttons) if item][:3] or ["Play", "Hint", "Next"]
    top = max(y + 24, 280)
    for i, label in enumerate(labels):
        yy = top + i * 62
        draw.rounded_rectangle((396, yy, 1110, yy + 50), 14, fill=palette["card"], outline=palette["line"], width=2)
        draw.text((420, yy + 12), label, font=body_font, fill=palette["ink"])
