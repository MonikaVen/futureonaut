from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    hash_password,
    verify_password,
)
from app.database import get_db
from app.models import User, UserRole
from app.schemas import TokenPair, TokenRefresh, UserCreate, UserLogin, UserOut, GuestMergeIn
from app.services.guest_merge import merge_guest_sessions

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(body: UserCreate, db: Session = Depends(get_db)) -> User:
    if db.query(User).filter(User.email == body.email.lower()).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        email=body.email.lower(),
        password_hash=hash_password(body.password),
        display_name=body.display_name or body.email.split("@")[0],
        role=UserRole.learner,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    if body.visitor_id:
        merge_guest_sessions(db, user.id, body.visitor_id)
    return user


@router.post("/login", response_model=TokenPair)
def login(body: UserLogin, db: Session = Depends(get_db)) -> TokenPair:
    user = db.query(User).filter(User.email == body.email.lower()).first()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if body.visitor_id:
        merge_guest_sessions(db, user.id, body.visitor_id)
    return TokenPair(
        access_token=create_access_token(user.id, user.role),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/merge-guest")
def merge_guest(
    body: GuestMergeIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    merged = merge_guest_sessions(db, user.id, body.visitor_id)
    return {"merged_sessions": merged}


@router.post("/refresh", response_model=TokenPair)
def refresh(body: TokenRefresh, db: Session = Depends(get_db)) -> TokenPair:
    payload = decode_token(body.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    user = db.get(User, UUID(payload["sub"]))
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return TokenPair(
        access_token=create_access_token(user.id, user.role),
        refresh_token=create_refresh_token(user.id),
    )


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user
