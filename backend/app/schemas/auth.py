"""Auth request/response schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterIn(BaseModel):
    email: EmailStr
    display_name: str
    password: str


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    display_name: str
    is_superuser: bool


class MeOut(BaseModel):
    user: UserOut
    groups: list[str] = []
    self_contact_id: int | None = None
    default_currency: str = "CHF"
    phone_country_code: str = "+41"
    phone_number_format: str = "xxx xxx xx xx"
    phone_include_country_code: bool = False
    date_format: str = "dd.mm.yyyy"
    default_phone_type: str = "mobile"
    default_email_type: str = "home"
    default_address_type: str = "home"
    # Whether this user has a usable Nextcloud (personal creds or instance fallback).
    nextcloud_configured: bool = False
    # Personal Nextcloud config (password never returned).
    nextcloud_url: str | None = None
    nextcloud_username: str | None = None
    nextcloud_addressbook: str | None = None
    nextcloud_calendar: str | None = None


class SelfContactIn(BaseModel):
    contact_id: int | None = None


class PreferencesIn(BaseModel):
    default_currency: str | None = Field(default=None, max_length=3)
    phone_country_code: str | None = Field(default=None, max_length=8)
    phone_number_format: str | None = Field(default=None, max_length=40)
    phone_include_country_code: bool | None = None
    date_format: str | None = Field(default=None, max_length=12)
    default_phone_type: str | None = Field(default=None, max_length=20)
    default_email_type: str | None = Field(default=None, max_length=20)
    default_address_type: str | None = Field(default=None, max_length=20)


class NextcloudSettingsIn(BaseModel):
    nextcloud_url: str | None = Field(default=None, max_length=500)
    nextcloud_username: str | None = Field(default=None, max_length=200)
    # Send to set/replace; omit/null to leave unchanged; empty string to clear.
    nextcloud_app_password: str | None = None
    nextcloud_addressbook: str | None = Field(default=None, max_length=200)
    nextcloud_calendar: str | None = Field(default=None, max_length=200)


class AuthConfigOut(BaseModel):
    allow_registration: bool
    oidc_enabled: bool
    oidc_display_name: str


class ApiTokenCreateIn(BaseModel):
    name: str


class ApiTokenOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    prefix: str
    last_used_at: datetime | None = None


class ApiTokenCreatedOut(ApiTokenOut):
    # The plaintext token, returned exactly once at creation.
    token: str
