import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models  # noqa: F401  — registers tables on Base.metadata
from app.db import Base


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
