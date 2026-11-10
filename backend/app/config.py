"""Runtime settings, read from environment variables (no secrets in code)."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str
    token_ttl_hours: int = 12
    sqlite_busy_timeout_ms: int = 5000  # plan §4.14: writers wait this long for the lock

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            database_url=os.environ.get("DEALFORGE_DATABASE_URL", "sqlite:///./dealforge.sqlite3"),
            token_ttl_hours=int(os.environ.get("DEALFORGE_TOKEN_TTL_HOURS", "12")),
            sqlite_busy_timeout_ms=int(os.environ.get("DEALFORGE_SQLITE_BUSY_TIMEOUT_MS", "5000")),
        )
