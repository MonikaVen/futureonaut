from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.auth import get_optional_user
from app.database import get_db
from app.models import User
from app.schemas import CreatorProfileOut, CreatorPublicOut
from app.services.avatars import avatar_file, has_user_avatar
from app.services.creators import creator_profile, list_creators

router = APIRouter(tags=["creators"])


@router.get("/creators", response_model=list[CreatorPublicOut])
def get_creators(db: Session = Depends(get_db)) -> list[CreatorPublicOut]:
    return list_creators(db)


@router.get("/creators/{slug}", response_model=CreatorProfileOut)
def get_creator_profile(
    slug: str,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> CreatorProfileOut:
    profile = creator_profile(db, slug, user.id if user else None)
    if profile is None:
        raise HTTPException(status_code=404, detail="Creator not found")
    return profile


@router.get("/users/{user_id}/avatar")
def get_user_avatar(user_id: UUID) -> FileResponse:
    if not has_user_avatar(user_id):
        raise HTTPException(status_code=404, detail="Avatar not found")
    return FileResponse(
        avatar_file(user_id),
        media_type="image/png",
        headers={
            "Cache-Control": "public, max-age=120",
            "Content-Disposition": 'inline; filename="avatar.png"',
        },
    )
