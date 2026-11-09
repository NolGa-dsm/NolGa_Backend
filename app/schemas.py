from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_serializer


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

class ApiKeyVerifyResponse(BaseModel):
    valid: bool
    api_key_id: int

#work관련 스키마
# 응답용 스키마
class WorkResponse(BaseModel):
    """작업 목록 항목. id는 문자열, createdAt은 ISO 날짜(YYYY-MM-DD)로 내려간다."""

    id: str
    title: str
    summary: str | None = None
    repository: str | None = None
    author: str
    created_at: date = Field(..., alias="createdAt")
    status: Literal["auto", "review", "edited"]  # auto | review | edited

    model_config = ConfigDict(
        from_attributes=True,   # ORM 객체를 Pydantic 모델로 직접 변환
        populate_by_name=True   # camelCase 및 snake_case 모두 허용
    )

    @field_validator("id", mode="before")
    @classmethod
    def _id_to_str(cls, v: Any) -> str:
        return str(v)

    @field_validator("created_at", mode="before")
    @classmethod
    def _datetime_to_date(cls, v: Any) -> Any:
        return v.date() if isinstance(v, datetime) else v


def _omit_none(data: dict[str, Any], *keys: str) -> dict[str, Any]:
    """선택값이 비어 있으면 null 대신 키 자체를 생략한다."""
    for key in keys:
        if key in data and data[key] is None:
            del data[key]
    return data


class WorkChangeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    path: str
    type: Literal["added", "modified", "deleted"]
    additions: int = 0
    deletions: int = 0


class WorkSourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    type: Literal["commit", "issue", "file", "note"]
    title: str

    @field_validator("id", mode="before")
    @classmethod
    def _id_to_key(cls, v: Any) -> str:
        return v if isinstance(v, str) else f"s{v}"

    @model_serializer(mode="wrap")
    def _serialize(self, handler: Any) -> dict[str, Any]:
        return _omit_none(handler(self))


# 작업 상세 응답 (목록 필드 + 상세 필드)
class WorkDetailResponse(WorkResponse):
    branch: str | None = None
    request: str | None = None
    style_name: str | None = Field(None, alias="styleName")
    changes: list[WorkChangeOut] = Field(default_factory=list)
    sources: list[WorkSourceOut] = Field(default_factory=list)

    @model_serializer(mode="wrap")
    def _serialize(self, handler: Any) -> dict[str, Any]:
        return _omit_none(handler(self), "branch", "request", "styleName", "style_name")

# Work 생성 요청 스키마

class WorkChangeCreate(BaseModel):
    path: str
    type: Literal["added", "modified", "deleted"]
    additions: int = 0
    deletions: int = 0


class WorkSourceCreate(BaseModel):
    type: Literal["commit", "issue", "file", "note"]
    title: str


class WorkCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    summary: str = Field(min_length=1)
    repository: str | None = None

    branch: str | None = None
    request: str | None = None
    style_name: str | None = Field(None, alias="styleName")

    status: Literal["auto", "review", "edited"]
    
    changes: list[WorkChangeCreate] = Field(default_factory=list)
    sources: list[WorkSourceCreate] = Field(default_factory=list)

    model_config = ConfigDict(
        populate_by_name=True
    )

# 요약 수정 요청
class WorkSummaryUpdate(BaseModel):
    summary: str