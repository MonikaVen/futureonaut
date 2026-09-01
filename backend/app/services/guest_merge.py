from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import EventType, PlaySession


def apply_session_event(session: PlaySession, event_type: EventType, payload: dict) -> None:
    if event_type == EventType.score:
        session.total_points += int(payload.get("delta") or 0)
    elif event_type == EventType.answer:
        session.attempt_count += 1
        if payload.get("correct"):
            session.correct_count += 1
    elif event_type == EventType.task_time:
        if payload.get("phase") == "end":
            session.total_time_ms += int(payload.get("durationMs") or 0)
    elif event_type == EventType.level_complete:
        level = int(payload.get("level") or 0)
        total = int(payload.get("totalLevels") or payload.get("total_levels") or 0)
        if level > session.levels_completed:
            session.levels_completed = level
        if total > 0:
            session.total_levels = total
    elif event_type == EventType.complete:
        session.ended_at = datetime.now(timezone.utc)
        if payload.get("durationMs") and session.total_time_ms == 0:
            session.total_time_ms = int(payload["durationMs"])
        levels_done = int(payload.get("levelsCompleted") or payload.get("levels_completed") or 0)
        total = int(payload.get("totalLevels") or payload.get("total_levels") or 0)
        if levels_done > session.levels_completed:
            session.levels_completed = levels_done
        if total > 0:
            session.total_levels = total
        elif session.levels_completed > 0 and session.total_levels is None:
            session.total_levels = session.levels_completed


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
