"""Authentication endpoints: local accounts plus optional Authentik OIDC."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.cookies import clear_auth_cookies, set_auth_cookies
from app.auth.crypto import encrypt
from app.auth.deps import get_current_user
from app.auth.security import (
    REFRESH_TOKEN_COOKIE,
    decode_token,
    generate_api_token,
    hash_api_token,
    hash_password,
    verify_password,
)
from app.config import settings
from app.db import get_session
from app.models import ApiToken, Contact, Group, GroupMembership, User
from app.schemas.auth import (
    ApiTokenCreatedOut,
    ApiTokenCreateIn,
    ApiTokenOut,
    AuthConfigOut,
    LoginIn,
    MeOut,
    NextcloudSettingsIn,
    PreferencesIn,
    RegisterIn,
    SelfContactIn,
    UserOut,
)
from app.services.nextcloud_accounts import user_has_nextcloud
from app.visibility import visibility_filter

router = APIRouter(prefix="/auth", tags=["auth"])


async def _is_first_user(session: AsyncSession) -> bool:
    return (await session.scalar(select(func.count(User.id)))) == 0


async def _group_names(session: AsyncSession, user: User) -> list[str]:
    rows = await session.scalars(
        select(Group.name)
        .join(GroupMembership, GroupMembership.group_id == Group.id)
        .where(GroupMembership.user_id == user.id)
        .order_by(Group.name)
    )
    return list(rows.all())


async def build_me(session: AsyncSession, user: User) -> MeOut:
    return MeOut(
        user=UserOut.model_validate(user),
        groups=await _group_names(session, user),
        self_contact_id=user.self_contact_id,
        default_currency=user.default_currency,
        phone_country_code=user.phone_country_code,
        phone_number_format=user.phone_number_format,
        nextcloud_configured=user_has_nextcloud(user),
        nextcloud_url=user.nextcloud_url,
        nextcloud_username=user.nextcloud_username,
        nextcloud_addressbook=user.nextcloud_addressbook,
        nextcloud_calendar=user.nextcloud_calendar,
    )


async def _sync_groups_from_claim(session: AsyncSession, user: User, claim: list[str]) -> None:
    """Reconcile Authentik group claims into Prism Group memberships.

    Unknown groups are auto-created (keyed by `oidc_group`) so Authentik remains
    the single place groups are defined. Membership in `oidc_admin_group` grants
    Prism admin.
    """
    for name in claim:
        group = await session.scalar(select(Group).where(Group.oidc_group == name))
        if group is None:
            group = Group(name=name, oidc_group=name)
            session.add(group)
            await session.flush()
        exists = await session.scalar(
            select(GroupMembership).where(
                GroupMembership.user_id == user.id, GroupMembership.group_id == group.id
            )
        )
        if exists is None:
            session.add(GroupMembership(user_id=user.id, group_id=group.id))
    if settings.oidc_admin_group and settings.oidc_admin_group in claim:
        user.is_superuser = True


@router.get("/config", response_model=AuthConfigOut)
async def auth_config() -> AuthConfigOut:
    return AuthConfigOut(
        allow_registration=settings.allow_registration,
        oidc_enabled=settings.oidc_enabled,
        oidc_display_name=settings.oidc_display_name,
    )


@router.post("/register", response_model=MeOut)
async def register(
    payload: RegisterIn, response: Response, session: AsyncSession = Depends(get_session)
) -> MeOut:
    first = await _is_first_user(session)
    if not settings.allow_registration and not first:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Self-registration is disabled")
    existing = await session.scalar(select(User).where(User.email == payload.email.lower()))
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    user = User(
        email=payload.email.lower(),
        display_name=payload.display_name,
        hashed_password=hash_password(payload.password),
        is_superuser=first,  # the first account bootstraps the admin
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    set_auth_cookies(response, user.id)
    return await build_me(session, user)


@router.post("/login", response_model=MeOut)
async def login(
    payload: LoginIn, response: Response, session: AsyncSession = Depends(get_session)
) -> MeOut:
    user = await session.scalar(select(User).where(User.email == payload.email.lower()))
    if (
        user is None
        or not user.hashed_password
        or not verify_password(payload.password, user.hashed_password)
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account is disabled")
    set_auth_cookies(response, user.id)
    return await build_me(session, user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> Response:
    clear_auth_cookies(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.post("/refresh", response_model=MeOut)
async def refresh(
    request: Request, response: Response, session: AsyncSession = Depends(get_session)
) -> MeOut:
    token = request.cookies.get(REFRESH_TOKEN_COOKIE)
    user_id = decode_token(token, "refresh") if token else None
    if user_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")
    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    set_auth_cookies(response, user.id)
    return await build_me(session, user)


@router.get("/me", response_model=MeOut)
async def me(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
) -> MeOut:
    return await build_me(session, user)


@router.put("/self-contact", response_model=MeOut)
async def set_self_contact(
    payload: SelfContactIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> MeOut:
    """Designate which contact represents the current user (their "me")."""
    if payload.contact_id is not None:
        filt = await visibility_filter(session, user, Contact)
        visible = await session.scalar(
            select(Contact.id).where(Contact.id == payload.contact_id, filt)
        )
        if visible is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Contact not found")
    user.self_contact_id = payload.contact_id
    await session.commit()
    await session.refresh(user)
    return await build_me(session, user)


@router.put("/preferences", response_model=MeOut)
async def set_preferences(
    payload: PreferencesIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> MeOut:
    if payload.default_currency is not None:
        user.default_currency = payload.default_currency.upper() or "CHF"
    if payload.phone_country_code is not None:
        user.phone_country_code = payload.phone_country_code
    if payload.phone_number_format is not None:
        user.phone_number_format = payload.phone_number_format
    await session.commit()
    await session.refresh(user)
    return await build_me(session, user)


@router.put("/nextcloud", response_model=MeOut)
async def set_nextcloud(
    payload: NextcloudSettingsIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> MeOut:
    """Set the current user's personal Nextcloud account. The app password is
    encrypted at rest; send an empty string to clear it."""
    if payload.nextcloud_url is not None:
        user.nextcloud_url = payload.nextcloud_url.strip() or None
    if payload.nextcloud_username is not None:
        user.nextcloud_username = payload.nextcloud_username.strip() or None
    if payload.nextcloud_app_password is not None:
        pw = payload.nextcloud_app_password.strip()
        user.nextcloud_app_password_enc = encrypt(pw) if pw else None
    if payload.nextcloud_addressbook is not None:
        user.nextcloud_addressbook = payload.nextcloud_addressbook.strip() or None
    if payload.nextcloud_calendar is not None:
        user.nextcloud_calendar = payload.nextcloud_calendar.strip() or None
    await session.commit()
    await session.refresh(user)
    return await build_me(session, user)


# --- Personal API tokens (for CalDAV / mobile clients) ----------------------


@router.get("/tokens", response_model=list[ApiTokenOut])
async def list_tokens(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
) -> list[ApiToken]:
    rows = await session.scalars(
        select(ApiToken).where(ApiToken.user_id == user.id).order_by(ApiToken.id)
    )
    return list(rows.all())


@router.post("/tokens", response_model=ApiTokenCreatedOut, status_code=status.HTTP_201_CREATED)
async def create_token(
    payload: ApiTokenCreateIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ApiTokenCreatedOut:
    plaintext, prefix = generate_api_token()
    token = ApiToken(
        user_id=user.id, name=payload.name, token_hash=hash_api_token(plaintext), prefix=prefix
    )
    session.add(token)
    await session.commit()
    await session.refresh(token)
    return ApiTokenCreatedOut(
        id=token.id, name=token.name, prefix=token.prefix, last_used_at=None, token=plaintext
    )


@router.delete("/tokens/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_token(
    token_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    token = await session.get(ApiToken, token_id)
    if token is None or token.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Token not found")
    await session.delete(token)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- OIDC (Authentik) -------------------------------------------------------


@router.get("/oidc/login")
async def oidc_login(request: Request):
    if not settings.oidc_enabled:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "OIDC is not enabled")
    from app.auth.oidc import get_oauth

    oauth = get_oauth()
    return await oauth.authentik.authorize_redirect(request, settings.oidc_redirect_url)


@router.get("/oidc/callback")
async def oidc_callback(request: Request, session: AsyncSession = Depends(get_session)):
    if not settings.oidc_enabled:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "OIDC is not enabled")
    from app.auth.oidc import get_oauth

    oauth = get_oauth()
    try:
        token = await oauth.authentik.authorize_access_token(request)
    except Exception as exc:  # noqa: BLE001 - surface provider errors as 400
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"OIDC exchange failed: {exc}") from exc

    userinfo = token.get("userinfo") or {}
    subject = userinfo.get("sub")
    email = (userinfo.get("email") or "").lower() or None
    name = userinfo.get("name") or userinfo.get("preferred_username") or email or "User"
    groups_claim = userinfo.get("groups") or []
    if not subject:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "OIDC response missing subject")

    user = await session.scalar(select(User).where(User.oidc_subject == subject))
    if user is None and email:
        user = await session.scalar(select(User).where(User.email == email))
        if user is not None:
            user.oidc_subject = subject  # link an existing local account
    if user is None:
        user = User(
            email=email or f"{subject}@oidc.local",
            display_name=name,
            oidc_subject=subject,
            is_superuser=await _is_first_user(session),
        )
        session.add(user)
        await session.flush()

    await _sync_groups_from_claim(session, user, groups_claim)
    await session.commit()
    await session.refresh(user)

    redirect = RedirectResponse(url=settings.public_url or "/")
    set_auth_cookies(redirect, user.id)
    return redirect
