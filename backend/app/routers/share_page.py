from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, Response
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Game, PlaySession
from app.public_url import public_base_url
from app.services.avatars import render_creator_card_png
from app.services.creators import find_user_by_slug
from app.services.handles import play_slug, resolve_game
from app.services.og import og_description, og_image_svg, score_card_svg, share_html
from app.services.snapshot import ensure_game_preview, has_game_screenshot, screenshot_file

router = APIRouter(tags=["share"])


@router.get("/share/u/{slug}", response_class=HTMLResponse)
def share_creator_page(slug: str, request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    user = find_user_by_slug(db, slug)
    if user is None:
        raise HTTPException(status_code=404, detail="Creator not found")
    game_count = db.query(func.count(Game.id)).filter(Game.owner_id == user.id).scalar() or 0
    base = public_base_url(request)
    profile_url = f"{base}/u/{slug}"
    share_url = f"{base}/share/u/{slug}"
    image_url = f"{base}/share/u/{slug}/card.png"
    name = user.display_name or slug
    html = share_html(
        title=f"{name} on Futureonaut",
        description=f"Play {game_count} educational game{'s' if game_count != 1 else ''} by {name}.",
        share_url=share_url,
        play_url=profile_url,
        image_url=image_url,
    )
    return HTMLResponse(content=html)


@router.get("/share/u/{slug}/card.png")
def share_creator_card_png(slug: str, db: Session = Depends(get_db)) -> Response:
    user = find_user_by_slug(db, slug)
    if user is None:
        raise HTTPException(status_code=404, detail="Creator not found")
    game_count = db.query(func.count(Game.id)).filter(Game.owner_id == user.id).scalar() or 0
    png = render_creator_card_png(user, game_count=int(game_count))
    return Response(
        content=png,
        media_type="image/png",
        headers={
            "Cache-Control": "public, max-age=300",
            "Content-Disposition": 'inline; filename="creator.png"',
        },
    )


@router.get("/share/{game_id}", response_class=HTMLResponse)
def share_page(game_id: str, request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    game = resolve_game(db, game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")
    base = public_base_url(request)
    share_url = f"{base}/share/{game.id}"
    play_url = f"{base}/play/{play_slug(game)}"
    image_url = f"{base}/share/{game.id}/card.png"
    html = share_html(
        title=game.title,
        description=og_description(game),
        share_url=share_url,
        play_url=play_url,
        image_url=image_url,
    )
    return HTMLResponse(content=html)


@router.get("/share/{game_id}/card.png")
def share_card_png(game_id: UUID, db: Session = Depends(get_db)) -> FileResponse:
    game = db.get(Game, game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")
    try:
        path = ensure_game_preview(game)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Preview not found") from exc
    return FileResponse(
        path,
        media_type="image/png",
        headers={
            "Cache-Control": "public, max-age=3600",
            "Content-Disposition": 'inline; filename="card.png"',
        },
    )


@router.get("/share/{game_id}/shot.png")
def share_shot_png(game_id: UUID, db: Session = Depends(get_db)) -> FileResponse:
    game = db.get(Game, game_id)
    if game is None or not has_game_screenshot(game.id):
        raise HTTPException(status_code=404, detail="Screenshot not found")
    return FileResponse(
        screenshot_file(game.id),
        media_type="image/png",
        headers={
            "Cache-Control": "public, max-age=3600",
            "Content-Disposition": 'inline; filename="shot.png"',
        },
    )


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
