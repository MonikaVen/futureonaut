from __future__ import annotations

import re
import unicodedata
from uuid import UUID, uuid4

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


def compose_handle_base(user: User | None, title: str) -> str:
    base = f"{username_slug(user)}-{slugify(title) or 'game'}"
    return base[:HANDLE_MAX].strip("-") or "player-game"


def allocate_handle(
    db: Session,
    user: User | None,
    title: str,
    *,
    exclude_id: UUID | None = None,
) -> str:
    base = compose_handle_base(user, title)
    candidate = base
    n = 2
    while True:
        q = db.query(Game).filter(Game.handle == candidate)
        if exclude_id is not None:
            q = q.filter(Game.id != exclude_id)
        if q.first() is None:
            return candidate
        suffix = f"-{n}"
        candidate = f"{base[: HANDLE_MAX - len(suffix)]}{suffix}"
        n += 1
        if n > 40:
            extra = uuid4().hex[:6]
            return f"{base[: HANDLE_MAX - 7]}-{extra}"


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
    return db.query(Game).filter(Game.handle == raw.lower()).first()
