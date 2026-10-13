"""Main FastAPI application factory and lifecycle coordination."""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
import logging
import sys
import time

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import __version__
from .api.auth import router as auth_router
from .api.inventory import router as inventory_router
from .api.khata import router as khata_router
from .api.masters import router as masters_router
from .api.purchases import router as purchases_router
from .api.reports import router as reports_router
from .api.returns import router as returns_router
from .api.sales import router as sales_router
from .api.system import router as system_router
from .api.wastage import router as wastage_router
from .config import DaemonConfig
from .db.engine import DatabaseEngine

logger = logging.getLogger("pharmacy_daemon")


def create_app(config: DaemonConfig | None = None) -> FastAPI:
    """Create and configure FastAPI application instance."""
    app_config = config or DaemonConfig.load()
    engine = DatabaseEngine(app_config.db_path)
    start_time = time.time()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Lifecycle manager: initialize database, directories, and background workers."""
        logger.info("Starting Pharmacy POS Daemon v%s...", __version__)
        app_config.ensure_directories()
        engine.initialize()
        app.state.db_engine = engine
        app.state.config = app_config
        app.state.start_time = start_time
        yield
        logger.info("Pharmacy POS Daemon shutting down.")

    app = FastAPI(
        title="Pharmacy POS Offline Daemon",
        description="Local background daemon and REST API for offline pharmacy management system",
        version=__version__,
        lifespan=lifespan,
    )

    # Attach initial state for access prior to lifespan in tests
    app.state.db_engine = engine
    app.state.config = app_config
    app.state.start_time = start_time

    # Configure CORS to permit local Chromium web interface and LAN network clients
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:5173",
            "http://localhost:5173",
            "http://127.0.0.1:38291",
            "http://localhost:38291",
        ],
        allow_origin_regex=r"https?://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+|172\.(1[6-9]|2[0-9]|3[0-1])\.\d+\.\d+)(:\d+)?",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Global Exception Handlers enforcing @pharmacy/api-contracts envelopes
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        code_str = {
            400: "BAD_REQUEST",
            401: "UNAUTHORIZED",
            403: "FORBIDDEN",
            404: "NOT_FOUND",
            409: "CONFLICT",
            422: "VALIDATION_ERROR",
        }.get(exc.status_code, "ERROR")

        now_str = datetime.now(timezone.utc).isoformat()
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "detail": exc.detail,
                "error": {
                    "code": code_str,
                    "message": exc.detail,
                    "details": None,
                    "timestamp": now_str,
                },
            },
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        now_str = datetime.now(timezone.utc).isoformat()
        from fastapi.encoders import jsonable_encoder
        error_msg = "; ".join([f"{'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}" for err in exc.errors()])
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "success": False,
                "detail": error_msg,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": error_msg,
                    "details": {"errors": jsonable_encoder(exc.errors())},
                    "timestamp": now_str,
                },
            },
        )

    # Register API Routers
    app.include_router(auth_router)
    app.include_router(masters_router)
    app.include_router(purchases_router)
    app.include_router(inventory_router)
    app.include_router(sales_router)
    app.include_router(khata_router)
    app.include_router(returns_router)
    app.include_router(wastage_router)
    app.include_router(reports_router)
    app.include_router(system_router)

    # Health & System Telemetry Endpoint
    @app.get("/api/v1/health", tags=["System"])
    @app.get("/health", tags=["System"])
    def health_check():
        """Telemetry check reporting uptime, database status, and version."""
        uptime = round(time.time() - app.state.start_time, 2)
        db_health = engine.get_health()

        return {
            "status": db_health.get("status", "HEALTHY"),
            "version": __version__,
            "uptime_seconds": uptime,
            "database": db_health,
            "port": app_config.port,
            "platform": sys.platform,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # Mount Static Web Assets if available (Production & Monorepo)
    if app_config.web_dir and (app_config.web_dir / "index.html").exists():
        from fastapi.staticfiles import StaticFiles

        logger.info("Serving web frontend from %s", app_config.web_dir)
        app.mount("/", StaticFiles(directory=str(app_config.web_dir), html=True), name="web_assets")
    else:
        logger.error(
            "Web frontend assets were not found; the API is running without the desktop UI. "
            "Install the web/ directory beside the daemon executable or set PHARMACY_WEB_DIR."
        )

        @app.get("/", include_in_schema=False)
        async def frontend_missing():
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={
                    "detail": "MediHisaab desktop interface files are missing. Repair or reinstall the application.",
                    "hint": "Expected web/index.html beside the installed daemon.",
                },
            )

    return app
