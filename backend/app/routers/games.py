from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.auth import (
    create_draft_file_token,
    decode_draft_file_token,
    decode_token,
    get_optional_user,
    require_game_author,
)
from app.database import get_db
from app.limits import MAX_LUNA_QUERY_CHARS
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
from app.services.llm import resolve_llm_key
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
from app.services.prompts import generation_context
from app.services.handles import allocate_handle, resolve_game, user_slug_for_game
from app.services.topics import ensure_topic_tag
from app.services.visibility import can_view_game

# Document CSP sandbox (no allow-same-origin) makes game HTML a unique origin even
# if opened top-level or framed without the Play UI sandbox, so it cannot read SPA
# localStorage tokens. Do not add X-Frame-Options or frame-ancestors: Chrome then
# treats the unique origin as a framing violation ("This content is blocked").
GAME_FRAME_CSP = (
    "sandbox allow-scripts allow-forms; "
    "default-src 'unsafe-inline'; "
    "connect-src 'none'; "
    "object-src 'none'; "
    "frame-src 'none'; "
    "form-action 'none'; "
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
    query = db.query(Game).options(joinedload(Game.owner))
    if user is None or user.role != UserRole.admin:
        if user is None:
            query = query.filter(Game.is_public.is_(True))
        else:
            query = query.filter(or_(Game.is_public.is_(True), Game.owner_id == user.id))
    games = query.order_by(Game.created_at.desc()).all()
    return enrich_games(db, games, user.id if user else None)


@router.get("/mine", response_model=list[GameOut])
def my_games(
    db: Session = Depends(get_db),
    user: User = Depends(require_game_author),
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
        html=raw.decode("utf-8", errors="replace") if not filename.lower().endswith(".zip") else None,
        handle=allocate_handle(db, user, title),
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
        handle=allocate_handle(db, user, content.get("title", "Untitled")),
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
    api_key = None
    provider, api_key = resolve_llm_key(db, user, body.provider, body.api_key)
    db.add(user)
    content = await generate_ai_content(
        topic=body.topic,
        difficulty=body.difficulty,
        template_type=body.template_type,
        description=body.description,
        question_count=body.question_count,
        api_key=api_key,
        provider=provider,
        model=body.model,
        style_guidelines=generation_context(db, user)[2],
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
        handle=allocate_handle(db, user, content.get("title", f"{body.topic} game")),
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
        source_game_id=getattr(draft, "source_game_id", None),
        created_at=draft.created_at,
        updated_at=draft.updated_at,
    )


def _game_or_404(db: Session, ref: str) -> Game:
    game = resolve_game(db, ref)
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")
    return game


def _user_from_access_token(db: Session, token: str | None) -> User | None:
    if not token:
        return None
    try:
        payload = decode_token(token)
    except HTTPException:
        return None
    if payload.get("type") != "access":
        return None
    user_id = payload.get("sub")
    try:
        return db.get(User, UUID(user_id)) if user_id else None
    except (TypeError, ValueError):
        return None


def _visible_or_404(db: Session, game: Game, user: User | None) -> Game:
    if not can_view_game(db, game, user):
        raise HTTPException(status_code=404, detail="Game not found")
    return game


def _owned_game(db: Session, user: User, ref: str) -> Game:
    game = _game_or_404(db, ref)
    if user.role != UserRole.admin and game.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Not your game")
    return game


def _game_html(game: Game) -> str:
    if game.html:
        return game.html
    path = game_dir(game.id) / (game.entry_path or "index.html")
    if path.is_file():
        return path.read_text(encoding="utf-8", errors="replace")
    return ""


def _refresh_handle(db: Session, game: Game, title: str, actor: User) -> None:
    if game.handle and "/" in game.handle and game.title == title[:200]:
        return
    owner = db.get(User, game.owner_id) if game.owner_id else None
    user_slug = user_slug_for_game(game, owner or actor)
    game.handle = allocate_handle(
        db, owner or actor, title, exclude_id=game.id, user_slug=user_slug
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
    provider, api_key = resolve_llm_key(db, user, body.provider, body.api_key)
    db.add(user)
    title = (body.title or "").strip() or f"{body.topic} game"
    gen_system, _rev_system, style = generation_context(db, user)
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
        style_guidelines=style,
        system_prompt=gen_system,
    )
    draft = GameDraft(
        title=title[:200],
        topic=body.topic[:200],
        description=body.levels_brief[:MAX_LUNA_QUERY_CHARS],
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
    provider, api_key = resolve_llm_key(db, user, body.provider, body.api_key)
    db.add(user)
    note = body.message.strip()
    gen_system, rev_system, style = generation_context(db, user)
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
            style_guidelines=style,
            system_prompt=rev_system,
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
        style_guidelines=style,
        system_prompt=gen_system,
    )
    draft = GameDraft(
        title=title[:200],
        topic=title[:200],
        description=note[:MAX_LUNA_QUERY_CHARS],
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
    provider, api_key = resolve_llm_key(db, user, body.provider, body.api_key)
    db.add(user)
    _gen_system, rev_system, style = generation_context(db, user)
    html, warnings = await revise_html_game(
        html=draft.html,
        message=body.message.strip(),
        level_count=draft.level_count,
        title=draft.title,
        api_key=api_key,
        provider=provider,
        model=body.model or draft.model,
        history=_draft_messages(draft.messages),
        style_guidelines=style,
        system_prompt=rev_system,
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
    if draft.source_game_id is not None:
        game = db.get(Game, draft.source_game_id)
        if game is None:
            raise HTTPException(status_code=404, detail="Game not found")
        if user.role != UserRole.admin and game.owner_id != user.id:
            raise HTTPException(status_code=403, detail="Not your game")
        try:
            entry = save_uploaded_html(game.id, draft.html, "index.html")
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        next_title = title[:200]
        _refresh_handle(db, game, next_title, user)
        game.title = next_title
        game.description = (draft.description or game.description or "")[:500]
        game.entry_path = entry
        game.html = draft.html
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
        handle=allocate_handle(db, user, title),
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


@router.post("/{game_id}/edit-draft", response_model=GameDraftOut)
def create_edit_draft(
    game_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_game_author),
) -> GameDraftOut:
    game = _owned_game(db, user, game_id)
    existing = (
        db.query(GameDraft)
        .filter(
            GameDraft.source_game_id == game.id,
            GameDraft.published_game_id.is_(None),
            GameDraft.owner_id == user.id,
        )
        .order_by(GameDraft.updated_at.desc())
        .first()
    )
    if existing is not None:
        if not existing.html:
            existing.html = _game_html(game)
            db.commit()
            db.refresh(existing)
        _write_draft_preview(existing)
        return _draft_to_out(existing)
    html = _game_html(game)
    if not html.strip():
        raise HTTPException(status_code=400, detail="This game has no HTML to edit")
    now = datetime.now(timezone.utc)
    draft = GameDraft(
        title=game.title[:200],
        topic=(game.topic_tags[0] if game.topic_tags else game.title)[:200],
        description=(game.description or "")[:MAX_LUNA_QUERY_CHARS],
        owner_id=user.id,
        difficulty=game.difficulty or 2,
        level_count=4,
        language=(game.source_language or "en")[:16],
        provider=getattr(user, "llm_provider", None) or "openai",
        model=None,
        html=html,
        warnings=[],
        messages=[
            {
                "role": "assistant",
                "content": "Editing your published game. Chat to change it, then Deploy to update the live version.",
            }
        ],
        source_game_id=game.id,
        created_at=now,
        updated_at=now,
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


@router.post("/{game_id}/snapshot", response_model=GameOut)
async def update_game_snapshot(
    game_id: str,
    icon: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_game_author),
) -> GameOut:
    game = _owned_game(db, user, game_id)
    raw = await icon.read()
    try:
        save_game_icon(game_dir(game.id), raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    write_game_preview(game)
    return game_to_out(game)


@router.get("/by/{owner_slug}/{game_slug}", response_model=GameOut)
def get_game_by_handle(
    owner_slug: str,
    game_slug: str,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> GameOut:
    game = resolve_game(db, f"{owner_slug}/{game_slug}")
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")
    _visible_or_404(db, game, user)
    return enrich_games(db, [game], user.id if user else None)[0]


@router.get("/{game_id}", response_model=GameOut)
def get_game(
    game_id: str,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> GameOut:
    game = _visible_or_404(db, _game_or_404(db, game_id), user)
    return enrich_games(db, [game], user.id if user else None)[0]


@router.post("/{game_id}/view", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def record_game_view(
    game_id: str,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
    x_visitor_id: str | None = Header(default=None, alias="X-Visitor-Id"),
) -> None:
    game = _visible_or_404(db, _game_or_404(db, game_id), user)
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
    game_id: str,
    body: GameUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_game_author),
) -> GameOut:
    game = _owned_game(db, user, game_id)
    data = body.model_dump(exclude_unset=True)
    html = data.pop("html", None)
    if "is_public" in data and user.role not in (UserRole.admin, UserRole.creator):
        raise HTTPException(status_code=403, detail="Only admins and creators can change game privacy")
    if "title" in data:
        data["title"] = (data["title"] or "").strip()
        if not data["title"]:
            raise HTTPException(status_code=400, detail="Title is required")
        _refresh_handle(db, game, data["title"], user)
    if "topic_tags" in data and data["topic_tags"] is not None:
        data["topic_tags"] = ensure_topic_tag(
            data["topic_tags"],
            data.get("title") or game.title,
            data.get("description") or game.description or "",
        )
    if html is not None:
        html = html.strip()
        if not html:
            raise HTTPException(status_code=400, detail="HTML is required")
        try:
            entry = save_uploaded_html(game.id, html, "index.html")
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        game.html = html
        game.entry_path = entry
    for key, value in data.items():
        setattr(game, key, value)
    if not game.handle:
        _refresh_handle(db, game, game.title, user)
    db.commit()
    db.refresh(game)
    write_game_preview(game)
    return game_to_out(game)


@router.delete("/{game_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_game(
    game_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_game_author),
) -> None:
    game = _owned_game(db, user, game_id)
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
    user: User | None = Depends(get_optional_user),
    access_token: str | None = Query(default=None),
):
    game = db.get(Game, game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")
    _visible_or_404(db, game, user or _user_from_access_token(db, access_token))
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
