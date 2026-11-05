"""Aperçu des chemins zone C (sanitisation Windows) — pas d'écriture disque."""

from __future__ import annotations

import re

from audio_video_manager.metadata.models import DiscMetadata

_WIN_FORBIDDEN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

# Noms réservés Windows (CreateFile) — y compris avec extension (CON.txt).
_WIN_RESERVED = frozenset(
    {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }
)

# Seuil d’avertissement chemins longs (MAX_PATH historique ≈ 260).
WARN_PATH_CHARS = 240


def _is_reserved_win_name(name: str) -> bool:
    stem = name.split(".", 1)[0].upper()
    return stem in _WIN_RESERVED


def sanitize_segment(value: str, *, fallback: str = "_") -> str:
    """
    Sanitize un segment de chemin (artiste, album, titre).

    AVM-10D : refuse les noms réservés Windows sans défigurer le titre musical —
    préfixe ``_`` si le segment (ou son stem) est réservé.
    """
    cleaned = _WIN_FORBIDDEN.sub("_", value.strip())
    cleaned = cleaned.rstrip(" .")
    cleaned = re.sub(r"\s+", " ", cleaned)
    if not cleaned:
        return fallback
    if _is_reserved_win_name(cleaned):
        cleaned = f"_{cleaned}"
    # Évite un segment redevenu réservé après strip (ex. ``_CON`` OK ; ``CON.`` → ``CON``)
    if _is_reserved_win_name(cleaned):
        cleaned = f"_{cleaned}"
    return cleaned or fallback


def build_path_preview(sheet: DiscMetadata) -> list[str]:
    """
    Chemins relatifs proposés pour la zone C.

    N'utilise que des valeurs présentes ; n'invente pas de titres.
    Si des titres manquent, retourne une liste courte avec un marqueur d'erreur
    (la validation bloquera l'approbation).
    """
    ed = sheet.edition
    disc = sheet.disc
    artist = sanitize_segment(ed.album_artist or "")
    album = sanitize_segment(ed.album_title or "")
    if not artist or not album or artist == "_" or album == "_":
        return ["<aperçu indisponible : album_artist/album_title incomplets>"]

    year_part = ""
    year_meta = ed.field_meta.get("year")
    if ed.year is not None:
        year_part = f" ({ed.year})"
    elif year_meta and year_meta.trust.value == "unavailable":
        year_part = ""
    else:
        return ["<aperçu indisponible : année non confirmée ni unavailable>"]

    album_dir = f"{artist}/{album}{year_part}"
    if disc.disc_total > 1:
        album_dir = f"{album_dir}/Disc {disc.disc_number}"

    paths: list[str] = []
    for t in sorted(sheet.tracks, key=lambda x: x.number):
        title = sanitize_segment(t.title or "")
        if not title or title == "_":
            paths.append(
                f"{album_dir}/{t.number:02d} - <titre manquant>.flac"
            )
        else:
            paths.append(f"{album_dir}/{t.number:02d} - {title}.flac")
    paths.append(f"{album_dir}/cover.jpg")
    # Avertissement chemins longs (MAX_PATH) — non bloquant ici
    if any(len(p) >= WARN_PATH_CHARS for p in paths):
        paths.append(
            f"<avertissement: chemin ≥{WARN_PATH_CHARS} caractères — "
            "risque MAX_PATH Windows>"
        )
    return paths
