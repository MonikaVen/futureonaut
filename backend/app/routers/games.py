from uuid import UUID, uuid4
import json
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy.orm import Session, joinedload

from app.auth import get_current_user, require_roles
from app.database import get_db
from app.models import Game, GameSource, PlaySession, User, UserRole
from app.schemas import (
    AIGenerateRequest,
    GameOut,
    GameUpdate,
    TemplateGameCreate,
)
from app.services.generate import generate_ai_content, validate_template_content
from app.services.i18n import (
    SUPPORTED_LANGS,
    detect_language,
    extract_visible_text,
    i18n_cache_path,
    translate_html,
)
from app.services.recommendations import game_to_out
from app.services.storage import (
    delete_game_files,
    game_dir,
    save_uploaded_html,
    save_uploaded_zip,
    write_template_game,
)
from app.services.topics import ensure_topic_tag

router = APIRouter(prefix="/games", tags=["games"])


@router.get("/languages")
def list_languages() -> dict:
    return {"languages": [{"code": k, "label": v} for k, v in SUPPORTED_LANGS.items()]}


@router.get("", response_model=list[GameOut])
def list_games(db: Session = Depends(get_db)) -> list[GameOut]:
    games = db.query(Game).options(joinedload(Game.owner)).order_by(Game.created_at.desc()).all()
    return [game_to_out(g) for g in games]


@router.get("/mine", response_model=list[GameOut])
def my_games(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.creator, UserRole.admin)),
) -> list[GameOut]:
    q = db.query(Game).options(joinedload(Game.owner))
    if user.role != UserRole.admin:
        q = q.filter(Game.owner_id == user.id)
    return [game_to_out(g) for g in q.order_by(Game.created_at.desc()).all()]


@router.post("/upload", response_model=GameOut, status_code=status.HTTP_201_CREATED)
async def upload_game(
    title: str = Form(...),
    description: str = Form(""),
    topic_tags: str = Form(""),
    difficulty: int = Form(1),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.creator, UserRole.admin)),
) -> GameOut:
    if difficulty < 1 or difficulty > 5:
        raise HTTPException(status_code=400, detail="difficulty must be 1-5")
    game_id = uuid4()
    raw = await file.read()
    filename = file.filename or "game.html"
    try:
        if filename.lower().endswith(".zip"):
            entry = save_uploaded_zip(game_id, raw)
        else:
            entry = save_uploaded_html(game_id, raw.decode("utf-8", errors="replace"), filename)
    except Exception as exc:
        delete_game_files(game_id)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    tags = ensure_topic_tag(
        [t.strip() for t in topic_tags.split(",") if t.strip()],
        title,
        description,
    )
    # Detect language from HTML content when possible
    try:
        html_sample = (game_dir(game_id) / entry).read_text(encoding="utf-8", errors="replace")
        lang = detect_language(title, description, extract_visible_text(html_sample))
    except Exception:
        lang = detect_language(title, description)
    game = Game(
        id=game_id,
        title=title,
        description=description,
        owner_id=user.id,
        source=GameSource.upload,
        topic_tags=tags,
        difficulty=difficulty,
        entry_path=entry,
        source_language=lang,
    )
    db.add(game)
    db.commit()
    db.refresh(game)
    return game_to_out(game)


