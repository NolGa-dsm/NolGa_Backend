# Nolga Backend

A FastAPI-based backend that supports JWT access tokens with HTTPOnly refresh token rotation and API key authentication.

## Tech Stack

- Python 3.13+
- FastAPI
- Uvicorn
- SQLAlchemy 2.0
- PyJWT, bcrypt, pydantic-settings
- SQLite (default; configurable via `DATABASE_URL`)

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

> **Note:** For production, you must change `SECRET_KEY` to a long, random string.

### 3. Run the server

```bash
uvicorn app.main:app --reload
```

### 4. Access API docs

- Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
- ReDoc: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- Health check: `GET http://localhost:8000/health`

## Environment Variables

All configuration is managed via `.env`. Default values are provided in `.env.example`.

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./nolga.db` | Database connection string |
| `SECRET_KEY` | `change-me-to-a-long-random-string` | JWT signing key (must be changed in production) |
| `ALGORITHM` | `HS256` | JWT signing algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Access token expiration (minutes) |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `30` | Refresh token expiration (days) |
| `REFRESH_COOKIE_NAME` | `refresh_token` | Refresh token cookie name |
| `REFRESH_COOKIE_SECURE` | `false` | Set to `true` when using HTTPS |
| `API_KEY_EXPIRE_DAYS` | `365` | API key expiration (days) |
| `API_KEY_PREFIX` | `nlk` | API key prefix |

## Authentication

The API supports two authentication methods. Routes protected with `get_current_user_or_api_key()` accept either method.

### 1. JWT Access + Refresh Tokens

- **Access token**: Short-lived, passed via `Authorization: Bearer <token>` header
- **Refresh token**: Long-lived, stored as an **httpOnly cookie** (not accessible via JavaScript). When refreshed, the old token is rotated and cannot be reused.
- Refresh tokens are hashed and stored in the database.

### 2. API Keys

- Pass via `X-API-Key` header
- Format: `nlk_<prefix>_<secret>` (shown only once on creation)
- Only the hash is stored in the database
- Supports revocation and expiration

## API Endpoints

### Auth (`/auth`)

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/auth/signup` | Create account. Body: `{"username": "...", "password": "..."}` (password ≥ 8 chars). Returns access token and sets refresh cookie. |
| `POST` | `/auth/login` | Log in. Body: `{"username": "...", "password": "..."}`. Returns access token and sets refresh cookie. |
| `POST` | `/auth/refresh` | Refresh using httpOnly cookie. Rotates token, returns new access token and sets new refresh cookie. |
| `POST` | `/auth/logout` | Revoke refresh token and clear cookie. Returns 204. |
| `GET` | `/auth/me` | Get current user info. Requires Bearer token or API key. |

### API Keys (`/api-keys`)

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api-keys` | Create API key. Body: `{"name": "..."}`. The `api_key` value is returned **only once**. |
| `GET` | `/api-keys` | List your API keys (actual keys not exposed). |
| `DELETE` | `/api-keys/{api_key_id}` | Revoke an API key. Returns 204. |

### Other

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health check. |

## Project Structure

```text
app/
├── main.py        # FastAPI app setup, router registration, /health endpoint
├── config.py      # Pydantic settings (env config)
├── database.py    # SQLAlchemy engine, session, DB initialization
├── models.py      # DB models: User, RefreshToken, ApiKey
├── schemas.py     # Pydantic request/response models
├── security.py    # Auth utilities (hashing, JWT, tokens, API keys)
├── deps.py        # Auth dependencies (Bearer + API key)
└── api/
    ├── auth.py      # Auth routes (signup, login, refresh, logout, me)
    └── api_keys.py  # API key management routes
```

## Notes

- The database (`nolga.db`) is created automatically on startup via `init_db()`.
- Refresh tokens are stored as SHA-256 hashes in the database for security.
- API keys are split into prefix and secret; only the hash of the full key is stored.
- Protected routes accept either Bearer tokens or API keys interchangeably.
