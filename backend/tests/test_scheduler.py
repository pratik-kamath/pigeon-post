from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import db
from app.main import SWEEP_INTERVAL_SECONDS, _run_sweep, create_app


def test_lifespan_starts_and_stops_scheduler(tmp_path, monkeypatch):
    # Point the app at a temp DB so the lifespan's create_all and any sweep
    # that fires never touch the real pigeon.db.
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}",
        connect_args={"check_same_thread": False},
    )
    monkeypatch.setattr(db, "engine", engine)
    monkeypatch.setattr(
        db,
        "SessionLocal",
        sessionmaker(bind=engine, autoflush=False, expire_on_commit=False),
    )

    app = create_app(start_scheduler=True)
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert app.state.scheduler.running is True
        [job] = app.state.scheduler.get_jobs()
        assert job.func is _run_sweep
        assert job.trigger.interval.total_seconds() == SWEEP_INTERVAL_SECONDS
    assert app.state.scheduler.running is False
    engine.dispose()


def test_scheduler_not_started_when_disabled(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}",
        connect_args={"check_same_thread": False},
    )
    monkeypatch.setattr(db, "engine", engine)

    app = create_app(start_scheduler=False)
    with TestClient(app):
        assert getattr(app.state, "scheduler", None) is None
    engine.dispose()
