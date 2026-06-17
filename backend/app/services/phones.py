"""Format phone numbers to a user's preferred pattern.

The user stores a country code (e.g. "+41") and a digit-group mask. The mask may
parenthesize the national trunk prefix, e.g. "(x)xx xxx xx xx": that "(0)" is
shown in the national form ("079 336 08 02") but dropped when the country code
is prepended ("+41 79 336 08 02"). Whether the country code is prepended is a
per-user toggle. Foreign numbers (a different country code) are only de-spaced.
"""

from __future__ import annotations

import re


def _segments(mask: str) -> tuple[int, list[int], list[int]]:
    """Parse a mask into (trunk_len, national_groups, intl_groups).

    "(x)xx xxx xx xx" -> trunk_len=1, national=[3,3,2,2] (trunk merged into the
    first group), intl=[2,3,2,2] (trunk dropped). A mask without parens has
    trunk_len 0 and identical national/intl groupings.
    """
    trunk_len = sum(len(x) for x in re.findall(r"\(\s*(x+)\s*\)", mask, flags=re.IGNORECASE))
    national_groups = [len(g) for g in re.findall(r"x+", re.sub(r"[()]", "", mask), re.IGNORECASE)]
    intl_groups = [len(g) for g in re.findall(r"x+", re.sub(r"\([^)]*\)", "", mask), re.IGNORECASE)]
    return trunk_len, national_groups, intl_groups


def _apply(digits: str, groups: list[int]) -> str:
    out, i = [], 0
    for g in groups:
        out.append(digits[i : i + g])
        i += g
    return " ".join(out)


def format_phone(
    raw: str, country_code: str, mask: str, include_country_code: bool = False
) -> str:
    """Return `raw` regrouped to `mask` when it's a home-country number.

    Home-country numbers (written +CC…, 00CC…, or national 0…) are reduced to
    their national-with-trunk form. With `include_country_code` they render as
    "<country_code> <national significant number>" (trunk dropped); otherwise as
    the national form. Foreign numbers / length mismatches are returned with
    whitespace collapsed but otherwise unchanged.
    """
    if not raw or not raw.strip():
        return ""
    value = raw.strip()
    cc = re.sub(r"\D", "", country_code or "")
    digits = re.sub(r"\D", "", value)

    national: str | None = None
    if value.startswith("+"):
        if cc and digits.startswith(cc):  # +CC… (foreign +xx stays None)
            national = "0" + digits[len(cc):]
    elif digits.startswith("00"):
        body = digits[2:]
        if cc and body.startswith(cc):  # 00CC…
            national = "0" + body[len(cc):]
    elif digits.startswith("0"):  # already national
        national = digits

    trunk_len, national_groups, intl_groups = _segments(mask)
    if national and national_groups and len(national) == sum(national_groups):
        if (
            include_country_code
            and country_code
            and intl_groups
            and len(national) - trunk_len == sum(intl_groups)
        ):
            return f"{country_code} {_apply(national[trunk_len:], intl_groups)}"
        return _apply(national, national_groups)

    # Foreign number, short code, or length mismatch — just collapse whitespace.
    return re.sub(r"\s+", " ", value).strip()


def format_phones(
    items: list[dict], country_code: str, mask: str, include_country_code: bool = False
) -> list[dict]:
    """Apply `format_phone` to the `value` of each {type, value} dict."""
    return [
        {**it, "value": format_phone(it.get("value", ""), country_code, mask, include_country_code)}
        for it in items
    ]
