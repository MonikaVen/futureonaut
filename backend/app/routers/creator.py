from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import require_roles
from app.database import get_db
from app.models import Game, User, UserRole
from app.schemas import GameAnalyticsDetailOut, GameAnalyticsOut
from app.services.game_analytics import build_game_analytics, build_game_analytics_detail

router = APIRouter(prefix="/creator", tags=["creator"])


@router.get("/analytics", response_model=list[GameAnalyticsOut])
def creator_analytics(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.creator, UserRole.admin)),
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
    user: User = Depends(require_roles(UserRole.creator, UserRole.admin)),
) -> GameAnalyticsDetailOut:
    game = db.get(Game, game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")
    if user.role != UserRole.admin and game.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Not your game")
    return build_game_analytics_detail(db, game_id)
