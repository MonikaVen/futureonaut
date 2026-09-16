from app.database import SessionLocal
from app.models import Classroom, User, UserRole
from app.auth import hash_password
from app.config import get_settings


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
