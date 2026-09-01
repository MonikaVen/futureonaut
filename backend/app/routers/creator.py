from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import require_roles
from app.database import get_db
from app.models import Game, User, UserRole
from app.schemas import GameAnalyticsOut
from app.services.game_analytics import build_game_analytics

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
