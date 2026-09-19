"""Seed demo template games and HTML pack from backend/seed_games/."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from uuid import uuid4

from app.database import SessionLocal
from app.models import Game, GameSource, User, UserRole
from app.services.i18n import detect_language, extract_visible_text
from app.services.storage import game_dir, save_uploaded_html, write_template_game
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


def _futureonaut(db) -> User | None:
    from app.config import get_settings

    settings = get_settings()
    return (
        db.query(User)
        .filter(User.email == settings.creator_email.lower())
        .first()
    )


def seed_demo_games() -> None:
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.role == UserRole.admin).first()
        if admin is None:
            return
        publisher = _futureonaut(db) or admin

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
                        owner_id=publisher.id,
                        source=source,
                        topic_tags=content["topic_tags"],
                        difficulty=content["difficulty"],
                        entry_path=entry,
                        template_type=template_type,
                        source_language=detect_language(
                            content["title"], content["description"]
                        ),
                    )
                )
            db.commit()

        seed_html_pack(db, publisher.id)
        assign_seed_pack_owner(db, publisher.id)
        refresh_seed_game_files(db)
        normalize_game_topics(db)
        detect_missing_languages(db)
        restore_missing_game_files(db)
    finally:
        db.close()


def assign_seed_pack_owner(db, owner_id) -> None:
    """Point seeded HTML labs at the Futureonaut creator account."""
    manifest_path = _seed_dir() / "manifest.json"
    if not manifest_path.exists():
        return
    titles = {
        item.get("title") or item["file"]
        for item in json.loads(manifest_path.read_text(encoding="utf-8"))
    }
    changed = False
    for game in db.query(Game).filter(Game.title.in_(titles)).all():
        if game.owner_id != owner_id:
            game.owner_id = owner_id
            changed = True
    if changed:
        db.commit()


def refresh_seed_game_files(db) -> None:
    """Overwrite seeded HTML from the pack so graphic/gameplay updates land on restart."""
    manifest_path = _seed_dir() / "manifest.json"
    if not manifest_path.exists():
        return
    by_title = {
        (item.get("title") or item["file"]): item
        for item in json.loads(manifest_path.read_text(encoding="utf-8"))
    }
    changed = False
    for game in db.query(Game).all():
        item = by_title.get(game.title)
        if not item:
            continue
        src = _seed_dir() / item["file"]
        if not src.exists():
            continue
        html = src.read_text(encoding="utf-8", errors="replace")
        save_uploaded_html(game.id, html, game.entry_path or "index.html")
        i18n_dir = game_dir(game.id) / "i18n"
        if i18n_dir.exists():
            shutil.rmtree(i18n_dir)
        desc = item.get("description") or game.description
        if desc and game.description != desc:
            game.description = desc
        changed = True
    if changed:
        db.commit()


def restore_missing_game_files(db) -> None:
    """Rehydrate game HTML from seed pack when the volume is empty (e.g. Azure ephemeral disk)."""
    manifest_path = _seed_dir() / "manifest.json"
    if not manifest_path.exists():
        return
    by_title = {
        (item.get("title") or item["file"]): item
        for item in json.loads(manifest_path.read_text(encoding="utf-8"))
    }
    for game in db.query(Game).all():
        target = game_dir(game.id) / (game.entry_path or "index.html")
        if target.exists():
            continue
        item = by_title.get(game.title)
        if item:
            src = _seed_dir() / item["file"]
            if src.exists():
                html = src.read_text(encoding="utf-8", errors="replace")
                save_uploaded_html(game.id, html, "index.html")
                continue
        if game.template_type:
            # cannot rebuild without content.json; skip
            continue


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


def seed_html_pack(db, owner_id) -> None:
    manifest_path = _seed_dir() / "manifest.json"
    if not manifest_path.exists():
        return
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
            )
        )
        existing_titles.add(title)
        added += 1
    if added:
        db.commit()
