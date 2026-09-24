from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.database import SessionLocal
from app.models import Game, User, UserRole
from app.schemas import CreatorProfileOut, CreatorPublicOut, GameOut
from app.services.avatars import has_user_avatar
from app.services.handles import allocate_profile_slug, profile_slug_for, slugify, split_handle
from app.services.social import enrich_games


def creator_slug(user: User | None) -> str:
    return profile_slug_for(user)


def owner_slug_for_game(game: Game) -> str | None:
    owner = getattr(game, "owner", None)
    if owner is not None:
        return profile_slug_for(owner)
    parts = split_handle(getattr(game, "handle", None))
    return parts[0] if parts else None


def find_user_by_slug(db: Session, slug: str) -> User | None:
    wanted = slugify(slug)
    if not wanted:
        return None
    return db.query(User).filter(User.profile_slug == wanted).first()


def ensure_profile_slug(db: Session, user: User) -> str:
    current = (getattr(user, "profile_slug", None) or "").strip()
    if current:
        return current
    user.profile_slug = allocate_profile_slug(db, user)
    db.add(user)
    db.flush()
    return user.profile_slug


def backfill_profile_slugs() -> None:
    db = SessionLocal()
    try:
        users = (
            db.query(User)
            .filter((User.profile_slug.is_(None)) | (User.profile_slug == ""))
            .order_by(User.created_at.asc())
            .all()
        )
        for user in users:
            ensure_profile_slug(db, user)
        if users:
            db.commit()
    finally:
        db.close()


def _game_counts(db: Session) -> dict:
    return dict(
        db.query(Game.owner_id, func.count(Game.id))
        .filter(Game.owner_id.isnot(None), Game.is_public.is_(True))
        .group_by(Game.owner_id)
        .all()
    )


def public_creator_out(user: User, game_count: int) -> CreatorPublicOut:
    return CreatorPublicOut(
        id=user.id,
        display_name=user.display_name,
        slug=profile_slug_for(user),
        role=user.role,
        has_avatar=has_user_avatar(user.id),
        game_count=game_count,
        created_at=user.created_at,
    )


def list_creators(db: Session) -> list[CreatorPublicOut]:
    counts = _game_counts(db)
    owner_ids = [owner_id for owner_id, total in counts.items() if owner_id and total]
    users = db.query(User).filter(User.id.in_(owner_ids)).all() if owner_ids else []
    extras = (
        db.query(User)
        .filter(User.role.in_([UserRole.creator, UserRole.teacher, UserRole.admin]))
        .all()
    )
    by_id = {user.id: user for user in users}
    for user in extras:
        by_id.setdefault(user.id, user)
    rows = [public_creator_out(user, int(counts.get(user.id, 0))) for user in by_id.values()]
    rows.sort(key=lambda row: (-row.game_count, row.display_name.lower()))
    return rows


def creator_profile(db: Session, slug: str, viewer_id=None) -> CreatorProfileOut | None:
    user = find_user_by_slug(db, slug)
    if user is None:
        return None
    games = (
        db.query(Game)
        .options(joinedload(Game.owner))
        .filter(Game.owner_id == user.id)
        .order_by(Game.created_at.desc())
        .all()
    )
    viewer = db.get(User, viewer_id) if viewer_id else None
    if viewer is None or (viewer.role != UserRole.admin and viewer.id != user.id):
        games = [game for game in games if getattr(game, "is_public", True) is not False]
    enriched: list[GameOut] = enrich_games(db, games, viewer_id)
    return CreatorProfileOut(
        **public_creator_out(user, len(games)).model_dump(),
        games=enriched,
    )
