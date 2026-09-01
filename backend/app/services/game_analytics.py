from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models import EventType, Game, GameView, PlaySession, SessionEvent, User
from app.schemas import (
    DailyViewsOut,
    GameAnalyticsDetailOut,
    GameAnalyticsOut,
    LevelFunnelOut,
    RecentSessionOut,
    TaskStatOut,
)
from app.services.topics import TOPICS, normalize_topic


def _primary_topic(tags: list[str] | None) -> str:
    for tag in tags or []:
        normalized = normalize_topic(tag)
        if normalized in TOPICS:
            return normalized
    return "AI"


def _slot_from_game(game: Game, views: int, unique_visitors: int) -> dict:
    return {
        "game_id": game.id,
        "title": game.title,
        "topic": _primary_topic(game.topic_tags),
        "difficulty": game.difficulty,
        "views": views,
        "unique_visitors": unique_visitors,
        "plays": 0,
        "players": set(),
        "total_time_ms": 0,
        "levels_sum": 0,
        "levels_n": 0,
        "completed": 0,
        "points_sum": 0,
        "attempts": 0,
        "correct": 0,
    }


def _slot_to_summary(slot: dict) -> GameAnalyticsOut:
    plays = slot["plays"]
    attempts = slot["attempts"]
    views = slot["views"]
    unique_visitors = slot["unique_visitors"]
    return GameAnalyticsOut(
        game_id=slot["game_id"],
        title=slot["title"],
        topic=slot["topic"],
        difficulty=slot["difficulty"],
        views=views,
        unique_visitors=unique_visitors,
        plays=plays,
        unique_players=len(slot["players"]),
        view_to_play_rate=(plays / views) if views else 0.0,
        total_time_ms=slot["total_time_ms"],
        avg_time_ms=(slot["total_time_ms"] / plays) if plays else 0.0,
        avg_levels_completed=(slot["levels_sum"] / slot["levels_n"]) if slot["levels_n"] else 0.0,
        completion_rate=(slot["completed"] / plays) if plays else 0.0,
        avg_accuracy=(slot["correct"] / attempts) if attempts else 0.0,
        avg_score=(slot["points_sum"] / plays) if plays else 0.0,
    )


def _aggregate_slots(db: Session) -> dict[UUID, dict]:
    games = db.query(Game).order_by(Game.title.asc()).all()
    view_counts = dict(
        db.query(GameView.game_id, func.count(GameView.id)).group_by(GameView.game_id).all()
    )
    unique_by_game: dict[UUID, set[str]] = defaultdict(set)
    for view in db.query(GameView.game_id, GameView.user_id, GameView.visitor_id, GameView.id).all():
        game_id, user_id, visitor_id, view_id = view
        key = visitor_id or (str(user_id) if user_id else str(view_id))
        unique_by_game[game_id].add(key)

    sessions = db.query(PlaySession).all()
    stats: dict[UUID, dict] = {}
    for game in games:
        stats[game.id] = _slot_from_game(
            game,
            int(view_counts.get(game.id, 0)),
            len(unique_by_game.get(game.id, set())),
        )

    for session in sessions:
        slot = stats.get(session.game_id)
        if slot is None:
            continue
        slot["plays"] += 1
        player_key = str(session.user_id) if session.user_id else (session.visitor_id or str(session.id))
        slot["players"].add(player_key)
        slot["total_time_ms"] += session.total_time_ms or 0
        slot["points_sum"] += session.total_points or 0
        slot["attempts"] += session.attempt_count or 0
        slot["correct"] += session.correct_count or 0
        if session.ended_at is not None:
            slot["completed"] += 1
        if session.levels_completed > 0:
            slot["levels_sum"] += session.levels_completed
            slot["levels_n"] += 1

    return stats


def build_game_analytics(db: Session) -> list[GameAnalyticsOut]:
    rows = [_slot_to_summary(slot) for slot in _aggregate_slots(db).values()]
    rows.sort(key=lambda r: (-r.views, -r.plays, r.title.lower()))
    return rows


