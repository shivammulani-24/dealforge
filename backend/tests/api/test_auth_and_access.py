"""Authentication (P3-05) and owner-only authorisation (P3-06)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from conftest import PASSWORD, full_setup, login
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from app.db.models import ApiToken, User


def test_register_login_me_logout(client: TestClient) -> None:
    r = client.post("/api/v1/auth/register", json={"email": "A@Example.com", "password": PASSWORD})
    assert r.status_code == 201 and r.json()["email"] == "a@example.com"
    tok = client.post(
        "/api/v1/auth/token", json={"email": "a@example.com", "password": PASSWORD}
    ).json()
    h = {"Authorization": f"Bearer {tok['access_token']}"}
    assert client.get("/api/v1/auth/me", headers=h).json()["email"] == "a@example.com"
    assert client.post("/api/v1/auth/logout", headers=h).status_code == 204
    after = client.get("/api/v1/auth/me", headers=h)
    assert after.status_code == 401 and after.json()["error_type"] == "authentication"


def test_secrets_are_never_stored_in_plain_text(client: TestClient) -> None:
    h = login(client)
    raw = h["Authorization"].split()[1]
    with client.app.state.session_factory() as s:  # type: ignore[attr-defined]
        user = s.scalar(select(User))
        assert user.password_hash.startswith("scrypt$") and PASSWORD not in user.password_hash
        dump = " ".join(str(v) for row in s.execute(text("SELECT * FROM api_tokens")) for v in row)
        assert raw not in dump


def test_bad_credentials_and_registration_rules(client: TestClient) -> None:
    login(client)
    wrong = client.post(
        "/api/v1/auth/token", json={"email": "analyst@example.com", "password": "nope-nope-nope"}
    )
    unknown = client.post(
        "/api/v1/auth/token", json={"email": "ghost@example.com", "password": "nope-nope-nope"}
    )
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["errors"][0]["message"] == unknown.json()["errors"][0]["message"]
    dup = client.post(
        "/api/v1/auth/register", json={"email": "analyst@example.com", "password": PASSWORD}
    )
    assert dup.status_code == 409
    weak = client.post(
        "/api/v1/auth/register", json={"email": "b@example.com", "password": "short"}
    )
    assert weak.status_code == 422 and weak.json()["errors"][0]["code"] == "WEAK_PASSWORD"
    bad_email = client.post("/api/v1/auth/register", json={"email": "nope", "password": PASSWORD})
    assert bad_email.status_code == 422 and bad_email.json()["error_type"] == "validation"


def test_requests_without_valid_token_are_rejected(client: TestClient) -> None:
    for headers in ({}, {"Authorization": "Bearer not-a-token"}, {"Authorization": "Basic abc"}):
        r = client.get("/api/v1/companies", headers=headers)
        assert r.status_code == 401, headers
        assert r.headers["www-authenticate"] == "Bearer"


def test_expired_token_is_rejected(client: TestClient) -> None:
    h = login(client)
    with client.app.state.session_factory() as s:  # type: ignore[attr-defined]
        row = s.scalar(select(ApiToken))
        row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        s.commit()
    r = client.get("/api/v1/auth/me", headers=h)
    assert r.status_code == 401 and "expired" in r.json()["errors"][0]["message"]


def test_users_cannot_see_each_others_data(client: TestClient) -> None:
    a = login(client, "a@example.com")
    ids = full_setup(client, a)
    run = client.post(f"/api/v1/scenarios/{ids['scenario']}/runs", headers=a, json={}).json()
    b = login(client, "b@example.com")
    for url in (
        f"/api/v1/companies/{ids['company']}",
        f"/api/v1/companies/{ids['company']}/financials",
        f"/api/v1/projects/{ids['project']}",
        f"/api/v1/scenarios/{ids['scenario']}",
        f"/api/v1/runs/{run['id']}",
    ):
        r = client.get(url, headers=b)
        assert r.status_code == 404, url  # 404, not 403: existence is not leaked
    assert (
        client.post(f"/api/v1/scenarios/{ids['scenario']}/runs", headers=b, json={}).status_code
        == 404
    )
    assert client.post(f"/api/v1/runs/{run['id']}/verify", headers=b).status_code == 404
    assert client.get("/api/v1/companies", headers=b).json() == []
    assert client.get("/api/v1/projects", headers=b).json() == []
    other_project = client.post(
        "/api/v1/projects",
        headers=b,
        json={"company_id": ids["company"], "name": "steal", "description": None},
    )
    assert other_project.status_code == 404
