import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.db import get_db
from app.main import create_app


@pytest.fixture()
def cors_client(monkeypatch, test_engine):
    # Set the env BEFORE create_app reads it (origins are parsed at app build,
    # so the shared `client` fixture can't be reconfigured in the test body,
    # and ambient CORS_ORIGINS must not leak in).
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173")
    TestingSession = sessionmaker(
        bind=test_engine, autoflush=False, expire_on_commit=False
    )
    app = create_app(start_scheduler=False, create_tables=False)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def test_cors_reflects_configured_origin(cors_client):
    resp = cors_client.get("/health", headers={"Origin": "http://localhost:5173"})
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_cors_omits_unknown_origin(cors_client):
    resp = cors_client.get("/health", headers={"Origin": "http://evil.example"})
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") is None
