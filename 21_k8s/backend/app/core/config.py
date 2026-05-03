from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """アプリケーション設定。環境変数および .env ファイルから自動ロードされる。"""

    ALLOWED_ORIGIN: str = "http://localhost:3000"
    PING_INTERVAL: int = 10
    PONG_TIMEOUT: int = 5

    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost:5432/chat_db"

    SECRET_KEY: str = "dev-secret-key-do-not-use-in-production"
    ALGORITHM: str = "HS256"
    TOKEN_EXPIRE_MINUTES: int = 30

    USERS: dict[str, str] = {
        "alice": "password1",
        "bob": "password2",
    }

    model_config = SettingsConfigDict(extra="ignore")


settings = Settings()
