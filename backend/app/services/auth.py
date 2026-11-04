"""Authentication (P3-05): scrypt password hashes and revocable opaque bearer tokens."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ApiToken, User

from .errors import Conflict, ServiceError, Unauthorized

SCRYPT_N, SCRYPT_R, SCRYPT_P = 2**14, 8, 1
MIN_PASSWORD_LENGTH = 10


class WeakPassword(ServiceError):
    status = 422
    code = "WEAK_PASSWORD"


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P)
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, n, r, p, salt_hex, digest_hex = stored.split("$")
    except ValueError:
        return False
    if algo != "scrypt":
        return False
    digest = hashlib.scrypt(
        password.encode(), salt=bytes.fromhex(salt_hex), n=int(n), r=int(r), p=int(p)
    )
    return hmac.compare_digest(digest.hex(), digest_hex)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def register(session: Session, email: str, password: str) -> User:
    email = email.strip().lower()
    if len(password) < MIN_PASSWORD_LENGTH:
        raise WeakPassword(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    if session.scalar(select(User).where(User.email == email)) is not None:
        raise Conflict("An account with this email already exists.")
    user = User(email=email, password_hash=hash_password(password))
    session.add(user)
    session.commit()
    return user


def login(session: Session, email: str, password: str, ttl_hours: int) -> tuple[str, datetime]:
    user = session.scalar(select(User).where(User.email == email.strip().lower()))
    # Same error for unknown email and wrong password: no account enumeration.
    if user is None or not verify_password(password, user.password_hash):
        raise Unauthorized("Invalid email or password.")
    token = secrets.token_urlsafe(32)
    expires = datetime.now(UTC) + timedelta(hours=ttl_hours)
    session.add(ApiToken(user_id=user.id, token_sha256=_token_hash(token), expires_at=expires))
    session.commit()
    return token, expires


def authenticate(session: Session, token: str) -> User:
    row = session.scalar(select(ApiToken).where(ApiToken.token_sha256 == _token_hash(token)))
    now = datetime.now(UTC)
    if row is None or row.revoked_at is not None:
        raise Unauthorized("Invalid or revoked token.")
    expires = row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=UTC)
    if expires <= now:
        raise Unauthorized("Token expired; log in again.")
    user = session.get(User, row.user_id)
    if user is None:  # pragma: no cover - FK cascade makes this unreachable
        raise Unauthorized("Invalid token.")
    return user


def logout(session: Session, token: str) -> None:
    row = session.scalar(select(ApiToken).where(ApiToken.token_sha256 == _token_hash(token)))
    if row is not None and row.revoked_at is None:
        row.revoked_at = datetime.now(UTC)
        session.commit()
