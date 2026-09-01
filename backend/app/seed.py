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
            changed = False
            if existing.role != UserRole.admin:
                existing.role = UserRole.admin
                changed = True
            new_hash = hash_password(settings.admin_password)
            if existing.password_hash != new_hash:
                existing.password_hash = new_hash
                changed = True
            if changed:
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
