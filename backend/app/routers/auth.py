from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    hash_password,
    require_game_author,
    user_to_out,
    verify_password,
)
from app.database import get_db
from app.models import User, UserRole
from app.schemas import (
    GuestMergeIn,
    LlmKeyIn,
    LlmKeyOut,
    TokenPair,
    TokenRefresh,
    UserCreate,
    UserLogin,
    UserOut,
)
from app.services.guest_merge import merge_guest_sessions
from app.services.llm import store_llm_key

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
    return user_to_out(user, db)


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
def me(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> UserOut:
    return user_to_out(user, db)


@router.post("/llm-key", response_model=LlmKeyOut)
def save_llm_key(
    body: LlmKeyIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_game_author),
) -> LlmKeyOut:
    store_llm_key(user, body.provider, body.api_key)
    db.commit()
    return LlmKeyOut(provider=user.llm_provider, configured=True, hint=user.llm_api_key_hint)


@router.delete("/llm-key", response_model=LlmKeyOut)
def clear_llm_key(
    db: Session = Depends(get_db),
    user: User = Depends(require_game_author),
) -> LlmKeyOut:
    user.llm_provider = None
    user.llm_api_key_hash = None
    user.llm_api_key_hint = None
    db.commit()
    return LlmKeyOut(provider=None, configured=False, hint=None)
