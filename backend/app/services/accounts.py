from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import (
    Classroom,
    ClassroomMember,
    Game,
    GameComment,
    GameDraft,
    GameLike,
    GameView,
    PlaySession,
    User,
    UserRole,
)


def delete_user_keeping_games(db: Session, *, actor: User, user_id: UUID) -> None:
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    if target.id == actor.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    if target.role == UserRole.admin:
        admins = db.query(User).filter(User.role == UserRole.admin).count()
        if admins <= 1:
            raise HTTPException(status_code=400, detail="Cannot delete the last admin")

    for game in db.query(Game).filter(Game.owner_id == target.id).all():
        game.owner_id = None
    db.flush()
    db.query(PlaySession).filter(PlaySession.user_id == target.id).update(
        {PlaySession.user_id: None}, synchronize_session=False
    )
    db.query(GameView).filter(GameView.user_id == target.id).update(
        {GameView.user_id: None}, synchronize_session=False
    )
    db.query(GameLike).filter(GameLike.user_id == target.id).delete(synchronize_session=False)
    db.query(GameComment).filter(GameComment.user_id == target.id).delete(synchronize_session=False)
    db.query(GameDraft).filter(GameDraft.owner_id == target.id).delete(synchronize_session=False)
    db.query(ClassroomMember).filter(ClassroomMember.user_id == target.id).delete(
        synchronize_session=False
    )
    classrooms = db.query(Classroom).filter(Classroom.teacher_id == target.id).all()
    for classroom in classrooms:
        db.delete(classroom)
    db.delete(target)
    db.commit()
