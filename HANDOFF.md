# Nolga Backend — Handoff

FastAPI 기반 백엔드. Access Token(JWT) + Refresh Token(httpOnly cookie) 인증과
API Key 인증을 지원하며, 로그인/회원가입/API 키 발급을 제공한다.

## 브랜치 구성

| 브랜치 | 내용 |
|---|---|
| `main` | FastAPI 기본 틀 (health, DB 연결). 인증 로직 없음 |
| `develop` | 로그인/회원가입, Access/Refresh Token, API Key 인증 전체 |

`develop`은 `main`에서 분기됨. 이후 기능은 `develop` 위에서 작업 후 병합하는 흐름 권장.

## 기술 스택

- Python 3.13, FastAPI, Uvicorn
- SQLAlchemy 2.0 (기본 SQLite, `DATABASE_URL`로 교체 가능)
- PyJWT, bcrypt, pydantic-settings

## 실행 방법

```bash
pip install -r requirements.txt
cp .env.example .env   # SECRET_KEY는 반드시 변경
uvicorn app.main:app --reload
```

- API 문서: `http://localhost:8000/docs`
- 헬스 체크: `GET /health`

## 환경 변수 (.env)

| 변수 | 기본값 | 설명 |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./nolga.db` | DB 접속 문자열 |
| `SECRET_KEY` | `change-me-...` | JWT 서명 키 (운영 시 필수 변경) |
| `ALGORITHM` | `HS256` | JWT 서명 알고리즘 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Access Token 만료(분) |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `30` | Refresh Token 만료(일) |
| `REFRESH_COOKIE_NAME` | `refresh_token` | 쿠키 이름 |
| `REFRESH_COOKIE_SECURE` | `false` | HTTPS 환경에서 `true` |
| `API_KEY_EXPIRE_DAYS` | `365` | API Key 만료(일) |
| `API_KEY_PREFIX` | `nlk` | API Key 접두어 |

## 인증 방식

1. **Access Token (JWT)** — 짧은 수명. 요청 시 `Authorization: Bearer <token>` 헤더.
2. **Refresh Token** — 긴 수명. **httpOnly cookie**로만 전달되며 클라이언트 JS에서 접근 불가.
   `/auth/refresh`에서 회전(rotation)되어 재사용 불가. DB에 해시로 저장.
3. **API Key** — `X-API-Key` 헤더. 발급 시점에 `nlk_<prefix>_<secret>`를 한 번만 노출하며,
   DB에는 해시만 저장. 폐기/만료 지원.

보호가 필요한 라우트에 `Depends(get_current_user_or_api_key)`를 붙이면
두 인증 중 하나라도 통과하면 user가 주입된다. (확장 포인트)

## 엔드포인트

### 인증 (`/auth`)

| 메서드 | 경로 | 설명 |
|---|---|---|
| POST | `/auth/signup` | 회원가입. body: `{username, password}` (password ≥ 8자). 성공 시 access token 반환 + refresh cookie 발급 |
| POST | `/auth/login` | 로그인. body: `{username, password}`. 성공 시 access token 반환 + refresh cookie 발급 |
| POST | `/auth/refresh` | cookie의 refresh token으로 새 access/refresh 쌍 발급 (회전) |
| POST | `/auth/logout` | refresh token 폐기 + cookie 삭제 |
| GET | `/auth/me` | 현재 유저 정보. Bearer 또는 API Key 필요 |

### API 키 (`/api-keys`)

| 메서드 | 경로 | 설명 |
|---|---|---|
| POST | `/api-keys` | 발급. body: `{name}`. 응답에 `api_key`는 **한 번만** 포함 |
| GET | `/api-keys` | 내 API 키 목록 (실제 키 표시 안 함) |
| DELETE | `/api-keys/{id}` | 폐기 |

### 기타

| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | `/health` | 헬스 체크 |

## 프로젝트 구조

```
app/
├── main.py        # FastAPI 앱, 라우터 등록, /health
├── config.py      # pydantic-settings (.env)
├── database.py    # SQLAlchemy 엔진/세션, init_db
├── models.py      # User / RefreshToken / ApiKey
├── schemas.py     # 요청/응답 DTO
├── security.py    # bcrypt, JWT, refresh/API key 생성·해시
├── deps.py        # HTTPBearer + X-API-Key 인증 의존성
└── api/
    ├── auth.py      # signup/login/refresh/logout/me
    └── api_keys.py  # API key 발급/조회/폐기
```

## 참고 사항

- 개발 시 SQLite가 기본이라 추가 설정 없이 바로 실행된다.
- Refresh Token은 매 갱신마다 이전 토큰을 `revoked_at`으로 무효화한다(회전).
- API Key도 DB에 해시만 저장되므로 유출 시 발급 당시 키가 필요하다.
- 다음 작업(예: 라우터 추가, 모델 확장)은 `develop`에서 진행한다.