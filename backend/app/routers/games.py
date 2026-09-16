from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.auth import create_draft_file_token, decode_draft_file_token, get_optional_user, require_game_author
from app.database import get_db
from app.models import (
    Classroom,
    ClassroomAssignment,
    Game,
    GameComment,
    GameDraft,
    GameLike,
    GameSource,
    GameView,
    PlaySession,
    User,
    UserRole,
)
from app.schemas import (
    AIGenerateRequest,
    DraftChatRequest,
    DraftPublishRequest,
    DraftReviseRequest,
    GameDraftOut,
    GameOut,
    GameUpdate,
    HtmlGenerateRequest,
    TemplateGameCreate,
)
from app.services.generate import (
    generate_ai_content,
    generate_html_from_chat,
    generate_html_game,
    revise_html_game,
    validate_template_content,
)
from app.services.llm import normalize_provider, require_api_key, store_llm_key
from app.services.recommendations import game_to_out
from app.services.snapshot import promote_pack_icon, save_game_icon, write_game_preview
from app.services.social import enrich_games
from app.services.storage import (
    delete_draft_files,
    delete_game_files,
    draft_dir,
    game_dir,
    save_draft_html,
    save_uploaded_html,
    save_uploaded_zip,
    write_template_game,
)
from app.services.demo_seed import restore_game_html_files
from app.services.topics import ensure_topic_tag

# Isolation comes from the play iframe sandbox attribute (no allow-same-origin).
# Do not put CSP sandbox or X-Frame-Options on the document: those make the
# framed game a unique origin, which Chrome then blocks as "This content is blocked".
GAME_FRAME_CSP = (
    "default-src 'self' 'unsafe-inline'; "
    "connect-src 'none'; "
    "object-src 'none'; "
    "frame-src 'none'; "
    "base-uri 'none'"
)
GAME_IFRAME_SANDBOX = "allow-scripts allow-forms"
VIEW_DEDUP_WINDOW = timedelta(hours=1)
VIEW_BURST_WINDOW = timedelta(minutes=10)
VIEW_BURST_MAX = 60


def game_file_headers(*, store: bool = False) -> dict[str, str]:
    return {
        # Opaque sandboxed play iframes fetch sibling assets with Origin: null.
        "Access-Control-Allow-Origin": "*",
        "Cross-Origin-Resource-Policy": "cross-origin",
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": GAME_FRAME_CSP,
        "Referrer-Policy": "no-referrer",
        "Cache-Control": "public, max-age=60" if store else "no-store",
    }


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
    api_key = require_api_key(body.api_key)
    store_llm_key(user, body.provider or "openai", api_key)
    db.add(user)
    content = await generate_ai_content(
        topic=body.topic,
        difficulty=body.difficulty,
        template_type=body.template_type,
        description=body.description,
        question_count=body.question_count,
        api_key=api_key,
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


def _draft_messages(raw) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "").strip()
        content = str(item.get("content") or "").strip()
        if role in {"user", "assistant"} and content:
            out.append({"role": role, "content": content[:4000]})
    return out


def _draft_to_out(draft: GameDraft) -> GameDraftOut:
    return GameDraftOut(
        id=draft.id,
        title=draft.title,
        topic=draft.topic,
        description=draft.description,
        difficulty=draft.difficulty,
        level_count=draft.level_count,
        language=draft.language,
        provider=draft.provider,
        model=draft.model,
        warnings=list(draft.warnings or []),
        messages=[
            {"role": m["role"], "content": m["content"]} for m in _draft_messages(draft.messages)
        ],
        preview_path="index.html",
        preview_token=create_draft_file_token(draft.id, draft.owner_id),
        published_game_id=draft.published_game_id,
        created_at=draft.created_at,
        updated_at=draft.updated_at,
    )


