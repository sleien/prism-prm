"""Shared enums and constants (leaf module — imports no app code)."""

from __future__ import annotations

from enum import StrEnum


class Visibility(StrEnum):
    """Who may see a record.

    - PUBLIC: every authenticated Prism user.
    - GROUP: members of the record's designated group (for events, the attendees).
    - PRIVATE: the owner plus the partners they have designated.
    """

    PUBLIC = "public"
    GROUP = "group"
    PRIVATE = "private"


class Gender(StrEnum):
    """A contact's gender. NULL (unset) means unspecified."""

    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


class Cadence(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"


class ReminderChannel(StrEnum):
    IN_APP = "in_app"
    EMAIL = "email"
    CALDAV = "caldav"  # written into the Nextcloud calendar as a VALARM


# vCard/iCalendar property used to correlate a Prism row with its Nextcloud object.
UID_PROPERTY = "UID"
