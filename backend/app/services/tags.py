"""Shared helpers for contact tags."""

from __future__ import annotations

# A small, readable palette for auto-coloring new tags (Tailwind-ish hexes).
_PALETTE = [
    "#ef4444", "#f97316", "#f59e0b", "#eab308", "#84cc16", "#22c55e",
    "#10b981", "#14b8a6", "#06b6d4", "#3b82f6", "#6366f1", "#8b5cf6",
    "#a855f7", "#d946ef", "#ec4899", "#f43f5e",
]


def auto_color(name: str) -> str:
    """Deterministically pick a palette color from a tag name."""
    return _PALETTE[sum(map(ord, name)) % len(_PALETTE)]
