"""Configuration management for the Pharmacy Daemon service.

Resolves local Windows paths, database files, and authentication secrets.
"""

from dataclasses import dataclass
import os
from pathlib import Path
import secrets
from typing import Optional


def get_default_app_dir() -> Path:
    """Return default application directory adhering to Windows NTFS conventions."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "PharmacyApp"
    return Path.home() / "AppData" / "Local" / "PharmacyApp"


def resolve_web_dir(custom_web_dir: Optional[Path] = None, app_dir: Optional[Path] = None) -> Optional[Path]:
    """Resolve production build assets directory for frontend static serving."""
    if custom_web_dir and (custom_web_dir / "index.html").exists():
        return custom_web_dir
    if "PHARMACY_WEB_DIR" in os.environ:
        p = Path(os.environ["PHARMACY_WEB_DIR"])
        if (p / "index.html").exists():
            return p
    # Check if packaged as frozen executable (PyInstaller)
    import sys
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        # Support both the normal installer layout (daemon/pharmacy-daemon.exe
        # beside web/) and releases where the executable is one directory deeper.
        for candidate in (exe_dir / "web", exe_dir.parent / "web", exe_dir.parent.parent / "web"):
            if (candidate / "index.html").is_file() and (candidate / "assets").is_dir():
                return candidate
    # Check app_dir / "web" (installed Windows application layout)
    if app_dir:
        cand = app_dir / "web"
        if (cand / "index.html").exists():
            return cand
    # Check parent directories for built production assets (dist or staged web folder).
    # In packaged builds __file__ may resolve into PyInstaller's _internal folder;
    # also inspect the executable location and current install working directory.
    search_roots = [Path(__file__).resolve(), Path.cwd()]
    if getattr(sys, "frozen", False):
        search_roots.append(Path(sys.executable).resolve())
    for root in search_roots:
        for parent in root.parents:
            cand_dist = parent / "apps" / "web" / "dist"
            if (cand_dist / "index.html").is_file() and (cand_dist / "assets").is_dir():
                return cand_dist
            cand_web = parent / "web"
            if (cand_web / "index.html").is_file() and (cand_web / "assets").is_dir():
                return cand_web
    return None


@dataclass
class DaemonConfig:
    """Application runtime configuration."""

    app_dir: Path
    data_dir: Path
    db_path: Path
    log_dir: Path
    host: str = "127.0.0.1"
    port: int = 38291
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 12  # 12 hours shift session
    web_dir: Optional[Path] = None

    @classmethod
    def load(
        cls,
        custom_db_path: Optional[Path] = None,
        custom_app_dir: Optional[Path] = None,
        custom_web_dir: Optional[Path] = None,
    ) -> "DaemonConfig":
        """Load configuration with optional environment variable overrides."""
        app_dir = custom_app_dir or (
            Path(os.environ["PHARMACY_APP_DIR"])
            if "PHARMACY_APP_DIR" in os.environ
            else get_default_app_dir()
        )
        data_dir = app_dir / "data"
        log_dir = app_dir / "logs"

        if custom_db_path:
            db_path = custom_db_path
        elif "PHARMACY_DB_PATH" in os.environ:
            db_path = Path(os.environ["PHARMACY_DB_PATH"])
        else:
            db_path = data_dir / "pharmacy.db"

        # Resolve or generate persistent JWT secret key
        jwt_secret = os.environ.get("PHARMACY_JWT_SECRET")
        if not jwt_secret:
            secret_file = app_dir / "secret.key"
            if secret_file.exists():
                try:
                    jwt_secret = secret_file.read_text(encoding="utf-8").strip()
                except Exception:
                    jwt_secret = ""
            if not jwt_secret:
                jwt_secret = secrets.token_hex(32)
                try:
                    app_dir.mkdir(parents=True, exist_ok=True)
                    secret_file.write_text(jwt_secret, encoding="utf-8")
                except Exception:
                    # In restricted or test contexts, keep in memory
                    pass

        # Host binding: check environment override first, then persisted system_config
        if "PHARMACY_HOST" in os.environ:
            host = os.environ["PHARMACY_HOST"]
        else:
            host = "127.0.0.1"
            if db_path.exists():
                try:
                    import sqlite3

                    conn = sqlite3.connect(str(db_path), timeout=1.0)
                    cur = conn.cursor()
                    cur.execute("SELECT value FROM system_config WHERE key = 'server_mode';")
                    row = cur.fetchone()
                    if row and row[0] == "LAN_SERVER":
                        host = "0.0.0.0"
                    conn.close()
                except Exception:
                    pass

        port = int(os.environ.get("PHARMACY_PORT", "38291"))
        web_dir = resolve_web_dir(custom_web_dir, app_dir)

        config = cls(
            app_dir=app_dir,
            data_dir=data_dir,
            db_path=db_path,
            log_dir=log_dir,
            host=host,
            port=port,
            jwt_secret_key=jwt_secret,
            web_dir=web_dir,
        )
        config.ensure_directories()
        return config

    def ensure_directories(self) -> None:
        """Create required local directories if they do not exist."""
        self.app_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        # Ensure parent of db_path exists in case of custom db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
