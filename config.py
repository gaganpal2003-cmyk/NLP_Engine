from __future__ import annotations
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

class Settings:
    def __init__(self):
        self.reload()

    def reload(self) -> None:
        """Reloads settings from .env file so runtime edits take effect immediately."""
        load_dotenv(BASE_DIR / ".env", override=True)
        # Server
        self.HOST: str = os.getenv("HOST", "0.0.0.0")
        self.PORT: int = int(os.getenv("PORT", "8000"))
        self.DEBUG: bool = os.getenv("DEBUG", "True").lower() in ("true", "1", "yes")
        self.CORS_ORIGINS: list[str] = [
            origin.strip() for origin in os.getenv("CORS_ORIGINS", "*").split(",") if origin.strip()
        ]

        # Database
        self.DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./data/detections.db")
        self.DB_TYPE: str = os.getenv("DB_TYPE", "mysql")
        self.DB_HOST: str = os.getenv("DB_HOST", "localhost")
        self.DB_PORT: str = os.getenv("DB_PORT", "3306")
        self.DB_USER: str = os.getenv("DB_USER", "root")
        self.DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")
        self.DB_NAME: str = os.getenv("DB_NAME", "cairo_face_recognition")

        self.MAX_ROW_LIMIT: int = int(os.getenv("MAX_ROW_LIMIT", "100"))
        self.QUERY_TIMEOUT_SECONDS: int = int(os.getenv("QUERY_TIMEOUT_SECONDS", "10"))

        # LLM
        self.LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
        self.LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
        self.LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
        self.LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.0"))

        # API Key & Multi-Tenant Authentication (Web Team Dashboard Integration)
        self.API_URL: str = os.getenv("API_URL", "http://localhost:8000")
        self.API_KEY: str = os.getenv("API_KEY", os.getenv("DEFAULT_CLIENT_API_KEY", "nlp_live_bothra_123"))
        self.DEFAULT_CLIENT_API_KEY: str = os.getenv("DEFAULT_CLIENT_API_KEY", os.getenv("API_KEY", "nlp_live_bothra_123"))
        self.ADMIN_API_KEY: str = os.getenv("ADMIN_API_KEY", "cairo_admin_secret_key")
        self.REQUIRE_API_KEY: bool = os.getenv("REQUIRE_API_KEY", "True").lower() in ("true", "1", "yes")

    def get_effective_database_url(self) -> str:
        """Returns the active database URL, re-checking .env in case user edited it."""
        self.reload()
        if self.DATABASE_URL and self.DATABASE_URL.strip():
            return self.DATABASE_URL.strip()
        
        # Build URL from components
        if self.DB_TYPE.lower() in ("mysql", "mariadb"):
            pwd = f":{self.DB_PASSWORD}" if self.DB_PASSWORD else ""
            return f"mysql+pymysql://{self.DB_USER}{pwd}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        elif self.DB_TYPE.lower() in ("postgres", "postgresql"):
            pwd = f":{self.DB_PASSWORD}" if self.DB_PASSWORD else ""
            return f"postgresql://{self.DB_USER}{pwd}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        elif self.DB_TYPE.lower() == "sqlite":
            return f"sqlite:///./data/{self.DB_NAME}.db"
        return "sqlite:///./data/detections.db"

settings = Settings()
