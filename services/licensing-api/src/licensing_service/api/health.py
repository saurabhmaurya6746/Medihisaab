"""Service health and diagnostics."""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from licensing_service import __version__
from licensing_service.config import settings
from licensing_service.db.session import get_db

router = APIRouter(tags=["Health"])


@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    """Service health probe for Render / Docker orchestration."""
    db_ok = False
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    return {
        "status": "HEALTHY" if db_ok else "DEGRADED",
        "service": "pharmacy-licensing-service",
        "version": __version__,
        "environment": settings.ENVIRONMENT,
        "database_connected": db_ok,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
