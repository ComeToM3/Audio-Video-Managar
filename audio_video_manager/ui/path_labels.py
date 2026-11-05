"""Libellés de chemins compréhensibles (AVM-06O) — chemin complet en info-bulle."""

from __future__ import annotations

from pathlib import Path


def friendly_path_label(path: str | None, *, empty: str = "—") -> str:
    """
    Affiche les 1–2 derniers segments du chemin (ex. « Music / Queen »).
    Le chemin absolu reste disponible via tooltip / sélection.
    """
    if not path or not str(path).strip():
        return empty
    p = Path(path)
    parts = [x for x in p.parts if x not in ("\\", "/", "")]
    if not parts:
        return empty
    if len(parts) == 1:
        return parts[0]
    # Drive letter alone on Windows: keep last two meaningful
    if len(parts) >= 2 and len(parts[-2]) <= 3 and parts[-2].endswith(":"):
        return " / ".join(parts[-2:])
    return " / ".join(parts[-2:])


def path_tooltip(path: str | None) -> str:
    if not path:
        return ""
    return str(path)
