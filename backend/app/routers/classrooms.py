from __future__ import annotations

import secrets
import string
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.auth import get_current_user, hash_password
from app.database import get_db
from app.models import (
    ClassGroup,
    Classroom,
    ClassroomAssignment,
    ClassroomMember,
    Game,
    PlaySession,
    User,
    UserRole,
)
from app.schemas import (
    AssignmentCreate,
    AssignmentUpdate,
    ClassGroupCreate,
    ClassGroupOut,
    ClassIssuedOut,
    ClassMemberOut,
    ClassMemberUpdate,
    ClassroomAssignmentOut,
    ClassroomCreate,
    ClassroomDetailOut,
    ClassroomJoin,
    ClassroomOut,
    IssuedLoginOut,
    StudentAccountCreate,
    StudentPasswordUpdate,
    StudentProgressOut,
)
from app.services.progress import (
    best_sessions_by_game,
    progress_from_session,
    session_is_solved,
    summarize_assignment,
)

router = APIRouter(prefix="/classrooms", tags=["classrooms"])

JOIN_CODE_MASK = "••••••"


def _gen_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(6))


def _gen_password() -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(12))


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


def _can_see_join_code(classroom: Classroom, user: User) -> bool:
    return classroom.teacher_id == user.id or user.role == UserRole.admin


def _classroom_out(classroom: Classroom, user: User) -> ClassroomOut:
    return ClassroomOut(
        id=classroom.id,
        name=classroom.name,
        join_code=classroom.join_code if _can_see_join_code(classroom, user) else JOIN_CODE_MASK,
        teacher_id=classroom.teacher_id,
        created_at=classroom.created_at,
    )


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
        config=assignment.config or "",
        published=bool(assignment.published),
        created_at=assignment.created_at,
        **progress,
        **extra,
    )


def _require_teacher(classroom: Classroom, user: User) -> None:
    if classroom.teacher_id != user.id:
        raise HTTPException(status_code=403, detail="Only the teacher can do that")


def _learner_member(db: Session, classroom: Classroom, user_id: UUID) -> ClassroomMember:
    member = (
        db.query(ClassroomMember)
        .options(joinedload(ClassroomMember.user))
        .filter(ClassroomMember.classroom_id == classroom.id, ClassroomMember.user_id == user_id)
        .first()
    )
    if member is None or member.user is None:
        raise HTTPException(status_code=404, detail="Student not found")
    if member.user.role != UserRole.learner:
        raise HTTPException(status_code=400, detail="Only student accounts can be managed here")
    return member


def _gen_password() -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(12))


