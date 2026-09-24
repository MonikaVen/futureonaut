from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.orm import Session, joinedload

from app.models import Game, PlaySession
from app.schemas import GameOut, RecommendationOut
from app.services.avatars import has_user_avatar
from app.services.handles import profile_slug_for, split_handle
from app.services.snapshot import has_game_screenshot
from app.services.topics import TOPICS, normalize_topic

NEW_GAME_DAYS = 7


def game_is_new(created_at: datetime | None, *, now: datetime | None = None) -> bool:
    if created_at is None:
        return False
    current = now or datetime.now(timezone.utc)
    created = created_at if created_at.tzinfo else created_at.replace(tzinfo=timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current - created <= timedelta(days=NEW_GAME_DAYS)


def game_to_out(game: Game) -> GameOut:
    owner = getattr(game, "owner", None)
    owner_slug = profile_slug_for(owner) if owner is not None else None
    if not owner_slug:
        parts = split_handle(getattr(game, "handle", None))
        owner_slug = parts[0] if parts else None
    owner_name = getattr(owner, "display_name", None) if owner is not None else None
    owner_id = getattr(game, "owner_id", None)
    return GameOut(
        id=game.id,
        title=game.title,
        description=game.description,
        owner_id=owner_id,
        source=game.source,
        topic_tags=game.topic_tags or [],
        difficulty=game.difficulty,
        entry_path=game.entry_path,
        template_type=game.template_type,
        source_language=getattr(game, "source_language", None) or "en",
        handle=getattr(game, "handle", None),
        created_at=game.created_at,
        play_url=f"/api/games/{game.id}/files/{game.entry_path}",
        has_screenshot=has_game_screenshot(game.id),
        is_new=game_is_new(getattr(game, "created_at", None)),
        owner_slug=owner_slug,
        owner_name=owner_name,
        owner_has_avatar=has_user_avatar(owner_id) if owner_id else False,
        is_public=getattr(game, "is_public", True) is not False,
    )


def _canonical_topic(tags: list[str] | None) -> str | None:
    for tag in tags or []:
        n = normalize_topic(tag)
        if n in TOPICS:
            return n
    return None


def recommend_games(db: Session, user_id: UUID, limit: int = 8) -> list[RecommendationOut]:
    sessions = (
        db.query(PlaySession)
        .options(joinedload(PlaySession.game))
        .filter(PlaySession.user_id == user_id)
        .order_by(PlaySession.started_at.desc())
        .all()
    )
    now = datetime.now(timezone.utc)
    played_ids = {s.game_id for s in sessions}
    last_played: dict[UUID, datetime] = {}
    topic_stats: dict[str, dict] = defaultdict(
        lambda: {"attempts": 0, "correct": 0, "sessions": 0, "last": None}
    )
    difficulty_sum = 0
    difficulty_n = 0

    for s in sessions:
        if not s.game:
            continue
        last_played[s.game_id] = max(last_played.get(s.game_id, s.started_at), s.started_at)
        difficulty_sum += s.game.difficulty
        difficulty_n += 1
        topic = _canonical_topic(s.game.topic_tags) or "AI"
        st = topic_stats[topic]
        st["attempts"] += s.attempt_count
        st["correct"] += s.correct_count
        st["sessions"] += 1
        st["last"] = s.started_at if st["last"] is None or s.started_at > st["last"] else st["last"]

    weak_topics = sorted(
        topic_stats.keys(),
        key=lambda t: (
            (topic_stats[t]["correct"] / topic_stats[t]["attempts"]) if topic_stats[t]["attempts"] else 1.0,
            -topic_stats[t]["sessions"],
        ),
    )[:4]
    avg_diff = round(difficulty_sum / difficulty_n) if difficulty_n else 1

    all_games = db.query(Game).order_by(Game.created_at.desc()).all()
    scored: list[RecommendationOut] = []

    for game in all_games:
        if getattr(game, "is_public", True) is False:
            continue
        reason_parts: list[str] = []
        score = 0.0
        game_topic = _canonical_topic(game.topic_tags)

        if game_topic and game_topic in weak_topics:
            acc = (
                topic_stats[game_topic]["correct"] / topic_stats[game_topic]["attempts"]
                if topic_stats[game_topic]["attempts"]
                else 1.0
            )
            score += 55
            reason_parts.append(f"Strengthen {game_topic} (your accuracy {acc * 100:.0f}%)")

        if game.id not in played_ids:
            score += 30
            reason_parts.append("New game you haven't tried")
        else:
            lp = last_played.get(game.id)
            if lp:
                days = (now - lp.replace(tzinfo=timezone.utc if lp.tzinfo is None else lp.tzinfo)).days
                if days >= 7:
                    score += 20
                    reason_parts.append(f"Spaced review — last played {days}d ago")
                elif days >= 3:
                    score += 10
                    reason_parts.append("Good time for a refresher")
            score -= 10

        if game.difficulty == avg_diff:
            score += 18
            reason_parts.append("Matches your usual level")
        elif game.difficulty == avg_diff + 1:
            score += 14
            reason_parts.append("Gentle step up in difficulty")
        elif game.difficulty < avg_diff:
            score += 6
            reason_parts.append("Confidence-building review")
        else:
            score -= (game.difficulty - avg_diff) * 4

        if not reason_parts:
            reason_parts.append("Popular pick in the catalog")
            score += 5

        scored.append(
            RecommendationOut(game=game_to_out(game), reason=" · ".join(reason_parts), score=score)
        )

    scored.sort(key=lambda r: r.score, reverse=True)
    return scored[:limit]
