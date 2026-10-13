"""FastAPI Application entrypoint for the Online Pharmacy Portal."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from portal_service import __version__
from portal_service.api import (
    catalog,
    customer_auth,
    customer_orders,
    health,
    staff_audit,
    staff_auth,
    staff_catalog,
    staff_customers,
    staff_dashboard,
    staff_orders,
    store,
)
from portal_service.config import settings
from portal_service.db.migrations import init_db, seed_default_data
from portal_service.db.session import SessionLocal

logger = logging.getLogger("portal_service")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database tables and seed sample data on service launch."""
    logger.info("Initializing Online Pharmacy Portal database...")
    init_db()
    db = SessionLocal()
    try:
        seed_default_data(db)
        logger.info("Online Pharmacy database seeded successfully.")
    finally:
        db.close()
    yield
    logger.info("Online Pharmacy Portal service shutdown.")


app = FastAPI(
    title="Apex Online Pharmacy Portal API",
    description="E-commerce storefront, customer portal, and staff management API for pharmacy operations.",
    version=__version__,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Routers
app.include_router(health.router)
app.include_router(store.router, prefix="/api/v1")
app.include_router(catalog.router, prefix="/api/v1")
app.include_router(customer_auth.router, prefix="/api/v1")
app.include_router(customer_orders.router, prefix="/api/v1")
app.include_router(staff_auth.router, prefix="/api/v1")
app.include_router(staff_dashboard.router, prefix="/api/v1")
app.include_router(staff_orders.router, prefix="/api/v1")
app.include_router(staff_catalog.router, prefix="/api/v1")
app.include_router(staff_customers.router, prefix="/api/v1")
app.include_router(staff_audit.router, prefix="/api/v1")

# Static / SPA Support (checks for built frontend distribution in apps/online-web/dist)
DIST_DIR = Path(__file__).resolve().parents[4] / "apps" / "online-web" / "dist"
INDEX_HTML = DIST_DIR / "index.html"


@app.get("/", include_in_schema=False)
async def serve_root():
    if INDEX_HTML.is_file():
        return FileResponse(str(INDEX_HTML))
    return JSONResponse(
        {
            "service": "Apex Online Pharmacy Portal API",
            "version": __version__,
            "status": "running",
            "docs": "/api/docs",
        }
    )


@app.get("/{path:path}", include_in_schema=False)
async def serve_spa_or_fallback(path: str):
    # If a static asset exists in dist (e.g. assets/index.js), return it
    asset_file = DIST_DIR / path
    if asset_file.is_file():
        return FileResponse(str(asset_file))

    # Otherwise return SPA index.html if available
    if INDEX_HTML.is_file():
        return FileResponse(str(INDEX_HTML))

    return JSONResponse(
        {
            "detail": "Resource not found",
            "path": path,
        },
        status_code=404,
    )
