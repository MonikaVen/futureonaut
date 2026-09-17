from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.auth import get_current_user, get_optional_user
from app.database import get_db
from app.models import EventType, Game, PlaySession, SessionEvent, User
from app.schemas import (
    ContinueSessionOut,
    GameProgressOut,
    GuestSessionCreate,
    SessionCreate,
    SessionEventIn,
    SessionOut,
)
from app.services.guest_merge import apply_session_event
from app.services.progress import best_sessions_by_game, progress_from_session
from app.services.snapshot import has_game_screenshot

router = APIRouter(prefix="/sessions", tags=["sessions"])


def _session_out(session: PlaySession) -> SessionOut:
    return SessionOut(
        id=session.id,
        user_id=session.user_id,
        game_id=session.game_id,
        started_at=session.started_at,
        ended_at=session.ended_at,
        total_points=session.total_points,
        total_time_ms=session.total_time_ms,
        correct_count=session.correct_count,
        attempt_count=session.attempt_count,
        levels_completed=session.levels_completed,
        total_levels=session.total_levels,
        game_title=session.game.title if session.game else None,
    )


def _resume_or_create(
    db: Session,
    game: Game,
    *,
    user_id: UUID | None = None,
    visitor_id: str | None = None,
) -> PlaySession:
    query = db.query(PlaySession).filter(PlaySession.game_id == game.id, PlaySession.ended_at.is_(None))
    if user_id:
        query = query.filter(PlaySession.user_id == user_id)
    else:
        query = query.filter(PlaySession.visitor_id == visitor_id, PlaySession.user_id.is_(None))
    existing = query.order_by(PlaySession.started_at.desc()).first()
    if existing:
        existing.game = game
        return existing
    session = PlaySession(user_id=user_id, visitor_id=visitor_id, game_id=game.id)
    db.add(session)
    db.commit()
    db.refresh(session)
    session.game = game
    return session


def _can_access(session: PlaySession, user: User | None, visitor_id: str | None) -> bool:
    if user and session.user_id == user.id:
        return True
    if user and user.role.value == "admin":
        return True
    if visitor_id and session.visitor_id == visitor_id and session.user_id is None:
        return True
    return False


@router.post("", response_model=SessionOut, status_code=201)
def start_session(
    body: SessionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SessionOut:
    game = db.get(Game, body.game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")
    return _session_out(_resume_or_create(db, game, user_id=user.id))


@router.post("/guest", response_model=SessionOut, status_code=201)
def start_guest_session(body: GuestSessionCreate, db: Session = Depends(get_db)) -> SessionOut:
    game = db.get(Game, body.game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")
    if not body.visitor_id or len(body.visitor_id) > 64:
        raise HTTPException(status_code=400, detail="visitor_id required")
    return _session_out(_resume_or_create(db, game, visitor_id=body.visitor_id))


@router.get("/continue", response_model=list[ContinueSessionOut])
def continue_sessions(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ContinueSessionOut]:
    sessions = (
        db.query(PlaySession)
        .options(joinedload(PlaySession.game))
        .filter(PlaySession.user_id == user.id)
        .order_by(PlaySession.started_at.desc())
        .limit(50)
        .all()
    )
    out: list[ContinueSessionOut] = []
    seen_games: set[UUID] = set()
    for s in sessions:
        if s.game_id in seen_games:
            continue
        incomplete = s.ended_at is None or (
            s.total_levels is not None and s.levels_completed < s.total_levels
        )
        if not incomplete:
            continue
        seen_games.add(s.game_id)
        out.append(
            ContinueSessionOut(
                session_id=s.id,
                game_id=s.game_id,
                game_title=s.game.title if s.game else "",
                game_description=s.game.description if s.game else "",
                topic_tags=list(s.game.topic_tags or []) if s.game else [],
                difficulty=s.game.difficulty if s.game else 1,
                levels_completed=s.levels_completed,
                total_levels=s.total_levels,
                total_points=s.total_points,
                started_at=s.started_at,
                has_screenshot=has_game_screenshot(s.game_id),
                handle=getattr(s.game, "handle", None) if s.game else None,
            )
        )
        if len(out) >= 6:
            break
    return out


@router.get("/mine", response_model=list[SessionOut])
def my_sessions(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[SessionOut]:
    sessions = (
        db.query(PlaySession)
        .options(joinedload(PlaySession.game))
        .filter(PlaySession.user_id == user.id)
        .order_by(PlaySession.started_at.desc())
        .limit(100)
        .all()
    )
    return [_session_out(s) for s in sessions]


@router.get("/progress", response_model=list[GameProgressOut])
def my_progress(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[GameProgressOut]:
    plays: dict = {}
    for session in db.query(PlaySession).filter(PlaySession.user_id == user.id).all():
        plays[session.game_id] = plays.get(session.game_id, 0) + 1
    best = best_sessions_by_game(db, user.id)
    out: list[GameProgressOut] = []
    for game_id, session in best.items():
        stats = progress_from_session(session)
        out.append(
            GameProgressOut(
                game_id=game_id,
                completed=stats["completed"],
                levels_completed=stats["levels_completed"],
                total_levels=stats["total_levels"],
                points=stats["points"],
                accuracy=stats["accuracy"],
                progress_pct=stats["progress_pct"],
                plays=plays.get(game_id, 0),
            )
        )
    out.sort(key=lambda row: (not row.completed, -row.levels_completed, row.game_id.hex))
    return out


@router.post("/{session_id}/events", response_model=SessionOut)
def post_event(
    session_id: UUID,
    body: SessionEventIn,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
    x_visitor_id: str | None = Header(default=None, alias="X-Visitor-Id"),
) -> SessionOut:
    session = db.query(PlaySession).options(joinedload(PlaySession.game)).filter(PlaySession.id == session_id).first()
    if session is None or not _can_access(session, user, x_visitor_id):
        raise HTTPException(status_code=404, detail="Session not found")
    if session.ended_at is not None:
        raise HTTPException(status_code=400, detail="Session already completed")

    event = SessionEvent(session_id=session.id, type=body.type, payload=body.payload or {})
    db.add(event)
    apply_session_event(session, body.type, body.payload or {})
    db.commit()
    db.refresh(session)
    return _session_out(session)


@router.get("/{session_id}", response_model=SessionOut)
def get_session(
    session_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SessionOut:
    session = db.query(PlaySession).options(joinedload(PlaySession.game)).filter(PlaySession.id == session_id).first()
    if session is None or not _can_access(session, user, None):
        raise HTTPException(status_code=404, detail="Session not found")
    return _session_out(session)
