from __future__ import annotations

from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Game, GameView, PlaySession
from app.schemas import GameAnalyticsOut
from app.services.topics import TOPICS, normalize_topic


def _primary_topic(tags: list[str] | None) -> str:
    for tag in tags or []:
        normalized = normalize_topic(tag)
        if normalized in TOPICS:
            return normalized
    return "AI"


def build_game_analytics(db: Session) -> list[GameAnalyticsOut]:
    games = db.query(Game).order_by(Game.title.asc()).all()
    view_counts = dict(
        db.query(GameView.game_id, func.count(GameView.id))
        .group_by(GameView.game_id)
        .all()
    )
    sessions = db.query(PlaySession).all()

    stats: dict[UUID, dict] = {}
    for game in games:
        stats[game.id] = {
            "game_id": game.id,
            "title": game.title,
            "topic": _primary_topic(game.topic_tags),
            "difficulty": game.difficulty,
            "views": int(view_counts.get(game.id, 0)),
            "plays": 0,
            "players": set(),
            "total_time_ms": 0,
            "levels_sum": 0,
            "levels_n": 0,
            "completed": 0,
        }

    for session in sessions:
        slot = stats.get(session.game_id)
        if slot is None:
            continue
        slot["plays"] += 1
        slot["players"].add(session.user_id)
        slot["total_time_ms"] += session.total_time_ms or 0
        if session.ended_at is not None:
            slot["completed"] += 1
        if session.levels_completed > 0:
            slot["levels_sum"] += session.levels_completed
            slot["levels_n"] += 1

    rows: list[GameAnalyticsOut] = []
    for slot in stats.values():
        plays = slot["plays"]
        rows.append(
            GameAnalyticsOut(
                game_id=slot["game_id"],
                title=slot["title"],
                topic=slot["topic"],
                difficulty=slot["difficulty"],
                views=slot["views"],
                plays=plays,
                unique_players=len(slot["players"]),
                total_time_ms=slot["total_time_ms"],
                avg_time_ms=(slot["total_time_ms"] / plays) if plays else 0.0,
                avg_levels_completed=(slot["levels_sum"] / slot["levels_n"]) if slot["levels_n"] else 0.0,
                completion_rate=(slot["completed"] / plays) if plays else 0.0,
            )
        )

    rows.sort(key=lambda r: (-r.views, -r.plays, r.title.lower()))
    return rows
