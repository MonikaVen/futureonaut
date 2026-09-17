from collections import defaultdict
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.auth import get_current_user, require_roles
from app.database import get_db
from app.models import Game, GameComment, PlaySession, User, UserRole
from app.schemas import (
    CommentOut,
    DashboardStats,
    GameAnalyticsDetailOut,
    GameAnalyticsOut,
    PlatformPromptsOut,
    PlatformPromptsUpdate,
    PlatformStats,
    RecommendationOut,
    SessionDetail,
    UserOut,
    UserRoleUpdate,
)
from app.services.accounts import delete_user_keeping_games
from app.services.avatars import has_user_avatar
from app.services.game_analytics import build_game_analytics, build_game_analytics_detail
from app.services.handles import username_slug
from app.services.prompts import get_or_create_platform_settings
from app.services.recommendations import recommend_games

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard", response_model=DashboardStats)
def dashboard(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> DashboardStats:
    sessions = (
        db.query(PlaySession)
        .options(joinedload(PlaySession.game))
        .filter(PlaySession.user_id == user.id)
        .order_by(PlaySession.started_at.desc())
        .all()
    )
    total_points = sum(s.total_points for s in sessions)
    accuracies = [
        (s.correct_count / s.attempt_count) for s in sessions if s.attempt_count > 0
    ]
    times = [s.total_time_ms for s in sessions if s.total_time_ms > 0]
    per_game_map: dict[UUID, dict] = {}
    topic_map: dict[str, dict] = defaultdict(lambda: {"attempts": 0, "correct": 0, "points": 0, "sessions": 0})

    for s in sessions:
        g = s.game
        if g is None:
            continue
        slot = per_game_map.setdefault(
            g.id,
            {
                "game_id": str(g.id),
                "title": g.title,
                "best_score": 0,
                "plays": 0,
                "accuracy": 0.0,
                "completed": False,
                "levels_completed": 0,
                "total_levels": None,
                "_correct": 0,
                "_attempts": 0,
            },
        )
        slot["plays"] += 1
        slot["best_score"] = max(slot["best_score"], s.total_points)
        slot["_correct"] += s.correct_count
        slot["_attempts"] += s.attempt_count
        slot["levels_completed"] = max(slot["levels_completed"], s.levels_completed or 0)
        if s.total_levels:
            slot["total_levels"] = max(slot["total_levels"] or 0, s.total_levels)
        if s.ended_at is not None or (
            s.total_levels and (s.levels_completed or 0) >= s.total_levels
        ):
            slot["completed"] = True
        for tag in g.topic_tags or []:
            t = topic_map[tag]
            t["attempts"] += s.attempt_count
            t["correct"] += s.correct_count
            t["points"] += s.total_points
            t["sessions"] += 1

    per_game = []
    for slot in per_game_map.values():
        attempts = slot.pop("_attempts")
        correct = slot.pop("_correct")
        slot["accuracy"] = (correct / attempts) if attempts else 0.0
        per_game.append(slot)

    by_topic = []
    for tag, t in topic_map.items():
        by_topic.append(
            {
                "topic": tag,
                "sessions": t["sessions"],
                "points": t["points"],
                "accuracy": (t["correct"] / t["attempts"]) if t["attempts"] else 0.0,
            }
        )
    by_topic.sort(key=lambda x: x["accuracy"])

    recent = [
        SessionDetail(
            id=s.id,
            user_id=s.user_id,
            game_id=s.game_id,
            started_at=s.started_at,
            ended_at=s.ended_at,
            total_points=s.total_points,
            total_time_ms=s.total_time_ms,
            correct_count=s.correct_count,
            attempt_count=s.attempt_count,
            levels_completed=s.levels_completed or 0,
            total_levels=s.total_levels,
            game_title=s.game.title if s.game else None,
        )
        for s in sessions[:20]
    ]

    return DashboardStats(
        total_sessions=len(sessions),
        total_points=total_points,
        avg_accuracy=(sum(accuracies) / len(accuracies)) if accuracies else 0.0,
        avg_task_time_ms=(sum(times) / len(times)) if times else 0.0,
        games_solved=sum(1 for slot in per_game if slot.get("completed")),
        levels_solved=sum(int(slot.get("levels_completed") or 0) for slot in per_game),
        recent_sessions=recent,
        per_game=per_game,
        by_topic=by_topic,
    )


@router.get("/recommendations", response_model=list[RecommendationOut])
def recommendations(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[RecommendationOut]:
    return recommend_games(db, user.id)


admin_router = APIRouter(prefix="/admin", tags=["admin"])


@admin_router.get("/users", response_model=list[UserOut])
def list_users(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.admin)),
) -> list[User]:
    return db.query(User).order_by(User.created_at.desc()).all()


