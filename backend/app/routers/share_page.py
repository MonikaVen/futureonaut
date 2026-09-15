from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Game, PlaySession
from app.public_url import public_base_url
from app.services.og import og_description, og_image_svg, score_card_svg, share_html

router = APIRouter(tags=["share"])


@router.get("/share/{game_id}", response_class=HTMLResponse)
def share_page(game_id: UUID, request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    game = db.get(Game, game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")
    base = public_base_url(request)
    share_url = f"{base}/share/{game.id}"
    play_url = f"{base}/play/{game.id}"
    image_url = f"{base}/share/{game.id}/card.svg"
    html = share_html(
        title=game.title,
        description=og_description(game),
        share_url=share_url,
        play_url=play_url,
        image_url=image_url,
    )
    return HTMLResponse(content=html)


@router.get("/share/{game_id}/card.svg")
def share_card(game_id: UUID, db: Session = Depends(get_db)) -> Response:
    game = db.get(Game, game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")
    svg = og_image_svg(game)
    return Response(content=svg, media_type="image/svg+xml", headers={"Cache-Control": "public, max-age=3600"})


@router.get("/share/score/{session_id}/card.svg")
def score_share_card(session_id: UUID, db: Session = Depends(get_db)) -> Response:
    session = db.query(PlaySession).options(joinedload(PlaySession.game)).filter(PlaySession.id == session_id).first()
    if session is None or session.game is None:
        raise HTTPException(status_code=404, detail="Session not found")
    acc = (session.correct_count / session.attempt_count * 100) if session.attempt_count else 0.0
    svg = score_card_svg(
        title=session.game.title,
        points=session.total_points,
        accuracy_pct=acc,
        levels_completed=session.levels_completed or None,
        total_levels=session.total_levels,
    )
    return Response(content=svg, media_type="image/svg+xml", headers={"Cache-Control": "public, max-age=3600"})
