from __future__ import annotations

import secrets
import string
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.auth import get_current_user, require_roles
from app.database import get_db
from app.models import Classroom, ClassroomAssignment, ClassroomMember, Game, PlaySession, User, UserRole
from app.schemas import (
    AssignmentCreate,
    ClassroomCreate,
    ClassroomDetailOut,
    ClassroomJoin,
    ClassroomOut,
    StudentProgressOut,
)

router = APIRouter(prefix="/classrooms", tags=["classrooms"])


def _gen_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(6))


@router.post("", response_model=ClassroomOut, status_code=status.HTTP_201_CREATED)
def create_classroom(
    body: ClassroomCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Classroom:
    if user.role not in (UserRole.creator, UserRole.admin, UserRole.learner):
        raise HTTPException(status_code=403, detail="Cannot create classroom")
    code = _gen_code()
    while db.query(Classroom).filter(Classroom.join_code == code).first():
        code = _gen_code()
    classroom = Classroom(name=body.name.strip(), join_code=code, teacher_id=user.id)
    db.add(classroom)
    db.commit()
    db.refresh(classroom)
    return classroom


@router.post("/join", response_model=ClassroomOut)
def join_classroom(
    body: ClassroomJoin,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Classroom:
    classroom = db.query(Classroom).filter(Classroom.join_code == body.code.strip().upper()).first()
    if classroom is None:
        raise HTTPException(status_code=404, detail="Invalid class code")
    exists = (
        db.query(ClassroomMember)
        .filter(ClassroomMember.classroom_id == classroom.id, ClassroomMember.user_id == user.id)
        .first()
    )
    if not exists:
        db.add(ClassroomMember(classroom_id=classroom.id, user_id=user.id))
        db.commit()
    return classroom


@router.get("/mine", response_model=list[ClassroomOut])
def my_classrooms(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Classroom]:
    teaching = db.query(Classroom).filter(Classroom.teacher_id == user.id).order_by(Classroom.created_at.desc()).all()
    member_ids = [
        m.classroom_id
        for m in db.query(ClassroomMember).filter(ClassroomMember.user_id == user.id).all()
    ]
    enrolled = []
    if member_ids:
        enrolled = (
            db.query(Classroom)
            .filter(Classroom.id.in_(member_ids), Classroom.teacher_id != user.id)
            .order_by(Classroom.created_at.desc())
            .all()
        )
    seen = set()
    out = []
    for c in teaching + enrolled:
        if c.id not in seen:
            seen.add(c.id)
            out.append(c)
    return out


@router.get("/{classroom_id}", response_model=ClassroomDetailOut)
def classroom_detail(
    classroom_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ClassroomDetailOut:
    classroom = db.get(Classroom, classroom_id)
    if classroom is None:
        raise HTTPException(status_code=404, detail="Classroom not found")
    is_teacher = classroom.teacher_id == user.id
    is_member = (
        db.query(ClassroomMember)
        .filter(ClassroomMember.classroom_id == classroom.id, ClassroomMember.user_id == user.id)
        .first()
        is not None
    )
    if not is_teacher and not is_member:
        raise HTTPException(status_code=403, detail="Not in this class")

    assignments = (
        db.query(ClassroomAssignment)
        .options(joinedload(ClassroomAssignment.game))
        .filter(ClassroomAssignment.classroom_id == classroom.id)
        .order_by(ClassroomAssignment.created_at.desc())
        .all()
    )
    members = (
        db.query(ClassroomMember)
        .options(joinedload(ClassroomMember.user))
        .filter(ClassroomMember.classroom_id == classroom.id)
        .all()
    )

    progress: list[StudentProgressOut] = []
    if is_teacher:
        game_ids = [a.game_id for a in assignments]
        for member in members:
            for gid in game_ids:
                session = (
                    db.query(PlaySession)
                    .filter(PlaySession.user_id == member.user_id, PlaySession.game_id == gid)
                    .order_by(PlaySession.started_at.desc())
                    .first()
                )
                game = db.get(Game, gid)
                if not game:
                    continue
                acc = 0.0
                if session and session.attempt_count:
                    acc = session.correct_count / session.attempt_count
                progress.append(
                    StudentProgressOut(
                        student_name=member.user.display_name if member.user else "?",
                        student_email=member.user.email if member.user else "",
                        game_id=gid,
                        game_title=game.title,
                        completed=bool(session and session.ended_at),
                        points=session.total_points if session else 0,
                        accuracy=acc,
                        levels_completed=session.levels_completed if session else 0,
                        total_levels=session.total_levels if session else None,
                    )
                )

    return ClassroomDetailOut(
        id=classroom.id,
        name=classroom.name,
        join_code=classroom.join_code if is_teacher else "••••••",
        teacher_id=classroom.teacher_id,
        is_teacher=is_teacher,
        member_count=len(members),
        assignments=[
            {
                "id": str(a.id),
                "game_id": str(a.game_id),
                "game_title": a.game.title if a.game else "",
                "created_at": a.created_at.isoformat(),
            }
            for a in assignments
        ],
        progress=progress,
    )


@router.post("/{classroom_id}/assignments", status_code=status.HTTP_201_CREATED)
def assign_game(
    classroom_id: UUID,
    body: AssignmentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    classroom = db.get(Classroom, classroom_id)
    if classroom is None:
        raise HTTPException(status_code=404, detail="Classroom not found")
    if classroom.teacher_id != user.id:
        raise HTTPException(status_code=403, detail="Only the teacher can assign games")
    game = db.get(Game, body.game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")
    exists = (
        db.query(ClassroomAssignment)
        .filter(ClassroomAssignment.classroom_id == classroom.id, ClassroomAssignment.game_id == game.id)
        .first()
    )
    if exists:
        raise HTTPException(status_code=400, detail="Game already assigned")
    db.add(ClassroomAssignment(classroom_id=classroom.id, game_id=game.id))
    db.commit()
    return {"ok": True}
