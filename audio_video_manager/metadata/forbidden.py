"""Placeholders et libellés interdits en fiche approuvée / zone C."""

from __future__ import annotations

import re

FORBIDDEN_EXACT = {
    "",
    "unknown artist",
    "unknown album",
    "unknown",
    "audio cd",
    "tbd",
    "n/a",
    "na",
    "various",  # trop vague — exiger « Various Artists » confirmé si compilation
    "track",
}

_TRACK_GENERIC = re.compile(r"^track\s*\d+$", re.IGNORECASE)
_DISC_GENERIC = re.compile(r"^disc\s*\d+$", re.IGNORECASE)


def is_forbidden_label(value: str | None) -> bool:
    if value is None:
        return True
    cleaned = " ".join(value.strip().split())
    if not cleaned:
        return True
    low = cleaned.lower()
    if low in FORBIDDEN_EXACT:
        return True
    if _TRACK_GENERIC.match(cleaned):
        return True
    if _DISC_GENERIC.match(cleaned) and low.startswith("disc"):
        # « Disc 1 » seul comme titre d'album est trop générique
        return True
    return False
