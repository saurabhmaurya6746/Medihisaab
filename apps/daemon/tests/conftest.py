"""Pytest configuration and test fixtures."""

from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from pharmacy_daemon.app import create_app
from pharmacy_daemon.config import DaemonConfig
from pharmacy_daemon.db.engine import DatabaseEngine


@pytest.fixture
def test_config(tmp_path: Path) -> DaemonConfig:
    """Create isolated test configuration with temporary directory."""
    app_dir = tmp_path / "PharmacyAppTest"
    data_dir = app_dir / "data"
    db_path = data_dir / "test_pharmacy.db"
    log_dir = app_dir / "logs"

    config = DaemonConfig(
        app_dir=app_dir,
        data_dir=data_dir,
        db_path=db_path,
        log_dir=log_dir,
        host="127.0.0.1",
        port=38299,
        jwt_secret_key="test_super_secret_jwt_key_for_unit_tests",
        jwt_algorithm="HS256",
        access_token_expire_minutes=60,
    )
    config.ensure_directories()

    # Provision default active test license so standard test suites have valid license state
    from datetime import date, timedelta
    from pharmacy_daemon.security.license import sign_license, LicenseManager
    private_key_path = Path(__file__).resolve().parent.parent.parent.parent / "publisher_keys" / "license_private_key.pem"
    lic_payload = {
        "client_name": "Test Chemist Workstation",
        "license_id": "LIC-TEST-DEFAULT",
        "terminal_count": 5,
        "activation_date": date.today().isoformat(),
        "expiry_date": (date.today() + timedelta(days=365)).isoformat(),
        "edition": "COMMERCIAL",
        "features": "ALL",
    }
    lic_payload["signature"] = sign_license(lic_payload, private_key_path)
    LicenseManager(app_dir / "license.json").save_license(lic_payload)

    return config


@pytest.fixture
def test_engine(test_config: DaemonConfig) -> DatabaseEngine:
    """Create and initialize an isolated database engine for testing."""
    engine = DatabaseEngine(test_config.db_path)
    engine.initialize()
    return engine


@pytest.fixture
def client(test_config: DaemonConfig) -> TestClient:
    """Create FastAPI test client with isolated database."""
    app = create_app(test_config)
    # Trigger lifespan events
    with TestClient(app) as test_client:
        yield test_client
