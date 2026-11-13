
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from sqlalchemy.engine import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    RAW_DB_URL: str = Field(alias="DB_URL")
    DB_USER: str = Field(alias="DB_USERNAME")
    DB_PASSWORD: str = Field(alias="DB_PASSWORD")

    SECRET_KEY: str = "change-me-to-a-long-random-string"
    ALGORITHM: str = "HS256"

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    REFRESH_COOKIE_NAME: str = "refresh_token"
    REFRESH_COOKIE_SECURE: bool = False

    API_KEY_EXPIRE_DAYS: int = 365
    API_KEY_PREFIX: str = "nlk"
    
    @property
    def DATABASE_URL(self) -> URL:
        raw_url = self.RAW_DB_URL.removeprefix("jdbc:mysql://").strip()

        host_port, database = raw_url.split("/", 1)
        host, port = host_port.rsplit(":", 1)

        return URL.create(
            drivername="mysql+pymysql",
            username=self.DB_USER,
            password=self.DB_PASSWORD,
            host=host,
            port=int(port),
            database=database
        )


settings = Settings()