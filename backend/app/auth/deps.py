"""Authentication dependencies."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import ACCESS_TOKEN_COOKIE, decode_token, hash_api_token
from app.db import get_session
from app.models import ApiToken, User


async def _user_from_bearer(request: Request, session: AsyncSession) -> User | None:
    """Authenticate via `Authorization: Bearer <api-token>` (for CalDAV/mobile)."""
    header = request.headers.get("authorization")
    if not header or not header.lower().startswith("bearer "):
        return None
    raw = header.split(" ", 1)[1].strip()
    token = await session.scalar(select(ApiToken).where(ApiToken.token_hash == hash_api_token(raw)))
    if token is None:
        return None
    user = await session.get(User, token.user_id)
    if user is None or not user.is_active:
        return None
    token.last_used_at = datetime.now(UTC)
    await session.commit()
    return user


async def get_current_user(
    request: Request, session: AsyncSession = Depends(get_session)
) -> User:
    # Browser cookie takes precedence; fall back to a personal API token.
    cookie = request.cookies.get(ACCESS_TOKEN_COOKIE)
    if cookie:
        user_id = decode_token(cookie, "access")
        if user_id is not None:
            user = await session.get(User, user_id)
            if user is not None and user.is_active:
                return user

    user = await _user_from_bearer(request, session)
    if user is not None:
        return user
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")


async def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_superuser:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin privileges required")
    return user
