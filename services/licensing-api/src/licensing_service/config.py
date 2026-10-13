"""Configuration settings for Central Vendor Licensing Service.

Reads from environment variables and supports PostgreSQL (production)
and SQLite (local development and test).
"""

from pathlib import Path
import os
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    ENVIRONMENT: str = "development"  # development, test, production
    DATABASE_URL: str = "sqlite:///./licensing_dev.db"
    SUPABASE_DB_URL: Optional[str] = None  # Supabase PostgreSQL connection string

    # Configurable Trial Defaults
    DEFAULT_TRIAL_DAYS: int = 15
    DEFAULT_GRACE_PERIOD_DAYS: int = 7

    # Vendor Authentication Security
    JWT_SECRET_KEY: str = "vendor_portal_dev_jwt_super_secret_key_change_in_production!"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60  # Short-lived access token (1 hour)

    # Cryptographic Ed25519 Signing Keys
    # In production on Render: provide via environment variable LICENSE_PRIVATE_KEY_PEM
    LICENSE_PRIVATE_KEY_PEM: Optional[str] = None
    LICENSE_PRIVATE_KEY_PATH: Optional[str] = None
    LICENSE_PUBLIC_KEY_HEX: str = "ba7a4f28067b0d4d4e7d90128c48f9316ba5c3069a0cb88fcc5a24b081b3632b"

    # CORS & Security
    ALLOWED_ORIGINS: str = (
        "http://localhost:8000,http://127.0.0.1:8000,"
        "http://localhost:3000,http://127.0.0.1:3000,"
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:38291,http://127.0.0.1:38291"
    )
    CORS_ORIGINS: Optional[str] = None
    RATE_LIMIT_LOGIN_ATTEMPTS: int = 5
    RATE_LIMIT_WINDOW_SECONDS: int = 60

    # Server Bindings
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Server-Side Email Provider (SMTP)
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM: str = "licensing@apexhealth.com"
    SMTP_USE_TLS: bool = True

    @property
    def cors_origins_list(self) -> List[str]:
        raw = self.CORS_ORIGINS or self.ALLOWED_ORIGINS
        origins = [o.strip() for o in raw.split(",") if o.strip()]
        defaults = [
            "http://127.0.0.1:38291",
            "http://localhost:38291",
            "http://127.0.0.1:5173",
            "http://localhost:5173",
            "http://127.0.0.1:5174",
            "http://localhost:5174",
        ]
        for d in defaults:
            if d not in origins:
                origins.append(d)
        return origins

    @property
    def normalized_database_url(self) -> str:
        raw_url = (self.SUPABASE_DB_URL or self.DATABASE_URL).strip()
        # Supabase and Render provide postgres:// or postgresql:// URLs; SQLAlchemy requires postgresql+psycopg2://
        if raw_url.startswith("postgres://"):
            raw_url = raw_url.replace("postgres://", "postgresql+psycopg2://", 1)
        elif raw_url.startswith("postgresql://") and not raw_url.startswith("postgresql+"):
            raw_url = raw_url.replace("postgresql://", "postgresql+psycopg2://", 1)
        return raw_url

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
