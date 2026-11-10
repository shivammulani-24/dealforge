"""Engine and session factories, with the SQLite transaction strategy of plan §4.14 (A8).

SQLite connections get:

* ``PRAGMA foreign_keys = ON``;
* ``PRAGMA busy_timeout`` (default 5,000 ms): a writer waits for the lock instead of failing;
* ``PRAGMA journal_mode = WAL`` on file databases: readers never block the writer and vice versa;
* the pysqlite driver's implicit transactions disabled (``isolation_level = None``); a ``begin``
  listener issues ``BEGIN`` itself. This is the SQLAlchemy-documented recipe; pysqlite's default
  defers ``BEGIN`` and makes locking unreliable.

``make_write_engine`` returns the same engine with ``sqlite_begin="IMMEDIATE"``: transactions on it
start with ``BEGIN IMMEDIATE``, taking SQLite's RESERVED write lock before any read, so a
read-check-insert sequence inside it is atomic with respect to other writers.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import sessionmaker

DEFAULT_BUSY_TIMEOUT_MS = 5000


def make_engine(url: str, *, busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS) -> Engine:
    connect_args: dict[str, Any] = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        connect_args["timeout"] = busy_timeout_ms / 1000
    engine = create_engine(url, connect_args=connect_args)
    if engine.dialect.name == "sqlite":
        in_memory = engine.url.database in (None, "", ":memory:")

        @event.listens_for(engine, "connect")
        def _sqlite_connect(dbapi_conn: Any, _rec: Any) -> None:
            dbapi_conn.isolation_level = None  # we issue BEGIN ourselves (see _sqlite_begin)
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute(f"PRAGMA busy_timeout={int(busy_timeout_ms)}")
            if not in_memory:
                cur.execute("PRAGMA journal_mode=WAL")
            cur.close()

        @event.listens_for(engine, "begin")
        def _sqlite_begin(conn: Any) -> None:
            mode = conn.get_execution_options().get("sqlite_begin", "DEFERRED")
            if mode not in ("DEFERRED", "IMMEDIATE"):  # pragma: no cover - programming error
                raise ValueError(f"unsupported sqlite_begin mode {mode!r}")
            conn.exec_driver_sql(f"BEGIN {mode}")

    return engine


def make_write_engine(engine: Engine) -> Engine:
    """The same engine and pool; transactions begin with BEGIN IMMEDIATE on SQLite."""
    if engine.dialect.name == "sqlite":
        return engine.execution_options(sqlite_begin="IMMEDIATE")
    return engine  # pragma: no cover - other databases use their own locking (LIM-18)


def make_session_factory(engine: Engine) -> sessionmaker:  # type: ignore[type-arg]
    return sessionmaker(bind=engine, expire_on_commit=False)
