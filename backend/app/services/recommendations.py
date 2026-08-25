from __future__ import annotations

from collections import defaultdict
from uuid import UUID

from sqlalchemy.orm import Session, joinedload

from app.models import Game, PlaySession
from app.schemas import GameOut, RecommendationOut


def game_to_out(game: Game) -> GameOut:
    return GameOut(
        id=game.id,
        title=game.title,
        description=game.description,
        owner_id=game.owner_id,
        source=game.source,
        topic_tags=game.topic_tags or [],
        difficulty=game.difficulty,
        entry_path=game.entry_path,
        template_type=game.template_type,
        source_language=getattr(game, "source_language", None) or "en",
        created_at=game.created_at,
        play_url=f"/api/games/{game.id}/files/{game.entry_path}",
    )


def recommend_games(db: Session, user_id: UUID, limit: int = 8) -> list[RecommendationOut]:
    sessions = (
        db.query(PlaySession)
        .options(joinedload(PlaySession.game))
        .filter(PlaySession.user_id == user_id)
        .all()
    )
    played_ids = {s.game_id for s in sessions}
    topic_stats: dict[str, dict[str, float]] = defaultdict(
        lambda: {"attempts": 0, "correct": 0, "time": 0, "sessions": 0}
    )
    difficulty_sum = 0
    difficulty_n = 0

    for s in sessions:
        if not s.game:
            continue
        difficulty_sum += s.game.difficulty
        difficulty_n += 1
        accuracy = (s.correct_count / s.attempt_count) if s.attempt_count else 0
        for tag in s.game.topic_tags or []:
            st = topic_stats[tag]
            st["attempts"] += s.attempt_count
            st["correct"] += s.correct_count
            st["time"] += s.total_time_ms
            st["sessions"] += 1
            st["accuracy"] = (st["correct"] / st["attempts"]) if st["attempts"] else accuracy

    weak_topics = sorted(
        topic_stats.keys(),
        key=lambda t: (topic_stats[t].get("accuracy", 1.0), -topic_stats[t]["time"]),
    )[:5]
    avg_diff = round(difficulty_sum / difficulty_n) if difficulty_n else 1

    all_games = db.query(Game).order_by(Game.created_at.desc()).all()
    scored: list[RecommendationOut] = []

    for game in all_games:
        reason_parts: list[str] = []
        score = 0.0
        tags = set(game.topic_tags or [])
        weak_overlap = tags.intersection(weak_topics)
        if weak_overlap:
            score += 50 + 10 * len(weak_overlap)
            reason_parts.append(f"Practice weak topics: {', '.join(sorted(weak_overlap))}")
        if game.id not in played_ids:
            score += 25
            reason_parts.append("New game you haven't played")
        else:
            score -= 15
        diff_delta = abs(game.difficulty - avg_diff)
        if diff_delta == 0:
            score += 15
            reason_parts.append("Matches your usual difficulty")
        elif game.difficulty == avg_diff + 1:
            score += 10
            reason_parts.append("Slightly harder stretch")
        else:
            score -= diff_delta * 3
        if not reason_parts:
            reason_parts.append("Popular learning activity")
            score += 5
        scored.append(
            RecommendationOut(game=game_to_out(game), reason="; ".join(reason_parts), score=score)
        )

    scored.sort(key=lambda r: r.score, reverse=True)
    # Prefer not repeating the same top reasons-only; still return best N
    return scored[:limit]
