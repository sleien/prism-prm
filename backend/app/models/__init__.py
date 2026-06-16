"""ORM models. Importing this package registers every table on Base.metadata."""

from app.models.contact import Contact
from app.models.enrichment import (
    ContactLifeEvent,
    ContactRelationship,
    LifeEventType,
    RelationshipType,
)
from app.models.event import Event, EventAttendee, Reminder
from app.models.journal import JournalEntry, JournalTemplate
from app.models.user import ApiToken, Group, GroupMembership, Partnership, User

__all__ = [
    "ApiToken",
    "Contact",
    "ContactLifeEvent",
    "ContactRelationship",
    "Event",
    "EventAttendee",
    "Group",
    "GroupMembership",
    "JournalEntry",
    "JournalTemplate",
    "LifeEventType",
    "Partnership",
    "RelationshipType",
    "Reminder",
    "User",
]
