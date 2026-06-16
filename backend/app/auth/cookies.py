"""Set/clear the signed auth cookies on a response."""

from __future__ import annotations

from fastapi import Response

from app.auth.security import (
    ACCESS_TOKEN_COOKIE,
    REFRESH_TOKEN_COOKIE,
    create_access_token,
    create_refresh_token,
)
from app.config import settings


def set_auth_cookies(response: Response, user_id: int) -> None:
    common = {
        "httponly": True,
        "secure": settings.cookie_secure,
        "samesite": "lax",
        "domain": settings.cookie_domain,
        "path": "/",
    }
    response.set_cookie(
        ACCESS_TOKEN_COOKIE,
        create_access_token(user_id),
        max_age=settings.access_token_ttl_minutes * 60,
        **common,
    )
    response.set_cookie(
        REFRESH_TOKEN_COOKIE,
        create_refresh_token(user_id),
        max_age=settings.refresh_token_ttl_days * 86400,
        **common,
    )


def clear_auth_cookies(response: Response) -> None:
    for name in (ACCESS_TOKEN_COOKIE, REFRESH_TOKEN_COOKIE):
        response.delete_cookie(name, domain=settings.cookie_domain, path="/")
