"""FastAPI Application for Central Vendor Licensing & Management Service."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from licensing_service import __version__
from licensing_service.release_manifest import serve_release_installer
from licensing_service.api import (
    audit,
    auth,
    client_portal,
    clients,
    dashboard,
    health,
    licenses,
    payments,
    plans,
    renewal_requests,
    settings as settings_api,
    subscriptions,
    users,
)
from licensing_service.config import settings
from licensing_service.db.migrations import init_db, seed_default_data
from licensing_service.db.session import SessionLocal

logger = logging.getLogger("licensing_service")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle startup and shutdown handler."""
    logger.info("Initializing Central Licensing Database...")
    init_db()
    db = SessionLocal()
    try:
        seed_default_data(db)
        logger.info("Default seed data verified.")
    finally:
        db.close()
    yield
    logger.info("Licensing Service shutdown complete.")


app = FastAPI(
    title="Pharmacy POS Central Licensing API",
    description="Central vendor licensing, client subscriptions, and Ed25519 license issuance service.",
    version=__version__,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Routers
app.include_router(health.router)
app.include_router(auth.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")
app.include_router(clients.router, prefix="/api/v1")
app.include_router(plans.router, prefix="/api/v1")
app.include_router(subscriptions.router, prefix="/api/v1")
app.include_router(payments.router, prefix="/api/v1")
app.include_router(licenses.router, prefix="/api/v1")
app.include_router(settings_api.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(audit.router, prefix="/api/v1")
app.include_router(client_portal.router, prefix="/api/v1")
app.include_router(renewal_requests.router, prefix="/api/v1")

# Static Portal Paths
PORTAL_DIR = Path(__file__).resolve().parent / "portal"
INDEX_HTML = PORTAL_DIR / "index.html"

CLIENT_PORTAL_DIR = Path(__file__).resolve().parent / "client_portal"
CLIENT_INDEX_HTML = CLIENT_PORTAL_DIR / "index.html"

PUBLIC_PORTAL_DIR = Path(__file__).resolve().parents[4] / "portal"
PUBLIC_INDEX_HTML = PUBLIC_PORTAL_DIR / "index.html"

DIST_RELEASE_DIR = Path(__file__).resolve().parents[4] / "dist-release"
DOCS_DIR = Path(__file__).resolve().parents[4] / "docs"

ONLINE_WEB_DIST_DIR = Path(__file__).resolve().parents[4] / "apps" / "online-web" / "dist"
ONLINE_WEB_INDEX_HTML = ONLINE_WEB_DIST_DIR / "index.html"

FRONTEND_DIST_DIR = Path(__file__).resolve().parents[4] / "apps" / "frontend" / "dist"
FRONTEND_INDEX_HTML = FRONTEND_DIST_DIR / "index.html"

if (FRONTEND_DIST_DIR / "assets").is_dir():
    from fastapi.staticfiles import StaticFiles
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST_DIR / "assets")), name="frontend-assets")
elif (ONLINE_WEB_DIST_DIR / "assets").is_dir():
    from fastapi.staticfiles import StaticFiles
    app.mount("/assets", StaticFiles(directory=str(ONLINE_WEB_DIST_DIR / "assets")), name="online-web-assets")


def _serve_spa_index():
    """Serve the primary SPA index.html (apps/frontend/dist with fallback to legacy portals)."""
    if FRONTEND_INDEX_HTML.is_file():
        return FileResponse(str(FRONTEND_INDEX_HTML))
    if ONLINE_WEB_INDEX_HTML.is_file():
        return FileResponse(str(ONLINE_WEB_INDEX_HTML))
    if INDEX_HTML.is_file():
        return FileResponse(str(INDEX_HTML))
    if PUBLIC_INDEX_HTML.is_file():
        return FileResponse(str(PUBLIC_INDEX_HTML))
    return JSONResponse({"message": "Pharmacy POS Licensing Service", "version": __version__})


@app.get("/favicon.png", include_in_schema=False)
@app.get("/favicon.ico", include_in_schema=False)
async def serve_favicon():
    """Serve favicon from primary frontend dist if available."""
    if (FRONTEND_DIST_DIR / "favicon.png").is_file():
        return FileResponse(str(FRONTEND_DIST_DIR / "favicon.png"))
    return JSONResponse({"message": "Favicon not found"}, status_code=404)


