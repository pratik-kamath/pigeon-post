from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI

from app import db, models  # noqa: F401  — models registers tables on Base.metadata
from app.auth_routes import router as auth_router
from app.cities import CITIES
from app.delivery import resolve_due_messages
from app.routes import router
from app.schemas import CityOut

SWEEP_INTERVAL_SECONDS = 5


def _run_sweep() -> None:
    session = db.SessionLocal()
    try:
        resolve_due_messages(session)
    finally:
        session.close()


def create_app(start_scheduler: bool = True, create_tables: bool = True) -> FastAPI:
    # Single-process assumption: each worker would run its own scheduler, so
    # this app is dev-only until that's revisited. Scheduler starts in the
    # lifespan — never at import time.
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if create_tables:
            db.Base.metadata.create_all(bind=db.engine)
        scheduler = None
        if start_scheduler:
            scheduler = BackgroundScheduler()
            scheduler.add_job(
                _run_sweep,
                "interval",
                seconds=SWEEP_INTERVAL_SECONDS,
                max_instances=1,
                coalesce=True,
            )
            scheduler.start()
        app.state.scheduler = scheduler
        yield
        if scheduler is not None:
            scheduler.shutdown(wait=False)

    app = FastAPI(title="Pigeon Post API", lifespan=lifespan)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/cities", response_model=list[CityOut], tags=["meta"])
    def cities() -> list[CityOut]:
        return [
            CityOut(name=name, lat=lat, lon=lon)
            for name, (lat, lon) in sorted(CITIES.items())
        ]

    app.include_router(router)
    app.include_router(auth_router)
    return app


app = create_app()
