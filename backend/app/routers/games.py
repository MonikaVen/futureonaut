from uuid import UUID, uuid4
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.auth import get_current_user, get_optional_user, require_game_author
from app.database import get_db
from app.models import (
    Classroom,
    ClassroomAssignment,
    Game,
    GameComment,
    GameLike,
    GameSource,
    GameView,
    PlaySession,
    User,
    UserRole,
)
from app.schemas import (
    AIGenerateRequest,
    GameOut,
    GameUpdate,
    HtmlGenerateRequest,
    TemplateGameCreate,
)
from app.services.generate import generate_ai_content, generate_html_game, validate_template_content
from app.services.llm import normalize_provider, require_api_key, store_llm_key
from app.services.recommendations import game_to_out
from app.services.snapshot import promote_pack_icon, save_game_icon, write_game_preview
from app.services.social import enrich_games
from app.services.storage import (
    delete_game_files,
    game_dir,
    save_uploaded_html,
    save_uploaded_zip,
    write_template_game,
)
from app.services.topics import ensure_topic_tag

router = APIRouter(prefix="/games", tags=["games"])


@router.get("", response_model=list[GameOut])
def list_games(
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> list[GameOut]:
    games = db.query(Game).order_by(Game.created_at.desc()).all()
    return enrich_games(db, games, user.id if user else None)


@router.get("/mine", response_model=list[GameOut])
def my_games(
    db: Session = Depends(get_db),
    user: User = Depends(require_game_author),
) -> list[GameOut]:
    q = db.query(Game)
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
    icon: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(require_game_author),
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
        dest = game_dir(game_id)
        if icon is not None and (icon.filename or "").strip():
            raw_icon = await icon.read()
            if raw_icon:
                save_game_icon(dest, raw_icon)
        else:
            promote_pack_icon(dest)
    except Exception as exc:
        delete_game_files(game_id)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    tags = ensure_topic_tag(
        [t.strip() for t in topic_tags.split(",") if t.strip()],
        title,
        description,
    )
    game = Game(
        id=game_id,
        title=title,
        description=description,
        owner_id=user.id,
        source=GameSource.upload,
        topic_tags=tags,
        difficulty=difficulty,
        entry_path=entry,
    )
    db.add(game)
    db.commit()
    db.refresh(game)
    write_game_preview(game)
    return game_to_out(game)


@router.post("/from-template", response_model=GameOut, status_code=status.HTTP_201_CREATED)
def create_from_template(
    body: TemplateGameCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_game_author),
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
    )
    db.add(game)
    db.commit()
    db.refresh(game)
    write_game_preview(game)
    return game_to_out(game)


@router.post("/generate", response_model=GameOut, status_code=status.HTTP_201_CREATED)
async def generate_game(
    body: AIGenerateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_game_author),
) -> GameOut:
    if body.api_key:
        store_llm_key(user, body.provider or "openai", body.api_key)
    content = await generate_ai_content(
        topic=body.topic,
        difficulty=body.difficulty,
        template_type=body.template_type,
        description=body.description,
        question_count=body.question_count,
        api_key=body.api_key,
        provider=body.provider,
        model=body.model,
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
    )
    db.add(game)
    db.commit()
    db.refresh(game)
    write_game_preview(game)
    return game_to_out(game)


def _assign_if_requested(db: Session, user: User, game: Game, classroom_id) -> None:
    if classroom_id is None:
        return
    classroom = db.get(Classroom, classroom_id)
    if classroom is None or classroom.teacher_id != user.id:
        raise HTTPException(status_code=403, detail="You can only assign games to your own class")
    exists = (
        db.query(ClassroomAssignment)
        .filter(
            ClassroomAssignment.classroom_id == classroom.id,
            ClassroomAssignment.game_id == game.id,
        )
        .first()
    )
    if exists:
        return
    db.add(ClassroomAssignment(classroom_id=classroom.id, game_id=game.id))
    db.commit()