@router.post("", response_model=ClassroomOut, status_code=status.HTTP_201_CREATED)
def create_classroom(
    body: ClassroomCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ClassroomOut:
    if user.role not in (UserRole.creator, UserRole.admin, UserRole.teacher):
        raise HTTPException(status_code=403, detail="Only teachers can create a classroom")
    code = _gen_code()
    while db.query(Classroom).filter(Classroom.join_code == code).first():
        code = _gen_code()
    classroom = Classroom(name=body.name.strip(), join_code=code, teacher_id=user.id)
    db.add(classroom)
    db.commit()
    db.refresh(classroom)
    return _classroom_out(classroom, user)


@router.post("/join", response_model=ClassroomOut)
def join_classroom(
    body: ClassroomJoin,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ClassroomOut:
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
    return _classroom_out(classroom, user)


@router.get("/mine", response_model=list[ClassroomOut])
def my_classrooms(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ClassroomOut]:
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
    out: list[ClassroomOut] = []
    for c in teaching + enrolled:
        if c.id not in seen:
            seen.add(c.id)
            out.append(_classroom_out(c, user))
    return out


@router.get("/issued", response_model=list[ClassIssuedOut])
def issued_for_student(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ClassIssuedOut]:
    memberships = db.query(ClassroomMember).filter(ClassroomMember.user_id == user.id).all()
    if not memberships:
        return []
    class_ids = [m.classroom_id for m in memberships]
    rows = (
        db.query(ClassroomAssignment)
        .options(joinedload(ClassroomAssignment.game), joinedload(ClassroomAssignment.classroom))
        .filter(
            ClassroomAssignment.classroom_id.in_(class_ids),
            ClassroomAssignment.published.is_(True),
        )
        .order_by(ClassroomAssignment.created_at.desc())
        .all()
    )
    return [
        ClassIssuedOut(
            classroom_id=row.classroom_id,
            classroom_name=row.classroom.name if row.classroom else "",
            assignment_id=row.id,
            game_id=row.game_id,
            game_title=row.game.title if row.game else "",
            config=row.config or "",
        )
        for row in rows
    ]


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
    if not is_teacher:
        assignments = [a for a in assignments if a.published]
    members = (
        db.query(ClassroomMember)
        .options(joinedload(ClassroomMember.user))
        .filter(ClassroomMember.classroom_id == classroom.id)
        .all()
    )
    groups = (
        db.query(ClassGroup)
        .filter(ClassGroup.classroom_id == classroom.id)
        .order_by(ClassGroup.name.asc())
        .all()
    )
    group_names = {g.id: g.name for g in groups}

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

    group_counts: dict[UUID, int] = {}
    for member in members:
        if member.group_id:
            group_counts[member.group_id] = group_counts.get(member.group_id, 0) + 1
    member_outs = [
        ClassMemberOut(
            user_id=member.user_id,
            display_name=member.user.display_name if member.user else "",
            email=member.user.email if member.user else "",
            group_id=member.group_id,
            group_name=group_names.get(member.group_id, "") if member.group_id else "",
        )
        for member in members
        if is_teacher and member.user and member.user.role == UserRole.learner
    ]
    return ClassroomDetailOut(
        id=classroom.id,
        name=classroom.name,
        join_code=classroom.join_code if is_teacher else JOIN_CODE_MASK,
        teacher_id=classroom.teacher_id,
        is_teacher=is_teacher,
        member_count=len(members),
        assignments=assignment_outs,
        progress=progress,
        groups=[
            ClassGroupOut(id=g.id, name=g.name, member_count=group_counts.get(g.id, 0))
            for g in groups
        ]
        if is_teacher
        else [],
        members=member_outs,
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
    db.add(
        ClassroomAssignment(
            classroom_id=classroom.id,
            game_id=game.id,
            config=(body.config or "").strip(),
            published=body.published,
        )
    )
    db.commit()
    return {"ok": True}


@router.patch("/{classroom_id}/assignments/{assignment_id}", response_model=ClassroomAssignmentOut)
def update_assignment(
    classroom_id: UUID,
    assignment_id: UUID,
    body: AssignmentUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ClassroomAssignmentOut:
    classroom = _require_classroom(db, classroom_id)
    _require_teacher(classroom, user)
    assignment = db.get(ClassroomAssignment, assignment_id)
    if assignment is None or assignment.classroom_id != classroom.id:
        raise HTTPException(status_code=404, detail="Assignment not found")
    if body.config is not None:
        assignment.config = body.config.strip()
    if body.published is not None:
        assignment.published = body.published
    db.commit()
    db.refresh(assignment)
    return _assignment_out(db, assignment, user.id)


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


@router.post("/{classroom_id}/students", response_model=IssuedLoginOut, status_code=status.HTTP_201_CREATED)
def create_student(
    classroom_id: UUID,
    body: StudentAccountCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> IssuedLoginOut:
    classroom = _require_classroom(db, classroom_id)
    _require_teacher(classroom, user)
    email = body.email.lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    if body.group_id is not None:
        group = db.get(ClassGroup, body.group_id)
        if group is None or group.classroom_id != classroom.id:
            raise HTTPException(status_code=404, detail="Group not found")
    password = body.password or _gen_password()
    student = User(
        email=email,
        password_hash=hash_password(password),
        display_name=(body.display_name or email.split("@")[0]).strip(),
        role=UserRole.learner,
        managed_by_id=user.id,
    )
    db.add(student)
    db.flush()
    from app.services.handles import allocate_profile_slug

    student.profile_slug = allocate_profile_slug(db, student)
    db.add(ClassroomMember(classroom_id=classroom.id, user_id=student.id, group_id=body.group_id))
    db.commit()
    db.refresh(student)
    return IssuedLoginOut(
        user_id=student.id,
        email=student.email,
        display_name=student.display_name,
        password=password,
    )


@router.patch("/{classroom_id}/students/{student_id}/password", response_model=IssuedLoginOut)
def set_student_password(
    classroom_id: UUID,
    student_id: UUID,
    body: StudentPasswordUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> IssuedLoginOut:
    classroom = _require_classroom(db, classroom_id)
    _require_teacher(classroom, user)
    member = _learner_member(db, classroom, student_id)
    member.user.password_hash = hash_password(body.password)
    db.commit()
    return IssuedLoginOut(
        user_id=member.user.id,
        email=member.user.email,
        display_name=member.user.display_name,
        password=body.password,
    )


@router.post("/{classroom_id}/groups", response_model=ClassGroupOut, status_code=status.HTTP_201_CREATED)
def create_group(
    classroom_id: UUID,
    body: ClassGroupCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ClassGroupOut:
    classroom = _require_classroom(db, classroom_id)
    _require_teacher(classroom, user)
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Group name is required")
    group = ClassGroup(classroom_id=classroom.id, name=name)
    db.add(group)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="A group with that name already exists")
    db.refresh(group)
    return ClassGroupOut(id=group.id, name=group.name, member_count=0)


@router.delete("/{classroom_id}/groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_group(
    classroom_id: UUID,
    group_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    classroom = _require_classroom(db, classroom_id)
    _require_teacher(classroom, user)
    group = db.get(ClassGroup, group_id)
    if group is None or group.classroom_id != classroom.id:
        raise HTTPException(status_code=404, detail="Group not found")
    (
        db.query(ClassroomMember)
        .filter(ClassroomMember.group_id == group.id)
        .update({ClassroomMember.group_id: None}, synchronize_session=False)
    )
    db.delete(group)
    db.commit()


@router.patch("/{classroom_id}/members/{member_user_id}", response_model=ClassMemberOut)
def move_member(
    classroom_id: UUID,
    member_user_id: UUID,
    body: ClassMemberUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ClassMemberOut:
    classroom = _require_classroom(db, classroom_id)
    _require_teacher(classroom, user)
    member = _learner_member(db, classroom, member_user_id)
    group_name = ""
    if body.group_id is not None:
        group = db.get(ClassGroup, body.group_id)
        if group is None or group.classroom_id != classroom.id:
            raise HTTPException(status_code=404, detail="Group not found")
        group_name = group.name
    member.group_id = body.group_id
    db.commit()
    return ClassMemberOut(
        user_id=member.user_id,
        display_name=member.user.display_name,
        email=member.user.email,
        group_id=member.group_id,
        group_name=group_name,
    )


@router.delete("/{classroom_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_classroom(
    classroom_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    classroom = _require_classroom(db, classroom_id)
    if classroom.teacher_id != user.id and user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Only the teacher can delete this class")
    (
        db.query(ClassroomMember)
        .filter(ClassroomMember.classroom_id == classroom.id)
        .update({ClassroomMember.group_id: None}, synchronize_session=False)
    )
    db.delete(classroom)
    db.commit()
