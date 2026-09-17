from __future__ import annotations

import re
import unicodedata
from uuid import UUID, uuid4

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Game, User

HANDLE_MAX = 120
PART_MAX = 48


def slugify(text: str, max_len: int = PART_MAX) -> str:
    normalized = unicodedata.normalize("NFKD", text or "")
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii").lower()
    ascii_text = re.sub(r"[^a-z0-9]+", "-", ascii_text)
    ascii_text = re.sub(r"-{2,}", "-", ascii_text).strip("-")
    return ascii_text[:max_len].strip("-")


def username_slug(user: User | None) -> str:
    if user is None:
        return "player"
    raw = str(getattr(user, "display_name", "") or "").strip()
    if not raw:
        email = str(getattr(user, "email", "") or "")
        raw = email.split("@")[0]
    return slugify(raw) or "player"


def profile_slug_for(user: User | None) -> str:
    stored = str(getattr(user, "profile_slug", "") or "").strip()
    if stored:
        return stored
    return username_slug(user)


def allocate_profile_slug(
    db: Session,
    user: User | None,
    *,
    preferred: str | None = None,
    exclude_id: UUID | None = None,
) -> str:
    base = slugify(preferred or "") or username_slug(user)
    candidate = base
    n = 2
    owner_id = exclude_id or getattr(user, "id", None)
    while True:
        q = db.query(User).filter(User.profile_slug == candidate)
        if owner_id is not None:
            q = q.filter(User.id != owner_id)
        if q.first() is None:
            return candidate
        suffix = f"-{n}"
        candidate = f"{base[: PART_MAX - len(suffix)]}{suffix}"
        n += 1
        if n > 40:
            extra = uuid4().hex[:6]
            return f"{base[: PART_MAX - 7]}-{extra}"


def split_handle(handle: str | None) -> tuple[str, str] | None:
    raw = (handle or "").strip().strip("/")
    if "/" not in raw:
        return None
    user_part, game_part = raw.split("/", 1)
    user_part = user_part.strip("-") or "player"
    game_part = game_part.strip("-") or "game"
    return user_part, game_part


def user_slug_for_game(game: Game, user: User | None) -> str:
    parts = split_handle(getattr(game, "handle", None))
    if parts:
        return parts[0]
    return username_slug(user)


def compose_handle_base(
    user: User | None,
    title: str,
    *,
    user_slug: str | None = None,
    game_slug: str | None = None,
) -> str:
    user_part = slugify(user_slug or "") or username_slug(user)
    game_part = slugify(game_slug or "") or slugify(title) or "game"
    room = HANDLE_MAX - len(user_part) - 1
    if room < 1:
        user_part = user_part[:40] or "player"
        room = HANDLE_MAX - len(user_part) - 1
    game_part = game_part[:room] or "game"
    return f"{user_part}/{game_part}"


def allocate_handle(
    db: Session,
    user: User | None,
    title: str,
    *,
    exclude_id: UUID | None = None,
    user_slug: str | None = None,
    game_slug: str | None = None,
) -> str:
    base = compose_handle_base(user, title, user_slug=user_slug, game_slug=game_slug)
    candidate = base
    n = 2
    while True:
        q = db.query(Game).filter(Game.handle == candidate)
        if exclude_id is not None:
            q = q.filter(Game.id != exclude_id)
        if q.first() is None:
            return candidate
        suffix = f"-{n}"
        cut = HANDLE_MAX - len(suffix)
        candidate = f"{base[:cut]}{suffix}"
        n += 1
        if n > 40:
            extra = uuid4().hex[:6]
            return f"{base[: HANDLE_MAX - 7]}-{extra}"


def migrate_handle(game: Game, user: User | None) -> str | None:
    """Turn a hyphenated username-gamename handle into username/gamename."""
    current = (getattr(game, "handle", None) or "").strip()
    if "/" in current:
        return None
    user_part = username_slug(user)
    game_part = slugify(game.title) or "game"
    if current and current.startswith(user_part + "-"):
        rest = current[len(user_part) + 1 :].strip("-")
        if rest:
            game_part = rest
    return compose_handle_base(user, game.title, user_slug=user_part, game_slug=game_part)


def play_slug(game: Game) -> str:
    return (game.handle or str(game.id)).strip() or str(game.id)


def resolve_game(db: Session, ref: str) -> Game | None:
    raw = str(ref or "").strip()
    if not raw:
        return None
    try:
        game = db.get(Game, UUID(raw))
        if game is not None:
            return game
    except ValueError:
        pass
    lowered = raw.lower().strip("/")
    game = db.query(Game).filter(Game.handle == lowered).first()
    if game is not None:
        return game
    if "/" not in lowered:
        return (
            db.query(Game)
            .filter(func.replace(Game.handle, "/", "-") == lowered)
            .first()
        )
    return None
