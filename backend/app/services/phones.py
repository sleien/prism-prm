"""Format phone numbers to a user's preferred pattern.

The user stores a country code (e.g. "+41") and a digit-group mask
(e.g. "xxx xxx xx xx"). We normalize home-country numbers to that mask, ignoring
however they were originally spaced. Foreign numbers (a different country code)
are only de-spaced, never forced into the home mask.
"""

from __future__ import annotations

import re


def _mask_groups(mask: str) -> list[int]:
    """"xxx xxx xx xx" -> [3, 3, 2, 2]. Non-x runs are ignored as separators."""
    return [len(g) for g in re.findall(r"x+", mask, flags=re.IGNORECASE)]


def format_phone(raw: str, country_code: str, mask: str) -> str:
    """Return `raw` regrouped to `mask` when it's a home-country number.

    Home-country numbers (written as +CC…, 00CC…, or a national 0…) are reduced
    to their national significant number (a leading 0 + subscriber digits) and,
    if that digit count matches the mask, regrouped per the mask. Anything else
    (foreign numbers, short codes, mask mismatches) is returned with surrounding
    whitespace collapsed but otherwise unchanged.
    """
    if not raw or not raw.strip():
        return ""
    value = raw.strip()
    cc = re.sub(r"\D", "", country_code or "")
    groups = _mask_groups(mask or "")
    digits = re.sub(r"\D", "", value)

    # Reduce a home-country number to its national significant form (leading 0).
    national: str | None = None
    if value.startswith("+"):
        if cc and digits.startswith(cc):  # +CC… (a foreign +xx stays None)
            national = "0" + digits[len(cc):]
    elif digits.startswith("00"):
        body = digits[2:]
        if cc and body.startswith(cc):  # 00CC…
            national = "0" + body[len(cc):]
    elif digits.startswith("0"):  # already national
        national = digits

    if national and groups and len(national) == sum(groups):
        out, i = [], 0
        for g in groups:
            out.append(national[i:i + g])
            i += g
        return " ".join(out)

    # Foreign number, short code, or length mismatch — just collapse whitespace.
    return re.sub(r"\s+", " ", value).strip()


def format_phones(items: list[dict], country_code: str, mask: str) -> list[dict]:
    """Apply `format_phone` to the `value` of each {type, value} dict."""
    out = []
    for it in items:
        v = format_phone(it.get("value", ""), country_code, mask)
        out.append({**it, "value": v})
    return out
