from typing import List
import json
from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    # Project Info
    PROJECT_NAME: str = "Nutricion API"
    ENVIRONMENT: str = "development"

    # Database
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/nutricion_db"
    TEST_DATABASE_URL: str = "sqlite:///./test.db"

    # Security & JWT
    SECRET_KEY: str = "supersecretkeydefault32charactersminimumlengthforsecurity"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    RESET_TOKEN_EXPIRE_MINUTES: int = 10

    # Frontend & Email Configuration
    FRONTEND_URL: str = "http://localhost:4200"
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    EMAILS_FROM_EMAIL: str = "soporte@nutrisalud.com"
    EMAILS_FROM_NAME: str = "NutriSalud"

    # CORS — stored as plain str so pydantic-settings never calls json.loads() on it.
    # Railway: set CORS_ORIGINS=https://your-app.com,https://other.com  (comma-separated)
    # OR leave unset to use the default localhost origins.
    CORS_ORIGINS: str = (
        "http://localhost:4200,"
        "http://127.0.0.1:4200,"
        "http://localhost:3000,"
        "http://localhost:8080,"
        "http://localhost:8000"
    )

    @computed_field
    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS_ORIGINS env var: accepts comma-separated or JSON array."""
        v = self.CORS_ORIGINS.strip()
        if not v:
            return []
        if v.startswith("["):
            try:
                result = json.loads(v)
                if isinstance(result, list):
                    return [str(i).strip() for i in result if str(i).strip()]
            except json.JSONDecodeError:
                pass
        return [i.strip() for i in v.split(",") if i.strip()]


settings = Settings()

