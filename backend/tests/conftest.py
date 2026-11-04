"""Shared fixtures: every test gets its own migrated SQLite database file."""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).parent / "engine"))  # engine test builders

from app.db.migrate import upgrade
from app.db.session import make_engine, make_session_factory


@pytest.fixture
def db_url(tmp_path: Path) -> str:
    url = f"sqlite:///{tmp_path / 'test.sqlite3'}"
    upgrade(url)
    return url


@pytest.fixture
def session(db_url: str) -> Iterator[Session]:
    engine = make_engine(db_url)
    factory = make_session_factory(engine)
    with factory() as s:
        yield s
    engine.dispose()
