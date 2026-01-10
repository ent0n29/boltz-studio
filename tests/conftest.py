"""Pytest fixtures for Boltz Studio tests."""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """Set up test database path before any imports."""
    # Create a temp file for the test database
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.environ["BOLTZ_STUDIO_DB_PATH"] = db_path

    yield db_path

    # Cleanup
    try:
        os.unlink(db_path)
    except OSError:
        pass


@pytest.fixture
def app(setup_test_db):
    """Create a test application instance."""
    from boltz_studio.app import create_app
    from boltz_studio.services.database import init_db

    # Ensure database is initialized
    init_db()

    return create_app()


@pytest.fixture
def client(app) -> TestClient:
    """Create a test client for the application."""
    return TestClient(app)


@pytest.fixture
def job_store(setup_test_db):
    """Create a fresh job store for testing."""
    from boltz_studio.services.database import init_db
    from boltz_studio.services.job_store import JobStore

    # Initialize database
    init_db()

    return JobStore()


@pytest.fixture
def rate_limiter():
    """Create a rate limiter for testing."""
    from boltz_studio.middleware.rate_limit import RateLimiter
    return RateLimiter(requests_per_minute=5)


@pytest.fixture
def mock_request():
    """Create a mock FastAPI request."""
    from unittest.mock import MagicMock

    request = MagicMock()
    request.client.host = "127.0.0.1"
    request.headers = {}
    return request
