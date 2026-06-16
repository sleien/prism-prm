"""Query-layer enforcement of the public / group / private visibility tiers.

Every list/read query for an owned, visibility-bearing model is filtered through
`visibility_filter`, so a user can never see rows they are not entitled to —
regardless of what the UI requests. Defense-in-depth (PostgreSQL RLS) is layered
on top in a later phase.
"""

from __future__ import annotations

from sqlalchemy import ColumnElement, and_, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import Visibility
from app.models import GroupMembership, Partnership, User


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
    """
    if user.is_superuser:
        return true()

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
