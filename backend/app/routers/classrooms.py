from __future__ import annotations

import secrets
import string
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.auth import get_current_user
from app.database import get_db
from app.models import Classroom, ClassroomAssignment, ClassroomMember, Game, PlaySession, User, UserRole
from app.schemas import (
    AssignmentCreate,
    ClassroomAssignmentOut,
    ClassroomCreate,
    ClassroomDetailOut,
    ClassroomJoin,
    ClassroomOut,
    StudentProgressOut,
)
from app.services.progress import (
    best_sessions_by_game,
    progress_from_session,
    session_is_solved,
    summarize_assignment,
)

router = APIRouter(prefix="/classrooms", tags=["classrooms"])


def _gen_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(6))


def _require_classroom(db: Session, classroom_id: UUID) -> Classroom:
    classroom = db.get(Classroom, classroom_id)
    if classroom is None:
        raise HTTPException(status_code=404, detail="Classroom not found")
    return classroom


def _is_member(db: Session, classroom_id: UUID, user_id: UUID) -> bool:
    return (
        db.query(ClassroomMember)
        .filter(ClassroomMember.classroom_id == classroom_id, ClassroomMember.user_id == user_id)
        .first()
        is not None
    )


def _best_session(db: Session, user_id: UUID, game_id: UUID) -> PlaySession | None:
    return best_sessions_by_game(db, user_id, [game_id]).get(game_id)


def _assignment_out(
    db: Session,
    assignment: ClassroomAssignment,
    user_id: UUID,
    *,
    class_stats: dict | None = None,
) -> ClassroomAssignmentOut:
    game = assignment.game or db.get(Game, assignment.game_id)
    progress = progress_from_session(_best_session(db, user_id, assignment.game_id))
    extra = class_stats or {}
    return ClassroomAssignmentOut(
        id=assignment.id,
        game_id=assignment.game_id,
        game_title=game.title if game else "",
        created_at=assignment.created_at,
        **progress,
        **extra,
    )


@router.post("", response_model=ClassroomOut, status_code=status.HTTP_201_CREATED)
def create_classroom(
    body: ClassroomCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Classroom:
    if user.role not in (UserRole.creator, UserRole.admin, UserRole.teacher):
        raise HTTPException(status_code=403, detail="Only teachers can create a classroom")
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
    classroom = _require_classroom(db, classroom_id)
    is_teacher = classroom.teacher_id == user.id
    is_member = _is_member(db, classroom.id, user.id)
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
    member_ids = [m.user_id for m in members]
    assignment_stats: dict = {}
    if is_teacher:
        game_ids = [a.game_id for a in assignments]
        for member in members:
            for gid in game_ids:
                session = _best_session(db, member.user_id, gid)
                game = db.get(Game, gid)
                if not game:
                    continue
                stats = progress_from_session(session)
                progress.append(
                    StudentProgressOut(
                        student_id=member.user_id,
                        student_name=member.user.display_name if member.user else "?",
                        student_email=member.user.email if member.user else "",
                        game_id=gid,
                        game_title=game.title,
                        **stats,
                    )
                )
        for assignment in assignments:
            per_member = [_best_session(db, mid, assignment.game_id) for mid in member_ids]
            assignment_stats[assignment.id] = summarize_assignment(per_member, len(member_ids))

    assignment_outs = [
        _assignment_out(db, a, user.id, class_stats=assignment_stats.get(a.id))
        for a in assignments
    ]
    solved_assignments = sum(1 for a in assignment_outs if a.completed)
    students_solved_all = 0
    if is_teacher and assignments:
        for member in members:
            if all(
                session_is_solved(_best_session(db, member.user_id, a.game_id))
                for a in assignments
            ):
                students_solved_all += 1

    return ClassroomDetailOut(
        id=classroom.id,
        name=classroom.name,
        join_code=classroom.join_code if is_teacher else "••••••",
        teacher_id=classroom.teacher_id,
        is_teacher=is_teacher,
        member_count=len(members),
        assignments=assignment_outs,
        progress=progress,
        solved_assignments=solved_assignments,
        total_assignments=len(assignments),
        students_solved_all=students_solved_all,
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


@router.delete("/{classroom_id}/assignments/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def unassign_game(
    classroom_id: UUID,
    assignment_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    classroom = _require_classroom(db, classroom_id)
    if classroom.teacher_id != user.id:
        raise HTTPException(status_code=403, detail="Only the teacher can unassign games")
    assignment = db.get(ClassroomAssignment, assignment_id)
    if assignment is None or assignment.classroom_id != classroom.id:
        raise HTTPException(status_code=404, detail="Assignment not found")
    db.delete(assignment)
    db.commit()


@router.post("/{classroom_id}/leave", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def leave_classroom(
    classroom_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    classroom = _require_classroom(db, classroom_id)
    if classroom.teacher_id == user.id:
        raise HTTPException(status_code=400, detail="Teacher cannot leave — delete the class instead")
    member = (
        db.query(ClassroomMember)
        .filter(ClassroomMember.classroom_id == classroom.id, ClassroomMember.user_id == user.id)
        .first()
    )
    if member is None:
        raise HTTPException(status_code=404, detail="Not in this class")
    db.delete(member)
    db.commit()


@router.delete("/{classroom_id}/members/{member_user_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def remove_member(
    classroom_id: UUID,
    member_user_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    classroom = _require_classroom(db, classroom_id)
    if classroom.teacher_id != user.id:
        raise HTTPException(status_code=403, detail="Only the teacher can remove members")
    if member_user_id == classroom.teacher_id:
        raise HTTPException(status_code=400, detail="Cannot remove the teacher")
    member = (
        db.query(ClassroomMember)
        .filter(ClassroomMember.classroom_id == classroom.id, ClassroomMember.user_id == member_user_id)
        .first()
    )
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found")
    db.delete(member)
    db.commit()


@router.delete("/{classroom_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_classroom(
    classroom_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    classroom = _require_classroom(db, classroom_id)
    if classroom.teacher_id != user.id and user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Only the teacher can delete this class")
    db.delete(classroom)
    db.commit()
