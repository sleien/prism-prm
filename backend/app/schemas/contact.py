"""Contact request/response schemas."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.constants import Gender, Visibility


class TypedValue(BaseModel):
    type: str = ""
    value: str


class AddressItem(BaseModel):
    type: str = ""
    street: str = ""
    city: str = ""
    region: str = ""
    code: str = ""
    country: str = ""


class TagOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    color: str | None = None


class ContactBase(BaseModel):
    display_name: str = Field(default="", max_length=300)
    first_name: str | None = Field(default=None, max_length=200)
    middle_name: str | None = Field(default=None, max_length=200)
    last_name: str | None = Field(default=None, max_length=200)
    organization: str | None = Field(default=None, max_length=300)
    job_title: str | None = Field(default=None, max_length=200)
    birthday: date | None = None
    notes: str | None = None
    gender: Gender | None = None
    telegram: str | None = Field(default=None, max_length=100)
    emails: list[TypedValue] = Field(default_factory=list)
    phones: list[TypedValue] = Field(default_factory=list)
    addresses: list[AddressItem] = Field(default_factory=list)
    visibility: Visibility = Visibility.PUBLIC
    group_id: int | None = None
    linked_user_id: int | None = None


class ContactCreate(ContactBase):
    # Tag names; unknown ones are created for the owner on save.
    tags: list[str] = Field(default_factory=list)


class ContactUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=300)
    first_name: str | None = Field(default=None, max_length=200)
    middle_name: str | None = Field(default=None, max_length=200)
    last_name: str | None = Field(default=None, max_length=200)
    organization: str | None = Field(default=None, max_length=300)
    job_title: str | None = Field(default=None, max_length=200)
    birthday: date | None = None
    notes: str | None = None
    gender: Gender | None = None
    telegram: str | None = Field(default=None, max_length=100)
    emails: list[TypedValue] | None = None
    phones: list[TypedValue] | None = None
    addresses: list[AddressItem] | None = None
    visibility: Visibility | None = None
    group_id: int | None = None
    linked_user_id: int | None = None
    tags: list[str] | None = None


class ContactOut(ContactBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int
    latitude: float | None = None
    longitude: float | None = None
    nextcloud_uid: str | None = None
    last_synced_at: datetime | None = None
    dirty: bool = False
    tags: list[TagOut] = Field(default_factory=list)
