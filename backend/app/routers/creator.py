from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import require_game_author
from app.database import get_db
from app.models import Game, User, UserRole
from app.schemas import GameAnalyticsDetailOut, GameAnalyticsOut, CreatorStyleOut, CreatorStyleUpdate
from app.services.game_analytics import build_game_analytics, build_game_analytics_detail
from app.services.prompts import (
    get_or_create_platform_settings,
    normalize_style_source,
    resolve_style_guidelines,
)

router = APIRouter(prefix="/creator", tags=["creator"])


@router.get("/analytics", response_model=list[GameAnalyticsOut])
def creator_analytics(
    db: Session = Depends(get_db),
    user: User = Depends(require_game_author),
) -> list[GameAnalyticsOut]:
    owned_ids = {g.id for g in db.query(Game.id).filter(Game.owner_id == user.id).all()}
    all_stats = build_game_analytics(db)
    if user.role == UserRole.admin:
        return all_stats
    return [row for row in all_stats if row.game_id in owned_ids]


@router.get("/analytics/{game_id}", response_model=GameAnalyticsDetailOut)
def creator_analytics_detail(
    game_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_game_author),
) -> GameAnalyticsDetailOut:
    game = db.get(Game, game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")
    if user.role != UserRole.admin and game.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Not your game")
    return build_game_analytics_detail(db, game_id, include_player_emails=user.role == UserRole.admin)


@router.get("/style", response_model=CreatorStyleOut)
def get_creator_style(
    db: Session = Depends(get_db),
    user: User = Depends(require_game_author),
) -> CreatorStyleOut:
    settings = get_or_create_platform_settings(db)
    source = normalize_style_source(getattr(user, "style_source", None))
    return CreatorStyleOut(
        source=source,
        custom_guidelines=(getattr(user, "style_guidelines", None) or ""),
        default_guidelines=settings.style_guidelines,
        effective_guidelines=resolve_style_guidelines(settings, user),
    )


@router.put("/style", response_model=CreatorStyleOut)
def update_creator_style(
    body: CreatorStyleUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_game_author),
) -> CreatorStyleOut:
    source = normalize_style_source(body.source)
    user.style_source = source
    user.style_guidelines = (body.custom_guidelines or "").strip() or None
    db.commit()
    db.refresh(user)
    settings = get_or_create_platform_settings(db)
    return CreatorStyleOut(
        source=source,
        custom_guidelines=user.style_guidelines or "",
        default_guidelines=settings.style_guidelines,
        effective_guidelines=resolve_style_guidelines(settings, user),
    )
