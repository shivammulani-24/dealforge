from __future__ import annotations

from fastapi import APIRouter, Request, status

from app.api.deps import SessionDep, TokenDep, UserDep
from app.schemas.api import LoginIn, RegisterIn, TokenOut, UserOut
from app.services import auth

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(body: RegisterIn, session: SessionDep) -> UserOut:
    return UserOut.model_validate(auth.register(session, body.email, body.password))


@router.post("/token", response_model=TokenOut)
def token(body: LoginIn, session: SessionDep, request: Request) -> TokenOut:
    tok, expires = auth.login(
        session, body.email, body.password, request.app.state.settings.token_ttl_hours
    )
    return TokenOut(access_token=tok, expires_at=expires)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(session: SessionDep, tok: TokenDep, _user: UserDep) -> None:
    auth.logout(session, tok)


@router.get("/me", response_model=UserOut)
def me(user: UserDep) -> UserOut:
    return UserOut.model_validate(user)