def _owned_draft(db: Session, user: User, draft_id: UUID) -> GameDraft:
    draft = db.get(GameDraft, draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")
    if user.role != UserRole.admin and draft.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Not your draft")
    return draft


def _write_draft_preview(draft: GameDraft) -> None:
    save_draft_html(draft.id, draft.html)


@router.post("/generate-html", response_model=GameDraftOut, status_code=status.HTTP_201_CREATED)
async def generate_html_game_endpoint(
    body: HtmlGenerateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_game_author),
) -> GameDraftOut:
    provider = normalize_provider(body.provider)
    api_key = require_api_key(body.api_key)
    store_llm_key(user, provider, api_key)
    db.add(user)
    title = (body.title or "").strip() or f"{body.topic} game"
    html, warnings = await generate_html_game(
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
    draft = GameDraft(
        title=title[:200],
        topic=body.topic[:200],
        description=body.levels_brief[:8000],
        owner_id=user.id,
        difficulty=body.difficulty,
        level_count=body.level_count,
        language=(body.language or "en")[:16],
        provider=provider,
        model=(body.model or None),
        html=html,
        warnings=warnings,
        messages=[
            {
                "role": "assistant",
                "content": "Draft ready. Play it, then tell me what to change before you publish.",
            }
        ],
        assign_classroom_id=body.assign_classroom_id,
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)
    try:
        _write_draft_preview(draft)
    except Exception as exc:
        delete_draft_files(draft.id)
        db.delete(draft)
        db.commit()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _draft_to_out(draft)


@router.get("/drafts", response_model=list[GameDraftOut])
def list_drafts(
    db: Session = Depends(get_db),
    user: User = Depends(require_game_author),
) -> list[GameDraftOut]:
    q = db.query(GameDraft).filter(GameDraft.published_game_id.is_(None))
    if user.role != UserRole.admin:
        q = q.filter(GameDraft.owner_id == user.id)
    drafts = q.order_by(GameDraft.updated_at.desc()).limit(20).all()
    return [_draft_to_out(d) for d in drafts]


@router.post("/drafts/chat", response_model=GameDraftOut)
async def chat_draft(
    body: DraftChatRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_game_author),
) -> GameDraftOut:
    provider = normalize_provider(body.provider)
    api_key = require_api_key(body.api_key)
    store_llm_key(user, provider, api_key)
    db.add(user)
    note = body.message.strip()
    if body.draft_id is not None:
        draft = _owned_draft(db, user, body.draft_id)
        if draft.published_game_id is not None:
            raise HTTPException(status_code=400, detail="This draft is already published")
        html, warnings = await revise_html_game(
            html=draft.html,
            message=note,
            level_count=draft.level_count,
            title=draft.title,
            api_key=api_key,
            provider=provider,
            model=body.model or draft.model,
            history=_draft_messages(draft.messages),
        )
        messages = _draft_messages(draft.messages)
        messages.append({"role": "user", "content": note})
        messages.append({"role": "assistant", "content": "Updated the game from your note."})
        draft.html = html
        draft.warnings = warnings
        draft.messages = messages[-24:]
        draft.provider = provider
        if body.model:
            draft.model = body.model
        draft.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(draft)
        _write_draft_preview(draft)
        return _draft_to_out(draft)

    html, warnings, title, level_count = await generate_html_from_chat(
        message=note,
        language=body.language or "en",
        api_key=api_key,
        provider=provider,
        model=body.model,
    )
    draft = GameDraft(
        title=title[:200],
        topic=title[:200],
        description=note[:8000],
        owner_id=user.id,
        difficulty=2,
        level_count=level_count,
        language=(body.language or "en")[:16],
        provider=provider,
        model=(body.model or None),
        html=html,
        warnings=warnings,
        messages=[
            {"role": "user", "content": note},
            {
                "role": "assistant",
                "content": "Here's a playable draft. Chat to change it, then deploy when it's ready.",
            },
        ],
        assign_classroom_id=body.assign_classroom_id,
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)
    try:
        _write_draft_preview(draft)
    except Exception as exc:
        delete_draft_files(draft.id)
        db.delete(draft)
        db.commit()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _draft_to_out(draft)


@router.get("/drafts/{draft_id}", response_model=GameDraftOut)
def get_draft(
    draft_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_game_author),
) -> GameDraftOut:
    return _draft_to_out(_owned_draft(db, user, draft_id))


