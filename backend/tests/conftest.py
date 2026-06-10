import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import sessionmaker as _sessionmaker

from app import models  # noqa: F401  — registers tables on Base.metadata
from app.db import Base, get_db
from app.main import create_app


@pytest.fixture()
def test_engine(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def db_session(test_engine):
    TestingSession = sessionmaker(
        bind=test_engine, autoflush=False, expire_on_commit=False
    )
    session = TestingSession()
    yield session
    session.close()


@pytest.fixture()
def client(test_engine):
    TestingSession = _sessionmaker(
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
