"""Mandatory, concurrency-safe idempotent freezes (A7, A8; plan §4.5 and §4.14)."""

from __future__ import annotations

import sqlite3
import threading
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from conftest import full_setup, login
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.config import Settings
from app.db.models import AuditEvent, ValuationRun
from app.main import create_app
from app.services import valuations as svc

THREADS = 8


def counts(app: FastAPI) -> tuple[int, int]:
    with app.state.session_factory() as s:
        runs = s.scalar(select(func.count()).select_from(ValuationRun))
        audits = s.scalar(
            select(func.count()).select_from(AuditEvent).where(AuditEvent.entity == "valuation_run")
        )
    return int(runs or 0), int(audits or 0)


def freeze(
    client: TestClient, h: dict[str, str], sid: int, key: str | None, label: str | None = None
) -> Any:
    headers = dict(h) if key is None else {**h, "Idempotency-Key": key}
    return client.post(f"/api/v1/scenarios/{sid}/runs", headers=headers, json={"label": label})


@pytest.fixture
def setup(client: TestClient, auth: dict[str, str]) -> dict[str, int]:
    return full_setup(client, auth)


def test_missing_key_is_rejected_before_any_work(
    client: TestClient,
    auth: dict[str, str],
    setup: dict[str, int],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[object] = []
    monkeypatch.setattr(svc, "run_dcf", lambda inp: calls.append(inp))
    r = freeze(client, auth, setup["scenario"], None)
    assert r.status_code == 422 and r.json()["error_type"] == "validation"
    err = r.json()["errors"][0]
    assert err["code"] == "missing" and err["loc"] == ["header", "Idempotency-Key"]
    assert calls == [] and counts(client.app) == (0, 0)  # type: ignore[arg-type]


@pytest.mark.parametrize("key", ["short", "has space here", "bad/char/key", "x" * 129])
def test_malformed_keys_are_rejected(
    client: TestClient, auth: dict[str, str], setup: dict[str, int], key: str
) -> None:
    r = freeze(client, auth, setup["scenario"], key)
    assert r.status_code == 422 and r.json()["error_type"] == "validation"
    assert counts(client.app) == (0, 0)  # type: ignore[arg-type]


def test_replay_returns_the_same_run(
    client: TestClient, auth: dict[str, str], setup: dict[str, int]
) -> None:
    first = freeze(client, auth, setup["scenario"], "key-replay-0001", "v1")
    assert first.status_code == 201 and "idempotent-replayed" not in first.headers
    again = freeze(client, auth, setup["scenario"], "key-replay-0001", "v1")
    assert again.status_code == 200 and again.headers["idempotent-replayed"] == "true"
    assert again.json() == first.json()  # same run, byte for byte
    assert counts(client.app) == (1, 1)  # type: ignore[arg-type]


def test_replay_after_scenario_edit_still_returns_the_original_run(
    client: TestClient, auth: dict[str, str], setup: dict[str, int]
) -> None:
    first = freeze(client, auth, setup["scenario"], "key-edit-00001").json()
    sc = client.get(f"/api/v1/scenarios/{setup['scenario']}", headers=auth).json()
    rows = [dict(a) for a in sc["assumptions"]]
    next(a for a in rows if a["key"] == "terminal_growth")["value"] = 0.03
    client.put(
        f"/api/v1/scenarios/{setup['scenario']}",
        headers=auth,
        json={"settings": sc["settings"], "assumptions": rows},
    )
    again = freeze(client, auth, setup["scenario"], "key-edit-00001")
    assert again.status_code == 200 and again.json()["input_hash"] == first["input_hash"]


def test_reusing_a_key_for_a_different_request_is_a_conflict(
    client: TestClient, auth: dict[str, str], setup: dict[str, int]
) -> None:
    freeze(client, auth, setup["scenario"], "key-reuse-0001", "v1")
    r = freeze(client, auth, setup["scenario"], "key-reuse-0001", "a different label")
    assert r.status_code == 409 and r.json()["errors"][0]["code"] == "IDEMPOTENCY_KEY_REUSED"
    assert r.json()["error_type"] == "conflict"
    assert counts(client.app) == (1, 1)  # type: ignore[arg-type]


def test_keys_are_scoped_per_user(
    client: TestClient, auth: dict[str, str], setup: dict[str, int]
) -> None:
    other = login(client, "other@example.com")
    theirs = full_setup(client, other)
    a = freeze(client, auth, setup["scenario"], "shared-key-0001")
    b = freeze(client, other, theirs["scenario"], "shared-key-0001")
    assert a.status_code == b.status_code == 201 and a.json()["id"] != b.json()["id"]


def race(app: FastAPI, h: dict[str, str], sid: int, keys: list[str]) -> list[Any]:
    barrier = threading.Barrier(len(keys))
    results: list[Any] = [None] * len(keys)

    def go(i: int) -> None:
        c = TestClient(app)
        barrier.wait()
        results[i] = freeze(c, h, sid, keys[i])

    threads = [threading.Thread(target=go, args=(i,)) for i in range(len(keys))]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    return results


def test_concurrent_requests_with_the_same_key_create_exactly_one_run(
    client: TestClient, auth: dict[str, str], setup: dict[str, int]
) -> None:
    res = race(client.app, auth, setup["scenario"], ["same-key-race-01"] * THREADS)  # type: ignore[arg-type]
    codes = sorted(r.status_code for r in res)
    assert codes == [200] * (THREADS - 1) + [201]
    assert len({r.json()["id"] for r in res}) == 1
    assert len({r.json()["input_hash"] for r in res}) == 1
    assert counts(client.app) == (1, 1)  # type: ignore[arg-type]


def test_concurrent_requests_with_different_keys_create_one_run_each(
    client: TestClient, auth: dict[str, str], setup: dict[str, int]
) -> None:
    keys = [f"distinct-key-{i:02d}" for i in range(THREADS)]
    res = race(client.app, auth, setup["scenario"], keys)  # type: ignore[arg-type]
    assert all(r.status_code == 201 for r in res)
    assert counts(client.app) == (THREADS, THREADS)  # type: ignore[arg-type]


def test_recheck_inside_begin_immediate_turns_a_lost_race_into_a_replay(
    client: TestClient,
    auth: dict[str, str],
    setup: dict[str, int],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A competing request commits the same key after this request's read phase but before its
    write phase (plan §4.14 step 3). The in-transaction re-check must return that run."""
    fired = {"done": False}
    real_hook = svc._before_write_phase

    def competitor() -> None:
        if not fired["done"]:
            fired["done"] = True
            inner = freeze(TestClient(client.app), auth, setup["scenario"], "injected-key-01")
            assert inner.status_code == 201
        real_hook()

    monkeypatch.setattr(svc, "_before_write_phase", competitor)
    outer = freeze(client, auth, setup["scenario"], "injected-key-01")
    assert fired["done"]
    assert outer.status_code == 200 and outer.headers["idempotent-replayed"] == "true"
    assert counts(client.app) == (1, 1)  # type: ignore[arg-type]


@pytest.fixture
def slow_lock_app(tmp_path: Path) -> Iterator[tuple[FastAPI, str]]:
    path = tmp_path / "lock.sqlite3"
    app = create_app(Settings(database_url=f"sqlite:///{path}", sqlite_busy_timeout_ms=50))
    yield app, str(path)
    app.state.db_engine.dispose()


def test_lock_timeout_returns_503_and_a_retry_with_the_same_key_succeeds(
    slow_lock_app: tuple[FastAPI, str],
) -> None:
    app, path = slow_lock_app
    c = TestClient(app)
    h = login(c)
    ids = full_setup(c, h)
    key = f"lock-{uuid.uuid4()}"
    holder = sqlite3.connect(path, isolation_level=None)
    holder.execute("BEGIN IMMEDIATE")  # another writer holds SQLite's RESERVED lock
    try:
        busy = freeze(c, h, ids["scenario"], key)
    finally:
        holder.execute("ROLLBACK")
        holder.close()
    assert busy.status_code == 503 and busy.headers["retry-after"] == "1"
    assert busy.json()["error_type"] == "unavailable"
    assert busy.json()["errors"][0]["code"] == "DATABASE_BUSY"
    assert counts(app) == (0, 0)
    retry = freeze(c, h, ids["scenario"], key)
    assert retry.status_code == 201 and counts(app) == (1, 1)


def test_wal_mode_is_active(client: TestClient) -> None:
    with client.app.state.db_engine.connect() as conn:  # type: ignore[attr-defined]
        assert conn.exec_driver_sql("PRAGMA journal_mode").scalar() == "wal"
        assert conn.exec_driver_sql("PRAGMA busy_timeout").scalar() == 5000
        assert conn.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
