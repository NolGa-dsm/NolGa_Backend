from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import get_current_user_or_api_key
from app.models import ApiKey, User
from app.schemas import ApiKeyCreate, ApiKeyCreated, ApiKeyOut
from app.security import generate_api_key, utcnow

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


def _get_owned_key(db: Session, api_key_id: int, user: User) -> ApiKey:
    record = db.scalar(
        select(ApiKey).where(ApiKey.id == api_key_id, ApiKey.user_id == user.id)
    )
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
    return record


@router.post("", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED)
def create_api_key(
    body: ApiKeyCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_or_api_key),
) -> ApiKeyCreated:
    raw_key, prefix, key_hash = generate_api_key()
    record = ApiKey(
        user_id=user.id,
        name=body.name,
        key_prefix=prefix,
        key_hash=key_hash,
        expires_at=utcnow() + timedelta(days=settings.API_KEY_EXPIRE_DAYS),
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    base = ApiKeyOut.model_validate(record)
    return ApiKeyCreated(api_key=raw_key, **base.model_dump())


@router.get("", response_model=list[ApiKeyOut])
def list_api_keys(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_or_api_key),
) -> list[ApiKey]:
    return list(db.scalars(select(ApiKey).where(ApiKey.user_id == user.id).order_by(ApiKey.created_at.desc())))


@router.delete("/{api_key_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_api_key(
    api_key_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_or_api_key),
) -> None:
    record = _get_owned_key(db, api_key_id, user)
    if record.revoked_at is None:
        record.revoked_at = utcnow()
        db.commit()