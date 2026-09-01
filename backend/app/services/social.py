from __future__ import annotations

from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Game, GameComment, GameLike
from app.schemas import GameOut
from app.services.recommendations import game_to_out


def _social_maps(
    db: Session, game_ids: list[UUID], user_id: UUID | None
) -> tuple[dict[UUID, int], dict[UUID, int], set[UUID]]:
    if not game_ids:
        return {}, {}, set()
    like_counts = dict(
        db.query(GameLike.game_id, func.count(GameLike.id))
        .filter(GameLike.game_id.in_(game_ids))
        .group_by(GameLike.game_id)
        .all()
    )
    comment_counts = dict(
        db.query(GameComment.game_id, func.count(GameComment.id))
        .filter(GameComment.game_id.in_(game_ids))
        .group_by(GameComment.game_id)
        .all()
    )
    liked_ids: set[UUID] = set()
    if user_id:
        liked_ids = {
            row[0]
            for row in db.query(GameLike.game_id)
            .filter(GameLike.user_id == user_id, GameLike.game_id.in_(game_ids))
            .all()
        }
    return like_counts, comment_counts, liked_ids


def enrich_games(db: Session, games: list[Game], user_id: UUID | None = None) -> list[GameOut]:
    ids = [g.id for g in games]
    like_counts, comment_counts, liked_ids = _social_maps(db, ids, user_id)
    out: list[GameOut] = []
    for game in games:
        base = game_to_out(game)
        out.append(
            GameOut(
                **base.model_dump(),
                like_count=int(like_counts.get(game.id, 0)),
                comment_count=int(comment_counts.get(game.id, 0)),
                liked_by_me=game.id in liked_ids,
            )
        )
    return out