@admin_router.patch("/users/{user_id}/role", response_model=UserOut)
def update_role(
    user_id: UUID,
    body: UserRoleUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(UserRole.admin)),
) -> User:
    target = db.get(User, user_id)
    if target is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="User not found")
    if target.id == admin.id and body.role != UserRole.admin:
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail="Cannot demote yourself")
    target.role = body.role
    db.commit()
    db.refresh(target)
    return target


@admin_router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(UserRole.admin)),
) -> None:
    delete_user_keeping_games(db, actor=admin, user_id=user_id)


@admin_router.get("/stats", response_model=PlatformStats)
def platform_stats(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.admin)),
) -> PlatformStats:
    users = db.query(User).count()
    return PlatformStats(
        users=users,
        games=db.query(Game).count(),
        sessions=db.query(PlaySession).count(),
        creators=db.query(User).filter(User.role == UserRole.creator).count(),
        learners=db.query(User).filter(User.role == UserRole.learner).count(),
    )


@admin_router.get("/game-analytics", response_model=list[GameAnalyticsOut])
def game_analytics(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.admin)),
) -> list[GameAnalyticsOut]:
    return build_game_analytics(db)


@admin_router.get("/game-analytics/{game_id}", response_model=GameAnalyticsDetailOut)
def game_analytics_detail(
    game_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.admin)),
) -> GameAnalyticsDetailOut:
    return build_game_analytics_detail(db, game_id, include_player_emails=True)


@admin_router.get("/comments", response_model=list[CommentOut])
def list_all_comments(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.admin)),
) -> list[CommentOut]:
    from sqlalchemy.orm import joinedload

    comments = (
        db.query(GameComment)
        .options(joinedload(GameComment.user), joinedload(GameComment.game))
        .order_by(GameComment.created_at.desc())
        .limit(200)
        .all()
    )
    return [
        CommentOut(
            id=c.id,
            game_id=c.game_id,
            user_id=c.user_id,
            author_name=c.user.display_name if c.user else "Unknown",
            body=c.body,
            created_at=c.created_at,
            author_slug=username_slug(c.user) if c.user else None,
            author_has_avatar=has_user_avatar(c.user_id) if c.user_id else False,
        )
        for c in comments
    ]


@admin_router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_comment(
    comment_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.admin)),
) -> None:
    comment = db.get(GameComment, comment_id)
    if comment is None:
        raise HTTPException(status_code=404, detail="Comment not found")
    db.delete(comment)
    db.commit()


@admin_router.get("/prompts", response_model=PlatformPromptsOut)
def get_prompts(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.admin)),
) -> PlatformPromptsOut:
    settings = get_or_create_platform_settings(db)
    return PlatformPromptsOut(
        style_guidelines=settings.style_guidelines,
        generation_system_prompt=settings.generation_system_prompt,
        revise_system_prompt=settings.revise_system_prompt,
    )


@admin_router.put("/prompts", response_model=PlatformPromptsOut)
def update_prompts(
    body: PlatformPromptsUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.admin)),
) -> PlatformPromptsOut:
    from datetime import datetime, timezone

    settings = get_or_create_platform_settings(db)
    settings.style_guidelines = body.style_guidelines.strip()
    settings.generation_system_prompt = body.generation_system_prompt.strip()
    settings.revise_system_prompt = body.revise_system_prompt.strip()
    settings.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(settings)
    return PlatformPromptsOut(
        style_guidelines=settings.style_guidelines,
        generation_system_prompt=settings.generation_system_prompt,
        revise_system_prompt=settings.revise_system_prompt,
    )
