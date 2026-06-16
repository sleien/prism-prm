"""Resolve a user's Nextcloud account into a client.

Each user can configure their own Nextcloud (Settings). If they haven't, the
instance-level NEXTCLOUD_* env settings are used as a fallback (handy for a
single-user deployment). Returns None when neither is available.
"""

from __future__ import annotations

from typing import Any

from app.auth.crypto import decrypt
from app.config import settings
from app.integrations.nextcloud import NextcloudClient


def client_for_user(user: Any) -> NextcloudClient | None:
    url = (user.nextcloud_url or "").strip() or None
    username = (user.nextcloud_username or "").strip() or None
    password = decrypt(user.nextcloud_app_password_enc) if user.nextcloud_app_password_enc else None
    addressbook = user.nextcloud_addressbook
    calendar = user.nextcloud_calendar

    if not (url and username and password):
        # Fall back to the instance-level service account.
        if not settings.nextcloud_configured:
            return None
        url = settings.nextcloud_url
        username = settings.nextcloud_username
        password = settings.nextcloud_app_password

    return NextcloudClient(
        url,  # type: ignore[arg-type]
        username,  # type: ignore[arg-type]
        password,  # type: ignore[arg-type]
        addressbook=addressbook or settings.nextcloud_addressbook,
        calendar=calendar or settings.nextcloud_calendar,
    )


def user_has_personal_nextcloud(user: Any) -> bool:
    return bool(user.nextcloud_url and user.nextcloud_username and user.nextcloud_app_password_enc)


def user_has_nextcloud(user: Any) -> bool:
    return client_for_user(user) is not None