@app.get("/robots.txt", include_in_schema=False)
async def serve_robots():
    """Serve robots.txt from primary frontend dist if available."""
    if (FRONTEND_DIST_DIR / "robots.txt").is_file():
        return FileResponse(str(FRONTEND_DIST_DIR / "robots.txt"))
    return JSONResponse({"message": "Robots not found"}, status_code=404)


@app.get("/MediHisaab-Setup-1.0.6.exe", include_in_schema=False)
@app.get("/downloads/MediHisaab-Setup-1.0.6.exe", include_in_schema=False)
@app.get("/download/MediHisaab-Setup-1.0.6.exe", include_in_schema=False)
@app.get("/MediHisaab-Setup-1.0.3.exe", include_in_schema=False)
@app.get("/MediHisaab-Setup-1.0.0.exe", include_in_schema=False)
@app.get("/downloads/MediHisaab-Setup-1.0.3.exe", include_in_schema=False)
@app.get("/downloads/MediHisaab-Setup-1.0.0.exe", include_in_schema=False)
@app.get("/download/MediHisaab-Setup-1.0.3.exe", include_in_schema=False)
@app.get("/download/MediHisaab-Setup-1.0.0.exe", include_in_schema=False)
@app.get("/downloads/{filename:path}", include_in_schema=False)
async def serve_installer(filename: Optional[str] = None, request: Request = None):
    """Serve Windows installer binary when available, falling back to verified release asset streaming."""
    target = filename
    if not target and request:
        target = request.url.path.strip("/").split("/")[-1]
    return serve_release_installer(target)


@app.get("/", include_in_schema=False)
async def serve_root():
    """Serve the primary SPA index.html."""
    return _serve_spa_index()


@app.get("/product", include_in_schema=False)
@app.get("/how-it-works", include_in_schema=False)
@app.get("/plans", include_in_schema=False)
@app.get("/account", include_in_schema=False)
@app.get("/download", include_in_schema=False)
@app.get("/about", include_in_schema=False)
@app.get("/support", include_in_schema=False)
@app.get("/privacy", include_in_schema=False)
@app.get("/faq", include_in_schema=False)
async def serve_online_web_routes():
    """Serve public website SPA routes."""
    return _serve_spa_index()


@app.get("/portal", include_in_schema=False)
@app.get("/portal/{path:path}", include_in_schema=False)
async def serve_public_portal(path: str = ""):
    """Serve public product portal assets or fallback."""
    if path:
        target = PUBLIC_PORTAL_DIR / path
        if target.is_file():
            return FileResponse(str(target))
    if PUBLIC_INDEX_HTML.is_file():
        return FileResponse(str(PUBLIC_INDEX_HTML))
    return JSONResponse({"message": "Product portal not found"}, status_code=404)


@app.get("/vendor", include_in_schema=False)
@app.get("/vendor/{path:path}", include_in_schema=False)
@app.get("/admin", include_in_schema=False)
@app.get("/admin/{path:path}", include_in_schema=False)
async def serve_vendor(path: str = ""):
    """Serve protected vendor licensing administration console."""
    if FRONTEND_INDEX_HTML.is_file():
        return FileResponse(str(FRONTEND_INDEX_HTML))
    if INDEX_HTML.is_file():
        return FileResponse(str(INDEX_HTML))
    return JSONResponse({"message": "Vendor portal not found"}, status_code=404)


@app.get("/client", include_in_schema=False)
@app.get("/client/{path:path}", include_in_schema=False)
async def serve_client(path: str = ""):
    """Serve client customer licensing & trial portal."""
    if FRONTEND_INDEX_HTML.is_file():
        return FileResponse(str(FRONTEND_INDEX_HTML))
    if CLIENT_INDEX_HTML.is_file():
        return FileResponse(str(CLIENT_INDEX_HTML))
    return JSONResponse({"message": "Client portal not found"}, status_code=404)


@app.get("/docs/{filename}", include_in_schema=False)
async def serve_documentation(filename: str):
    """Serve markdown documentation files if requested."""
    doc_file = DOCS_DIR / filename
    if doc_file.is_file() and doc_file.suffix.lower() in (".md", ".txt", ".pdf"):
        return FileResponse(str(doc_file), media_type="text/markdown; charset=utf-8")
    return JSONResponse({"message": "Documentation file not found"}, status_code=404)

