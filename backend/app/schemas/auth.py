"""Auth request/response schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


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


class SelfContactIn(BaseModel):
    contact_id: int | None = None


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
