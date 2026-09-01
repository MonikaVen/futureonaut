from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.auth import get_current_user, require_roles
from app.database import get_db
from app.models import Game, GameComment, GameLike, User, UserRole
from app.schemas import CommentCreate, CommentOut, LikeToggleOut

router = APIRouter(prefix="/games", tags=["social"])


def _comment_out(comment: GameComment) -> CommentOut:
    return CommentOut(
        id=comment.id,
        game_id=comment.game_id,
        user_id=comment.user_id,
        author_name=comment.user.display_name if comment.user else "Unknown",
        body=comment.body,
        created_at=comment.created_at,
    )


@router.get("/{game_id}/comments", response_model=list[CommentOut])
def list_comments(game_id: UUID, db: Session = Depends(get_db)) -> list[CommentOut]:
    game = db.get(Game, game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")
    comments = (
        db.query(GameComment)
        .options(joinedload(GameComment.user))
        .filter(GameComment.game_id == game_id)
        .order_by(GameComment.created_at.desc())
        .limit(100)
        .all()
    )
    return [_comment_out(c) for c in comments]


@router.post("/{game_id}/comments", response_model=CommentOut, status_code=status.HTTP_201_CREATED)
def add_comment(
    game_id: UUID,
    body: CommentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CommentOut:
    game = db.get(Game, game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")
    comment = GameComment(game_id=game.id, user_id=user.id, body=body.body.strip())
    db.add(comment)
    db.commit()
    db.refresh(comment)
    comment.user = user
    return _comment_out(comment)


@router.post("/{game_id}/like", response_model=LikeToggleOut)
def toggle_like(
    game_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> LikeToggleOut:
    game = db.get(Game, game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")
    existing = (
        db.query(GameLike)
        .filter(GameLike.game_id == game_id, GameLike.user_id == user.id)
        .first()
    )
    if existing:
        db.delete(existing)
        liked = False
    else:
        db.add(GameLike(game_id=game.id, user_id=user.id))
        liked = True
    db.commit()
    like_count = (
        db.query(GameLike).filter(GameLike.game_id == game_id).count()
    )
    return LikeToggleOut(liked=liked, like_count=like_count)
