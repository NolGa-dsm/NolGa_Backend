from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SignupRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    is_active: bool
    created_at: datetime


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)


class ApiKeyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None = None


class ApiKeyCreated(ApiKeyOut):
    api_key: str