"""Query-layer enforcement of the public / group / private visibility tiers.

Every list/read query for an owned, visibility-bearing model is filtered through
`visibility_filter`, so a user can never see rows they are not entitled to —
regardless of what the UI requests. Defense-in-depth (PostgreSQL RLS) is layered
on top in a later phase.
"""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import ColumnElement, and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import Visibility
from app.models import Event, EventAttendee, GroupMembership, Partnership, User


async def user_group_ids(session: AsyncSession, user: User) -> list[int]:
    rows = await session.scalars(
        select(GroupMembership.group_id).where(GroupMembership.user_id == user.id)
    )
    return list(rows.all())


async def partner_of_owner_ids(session: AsyncSession, user: User) -> list[int]:
    """Owner ids who have designated this user as a partner (granting them view
    of the owner's PRIVATE records)."""
    rows = await session.scalars(
        select(Partnership.owner_id).where(Partnership.partner_id == user.id)
    )
    return list(rows.all())


async def visibility_filter(session: AsyncSession, user: User, model) -> ColumnElement[bool]:
    """Build a WHERE clause selecting only rows of `model` visible to `user`.

    `model` must expose `owner_id`, `visibility`, and `group_id` columns.

    Admins are NOT exempt: the private tier protects every user's data, including
    from the instance admin (consistent with how journals are owner-scoped).
    """
    conditions: list[ColumnElement[bool]] = [
        model.owner_id == user.id,
        model.visibility == Visibility.PUBLIC,
    ]

    group_ids = await user_group_ids(session, user)
    if group_ids:
        conditions.append(
            and_(model.visibility == Visibility.GROUP, model.group_id.in_(group_ids))
        )

    owner_ids = await partner_of_owner_ids(session, user)
    if owner_ids:
        conditions.append(
            and_(model.visibility == Visibility.PRIVATE, model.owner_id.in_(owner_ids))
        )

    return or_(*conditions)


async def event_visibility_filter(session: AsyncSession, user: User) -> ColumnElement[bool]:
    """Event visibility, plus: anyone who attends an event may see it.

    This realizes the "group = all that attended" tier — an attendee linked to a
    Prism user (matched by email when the event was created) can see the event
    regardless of its base visibility.
    """
    base = await visibility_filter(session, user, Event)
    # An attendee linked to a Prism user can see the event regardless of its
    # visibility — that linkage is set deliberately (a contact is explicitly
    # connected to a user), so it's intentional sharing, e.g. a partner inviting
    # you to their otherwise-private event.
    attended = select(EventAttendee.event_id).where(EventAttendee.user_id == user.id)
    return or_(base, Event.id.in_(attended))


async def validate_group_choice(
    session: AsyncSession,
    user: User,
    visibility: str,
    group_id: int | None,
    *,
    require_group: bool = True,
) -> None:
    """Validate the group target on a record.

    Any provided group_id must reference a group the user belongs to (prevents
    FK-violation 500s and stops a non-member from targeting another group). When
    no group is chosen, contacts require one for GROUP visibility, while events
    pass `require_group=False` because their GROUP tier means "all who attend".
    """
    if group_id is not None:
        if group_id not in await user_group_ids(session, user):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You are not a member of that group")
        return
    if visibility == Visibility.GROUP and require_group:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "A group is required for group visibility")
