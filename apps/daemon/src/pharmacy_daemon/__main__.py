"""Entry point for launching the Pharmacy Daemon service via python -m pharmacy_daemon."""

import logging
import sys
import uvicorn

from .app import create_app
from .config import DaemonConfig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("pharmacy_daemon")


def main():
    """Start uvicorn server on configured host and port."""
    config = DaemonConfig.load()
    # The packaged daemon is a background process with no console window.
    # Keep diagnostics in the user's app-data directory instead.
    log_path = config.log_dir / "daemon.log"
    logging.basicConfig(
        filename=str(log_path),
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        force=True,
    )
    if sys.stdout is None:
        sys.stdout = open(log_path, "a", encoding="utf-8", buffering=1)
    if sys.stderr is None:
        sys.stderr = open(log_path, "a", encoding="utf-8", buffering=1)
    app = create_app(config)

    logger.info("Starting Pharmacy Daemon on %s:%d (Database: %s)", config.host, config.port, config.db_path)
    uvicorn.run(
        app,
        host=config.host,
        port=config.port,
        log_level="info",
        log_config=None,
    )


if __name__ == "__main__":
    main()
