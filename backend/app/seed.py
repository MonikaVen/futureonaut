from app.auth import hash_password
from app.config import get_settings
from app.database import SessionLocal
from app.models import Classroom, User, UserRole
from app.services.handles import allocate_profile_slug


def seed_admin() -> None:
    settings = get_settings()
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == settings.admin_email).first()
        if existing:
            return
        admin = User(
            email=settings.admin_email,
            password_hash=hash_password(settings.admin_password),
            display_name="Admin",
            role=UserRole.admin,
        )
        db.add(admin)
        db.flush()
        admin.profile_slug = allocate_profile_slug(db, admin)
        db.commit()
    finally:
        db.close()


DEMO_TEACHER_CLASS = "Example class"
DEMO_TEACHER_JOIN_CODE = "TEACH01"


def seed_teacher() -> None:
    """Create a demo teacher login and one classroom if they do not exist."""
    settings = get_settings()
    if not settings.teacher_email or not settings.teacher_password:
        return
    db = SessionLocal()
    try:
        teacher = db.query(User).filter(User.email == settings.teacher_email).first()
        if teacher is None:
            teacher = User(
                email=settings.teacher_email,
                password_hash=hash_password(settings.teacher_password),
                display_name="Example Teacher",
                role=UserRole.teacher,
            )
            db.add(teacher)
            db.flush()
            teacher.profile_slug = allocate_profile_slug(db, teacher)
            db.commit()
            db.refresh(teacher)

        has_class = db.query(Classroom).filter(Classroom.teacher_id == teacher.id).first()
        if has_class is None:
            taken = db.query(Classroom).filter(Classroom.join_code == DEMO_TEACHER_JOIN_CODE).first()
            join_code = DEMO_TEACHER_JOIN_CODE if taken is None else "TEACH02"
            if db.query(Classroom).filter(Classroom.join_code == join_code).first() is None:
                db.add(
                    Classroom(
                        name=DEMO_TEACHER_CLASS,
                        join_code=join_code,
                        teacher_id=teacher.id,
                    )
                )
                db.commit()
    finally:
        db.close()


def seed_creator() -> None:
    """Create the Futureonaut creator login if it does not exist."""
    settings = get_settings()
    email = (settings.creator_email or "").strip().lower()
    if not email or not settings.creator_password:
        return
    display_name = (settings.creator_display_name or "futureonaut").strip() or "futureonaut"
    db = SessionLocal()
    try:
        creator = db.query(User).filter(User.email == email).first()
        if creator is None:
            creator = User(
                email=email,
                password_hash=hash_password(settings.creator_password),
                display_name=display_name,
                role=UserRole.creator,
            )
            db.add(creator)
            db.flush()
            creator.profile_slug = allocate_profile_slug(db, creator)
            db.commit()
            return
        changed = False
        if creator.role not in (UserRole.admin, UserRole.creator):
            creator.role = UserRole.creator
            changed = True
        if display_name and creator.display_name != display_name:
            creator.display_name = display_name
            changed = True
        if changed:
            db.commit()
    finally:
        db.close()
