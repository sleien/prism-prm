"""Contacts — a local mirror of Nextcloud's CardDAV address book.

Nextcloud is the source of truth. Each row carries the vCard UID and the last
seen ETag/href so the sync engine can correlate, detect remote changes, and
write edits back. The full vCard is retained so unknown properties survive a
round-trip.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.constants import Visibility
from app.db import Base, JSONType, TimestampMixin

if TYPE_CHECKING:
    from app.models.tag import Tag


class Contact(Base, TimestampMixin):
    __tablename__ = "contact"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)

    # Visibility — new contacts are public by default.
    visibility: Mapped[str] = mapped_column(
        String(20), default=Visibility.PUBLIC, nullable=False
    )
    # Set when visibility == GROUP.
    group_id: Mapped[int | None] = mapped_column(
        ForeignKey("group.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Optionally link this contact to a registered Prism user, so that user gets
    # attendee-based visibility of events this contact is invited to.
    linked_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # --- Nextcloud / CardDAV correlation ---
    nextcloud_uid: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    nextcloud_href: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    etag: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # True while a local edit has not yet been pushed back to Nextcloud.
    dirty: Mapped[bool] = mapped_column(default=False, nullable=False)
    # Full vCard text, so properties Prism does not model survive a round-trip.
    vcard_raw: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Parsed fields (denormalized from the vCard for display & search) ---
    display_name: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    first_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # vCard N "additional names" component (between given and family names).
    middle_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    organization: Mapped[str | None] = mapped_column(String(300), nullable=True)
    job_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    birthday: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # "male" | "female" | "other"; NULL = unspecified. Drives gendered
    # relationship labels (e.g. a male "Parent" reads "Father").
    gender: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Telegram username/handle (stored without a leading @).
    telegram: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Geocoded from the primary address (for the map widget).
    latitude: Mapped[float | None] = mapped_column(nullable=True)
    longitude: Mapped[float | None] = mapped_column(nullable=True)

    # Lists of {"type": ..., "value": ...} objects.
    emails: Mapped[list] = mapped_column(JSONType, default=list, nullable=False)
    phones: Mapped[list] = mapped_column(JSONType, default=list, nullable=False)
    addresses: Mapped[list] = mapped_column(JSONType, default=list, nullable=False)
    # User-defined extra fields.
    custom_fields: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)

    # Owner-defined tags, via the contact_tag association. Read-only: the API
    # writes the association rows directly (so it never fights the unit of work),
    # and this eager-loaded (selectin is async-safe) view is just for serializing.
    tags: Mapped[list[Tag]] = relationship(
        secondary="contact_tag", lazy="selectin", order_by="Tag.name", viewonly=True
    )