@router.post("/from-template", response_model=GameOut, status_code=status.HTTP_201_CREATED)
def create_from_template(
    body: TemplateGameCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.creator, UserRole.admin)),
) -> GameOut:
    content = validate_template_content(body.template_type, body.content)
    game_id = uuid4()
    try:
        entry = write_template_game(game_id, body.template_type, content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    game = Game(
        id=game_id,
        title=content.get("title", "Untitled"),
        description=content.get("description", ""),
        owner_id=user.id,
        source=GameSource.template,
        topic_tags=ensure_topic_tag(
            content.get("topic_tags") or [],
            content.get("title", ""),
            content.get("description", ""),
        ),
        difficulty=int(content.get("difficulty") or 1),
        entry_path=entry,
        template_type=body.template_type,
        source_language=detect_language(
            content.get("title", ""),
            content.get("description", ""),
            json.dumps(content, ensure_ascii=False),
        ),
    )
    db.add(game)
    db.commit()
    db.refresh(game)
    return game_to_out(game)


@router.post("/generate", response_model=GameOut, status_code=status.HTTP_201_CREATED)
async def generate_game(
    body: AIGenerateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.creator, UserRole.admin)),
) -> GameOut:
    content = await generate_ai_content(
        topic=body.topic,
        difficulty=body.difficulty,
        template_type=body.template_type,
        description=body.description,
        question_count=body.question_count,
    )
    game_id = uuid4()
    entry = write_template_game(game_id, body.template_type, content)
    game = Game(
        id=game_id,
        title=content.get("title", f"{body.topic} game"),
        description=content.get("description") or body.description,
        owner_id=user.id,
        source=GameSource.ai,
        topic_tags=ensure_topic_tag(
            content.get("topic_tags") or [body.topic],
            body.topic,
            body.description,
        ),
        difficulty=body.difficulty,
        entry_path=entry,
        template_type=body.template_type,
        source_language=detect_language(
            content.get("title", ""),
            content.get("description", ""),
            json.dumps(content, ensure_ascii=False),
        ),
    )
    db.add(game)
    db.commit()
    db.refresh(game)
    return game_to_out(game)


@router.get("/{game_id}", response_model=GameOut)
def get_game(game_id: UUID, db: Session = Depends(get_db)) -> GameOut:
    game = db.get(Game, game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")
    return game_to_out(game)


@router.patch("/{game_id}", response_model=GameOut)
def update_game(
    game_id: UUID,
    body: GameUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.creator, UserRole.admin)),
) -> GameOut:
    game = db.get(Game, game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")
    if user.role != UserRole.admin and game.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Not your game")
    data = body.model_dump(exclude_unset=True)
    if "topic_tags" in data and data["topic_tags"] is not None:
        data["topic_tags"] = ensure_topic_tag(
            data["topic_tags"],
            data.get("title") or game.title,
            data.get("description") or game.description or "",
        )
    for key, value in data.items():
        setattr(game, key, value)
    db.commit()
    db.refresh(game)
    return game_to_out(game)


@router.delete("/{game_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_game(
    game_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.creator, UserRole.admin)),
) -> None:
    game = db.get(Game, game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")
    if user.role != UserRole.admin and game.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Not your game")
    sessions = db.query(PlaySession).filter(PlaySession.game_id == game.id).all()
    for session in sessions:
        db.delete(session)
    delete_game_files(game.id)
    db.delete(game)
    db.commit()


@router.get("/{game_id}/files/{file_path:path}")
async def serve_game_file(
    game_id: UUID,
    file_path: str,
    lang: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    game = db.get(Game, game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")
    base = game_dir(game_id).resolve()
    target = (base / file_path).resolve()
    if not str(target).startswith(str(base)) or not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    source_lang = getattr(game, "source_language", None) or "en"
    target_lang = (lang or source_lang).lower()
    is_html = target.suffix.lower() in {".html", ".htm"}

    if (
        not is_html
        or target_lang == source_lang
        or target_lang not in SUPPORTED_LANGS
    ):
        return FileResponse(
            target,
            headers={"Cache-Control": "no-store, max-age=0"} if is_html else {},
        )

    cache = i18n_cache_path(base, target_lang, file_path)
    if cache.exists():
        html = cache.read_text(encoding="utf-8", errors="replace")
    else:
        original = target.read_text(encoding="utf-8", errors="replace")
        try:
            html = await translate_html(original, source_lang, target_lang)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Translation failed: {exc}") from exc
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(html, encoding="utf-8")

    # Keep relative asset paths resolving to the original game folder
    if "<base " not in html.lower():
        base_href = f"/api/games/{game_id}/files/"
        if re_search_head := __import__("re").search(r"<head[^>]*>", html, flags=__import__("re").I):
            idx = re_search_head.end()
            html = html[:idx] + f'\n<base href="{base_href}">\n' + html[idx:]
        else:
            html = f'<base href="{base_href}">\n' + html

    return HTMLResponse(content=html, headers={"Cache-Control": "no-store, max-age=0"})
