"""Async CardDAV / CalDAV client for Nextcloud (and any RFC 4791/6352 server).

Rather than hardcoding Nextcloud's URL layout, this performs standard DAV
discovery (`.well-known` -> current-user-principal -> *-home-set -> collection),
so it works unchanged against the Radicale server used in tests.

Concurrency: built on httpx.AsyncClient. ETags are surfaced on every read so the
sync engine can do optimistic concurrency (If-Match / If-None-Match) on writes.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree as ET

import httpx

from app.config import settings

# XML namespaces used in DAV responses.
NS = {
    "d": "DAV:",
    "card": "urn:ietf:params:xml:ns:carddav",
    "cal": "urn:ietf:params:xml:ns:caldav",
}
_DAV = "{DAV:}"
_CARD = "{urn:ietf:params:xml:ns:carddav}"
_CAL = "{urn:ietf:params:xml:ns:caldav}"

VCARD_CONTENT_TYPE = "text/vcard; charset=utf-8"
ICAL_CONTENT_TYPE = "text/calendar; charset=utf-8"


class DavError(RuntimeError):
    """Raised when a DAV request fails or returns an unexpected status."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


@dataclass(slots=True)
class DavObject:
    """A resource within a collection. `data` is populated by reads, not listings."""

    href: str  # server-relative path
    etag: str | None = None
    data: str | None = None
    content_type: str | None = None


