from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import get_current_user_or_api_key, invalid_credentials
from app.models import ApiKey, User
from app.schemas import ApiKeyCreate, ApiKeyCreated, ApiKeyOut, ApiKeyVerifyResponse
from app.security import as_utc, generate_api_key, hash_token, utcnow

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
@router.get("/verify", response_model=ApiKeyVerifyResponse)
def verify_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    db: Session = Depends(get_db),
) -> ApiKeyVerifyResponse:
    if not x_api_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="X-API-Key header required")

    parts = x_api_key.split("_")
    if len(parts) != 3 or parts[0] != settings.API_KEY_PREFIX:
        raise invalid_credentials

    record = db.scalar(select(ApiKey).where(ApiKey.key_prefix == parts[1]))
    if record is None or record.key_hash != hash_token(x_api_key):
        raise invalid_credentials

    if record.revoked_at is not None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="API key revoked")
    if as_utc(record.expires_at) < utcnow():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="API key expired")
    if record.user is None or not record.user.is_active:
        raise invalid_credentials

    return ApiKeyVerifyResponse(
        valid=True,
        api_key_id=record.id,
    )
