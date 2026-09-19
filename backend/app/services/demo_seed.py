"""Seed demo template games and HTML pack from backend/seed_games/."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from app.database import SessionLocal
from app.models import Game, GameSource, User, UserRole
from app.services.i18n import detect_language, extract_visible_text
from app.services.storage import (
    game_dir,
    materialize_game_files,
    save_uploaded_html,
    snapshot_game_files,
    write_template_game,
)
from app.services.topics import ensure_topic_tag

DEMO_QUIZ = {
    "title": "Intro to Neural Nets",
    "description": "Quick quiz on basic neural network concepts.",
    "topic_tags": ["ML", "neural-nets", "ai-basics"],
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
    "topic_tags": ["ML", "nlp", "tokenization"],
    "difficulty": 2,
    "pairs": [
        {"id": "p1", "left": "Token", "right": "A unit of text the model sees", "points": 10},
        {"id": "p2", "left": "Vocabulary", "right": "The set of known tokens", "points": 10},
        {"id": "p3", "left": "BPE", "right": "A subword tokenization algorithm", "points": 10},
    ],
}


def _seed_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "seed_games"


def seed_demo_games() -> None:
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.role == UserRole.admin).first()
        if admin is None:
            return

        empty = db.query(Game).count() == 0
        if empty:
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
                        owner_id=admin.id,
                        source=source,
                        topic_tags=content["topic_tags"],
                        difficulty=content["difficulty"],
                        entry_path=entry,
                        template_type=template_type,
                        source_language=detect_language(
                            content["title"], content["description"]
                        ),
                        files=snapshot_game_files(game_id),
                    )
                )
            db.commit()
            # First empty database only. Later deploys keep whatever is already stored.
            seed_html_pack(db, admin.id)

        persist_and_hydrate_game_files(db)
        normalize_game_topics(db)
        detect_missing_languages(db)
    finally:
        db.close()


def persist_and_hydrate_game_files(db) -> None:
    """Keep game HTML in Postgres and replay it onto disk. Never overwrite DB files from the seed pack."""
    changed = False
    pack = _pack_by_title()
    for game in db.query(Game).all():
        stored = dict(game.files or {})
        if not stored:
            stored = snapshot_game_files(game.id)
        if not stored:
            stored = _files_from_pack(game, pack.get(game.title))
        if stored and stored != (game.files or {}):
            game.files = stored
            changed = True
        if stored:
            entry = materialize_game_files(game.id, stored, game.entry_path or "index.html")
            if entry and entry != game.entry_path:
                game.entry_path = entry
                changed = True
    if changed:
        db.commit()


def _pack_by_title() -> dict:
    manifest_path = _seed_dir() / "manifest.json"
    if not manifest_path.exists():
        return {}
    return {
        (item.get("title") or item["file"]): item
        for item in json.loads(manifest_path.read_text(encoding="utf-8"))
    }


def _files_from_pack(game: Game, item: dict | None) -> dict:
    """One-time fill of an existing row whose files blob is empty. Does not insert games."""
    if not item:
        return {}
    src = _seed_dir() / item["file"]
    if not src.exists():
        return {}
    html = src.read_text(encoding="utf-8", errors="replace")
    save_uploaded_html(game.id, html, "index.html")
    return snapshot_game_files(game.id)


def persist_game_files(db, game: Game) -> None:
    game.files = snapshot_game_files(game.id)
    db.add(game)


def import_named_lab(db, title: str, owner_id) -> Game | None:
    """Insert one pack lab if that title is not already in the database."""
    if db.query(Game).filter(Game.title == title).first():
        return None
    item = _pack_by_title().get(title)
    if not item:
        return None
    src = _seed_dir() / item["file"]
    if not src.exists():
        return None
    html = src.read_text(encoding="utf-8", errors="replace")
    game_id = uuid4()
    entry = save_uploaded_html(game_id, html, "index.html")
    tags = ensure_topic_tag(
        item.get("topic_tags") or [],
        item.get("title") or "",
        item.get("file") or "",
    )
    game = Game(
        id=game_id,
        title=title,
        description=item.get("description") or "",
        owner_id=owner_id,
        source=GameSource.upload,
        topic_tags=tags,
        difficulty=int(item.get("difficulty") or 1),
        entry_path=entry,
        source_language=detect_language(
            title,
            item.get("description") or "",
            extract_visible_text(html),
        ),
        files=snapshot_game_files(game_id),
    )
    db.add(game)
    db.commit()
    db.refresh(game)
    return game


def normalize_game_topics(db) -> None:
    changed = False
    for game in db.query(Game).all():
        updated = ensure_topic_tag(game.topic_tags, game.title, game.description or "")
        if updated != list(game.topic_tags or []):
            game.topic_tags = updated
            changed = True
    if changed:
        db.commit()


def detect_missing_languages(db) -> None:
    changed = False
    for game in db.query(Game).all():
        sample = f"{game.title} {game.description or ''}"
        try:
            path = game_dir(game.id) / game.entry_path
            if path.exists():
                sample = (
                    f"{sample} "
                    f"{extract_visible_text(path.read_text(encoding='utf-8', errors='replace'))}"
                )
        except Exception:
            pass
        detected = detect_language(sample)
        if (getattr(game, "source_language", None) or "en") != detected:
            game.source_language = detected
            changed = True
    if changed:
        db.commit()


def seed_html_pack(db, owner_id) -> int:
    manifest_path = _seed_dir() / "manifest.json"
    if not manifest_path.exists():
        return 0
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    existing_titles = {g.title for g in db.query(Game.title).all()}
    added = 0
    for item in manifest:
        title = item.get("title") or item["file"]
        if title in existing_titles:
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
                source_language=detect_language(
                    title,
                    item.get("description") or "",
                    extract_visible_text(html),
                ),
                files=snapshot_game_files(game_id),
            )
        )
        existing_titles.add(title)
        added += 1
    if added:
        db.commit()
    return added