class NextcloudClient:
    """Thin async DAV client. Use as an async context manager."""

    def __init__(self, base_url: str, username: str, password: str) -> None:
        self.base_url = base_url.rstrip("/")
        origin = urlparse(self.base_url)
        self.origin = f"{origin.scheme}://{origin.netloc}"
        self._client = httpx.AsyncClient(
            auth=(username, password),
            follow_redirects=True,
            timeout=httpx.Timeout(30.0),
            headers={"User-Agent": "Prism-PRM/0.1 (+https://github.com/sleien/prism-prm)"},
        )

    @classmethod
    def from_settings(cls) -> NextcloudClient:
        if not settings.nextcloud_configured:
            raise DavError("Nextcloud is not configured (set NEXTCLOUD_* env vars).")
        return cls(
            settings.nextcloud_url,  # type: ignore[arg-type]
            settings.nextcloud_username,  # type: ignore[arg-type]
            settings.nextcloud_app_password,  # type: ignore[arg-type]
        )

    async def __aenter__(self) -> NextcloudClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self._client.aclose()

    # -- low-level ----------------------------------------------------------

    def _abs(self, href: str) -> str:
        """Resolve a (possibly server-relative) href to a full URL."""
        if href.startswith("http://") or href.startswith("https://"):
            return href
        return urljoin(self.origin + "/", href.lstrip("/"))

    async def _propfind(self, url: str, body: str, depth: str = "0") -> list[ET.Element]:
        resp = await self._client.request(
            "PROPFIND",
            url,
            content=body.encode(),
            headers={"Depth": depth, "Content-Type": "application/xml; charset=utf-8"},
        )
        if resp.status_code not in (207, 200):
            raise DavError(f"PROPFIND {url} -> {resp.status_code}", resp.status_code)
        root = ET.fromstring(resp.text)
        return root.findall(f"{_DAV}response")

    @staticmethod
    def _href_of(response: ET.Element) -> str | None:
        el = response.find(f"{_DAV}href")
        return el.text if el is not None and el.text else None

    @staticmethod
    def _ok_propstat(response: ET.Element) -> ET.Element | None:
        """Return the <prop> from the 200 propstat of a response, if any."""
        for propstat in response.findall(f"{_DAV}propstat"):
            status = propstat.findtext(f"{_DAV}status") or ""
            if "200" in status:
                return propstat.find(f"{_DAV}prop")
        # Some servers omit status; fall back to the first prop.
        ps = response.find(f"{_DAV}propstat")
        return ps.find(f"{_DAV}prop") if ps is not None else None

    # -- discovery ----------------------------------------------------------

    async def _current_user_principal(self, kind: str) -> str:
        """Find the principal URL via .well-known/{carddav,caldav}."""
        body = (
            '<d:propfind xmlns:d="DAV:"><d:prop>'
            "<d:current-user-principal/></d:prop></d:propfind>"
        )
        start = f"{self.origin}/.well-known/{kind}"
        try:
            responses = await self._propfind(start, body, depth="0")
        except DavError:
            # Fall back to the configured base URL if .well-known is unavailable.
            responses = await self._propfind(self.base_url + "/", body, depth="0")
        for response in responses:
            prop = self._ok_propstat(response)
            if prop is None:
                continue
            cup = prop.find(f"{_DAV}current-user-principal")
            if cup is not None:
                href = cup.findtext(f"{_DAV}href")
                if href:
                    return self._abs(href)
        raise DavError("Could not resolve current-user-principal")

    async def _home_set(self, kind: str) -> str:
        principal = await self._current_user_principal(kind)
        prop_name = "addressbook-home-set" if kind == "carddav" else "calendar-home-set"
        ns = "card" if kind == "carddav" else "cal"
        body = (
            f'<d:propfind xmlns:d="DAV:" xmlns:{ns}="{NS[ns]}">'
            f"<d:prop><{ns}:{prop_name}/></d:prop></d:propfind>"
        )
        responses = await self._propfind(principal, body, depth="0")
        tag = (_CARD if kind == "carddav" else _CAL) + prop_name
        for response in responses:
            prop = self._ok_propstat(response)
            if prop is None:
                continue
            home = prop.find(tag)
            if home is not None:
                href = home.findtext(f"{_DAV}href")
                if href:
                    return self._abs(href)
        raise DavError(f"Could not resolve {prop_name}")

    async def discover_collection(self, kind: str, name: str) -> str:
        """Return the full URL of the address book / calendar called `name`.

        Matches on the trailing path segment first, then on display name; falls
        back to the first collection of the right resource type.
        """
        home = await self._home_set(kind)
        body = (
            '<d:propfind xmlns:d="DAV:"><d:prop>'
            "<d:resourcetype/><d:displayname/></d:prop></d:propfind>"
        )
        responses = await self._propfind(home, body, depth="1")
        rtype_tag = (_CARD + "addressbook") if kind == "carddav" else (_CAL + "calendar")
        fallback: str | None = None
        for response in responses:
            href = self._href_of(response)
            prop = self._ok_propstat(response)
            if not href or prop is None:
                continue
            resourcetype = prop.find(f"{_DAV}resourcetype")
            if resourcetype is None or resourcetype.find(rtype_tag) is None:
                continue
            full = self._abs(href)
            fallback = fallback or full
            segment = href.rstrip("/").rsplit("/", 1)[-1]
            displayname = prop.findtext(f"{_DAV}displayname") or ""
            if segment == name or displayname == name:
                return full
        if fallback:
            return fallback
        raise DavError(f"No {kind} collection found (looked for '{name}')")

    # -- collection contents ------------------------------------------------

    async def list_objects(self, collection_url: str) -> list[DavObject]:
        """List the resources (with ETags) in a collection. Does not fetch bodies."""
        body = (
            '<d:propfind xmlns:d="DAV:"><d:prop>'
            "<d:getetag/><d:getcontenttype/><d:resourcetype/></d:prop></d:propfind>"
        )
        responses = await self._propfind(collection_url, body, depth="1")
        collection_path = urlparse(collection_url).path.rstrip("/")
        objects: list[DavObject] = []
        for response in responses:
            href = self._href_of(response)
            if not href:
                continue
            # Skip the collection itself.
            if urlparse(self._abs(href)).path.rstrip("/") == collection_path:
                continue
            prop = self._ok_propstat(response)
            if prop is None:
                continue
            resourcetype = prop.find(f"{_DAV}resourcetype")
            if resourcetype is not None and resourcetype.find(f"{_DAV}collection") is not None:
                continue  # nested collection, not a resource
            etag = prop.findtext(f"{_DAV}getetag")
            ctype = prop.findtext(f"{_DAV}getcontenttype")
            objects.append(DavObject(href=href, etag=etag, content_type=ctype))
        return objects

    async def get_object(self, href: str) -> DavObject:
        url = self._abs(href)
        resp = await self._client.get(url)
        if resp.status_code != 200:
            raise DavError(f"GET {url} -> {resp.status_code}", resp.status_code)
        return DavObject(
            href=href,
            etag=resp.headers.get("etag"),
            data=resp.text,
            content_type=resp.headers.get("content-type"),
        )

    async def put_object(
        self, href: str, data: str, content_type: str, etag: str | None = None
    ) -> str | None:
        """Create or update a resource.

        - new resource: pass etag=None -> sent with If-None-Match: * (fails 412 if it exists)
        - update: pass the known etag -> sent with If-Match (fails 412 on remote change)
        Returns the new ETag if the server provides one.
        """
        url = self._abs(href)
        headers = {"Content-Type": content_type}
        if etag:
            headers["If-Match"] = etag
        else:
            headers["If-None-Match"] = "*"
        resp = await self._client.put(url, content=data.encode(), headers=headers)
        if resp.status_code == 412:
            raise DavError(f"PUT {url} precondition failed (concurrent change)", 412)
        if resp.status_code not in (200, 201, 204):
            raise DavError(f"PUT {url} -> {resp.status_code}", resp.status_code)
        new_etag = resp.headers.get("etag")
        if not new_etag:
            # Some servers (incl. Nextcloud) omit the ETag on PUT; re-read it.
            try:
                new_etag = (await self.get_object(href)).etag
            except DavError:
                new_etag = None
        return new_etag

    async def delete_object(self, href: str, etag: str | None = None) -> None:
        url = self._abs(href)
        headers = {"If-Match": etag} if etag else {}
        resp = await self._client.delete(url, headers=headers)
        # 404 means it is already gone, which satisfies the intent.
        if resp.status_code not in (200, 204, 404):
            raise DavError(f"DELETE {url} -> {resp.status_code}", resp.status_code)

    # -- convenience --------------------------------------------------------

    async def addressbook_url(self) -> str:
        return await self.discover_collection("carddav", settings.nextcloud_addressbook)

    async def calendar_url(self) -> str:
        return await self.discover_collection("caldav", settings.nextcloud_calendar)
