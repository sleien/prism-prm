"""Users, groups, partner designations, and API tokens.

Visibility tiers are built on these primitives:
- PUBLIC  -> every active user
- GROUP   -> members of a Group (and, for events, the attendee users)
- PRIVATE -> the owner plus their designated partners (Partnership rows)
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    # Null for users that authenticate exclusively through OIDC.
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Subject claim from the OIDC provider (Authentik), if linked.
    oidc_subject: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Which contact represents this user ("me" in relationships). Soft reference
    # (no FK) to avoid a user<->contact dependency cycle; existence is checked
    # at the app layer.
    self_contact_id: Mapped[int | None] = mapped_column(nullable=True)


class Group(Base, TimestampMixin):
    """A named circle of users. Optionally mapped to an Authentik group so that
    membership is synced from the OIDC `groups` claim at login."""

    __tablename__ = "group"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # If set, members of this Authentik group are added to this group at login.
    oidc_group: Mapped[str | None] = mapped_column(String(200), unique=True, nullable=True)

    memberships: Mapped[list[GroupMembership]] = relationship(
        back_populates="group", cascade="all, delete-orphan"
    )


class GroupMembership(Base, TimestampMixin):
    __tablename__ = "group_membership"
    __table_args__ = (UniqueConstraint("user_id", "group_id", name="uq_group_membership"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("group.id", ondelete="CASCADE"), index=True)

    group: Mapped[Group] = relationship(back_populates="memberships")


class Partnership(Base, TimestampMixin):
    """Directed designation: `owner` grants `partner` visibility of their PRIVATE
    records. Make it mutual by creating the reverse row too."""

    __tablename__ = "partnership"
    __table_args__ = (UniqueConstraint("owner_id", "partner_id", name="uq_partnership"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    partner_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)


class ApiToken(Base, TimestampMixin):
    """A personal access token for programmatic / CalDAV-client use. Only the
    SHA-256 hash is stored; the plaintext is shown once at creation."""

    __tablename__ = "api_token"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