def _level_funnel(sessions: list[PlaySession], events: list[SessionEvent]) -> list[LevelFunnelOut]:
    max_level = 0
    session_peak: dict[UUID, int] = {}
    for session in sessions:
        peak = session.levels_completed or 0
        session_peak[session.id] = peak
        if session.total_levels:
            max_level = max(max_level, session.total_levels)
        max_level = max(max_level, peak)

    for event in events:
        if event.type != EventType.level_complete:
            continue
        level = int(event.payload.get("level") or 0)
        total = int(event.payload.get("totalLevels") or event.payload.get("total_levels") or 0)
        if level > session_peak.get(event.session_id, 0):
            session_peak[event.session_id] = level
        max_level = max(max_level, level, total)

    if max_level <= 0 and sessions:
        max_level = 1

    plays = len(sessions)
    funnel: list[LevelFunnelOut] = []
    for level in range(1, max_level + 1):
        reached = sum(1 for peak in session_peak.values() if peak >= level)
        funnel.append(
            LevelFunnelOut(
                level=level,
                sessions_reached=reached,
                reach_rate=(reached / plays) if plays else 0.0,
            )
        )
    return funnel


def _task_stats(events: list[SessionEvent]) -> list[TaskStatOut]:
    buckets: dict[str, dict[str, float]] = defaultdict(lambda: {"count": 0, "duration": 0})
    for event in events:
        if event.type != EventType.task_time:
            continue
        if event.payload.get("phase") != "end":
            continue
        task_id = str(event.payload.get("taskId") or "default")
        buckets[task_id]["count"] += 1
        buckets[task_id]["duration"] += float(event.payload.get("durationMs") or 0)

    rows = []
    for task_id, data in buckets.items():
        count = int(data["count"])
        rows.append(
            TaskStatOut(
                task_id=task_id,
                completions=count,
                avg_duration_ms=(data["duration"] / count) if count else 0.0,
            )
        )
    rows.sort(key=lambda r: (-r.completions, r.task_id))
    return rows


def _daily_views(views: list[GameView], days: int = 14) -> list[DailyViewsOut]:
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=days - 1)
    counts: dict[date, int] = defaultdict(int)
    for view in views:
        day = view.viewed_at.date() if view.viewed_at.tzinfo else view.viewed_at.replace(tzinfo=timezone.utc).date()
        if day >= start:
            counts[day] += 1
    return [
        DailyViewsOut(date=day.isoformat(), views=counts.get(day, 0))
        for day in (start + timedelta(days=i) for i in range(days))
    ]


def build_game_analytics_detail(db: Session, game_id: UUID) -> GameAnalyticsDetailOut:
    game = db.get(Game, game_id)
    if game is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Game not found")

    slots = _aggregate_slots(db)
    summary = _slot_to_summary(slots[game_id])

    sessions = (
        db.query(PlaySession)
        .options(joinedload(PlaySession.user))
        .filter(PlaySession.game_id == game_id)
        .order_by(PlaySession.started_at.desc())
        .all()
    )
    session_ids = [s.id for s in sessions]
    events: list[SessionEvent] = []
    if session_ids:
        events = (
            db.query(SessionEvent)
            .filter(SessionEvent.session_id.in_(session_ids))
            .order_by(SessionEvent.ts.asc())
            .all()
        )

    views = (
        db.query(GameView)
        .filter(GameView.game_id == game_id)
        .order_by(GameView.viewed_at.desc())
        .limit(5000)
        .all()
    )

    event_counts: dict[str, int] = defaultdict(int)
    for event in events:
        event_counts[event.type.value] += 1

    recent = []
    for session in sessions[:25]:
        user = session.user
        attempts = session.attempt_count or 0
        recent.append(
            RecentSessionOut(
                session_id=session.id,
                user_email=user.email if user else "unknown",
                started_at=session.started_at,
                duration_ms=session.total_time_ms or 0,
                levels_completed=session.levels_completed or 0,
                total_levels=session.total_levels,
                completed=session.ended_at is not None,
                points=session.total_points or 0,
                accuracy=(session.correct_count / attempts) if attempts else 0.0,
            )
        )

    return GameAnalyticsDetailOut(
        **summary.model_dump(),
        level_funnel=_level_funnel(sessions, events),
        task_stats=_task_stats(events),
        daily_views=_daily_views(views),
        recent_sessions=recent,
        event_counts=dict(event_counts),
    )
