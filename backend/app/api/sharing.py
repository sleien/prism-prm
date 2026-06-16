"""Sharing management: users directory, partner designations, and groups.

These power the visibility tiers — PRIVATE records are visible to designated
partners; GROUP records to members of the chosen group.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.db import get_session
from app.models import Group, GroupMembership, Partnership, User
from app.schemas.auth import UserOut
from app.schemas.sharing import GroupCreate, GroupOut

router = APIRouter(tags=["sharing"])


# --- users directory --------------------------------------------------------


@router.get("/users", response_model=list[UserOut])
async def list_users(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
) -> list[User]:
    rows = await session.scalars(
        select(User).where(User.is_active.is_(True)).order_by(User.display_name)
    )
    return list(rows.all())


# --- partner designations ---------------------------------------------------


@router.get("/sharing/partners", response_model=list[UserOut])
async def list_partners(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
) -> list[User]:
    rows = await session.scalars(
        select(User)
        .join(Partnership, Partnership.partner_id == User.id)
        .where(Partnership.owner_id == user.id)
        .order_by(User.display_name)
    )
    return list(rows.all())


@router.put("/sharing/partners/{partner_id}", status_code=status.HTTP_204_NO_CONTENT)
async def add_partner(
    partner_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    if partner_id == user.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot partner with yourself")
    if await session.get(User, partner_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    exists = await session.scalar(
        select(Partnership).where(
            Partnership.owner_id == user.id, Partnership.partner_id == partner_id
        )
    )
    if exists is None:
        session.add(Partnership(owner_id=user.id, partner_id=partner_id))
        await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/sharing/partners/{partner_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_partner(
    partner_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    row = await session.scalar(
        select(Partnership).where(
            Partnership.owner_id == user.id, Partnership.partner_id == partner_id
        )
    )
    if row is not None:
        await session.delete(row)
        await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- groups -----------------------------------------------------------------


async def _member_ids(session: AsyncSession, group_id: int) -> list[int]:
    rows = await session.scalars(
        select(GroupMembership.user_id).where(GroupMembership.group_id == group_id)
    )
    return list(rows.all())


@router.get("/groups", response_model=list[GroupOut])
async def list_groups(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
) -> list[Group]:
    """Groups the user belongs to."""
    rows = await session.scalars(
        select(Group)
        .join(GroupMembership, GroupMembership.group_id == Group.id)
        .where(GroupMembership.user_id == user.id)
        .order_by(Group.name)
    )
    return list(rows.all())


@router.post("/groups", response_model=GroupOut, status_code=status.HTTP_201_CREATED)
async def create_group(
    payload: GroupCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Group:
    group = Group(name=payload.name, description=payload.description)
    session.add(group)
    await session.flush()
    session.add(GroupMembership(user_id=user.id, group_id=group.id))  # creator joins
    await session.commit()
    await session.refresh(group)
    return group


@router.get("/groups/{group_id}/members", response_model=list[UserOut])
async def group_members(
    group_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[User]:
    ids = await _member_ids(session, group_id)
    if user.id not in ids and not user.is_superuser:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not a member of this group")
    rows = await session.scalars(select(User).where(User.id.in_(ids)).order_by(User.display_name))
    return list(rows.all())


@router.put("/groups/{group_id}/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def add_member(
    group_id: int,
    member_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    if user.id not in await _member_ids(session, group_id) and not user.is_superuser:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not a member of this group")
    if await session.get(User, member_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    exists = await session.scalar(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id, GroupMembership.user_id == member_id
        )
    )
    if exists is None:
        session.add(GroupMembership(user_id=member_id, group_id=group_id))
        await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/groups/{group_id}/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    group_id: int,
    member_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    if user.id not in await _member_ids(session, group_id) and not user.is_superuser:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not a member of this group")
    row = await session.scalar(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id, GroupMembership.user_id == member_id
        )
    )
    if row is not None:
        await session.delete(row)
        await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
