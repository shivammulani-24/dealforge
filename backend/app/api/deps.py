"""Request-scoped dependencies: database session and the authenticated user."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db.models import User
from app.services import auth
from app.services.errors import Unauthorized

bearer = HTTPBearer(auto_error=False)


def get_session(request: Request) -> Iterator[Session]:
    with request.app.state.session_factory() as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]


def get_token(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> str:
    if creds is None or creds.scheme.lower() != "bearer":
        raise Unauthorized("Missing bearer token.")
    return creds.credentials


TokenDep = Annotated[str, Depends(get_token)]


def current_user(session: SessionDep, token: TokenDep) -> User:
    return auth.authenticate(session, token)


UserDep = Annotated[User, Depends(current_user)]
