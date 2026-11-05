"""Chemins des ressources graphiques UI (AVM-08E Brume pastel)."""

from __future__ import annotations

from pathlib import Path

_ASSETS = Path(__file__).resolve().parent / "assets"

# Priorité : Brume pastel (08E) → toiles 08D.1 en secours
BRUME_PASTEL = _ASSETS / "brume_pastel_canvas.jpg"
PAINT_CANVAS = _ASSETS / "atelier_paint_canvas.jpg"
PAINT_CANVAS_SOURCE = _ASSETS / "atelier_paint_canvas_src.jpg"


def paint_canvas_path() -> Path:
    for path in (BRUME_PASTEL, PAINT_CANVAS, PAINT_CANVAS_SOURCE):
        if path.is_file():
            return path
    return BRUME_PASTEL
