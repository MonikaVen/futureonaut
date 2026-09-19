from app.database import SessionLocal
from app.models import User, UserRole
from app.auth import hash_password
from app.config import get_settings


def seed_admin() -> None:
    settings = get_settings()
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == settings.admin_email).first()
        if existing:
            if existing.role != UserRole.admin:
                existing.role = UserRole.admin
                db.commit()
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


def seed_futureonaut() -> None:
    """Platform creator who publishes the seeded HTML labs."""
    settings = get_settings()
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == settings.creator_email.lower()).first()
        if existing:
            existing.display_name = settings.creator_name
            if existing.role == UserRole.learner:
                existing.role = UserRole.creator
            db.commit()
            return
        db.add(
            User(
                email=settings.creator_email.lower(),
                password_hash=hash_password(settings.creator_password),
                display_name=settings.creator_name,
                role=UserRole.creator,
            )
        )
        db.commit()
    finally:
        db.close()