@router.post("/generate-html", response_model=GameOut, status_code=status.HTTP_201_CREATED)
async def generate_html_game_endpoint(
    body: HtmlGenerateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_game_author),
) -> GameOut:
    provider = normalize_provider(body.provider)
    api_key = require_api_key(body.api_key)
    store_llm_key(user, provider, api_key)
    title = (body.title or "").strip() or f"{body.topic} game"
    html = await generate_html_game(
        title=title,
        topic=body.topic,
        difficulty=body.difficulty,
        level_count=body.level_count,
        levels_brief=body.levels_brief,
        language=body.language or "en",
        api_key=api_key,
        provider=provider,
        model=body.model,
    )
    game_id = uuid4()
    try:
        entry = save_uploaded_html(game_id, html, "index.html")
    except Exception as exc:
        delete_game_files(game_id)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    game = Game(
        id=game_id,
        title=title[:200],
        description=body.levels_brief[:500],
        owner_id=user.id,
        source=GameSource.ai,
        topic_tags=ensure_topic_tag([body.topic], title, body.levels_brief),
        difficulty=body.difficulty,
        entry_path=entry,
        source_language=(body.language or "en")[:16],
    )
    db.add(game)
    db.commit()
    db.refresh(game)
    write_game_preview(game)
    _assign_if_requested(db, user, game, body.assign_classroom_id)
    db.refresh(game)
    return game_to_out(game)


@router.get("/{game_id}", response_model=GameOut)
def get_game(
    game_id: UUID,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> GameOut:
    game = db.get(Game, game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")
    return enrich_games(db, [game], user.id if user else None)[0]


@router.post("/{game_id}/view", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def record_game_view(
    game_id: UUID,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
    x_visitor_id: str | None = Header(default=None, alias="X-Visitor-Id"),
) -> None:
    game = db.get(Game, game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")
    visitor = (x_visitor_id or "").strip()[:64] or None
    db.add(
        GameView(
            game_id=game.id,
            user_id=user.id if user else None,
            visitor_id=visitor,
        )
    )
    db.commit()


@router.patch("/{game_id}", response_model=GameOut)
def update_game(
    game_id: UUID,
    body: GameUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_game_author),
) -> GameOut:
    game = db.get(Game, game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")
    if user.role != UserRole.admin and game.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Not your game")
    data = body.model_dump(exclude_unset=True)
    if "title" in data:
        data["title"] = (data["title"] or "").strip()
        if not data["title"]:
            raise HTTPException(status_code=400, detail="Title is required")
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
    write_game_preview(game)
    return game_to_out(game)


@router.delete("/{game_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_game(
    game_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_game_author),
) -> None:
    game = db.get(Game, game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")
    if user.role != UserRole.admin and game.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Not your game")
    sessions = db.query(PlaySession).filter(PlaySession.game_id == game.id).all()
    for session in sessions:
        db.delete(session)
    db.query(ClassroomAssignment).filter(ClassroomAssignment.game_id == game.id).delete()
    db.query(GameView).filter(GameView.game_id == game.id).delete()
    db.query(GameLike).filter(GameLike.game_id == game.id).delete()
    db.query(GameComment).filter(GameComment.game_id == game.id).delete()
    delete_game_files(game.id)
    db.delete(game)
    db.commit()


@router.get("/{game_id}/files/{file_path:path}")
def serve_game_file(
    game_id: UUID,
    file_path: str,
    db: Session = Depends(get_db),
):
    game = db.get(Game, game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")
    base = game_dir(game_id).resolve()
    target = (base / file_path).resolve()
    if not target.is_file() or not target.is_relative_to(base):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(
        target,
        headers={
            # Opaque sandboxed play iframes fetch sibling assets with Origin: null.
            "Access-Control-Allow-Origin": "*",
            "Cross-Origin-Resource-Policy": "cross-origin",
            "X-Content-Type-Options": "nosniff",
        },
    )
