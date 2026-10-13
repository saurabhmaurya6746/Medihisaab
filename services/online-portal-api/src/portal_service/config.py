"""Application configuration and environment settings."""

import os
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    ENVIRONMENT: str = "development"
    DATABASE_URL: str = "sqlite:///./online_portal.db"

    # JWT Settings
    JWT_SECRET_KEY: str = "insecure-dev-key-change-in-production-apex-2026-online"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    # CORS
    CORS_ORIGINS: str = "*"

    # Pharmacy Storefront Information
    STORE_NAME: str = "Apex Healthcare & Pharmacy"
    STORE_TAGLINE: str = "Your Trusted Neighborhood & Online Pharmacy"
    STORE_LICENSE_NUMBER: str = "DL-2024-APEX-7789"
    STORE_PHONE: str = "+91 98765 43210"
    STORE_EMAIL: str = "care@apexhealthcare.com"
    STORE_ADDRESS: str = "Plot 42, Health City Avenue, Medical District, Hyderabad 500081"
    OPERATING_HOURS: str = "Mon - Sat: 8:00 AM - 10:30 PM | Sun: 9:00 AM - 9:00 PM"
    DELIVERY_FEE_PAISE: int = 4000  # ₹40.00
    FREE_DELIVERY_THRESHOLD_PAISE: int = 50000  # ₹500.00
    ESTIMATED_DELIVERY_TIME: str = "45 - 90 minutes"
    ESTIMATED_PICKUP_TIME: str = "Ready in 15 minutes"
    RX_POLICY_NOTICE: str = (
        "Prescription medicines (Rx) cannot be dispensed or dispatched without verification "
        "by our registered pharmacist. You may place the order for pharmacist review, and we will "
        "confirm physical stock and prescription details before dispensing."
    )

    @property
    def normalized_database_url(self) -> str:
        """Ensure postgresql:// compatibility with SQLAlchemy."""
        url = self.DATABASE_URL
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+psycopg2://", 1)
        elif url.startswith("postgresql://") and not url.startswith("postgresql+"):
            url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
        return url

    @property
    def cors_origins_list(self) -> List[str]:
        """Convert comma-separated CORS origins into a list."""
        if not self.CORS_ORIGINS or self.CORS_ORIGINS.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


settings = Settings()
