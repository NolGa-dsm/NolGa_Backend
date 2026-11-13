from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    RAW_DB_URL: str = Field(alias="DB_URL")          # jdbc:mysql://localhost:4272/myapp_db
    DB_USER: str = Field(alias="DB_USERNAME")        # .env의 실제 아이디 변수명
    DB_PASSWORD: str = Field(alias="DB_PASSWORD")    # .env의 실제 비밀번호 변수명

    SECRET_KEY: str = "change-me-to-a-long-random-string"
    ALGORITHM: str = "HS256"

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    REFRESH_COOKIE_NAME: str = "refresh_token"
    REFRESH_COOKIE_SECURE: bool = False

    API_KEY_EXPIRE_DAYS: int = 365
    API_KEY_PREFIX: str = "nlk"
    
    @property
    def DATABASE_URL(self) -> str:
        host_and_db = self.RAW_DB_URL.replace("jdbc:mysql://", "")
        return f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}@{host_and_db}"


settings = Settings()