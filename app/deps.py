import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import ApiKey, User
from app.security import as_utc, decode_access_token, hash_token, utcnow

bearer_scheme = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

invalid_credentials = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid authentication credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_user_by_username(db: Session, username: str) -> User | None:
    return db.scalar(select(User).where(User.username == username))


def _user_from_access_token(db: Session, token: str) -> User:
    try:
        user_id = decode_access_token(token)
    except jwt.InvalidTokenError as exc:
        raise invalid_credentials from exc
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise invalid_credentials
    return user


def _user_from_api_key(db: Session, api_key: str) -> User:
    parts = api_key.split("_")
    if len(parts) != 3 or parts[0] != settings.API_KEY_PREFIX:
        raise invalid_credentials

    record = db.scalar(select(ApiKey).where(ApiKey.key_prefix == parts[1]))
    if record is None or record.key_hash != hash_token(api_key):
        raise invalid_credentials
    if record.revoked_at is not None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="API key revoked")
    if as_utc(record.expires_at) < utcnow():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="API key expired")
    if record.user is None or not record.user.is_active:
        raise invalid_credentials
    return record.user


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise invalid_credentials
    return _user_from_access_token(db, credentials.credentials)


def get_current_user_or_api_key(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    api_key: str | None = Depends(api_key_header),
    db: Session = Depends(get_db),
) -> User:
    if api_key:
        return _user_from_api_key(db, api_key)
    if credentials:
        return _user_from_access_token(db, credentials.credentials)
    raise invalid_credentials