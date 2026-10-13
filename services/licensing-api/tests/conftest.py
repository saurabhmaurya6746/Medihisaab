"""Test fixtures for Central Vendor Licensing API."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from licensing_service.app import app
from licensing_service.db.migrations import hash_password, seed_default_data
from licensing_service.db.models import Base, VendorRole, VendorUser
from licensing_service.db.session import get_db
from licensing_service.security.auth import create_access_token

# In-memory test SQLite engine
TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """Create schema and test users once for the session."""
    Base.metadata.create_all(bind=test_engine)
    db = TestingSessionLocal()
    try:
        seed_default_data(db)

        # Seed additional roles for RBAC testing
        admin = VendorUser(
            full_name="Admin Test User",
            email="admin@apexhealth.local",
            password_hash=hash_password("AdminSecurePass2026!"),
            role=VendorRole.ADMIN.value,
            is_active=True,
        )
        support = VendorUser(
            full_name="Support Test User",
            email="support@apexhealth.local",
            password_hash=hash_password("SupportSecurePass2026!"),
            role=VendorRole.SUPPORT.value,
            is_active=True,
        )
        readonly = VendorUser(
            full_name="ReadOnly Test User",
            email="readonly@apexhealth.local",
            password_hash=hash_password("ReadOnlySecurePass2026!"),
            role=VendorRole.READ_ONLY.value,
            is_active=True,
        )
        db.add_all([admin, support, readonly])
        db.commit()
    finally:
        db.close()
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session():
    """Provide a database session for a test, rolled back on teardown."""
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session):
    """Provide a FastAPI TestClient configured to use the test db session."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    from licensing_service.security.auth import clear_signup_attempts, clear_renewal_attempts
    clear_signup_attempts()
    clear_renewal_attempts()
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    clear_signup_attempts()
    clear_renewal_attempts()


@pytest.fixture
def owner_headers(db_session):
    """Bearer token headers for OWNER user."""
    owner = db_session.query(VendorUser).filter(VendorUser.email == "owner@apexhealth.local").first()
    token = create_access_token({"sub": str(owner.id), "email": owner.email, "role": owner.role})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers(db_session):
    """Bearer token headers for ADMIN user."""
    admin = db_session.query(VendorUser).filter(VendorUser.email == "admin@apexhealth.local").first()
    token = create_access_token({"sub": str(admin.id), "email": admin.email, "role": admin.role})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def support_headers(db_session):
    """Bearer token headers for SUPPORT user."""
    support = db_session.query(VendorUser).filter(VendorUser.email == "support@apexhealth.local").first()
    token = create_access_token({"sub": str(support.id), "email": support.email, "role": support.role})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def readonly_headers(db_session):
    """Bearer token headers for READ_ONLY user."""
    ro = db_session.query(VendorUser).filter(VendorUser.email == "readonly@apexhealth.local").first()
    token = create_access_token({"sub": str(ro.id), "email": ro.email, "role": ro.role})
    return {"Authorization": f"Bearer {token}"}
