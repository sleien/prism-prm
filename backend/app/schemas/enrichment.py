"""Schemas for relationships, life events, and their per-user type catalogs."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


# --- relationship types ---
class RelationshipTypeIn(BaseModel):
    name: str = Field(max_length=80)
    reverse_name: str | None = Field(default=None, max_length=80)
    name_male: str | None = Field(default=None, max_length=80)
    name_female: str | None = Field(default=None, max_length=80)
    reverse_name_male: str | None = Field(default=None, max_length=80)
    reverse_name_female: str | None = Field(default=None, max_length=80)


class RelationshipTypeUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=80)
    reverse_name: str | None = Field(default=None, max_length=80)
    name_male: str | None = Field(default=None, max_length=80)
    name_female: str | None = Field(default=None, max_length=80)
    reverse_name_male: str | None = Field(default=None, max_length=80)
    reverse_name_female: str | None = Field(default=None, max_length=80)


class RelationshipTypeOut(RelationshipTypeIn):
    model_config = ConfigDict(from_attributes=True)

    id: int


# --- relationships ---
class RelationshipCreate(BaseModel):
    from_contact_id: int
    to_contact_id: int
    type_id: int


class RelatedContactOut(BaseModel):
    """One relationship as seen from a given contact's perspective."""

    relationship_id: int  # 0 for derived (auto) relationships
    contact_id: int  # the other person
    contact_name: str
    label: str  # how the other person relates to the viewed contact
    derived: bool = False  # inferred (e.g. grandparent via two parent links), not stored


# --- life-event types ---
class LifeEventTypeIn(BaseModel):
    name: str = Field(max_length=120)
    emoji: str | None = Field(default=None, max_length=16)


class LifeEventTypeOut(LifeEventTypeIn):
    model_config = ConfigDict(from_attributes=True)

    id: int


# --- event types ---
class EventTypeIn(BaseModel):
    name: str = Field(max_length=80)
    emoji: str | None = Field(default=None, max_length=16)


class EventTypeOut(EventTypeIn):
    model_config = ConfigDict(from_attributes=True)

    id: int


# --- tags ---
class TagIn(BaseModel):
    name: str = Field(max_length=80)
    color: str | None = Field(default=None, max_length=20)


class TagUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=80)
    color: str | None = Field(default=None, max_length=20)


class TagCatalogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    color: str | None = None
    count: int = 0


# --- life events ---
class LifeEventCreate(BaseModel):
    contact_id: int
    title: str = Field(max_length=120)
    emoji: str | None = Field(default=None, max_length=16)
    happened_on: date | None = None
    note: str | None = None


class LifeEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    contact_id: int
    title: str
    emoji: str | None = None
    happened_on: date | None = None
    note: str | None = None
