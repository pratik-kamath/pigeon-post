from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import db, models  # noqa: F401  — models registers tables on Base.metadata
from app.routes import router


def create_app(start_scheduler: bool = True, create_tables: bool = True) -> FastAPI:
    # Both flags exist so tests can opt out: start_scheduler is wired up in the
    # scheduler task; create_tables=False keeps test runs away from pigeon.db.
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if create_tables:
            db.Base.metadata.create_all(bind=db.engine)
        yield

    app = FastAPI(title="Pigeon Post API", lifespan=lifespan)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(router)
    return app


app = create_app()
