from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    DATABASE_URL: str = "sqlite:///./nolga.db"
    SECRET_KEY: str = "change-me-to-a-long-random-string"
    ALGORITHM: str = "HS256"

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    REFRESH_COOKIE_NAME: str = "refresh_token"
    REFRESH_COOKIE_SECURE: bool = False

    API_KEY_EXPIRE_DAYS: int = 365
    API_KEY_PREFIX: str = "nlk"


settings = Settings()