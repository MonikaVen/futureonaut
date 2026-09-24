"""Seed demo template games and HTML pack from backend/seed_games/."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from app.config import get_settings
from app.database import SessionLocal
from app.models import Game, GameDraft, GameSource, User, UserRole
from app.services.handles import allocate_handle
from app.services.snapshot import ensure_game_preview, write_game_preview
from app.services.storage import ensure_sdk_injected, game_dir, save_uploaded_html, write_sdk, write_template_game
from app.services.topics import ensure_topic_tag

DEMO_QUIZ = {
    "title": "Intro to Neural Nets",
    "description": "Quick quiz on basic neural network concepts.",
    "topic_tags": ["AI", "Trustworthiness of AI"],
    "difficulty": 1,
    "questions": [
        {
            "id": "q1",
            "prompt": "What does a neuron compute first?",
            "options": [
                {"text": "A weighted sum of inputs", "correct": True},
                {"text": "Only the bias", "correct": False},
                {"text": "A random number", "correct": False},
                {"text": "The loss directly", "correct": False},
            ],
            "points": 10,
        },
        {
            "id": "q2",
            "prompt": "Sigmoid outputs are typically in which range?",
            "options": [
                {"text": "0 to 1", "correct": True},
                {"text": "-1 to 1", "correct": False},
                {"text": "0 to infinity", "correct": False},
                {"text": "Any real number equally", "correct": False},
            ],
            "points": 10,
        },
        {
            "id": "q3",
            "prompt": "Gradient descent updates weights to...",
            "options": [
                {"text": "Reduce the loss", "correct": True},
                {"text": "Increase the loss", "correct": False},
                {"text": "Freeze the network", "correct": False},
                {"text": "Remove all bias terms", "correct": False},
            ],
            "points": 10,
        },
    ],
}

DEMO_MATCH = {
    "title": "Tokenization Match",
    "description": "Match NLP terms with their meanings.",
    "topic_tags": ["AI", "Large Language Models"],
    "difficulty": 2,
    "pairs": [
        {"id": "p1", "left": "Token", "right": "A unit of text the model sees", "points": 10},
        {"id": "p2", "left": "Vocabulary", "right": "The set of known tokens", "points": 10},
        {"id": "p3", "left": "BPE", "right": "A subword tokenization algorithm", "points": 10},
    ],
}


def _seed_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "seed_games"


def catalog_owner(db) -> User | None:
    settings = get_settings()
    email = (settings.creator_email or "").strip().lower()
    if email:
        owner = db.query(User).filter(User.email == email).first()
        if owner is not None:
            return owner
    display = (settings.creator_display_name or "futureonaut").strip()
    if display:
        named = db.query(User).filter(User.display_name.ilike(display)).all()
        creator_named = next((user for user in named if user.role == UserRole.creator), None)
        if creator_named is not None:
            return creator_named
        if named:
            return named[0]
    creator = db.query(User).filter(User.role == UserRole.creator).first()
    if creator is not None:
        return creator
    return db.query(User).filter(User.role == UserRole.admin).first()


def _should_reassign_game(db, game: Game, owner: User) -> bool:
    if game.owner_id is None or game.owner_id == owner.id:
        return True
    current = db.get(User, game.owner_id)
    if current is None:
        return True
    if current.role == UserRole.admin:
        return True
    teacher_email = (get_settings().teacher_email or "").strip().lower()
    if teacher_email and str(getattr(current, "email", "") or "").lower() == teacher_email:
        return True
    return False


def assign_catalog_to_owner(db, owner: User) -> None:
    """One-time handoff of demo/admin catalog games to the Futureonaut creator."""
    from app.services.handles import allocate_handle, split_handle, username_slug
    from app.services.prompts import get_or_create_platform_settings

    settings_row = get_or_create_platform_settings(db)
    if settings_row.catalog_assigned:
        return

    user_part = username_slug(owner)
    changed = False
    for game in db.query(Game).all():
        if not _should_reassign_game(db, game, owner):
            continue
        if game.owner_id != owner.id:
            game.owner_id = owner.id
            changed = True
        parts = split_handle(game.handle)
        game_part = parts[1] if parts else None
        next_handle = allocate_handle(
            db,
            owner,
            game.title,
            exclude_id=game.id,
            user_slug=user_part,
            game_slug=game_part,
        )
        if game.handle == next_handle:
            continue
        game.handle = next_handle
        db.flush()
        changed = True
    settings_row.catalog_assigned = True
    db.commit()


def seed_demo_games() -> None:
    """Load files and previews for the DB catalog. Do not rebuild the list from seed."""
    db = SessionLocal()
    try:
        owner = catalog_owner(db)
        if owner is None:
            return

        if db.query(Game).count() == 0:
            for template_type, content, source in (
                ("quiz", DEMO_QUIZ, GameSource.template),
                ("drag_match", DEMO_MATCH, GameSource.template),
            ):
                game_id = uuid4()
                entry = write_template_game(game_id, template_type, content)
                db.add(
                    Game(
                        id=game_id,
                        title=content["title"],
                        description=content["description"],
                        owner_id=owner.id,
                        source=source,
                        topic_tags=content["topic_tags"],
                        difficulty=content["difficulty"],
                        entry_path=entry,
                        template_type=template_type,
                        seed_file=f"template:{template_type}",
                        handle=allocate_handle(db, owner, content["title"]),
                    )
                )
            db.commit()
            seed_html_pack(db, owner.id)

        ensure_flagged_seed_games(db, owner.id)
        backfill_seed_files(db)
        normalize_game_topics(db)
        restore_published_html(db)
        restore_missing_game_files(db)
        restore_missing_template_html(db)
        refresh_game_previews(db)
        backfill_game_handles(db)
        assign_catalog_to_owner(db, owner)
    finally:
        db.close()


def prune_games_to_manifest(db) -> None:
    """Unused on boot. Catalog membership is curated in Postgres by admins."""
    return


def restore_published_html(db) -> None:
    """Rewrite catalog HTML from Postgres after a container replace."""
    changed = False
    drafts = {
        d.published_game_id: d.html
        for d in db.query(GameDraft).filter(GameDraft.published_game_id.isnot(None)).all()
        if d.html
    }
    for game in db.query(Game).all():
        html = game.html or drafts.get(game.id)
        if html and not game.html:
            game.html = html
            changed = True
        restore_game_html_files(game, html)
    if changed:
        db.commit()


def restore_game_html_files(game: Game, html: str | None) -> bool:
    if not html:
        return False
    target = game_dir(game.id) / (game.entry_path or "index.html")
    if target.is_file():
        return False
    save_uploaded_html(game.id, html, "index.html")
    return True


def restore_missing_game_files(db) -> None:
    """Rehydrate HTML for existing catalog rows if the game volume is empty."""
    manifest_path = _seed_dir() / "manifest.json"
    if not manifest_path.exists():
        return
    items = json.loads(manifest_path.read_text(encoding="utf-8"))
    by_file = {item["file"]: item for item in items if item.get("file")}
    by_title = {(item.get("title") or item["file"]): item for item in items}
    for game in db.query(Game).all():
        target = game_dir(game.id) / (game.entry_path or "index.html")
        if target.exists():
            continue
        item = None
        if game.seed_file and not str(game.seed_file).startswith("template:"):
            item = by_file.get(game.seed_file)
        if item is None:
            item = by_title.get(game.title)
        if not item:
            continue
        src = _seed_dir() / item["file"]
        if src.exists():
            html = src.read_text(encoding="utf-8", errors="replace")
            save_uploaded_html(game.id, html, "index.html")
            write_game_preview(game)


def refresh_seed_html(db) -> None:
    """No longer rewrites catalog HTML from the seed pack on boot."""
    return


def restore_missing_template_html(db) -> None:
    """Write template HTML only when the game folder is missing its entry file."""
    template_root = Path(__file__).resolve().parents[2] / "templates"
    for game in db.query(Game).all():
        kind = (game.template_type or "").strip()
        if not kind:
            continue
        dest = game_dir(game.id)
        target = dest / (game.entry_path or "index.html")
        if target.exists():
            continue
        src = template_root / kind / "index.html"
        if not src.exists():
            continue
        dest.mkdir(parents=True, exist_ok=True)
        target.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        ensure_sdk_injected(dest, game.entry_path or "index.html")


def refresh_template_html(db) -> None:
    restore_missing_template_html(db)


def backfill_seed_files(db) -> None:
    """Remember the original seed file so a renamed game can still restore files."""
    manifest_path = _seed_dir() / "manifest.json"
    if not manifest_path.exists():
        return
    by_title = {
        (item.get("title") or item["file"]): item["file"]
        for item in json.loads(manifest_path.read_text(encoding="utf-8"))
        if item.get("file")
    }
    changed = False
    for game in db.query(Game).all():
        if game.seed_file:
            continue
        if game.template_type:
            game.seed_file = f"template:{game.template_type}"
            changed = True
            continue
        origin = by_title.get(game.title)
        if origin:
            game.seed_file = origin
            changed = True
    if changed:
        db.commit()


def normalize_game_topics(db) -> None:
    changed = False
    for game in db.query(Game).all():
        updated = ensure_topic_tag(game.topic_tags, game.title, game.description or "")
        if updated != list(game.topic_tags or []):
            game.topic_tags = updated
            changed = True
    if changed:
        db.commit()


def ensure_flagged_seed_games(db, owner_id) -> None:
    """Insert seed titles marked ensure=true when a live catalog does not have them yet."""
    manifest_path = _seed_dir() / "manifest.json"
    if not manifest_path.exists():
        return
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    flagged = [item for item in manifest if item.get("ensure")]
    if not flagged:
        return
    existing_files = {g.seed_file for g in db.query(Game).all() if g.seed_file}
    existing_titles = {g.title for g in db.query(Game.title).all()}
    owner = db.get(User, owner_id)
    added = 0
    for item in flagged:
        title = item.get("title") or item["file"]
        seed_file = item.get("file")
        if seed_file in existing_files or title in existing_titles:
            continue
        src = _seed_dir() / item["file"]
        if not src.is_file():
            continue
        html = src.read_text(encoding="utf-8", errors="replace")
        game_id = uuid4()
        entry = save_uploaded_html(game_id, html, "index.html")
        tags = ensure_topic_tag(
            item.get("topic_tags") or [],
            title,
            item.get("description") or "",
        )
        db.add(
            Game(
                id=game_id,
                title=title,
                description=item.get("description") or "",
                owner_id=owner_id,
                source=GameSource.upload,
                topic_tags=tags,
                difficulty=int(item.get("difficulty") or 1),
                entry_path=entry,
                seed_file=seed_file,
                html=html,
                handle=allocate_handle(db, owner, title),
            )
        )
        existing_files.add(seed_file)
        existing_titles.add(title)
        added += 1
    if added:
        db.commit()


def seed_html_pack(db, owner_id) -> None:
    """Insert the seed pack once, when the catalog is empty."""
    manifest_path = _seed_dir() / "manifest.json"
    if not manifest_path.exists():
        return
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    existing_files = {g.seed_file for g in db.query(Game).all() if g.seed_file}
    existing_titles = {g.title for g in db.query(Game.title).all()}
    added = 0
    for item in manifest:
        title = item.get("title") or item["file"]
        seed_file = item.get("file")
        if seed_file in existing_files or title in existing_titles:
            continue
        src = _seed_dir() / item["file"]
        if not src.exists():
            continue
        html = src.read_text(encoding="utf-8", errors="replace")
        game_id = uuid4()
        entry = save_uploaded_html(game_id, html, "index.html")
        tags = ensure_topic_tag(
            item.get("topic_tags") or [],
            item.get("title") or "",
            item.get("file") or "",
        )
        owner = db.get(User, owner_id)
        db.add(
            Game(
                id=game_id,
                title=title,
                description=item.get("description") or "",
                owner_id=owner_id,
                source=GameSource.upload,
                topic_tags=tags,
                difficulty=int(item.get("difficulty") or 1),
                entry_path=entry,
                seed_file=seed_file,
                handle=allocate_handle(db, owner, title),
            )
        )
        existing_files.add(seed_file)
        existing_titles.add(title)
        added += 1
    if added:
        db.commit()


def backfill_game_handles(db) -> None:
    from app.services.handles import allocate_handle, migrate_handle, split_handle, username_slug

    changed = False
    for game in db.query(Game).all():
        owner = db.get(User, game.owner_id) if game.owner_id else None
        migrated = migrate_handle(game, owner)
        if migrated is None and game.handle:
            continue
        desired = migrated or game.handle
        parts = split_handle(desired)
        user_part = parts[0] if parts else username_slug(owner)
        game_part = parts[1] if parts else None
        next_handle = allocate_handle(
            db,
            owner,
            game.title,
            exclude_id=game.id,
            user_slug=user_part,
            game_slug=game_part,
        )
        if game.handle == next_handle:
            continue
        game.handle = next_handle
        db.flush()
        changed = True
    if changed:
        db.commit()


def refresh_game_previews(db) -> None:
    for game in db.query(Game).all():
        try:
            write_sdk(game_dir(game.id))
        except FileNotFoundError:
            pass
        try:
            ensure_game_preview(game)
        except FileNotFoundError:
            continue
