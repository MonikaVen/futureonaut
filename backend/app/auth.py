from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWTError
import jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import User, UserRole
from app.schemas import LlmKeyStatus, UserOut

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=False)
settings = get_settings()

AUTHOR_ROLES = {UserRole.admin, UserRole.creator, UserRole.teacher}


def can_author_games(user: User, db: Session | None = None) -> bool:
    return user.role in AUTHOR_ROLES


def user_to_out(user: User, db: Session | None = None) -> UserOut:
    from app.services.avatars import has_user_avatar
    from app.services.handles import username_slug
    from app.services.llm import list_llm_keys

    keys = [LlmKeyStatus(provider=row["provider"], hint=row.get("hint")) for row in list_llm_keys(db, user)] if db is not None else []
    configured = bool(keys) or bool(user.llm_api_key_hash)
    hint = None
    if keys:
        active = next((row for row in keys if row.provider == user.llm_provider), keys[0])
        hint = active.hint
    elif user.llm_api_key_hash:
        hint = user.llm_api_key_hint
    return UserOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        created_at=user.created_at,
        can_create_games=can_author_games(user, db),
        llm_provider=user.llm_provider,
        llm_key_configured=configured,
        llm_key_hint=hint,
        llm_keys=keys,
        style_source=getattr(user, "style_source", None) or "futureonaut",
        style_guidelines=getattr(user, "style_guidelines", None),
        slug=username_slug(user),
        has_avatar=has_user_avatar(user.id),
    )


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_token(subject: str, token_type: str, expires_delta: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: UUID, role: UserRole) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "role": role.value,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: UUID) -> str:
    return create_token(
        str(user_id),
        "refresh",
        timedelta(days=settings.refresh_token_expire_days),
    )


def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if creds is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    payload = decode_token(creds.credentials)
    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token")
    user_id = payload.get("sub")
    user = db.get(User, UUID(user_id)) if user_id else None
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def get_optional_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User | None:
    if creds is None:
        return None
    try:
        return get_current_user(creds, db)
    except HTTPException:
        return None


def require_roles(*roles: UserRole):
    def _dep(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient privileges")
        return user

    return _dep


def require_game_author(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    if not can_author_games(user, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only teachers and creators can generate or deploy games",
        )
    return user


def create_draft_file_token(draft_id: UUID, owner_id: UUID) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(owner_id),
        "draft": str(draft_id),
        "type": "draft_file",
        "iat": now,
        "exp": now + timedelta(hours=2),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_draft_file_token(token: str, draft_id: UUID) -> UUID:
    payload = decode_token(token)
    if payload.get("type") != "draft_file" or payload.get("draft") != str(draft_id):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid preview token")
    try:
        return UUID(str(payload.get("sub")))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid preview token") from exc
