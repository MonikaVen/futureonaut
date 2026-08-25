from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import EventType, Game, PlaySession, SessionEvent, User
from app.schemas import SessionCreate, SessionEventIn, SessionOut

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", response_model=SessionOut, status_code=201)
def start_session(
    body: SessionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PlaySession:
    game = db.get(Game, body.game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")
    session = PlaySession(user_id=user.id, game_id=game.id)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.get("/mine", response_model=list[SessionOut])
def my_sessions(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[PlaySession]:
    return (
        db.query(PlaySession)
        .filter(PlaySession.user_id == user.id)
        .order_by(PlaySession.started_at.desc())
        .limit(100)
        .all()
    )


@router.post("/{session_id}/events", response_model=SessionOut)
def post_event(
    session_id: UUID,
    body: SessionEventIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PlaySession:
    session = db.get(PlaySession, session_id)
    if session is None or session.user_id != user.id:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.ended_at is not None:
        raise HTTPException(status_code=400, detail="Session already completed")

    event = SessionEvent(session_id=session.id, type=body.type, payload=body.payload or {})
    db.add(event)

    if body.type == EventType.score:
        session.total_points += int(body.payload.get("delta") or 0)
    elif body.type == EventType.answer:
        session.attempt_count += 1
        if body.payload.get("correct"):
            session.correct_count += 1
    elif body.type == EventType.task_time:
        if body.payload.get("phase") == "end":
            session.total_time_ms += int(body.payload.get("durationMs") or 0)
    elif body.type == EventType.complete:
        session.ended_at = datetime.now(timezone.utc)
        if body.payload.get("durationMs") and session.total_time_ms == 0:
            session.total_time_ms = int(body.payload["durationMs"])

    db.commit()
    db.refresh(session)
    return session


@router.get("/{session_id}", response_model=SessionOut)
def get_session(
    session_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PlaySession:
    session = db.get(PlaySession, session_id)
    if session is None or (session.user_id != user.id and user.role.value != "admin"):
        raise HTTPException(status_code=404, detail="Session not found")
    return session
