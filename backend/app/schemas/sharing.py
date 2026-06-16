"""Sharing schemas: groups and partner designations."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class GroupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None = None
    oidc_group: str | None = None


class GroupCreate(BaseModel):
    name: str
    description: str | None = None