@router.post("/drafts/{draft_id}/revise", response_model=GameDraftOut)
async def revise_draft(
    draft_id: UUID,
    body: DraftReviseRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_game_author),
) -> GameDraftOut:
    draft = _owned_draft(db, user, draft_id)
    if draft.published_game_id is not None:
        raise HTTPException(status_code=400, detail="This draft is already published")
    provider = normalize_provider(body.provider)
    api_key = require_api_key(body.api_key)
    store_llm_key(user, provider, api_key)
    db.add(user)
    html, warnings = await revise_html_game(
        html=draft.html,
        message=body.message.strip(),
        level_count=draft.level_count,
        title=draft.title,
        api_key=api_key,
        provider=provider,
        model=body.model or draft.model,
        history=_draft_messages(draft.messages),
    )
    messages = _draft_messages(draft.messages)
    messages.append({"role": "user", "content": body.message.strip()})
    messages.append({"role": "assistant", "content": "Updated the game from your note."})
    draft.html = html
    draft.warnings = warnings
    draft.messages = messages[-24:]
    draft.provider = provider
    if body.model:
        draft.model = body.model
    draft.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(draft)
    _write_draft_preview(draft)
    return _draft_to_out(draft)


@router.post("/drafts/{draft_id}/publish", response_model=GameOut, status_code=status.HTTP_201_CREATED)
def publish_draft(
    draft_id: UUID,
    body: DraftPublishRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_game_author),
) -> GameOut:
    draft = _owned_draft(db, user, draft_id)
    if draft.published_game_id is not None:
        game = db.get(Game, draft.published_game_id)
        if game is not None:
            return game_to_out(game)
        raise HTTPException(status_code=400, detail="Published game is missing")
    title = (body.title or draft.title or "").strip() or "Untitled game"
    game_id = uuid4()
    try:
        entry = save_uploaded_html(game_id, draft.html, "index.html")
    except Exception as exc:
        delete_game_files(game_id)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    game = Game(
        id=game_id,
        title=title[:200],
        description=(draft.description or "")[:500],
        owner_id=user.id,
        source=GameSource.ai,
        topic_tags=ensure_topic_tag([draft.topic], title, draft.description),
        difficulty=draft.difficulty,
        entry_path=entry,
        source_language=(draft.language or "en")[:16],
        html=draft.html,
    )
    db.add(game)
    draft.published_game_id = game.id
    draft.title = title[:200]
    draft.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(game)
    write_game_preview(game)
    classroom_id = body.assign_classroom_id if body.assign_classroom_id is not None else draft.assign_classroom_id
    _assign_if_requested(db, user, game, classroom_id)
    db.refresh(game)
    return game_to_out(game)


@router.delete("/drafts/{draft_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_draft(
    draft_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_game_author),
) -> None:
    draft = _owned_draft(db, user, draft_id)
    delete_draft_files(draft.id)
    db.delete(draft)
    db.commit()


@router.get("/drafts/{draft_id}/t/{token}/{file_path:path}")
def serve_draft_file(
    draft_id: UUID,
    token: str,
    file_path: str,
    db: Session = Depends(get_db),
):
    owner_id = decode_draft_file_token(token, draft_id)
    draft = db.get(GameDraft, draft_id)
    if draft is None or draft.published_game_id is not None:
        raise HTTPException(status_code=404, detail="Draft not found")
    if draft.owner_id != owner_id:
        raise HTTPException(status_code=403, detail="Not your draft")
    base = draft_dir(draft_id).resolve()
    target = (base / file_path).resolve()
    if (not target.is_file() or not target.is_relative_to(base)) and draft.html:
        save_draft_html(draft.id, draft.html)
        target = (base / file_path).resolve()
    if not target.is_file() or not target.is_relative_to(base):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(
        target,
        headers=game_file_headers(),
    )


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
    if user is None and not visitor:
        return
    now = datetime.now(timezone.utc)
    recent = db.query(GameView).filter(
        GameView.game_id == game.id,
        GameView.viewed_at >= now - VIEW_DEDUP_WINDOW,
    )
    if user is not None:
        recent = recent.filter(GameView.user_id == user.id)
    else:
        recent = recent.filter(GameView.visitor_id == visitor)
    if recent.first() is not None:
        return
    burst = (
        db.query(GameView)
        .filter(GameView.game_id == game.id, GameView.viewed_at >= now - VIEW_BURST_WINDOW)
        .count()
    )
    if burst >= VIEW_BURST_MAX:
        return
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
        html = game.html
        if not html:
            draft = (
                db.query(GameDraft)
                .filter(GameDraft.published_game_id == game.id)
                .first()
            )
            html = draft.html if draft else None
            if html and not game.html:
                game.html = html
                db.commit()
        restore_game_html_files(game, html)
        target = (base / file_path).resolve()
    if not target.is_file() or not target.is_relative_to(base):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(
        target,
        headers=game_file_headers(store=True),
    )
