"""Chargement des polices embarquées (OFL — Fraunces, Outfit) pour AVM-08D."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QFontDatabase

_FONT_DIR = Path(__file__).resolve().parent / "fonts"

# Noms familiaux attendus après enregistrement (fallback Segoe si échec)
FONT_UI = "Outfit"
FONT_DISPLAY = "Fraunces"

_loaded = False
_families: list[str] = []


def load_embedded_fonts() -> list[str]:
    """Enregistre les TTF/OTF du dossier ui/fonts. Idempotent."""
    global _loaded, _families
    if _loaded:
        return list(_families)
    found: list[str] = []
    if _FONT_DIR.is_dir():
        for path in sorted(_FONT_DIR.glob("*.ttf")) + sorted(_FONT_DIR.glob("*.otf")):
            fid = QFontDatabase.addApplicationFont(str(path))
            if fid < 0:
                continue
            for name in QFontDatabase.applicationFontFamilies(fid):
                if name not in found:
                    found.append(name)
    _families = found
    _loaded = True
    return list(_families)


def ui_font_family() -> str:
    load_embedded_fonts()
    families = set(_families)
    if FONT_UI in families:
        return FONT_UI
    return "Segoe UI"


def display_font_family() -> str:
    load_embedded_fonts()
    families = set(_families)
    if FONT_DISPLAY in families:
        return FONT_DISPLAY
    return "Segoe UI Semibold"
