from __future__ import annotations

import io
from pathlib import Path
from uuid import UUID

from PIL import Image, ImageDraw

from app.config import get_settings

AVATAR_SIZE = 512
MAX_AVATAR_BYTES = 8 * 1024 * 1024
OG_SIZE = (1200, 630)


def avatars_root() -> Path:
    root = Path(get_settings().games_dir).resolve().parent / "avatars"
    root.mkdir(parents=True, exist_ok=True)
    return root


def avatar_file(user_id: UUID) -> Path:
    return avatars_root() / f"{user_id}.png"


def has_user_avatar(user_id: UUID) -> bool:
    path = avatar_file(user_id)
    try:
        return path.is_file() and path.stat().st_size > 32
    except OSError:
        return False


def avatar_public_path(user_id: UUID) -> str | None:
    if not has_user_avatar(user_id):
        return None
    try:
        version = int(avatar_file(user_id).stat().st_mtime)
    except OSError:
        version = 1
    return f"/api/users/{user_id}/avatar?v={version}"


def save_user_avatar(user_id: UUID, data: bytes) -> Path:
    from app.services.snapshot import cover_crop

    if len(data) > MAX_AVATAR_BYTES:
        raise ValueError("Avatar is too large (max 8MB)")
    if len(data) < 32:
        raise ValueError("Avatar file is empty")
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
    except Exception as exc:
        raise ValueError("Avatar must be a PNG, JPEG, WebP, or GIF image") from exc
    square = cover_crop(image, (AVATAR_SIZE, AVATAR_SIZE))
    path = avatar_file(user_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    square.save(path, format="PNG", optimize=True)
    return path


def delete_user_avatar(user_id: UUID) -> None:
    path = avatar_file(user_id)
    try:
        if path.is_file():
            path.unlink()
    except OSError:
        return


def render_creator_card_png(user, *, game_count: int) -> bytes:
    from app.services.snapshot import cover_crop, _font

    img = Image.new("RGB", OG_SIZE, (5, 8, 16))
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, 1200, 6), fill=(0, 212, 255))
    draw.ellipse((920, -40, 1280, 320), fill=(0, 40, 70))
    draw.ellipse((-80, 400, 280, 760), fill=(40, 20, 80))

    name = (getattr(user, "display_name", None) or "Creator").strip() or "Creator"
    portrait = Image.new("RGB", (220, 220), (13, 33, 55))
    if has_user_avatar(user.id):
        try:
            photo = Image.open(avatar_file(user.id))
            portrait = cover_crop(photo, (220, 220))
        except OSError:
            pass
    else:
        pdraw = ImageDraw.Draw(portrait)
        initials = "".join(part[0] for part in name.split()[:2] if part).upper() or "F"
        pdraw.text((110, 110), initials, fill=(0, 212, 255), font=_font(72, bold=True), anchor="mm")
    mask = Image.new("L", (220, 220), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, 219, 219), fill=255)
    img.paste(portrait, (72, 160), mask)

    draw.text((72, 72), "FUTUREONAUT", fill=(122, 139, 168), font=_font(22, bold=True))
    draw.text((330, 210), name[:42], fill=(232, 244, 255), font=_font(48, bold=True))
    count_label = "1 game" if game_count == 1 else f"{game_count} games"
    draw.text((330, 280), f"{count_label} to play and share", fill=(158, 180, 208), font=_font(28))
    draw.text((72, 540), "Creator page", fill=(90, 109, 136), font=_font(22))

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
