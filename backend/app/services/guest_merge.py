from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.limits import MAX_DURATION_MS, MAX_GAME_LEVEL, MAX_SCORE_DELTA, bounded_int
from app.models import EventType, PlaySession


def apply_session_event(session: PlaySession, event_type: EventType, payload: dict) -> None:
    if event_type == EventType.score:
        session.total_points += bounded_int(
            payload.get("delta"), lo=-MAX_SCORE_DELTA, hi=MAX_SCORE_DELTA
        )
    elif event_type == EventType.answer:
        session.attempt_count += 1
        if payload.get("correct"):
            session.correct_count += 1
    elif event_type == EventType.task_time:
        if payload.get("phase") == "end":
            session.total_time_ms += bounded_int(payload.get("durationMs"), hi=MAX_DURATION_MS)
    elif event_type == EventType.level_complete:
        level = bounded_int(payload.get("level"), hi=MAX_GAME_LEVEL)
        total = bounded_int(
            payload.get("totalLevels") or payload.get("total_levels"), hi=MAX_GAME_LEVEL
        )
        if level > session.levels_completed:
            session.levels_completed = level
        if total > 0:
            session.total_levels = total
        if payload.get("solved") and total > 0 and level >= total and session.ended_at is None:
            session.ended_at = datetime.now(timezone.utc)
    elif event_type == EventType.milestone:
        level = bounded_int(payload.get("level"), hi=MAX_GAME_LEVEL)
        total = bounded_int(
            payload.get("totalLevels") or payload.get("total_levels"), hi=MAX_GAME_LEVEL
        )
        if level > session.levels_completed:
            session.levels_completed = level
        if total > 0:
            session.total_levels = total
    elif event_type == EventType.complete:
        session.ended_at = datetime.now(timezone.utc)
        if payload.get("durationMs") and session.total_time_ms == 0:
            session.total_time_ms = bounded_int(payload.get("durationMs"), hi=MAX_DURATION_MS)
        levels_done = bounded_int(
            payload.get("levelsCompleted") or payload.get("levels_completed"),
            hi=MAX_GAME_LEVEL,
        )
        total = bounded_int(
            payload.get("totalLevels") or payload.get("total_levels"), hi=MAX_GAME_LEVEL
        )
        if levels_done > session.levels_completed:
            session.levels_completed = levels_done
        if total > 0:
            session.total_levels = total
        elif session.levels_completed > 0 and session.total_levels is None:
            session.total_levels = min(session.levels_completed, MAX_GAME_LEVEL)


def merge_guest_sessions(db: Session, user_id: UUID, visitor_id: str) -> int:
    if not visitor_id:
        return 0
    rows = (
        db.query(PlaySession)
        .filter(PlaySession.visitor_id == visitor_id, PlaySession.user_id.is_(None))
        .all()
    )
    for session in rows:
        session.user_id = user_id
        session.visitor_id = None
    if rows:
        db.commit()
    return len(rows)
