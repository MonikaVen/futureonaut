from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.models import PlaySession


def session_is_solved(session: PlaySession | None) -> bool:
    if session is None:
        return False
    if session.ended_at is not None:
        return True
    total = session.total_levels
    if total and (session.levels_completed or 0) >= total:
        return True
    return False


def session_progress_pct(session: PlaySession | None) -> int | None:
    if session is None:
        return None
    total = session.total_levels
    if total and total > 0:
        return max(0, min(100, round((session.levels_completed or 0) * 100 / total)))
    if session.ended_at is not None:
        return 100
    if (session.levels_completed or 0) > 0 or session.total_points > 0:
        return None
    return 0 if session else None


def progress_from_session(session: PlaySession | None) -> dict:
    if session is None:
        return {
            "completed": False,
            "points": 0,
            "accuracy": 0.0,
            "levels_completed": 0,
            "total_levels": None,
            "progress_pct": None,
        }
    acc = (session.correct_count / session.attempt_count) if session.attempt_count else 0.0
    return {
        "completed": session_is_solved(session),
        "points": session.total_points,
        "accuracy": acc,
        "levels_completed": session.levels_completed or 0,
        "total_levels": session.total_levels,
        "progress_pct": session_progress_pct(session),
    }


def _better(a: PlaySession | None, b: PlaySession) -> PlaySession:
    if a is None:
        return b
    a_solved = 1 if session_is_solved(a) else 0
    b_solved = 1 if session_is_solved(b) else 0
    a_key = (a_solved, a.levels_completed or 0, a.total_points, a.started_at)
    b_key = (b_solved, b.levels_completed or 0, b.total_points, b.started_at)
    return b if b_key > a_key else a


def best_sessions_by_game(
    db: Session, user_id: UUID, game_ids: list[UUID] | None = None
) -> dict[UUID, PlaySession]:
    q = db.query(PlaySession).filter(PlaySession.user_id == user_id)
    if game_ids is not None:
        if not game_ids:
            return {}
        q = q.filter(PlaySession.game_id.in_(game_ids))
    best: dict[UUID, PlaySession] = {}
    for session in q.all():
        best[session.game_id] = _better(best.get(session.game_id), session)
    return best


def summarize_assignment(
    sessions: list[PlaySession | None], member_count: int
) -> dict:
    solved = in_progress = 0
    points = 0
    levels = 0
    acc_sum = 0.0
    acc_n = 0
    for session in sessions:
        if session is None:
            continue
        stats = progress_from_session(session)
        if stats["completed"]:
            solved += 1
        elif stats["points"] or stats["levels_completed"]:
            in_progress += 1
        points += stats["points"]
        levels += stats["levels_completed"]
        if session.attempt_count:
            acc_sum += stats["accuracy"]
            acc_n += 1
    started = solved + in_progress
    not_started = max(0, member_count - started)
    return {
        "solved_count": solved,
        "in_progress_count": in_progress,
        "not_started_count": not_started,
        "avg_points": (points / started) if started else 0.0,
        "avg_levels": (levels / started) if started else 0.0,
        "avg_accuracy": (acc_sum / acc_n) if acc_n else 0.0,
    }
