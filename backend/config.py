import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    app_name: str = os.getenv("APP_NAME", "Voice Lab Assistant")
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./voice_lab.db")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    google_client_id: str = os.getenv("GOOGLE_CLIENT_ID", "")
    jwt_secret: str = os.getenv("JWT_SECRET", "change-me-in-production")
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    access_token_expire_minutes: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "720"))
    cors_origins: list[str] = None
    max_history_messages: int = int(os.getenv("MAX_HISTORY_MESSAGES", "12"))

    def __post_init__(self):
        origins = os.getenv(
            "CORS_ORIGINS",
            "http://localhost:3000,http://127.0.0.1:3000",
        )
        self.cors_origins = [origin.strip() for origin in origins.split(",") if origin.strip()]


settings = Settings()
