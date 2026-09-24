from __future__ import annotations

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.models import Classroom, ClassroomAssignment, ClassroomMember, Game, User, UserRole


def game_is_public(game: Game) -> bool:
    return getattr(game, "is_public", True) is not False


def can_view_game(db: Session, game: Game, user: User | None) -> bool:
    """Public games are open. Private games are visible to the owner, admins, and a class that has them."""
    if game_is_public(game):
        return True
    if user is None:
        return False
    if user.role == UserRole.admin:
        return True
    if game.owner_id and game.owner_id == user.id:
        return True
    assigned = (
        db.query(ClassroomAssignment.id)
        .join(Classroom, Classroom.id == ClassroomAssignment.classroom_id)
        .outerjoin(
            ClassroomMember,
            and_(
                ClassroomMember.classroom_id == Classroom.id,
                ClassroomMember.user_id == user.id,
            ),
        )
        .filter(ClassroomAssignment.game_id == game.id)
        .filter(
            or_(
                Classroom.teacher_id == user.id,
                and_(ClassroomAssignment.published.is_(True), ClassroomMember.id.isnot(None)),
            )
        )
        .first()
    )
    return assigned is not None
