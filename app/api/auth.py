from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import get_current_user_or_api_key, get_user_by_username
from app.models import RefreshToken, User
from app.schemas import AccessTokenResponse, LoginRequest, SignupRequest, UserOut
from app.security import (
    as_utc,
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_token,
    utcnow,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])

COOKIE_NAME = settings.REFRESH_COOKIE_NAME


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        httponly=True,
        samesite="lax",
        secure=settings.REFRESH_COOKIE_SECURE,
        path="/",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key=COOKIE_NAME, path="/")


def _issue_tokens(db: Session, user: User, response: Response) -> AccessTokenResponse:
    raw = generate_refresh_token()
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_token(raw),
            expires_at=utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
    )
    db.commit()
    _set_refresh_cookie(response, raw)
    return AccessTokenResponse(access_token=create_access_token(user.id))


def _refresh_token_from_cookie(request: Request) -> str:
    raw = request.cookies.get(COOKIE_NAME)
    if not raw:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token cookie missing")
    return raw


@router.post("/signup", response_model=AccessTokenResponse, status_code=status.HTTP_201_CREATED)
def signup(
    body: SignupRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> AccessTokenResponse:
    if get_user_by_username(db, body.username):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already taken")

    user = User(username=body.username, password_hash=hash_password(body.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return _issue_tokens(db, user, response)


@router.post("/login", response_model=AccessTokenResponse)
def login(
    response: Response,
    body: LoginRequest,
    db: Session = Depends(get_db),
) -> AccessTokenResponse:
    user = get_user_by_username(db, body.username)
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")
    return _issue_tokens(db, user, response)


@router.post("/refresh", response_model=AccessTokenResponse)
def refresh(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> AccessTokenResponse:
    raw = _refresh_token_from_cookie(request)
    record = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw)))
    if record is None:
        _clear_refresh_cookie(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    now = utcnow()
    if record.revoked_at is not None:
        _clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been revoked",
        )
    if as_utc(record.expires_at) < now:
        _clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has expired",
        )

    record.revoked_at = now  # rotate: old token can no longer be reused
    db.commit()
    return _issue_tokens(db, record.user, response)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> None:
    raw = request.cookies.get(COOKIE_NAME)
    if raw:
        record = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw)))
        if record is not None and record.revoked_at is None:
            record.revoked_at = utcnow()
            db.commit()
    _clear_refresh_cookie(response)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user_or_api_key)) -> User:
    return user