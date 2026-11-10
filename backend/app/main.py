"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI

from app.api import errors
from app.api.v1 import auth, companies, valuations
from app.config import Settings
from app.db.migrate import upgrade
from app.db.session import make_engine, make_session_factory, make_write_engine
from app.engine.version import ENGINE_VERSION


def create_app(settings: Settings | None = None, *, migrate: bool = True) -> FastAPI:
    settings = settings or Settings.from_env()
    if migrate:
        upgrade(settings.database_url)
    app = FastAPI(
        title="DealForge API",
        version="0.3.0",
        description="M&A valuation engine API. All sample data is synthetic.",
    )
    app.state.settings = settings
    app.state.db_engine = make_engine(
        settings.database_url, busy_timeout_ms=settings.sqlite_busy_timeout_ms
    )
    app.state.session_factory = make_session_factory(app.state.db_engine)
    # Write transactions that must check-then-insert atomically start with BEGIN IMMEDIATE
    app.state.write_session_factory = make_session_factory(make_write_engine(app.state.db_engine))
    errors.install(app)
    for r in (auth.router, companies.router, valuations.router):
        app.include_router(r, prefix="/api/v1")

    @app.get("/api/v1/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "engine_version": ENGINE_VERSION}

    return app
