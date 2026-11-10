"""Libellés FR de progression — humanisation AVM-06I."""

from __future__ import annotations

import re
from typing import Sequence

PIPELINE_STEPS: tuple[str, ...] = (
    "Vérification du disque",
    "Extraction audio",
    "Contrôle des fichiers",
    "Mise en tags et pochette",
    "Organisation",
    "Publication",
    "Terminé",
)

_RULES: list[tuple[str, str]] = [
    ("vérification", "Vérification du disque"),
    ("disc id", "Vérification du disque"),
    ("correspondance", "Vérification du disque"),
    ("extraction", "Extraction audio"),
    ("fre:ac", "Extraction audio"),
    ("freaccmd", "Extraction audio"),
    ("staging", "Extraction audio"),
    ("copie staging", "Extraction audio"),
    ("f-08a", "Contrôle des fichiers"),
    ("intégrité", "Contrôle des fichiers"),
    ("décodage", "Contrôle des fichiers"),
    ("contrôle", "Contrôle des fichiers"),
    ("tag", "Mise en tags et pochette"),
    ("pochette", "Mise en tags et pochette"),
    ("mutagen", "Mise en tags et pochette"),
    ("inbox", "Organisation"),
    ("zone b", "Organisation"),
    ("organisation", "Organisation"),
    ("publication", "Publication"),
    ("bibliothèque", "Publication"),
    ("terminé", "Terminé"),
]

# fre:ac / noms de fichiers : « Processing file: 3.flac », « track03.flac », …
_TRACK_FILE_RE = re.compile(
    r"(?:processing\s+file\s*:?\s*)?(?:track[\s._-]*)?(\d{1,2})\.flac\b",
    re.IGNORECASE,
)
_TRACK_OF_RE = re.compile(
    r"track\s+(\d+)\s*/\s*(\d+)",
    re.IGNORECASE,
)
_TRACK_DONE_RE = re.compile(
    r"processing\s+file:.*?\btrack\s+(\d+)\s*\.{3,}\s*done\.",
    re.IGNORECASE,
)


def parse_completed_track_number(raw: str) -> int | None:
    """Extrait une piste terminée depuis l’événement observé dans freac_stdout.txt."""
    match = _TRACK_DONE_RE.search(raw or "")
    if not match:
        return None
    try:
        number = int(match.group(1))
    except ValueError:
        return None
    return number if number >= 1 else None


def parse_track_number_from_progress(raw: str) -> int | None:
    """Extrait un numéro de piste depuis une ligne fre:ac / pipeline (1-based)."""
    text = raw or ""
    m = _TRACK_OF_RE.search(text)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return None
    completed = parse_completed_track_number(text)
    if completed is not None:
        return completed
    m = _TRACK_FILE_RE.search(text)
    if m:
        try:
            n = int(m.group(1))
        except ValueError:
            return None
        return n if n >= 1 else None
    return None


def map_progress_message(
    raw: str,
    *,
    track_titles: Sequence[str] | None = None,
    track_total: int | None = None,
) -> str:
    """
    Traduit un message interne / fre:ac en libellé utilisateur.

    Si une piste est détectée et qu’un titre approuvé existe → 
    « Piste 3/17 — Killer Queen ». Sinon repli honnête, sans inventer de %.
    """
    text = (raw or "").strip()
    low = text.casefold()
    track_no = parse_track_number_from_progress(text)

    if "fre:ac est actif" in low and "aucun nouvel événement observé" in low:
        return text

    if track_no is not None:
        total = track_total
        if total is None and track_titles is not None:
            total = len(track_titles)
        title: str | None = None
        if track_titles and 1 <= track_no <= len(track_titles):
            cand = (track_titles[track_no - 1] or "").strip()
            if cand:
                title = cand
        if total and total > 0:
            prefix = f"Piste {track_no}/{total}"
        else:
            prefix = f"Piste {track_no}"
        if title:
            return f"{prefix} — {title}"
        return f"{prefix} — titre non déterminé"

    for needle, label in _RULES:
        if needle in low:
            return label

    # Masquer les lignes fre:ac brutes restantes
    if "processing" in low or ".flac" in low:
        return "Extraction audio"
    if text.startswith("Démarrage freaccmd") or "freaccmd" in low:
        return "Extraction audio"

    return text if text else "En cours…"


def progress_step_index(raw: str, *, track_titles: Sequence[str] | None = None) -> int:
    """Index dans PIPELINE_STEPS (−1 si inconnu)."""
    if parse_track_number_from_progress(raw or "") is not None:
        return PIPELINE_STEPS.index("Extraction audio")
    label = map_progress_message(raw, track_titles=track_titles)
    # Les libellés « Piste N/… » restent sur Extraction
    if label.startswith("Piste "):
        return PIPELINE_STEPS.index("Extraction audio")
    try:
        return PIPELINE_STEPS.index(label)
    except ValueError:
        return -1


def humanize_error_for_user(raw: str | None) -> tuple[str, str | None]:
    """
    Sépare résumé utilisateur / détail technique.

    Retourne (résumé_fr, détail_ou_None).
    Les codes fre:ac / returncode numériques restent dans le détail technique (A-04).
    """
    import re

    if not raw or not raw.strip():
        return "Une erreur est survenue.", None
    text = raw.strip()
    tech: str | None = None
    summary = text
    marker = "Détail technique :"
    if marker in text:
        head, _, tail = text.partition(marker)
        summary = head.strip() or "Une erreur est survenue."
        tech = tail.strip() or None

    # Codes numériques seuls ou préfixés → message clair
    code_only = re.fullmatch(
        r"(?:freaccmd\s*)?(?:returncode|code(?:\s*d[’']extraction)?)\s*=\s*-?\d+\s*",
        summary,
        flags=re.IGNORECASE,
    )
    has_code = re.search(
        r"(?:freaccmd\s*)?(?:returncode|code(?:\s*d[’']extraction)?)\s*=\s*-?\d+",
        summary,
        flags=re.IGNORECASE,
    ) or re.search(r"\b4294967293\b", summary)

    if code_only:
        if tech is None:
            tech = text
        return "L’extraction audio n’a pas abouti.", tech

    # Jargon fréquent → formulation plus douce (détail conservé)
    replacements = (
        ("freaccmd returncode=", "code d’extraction = "),
        ("freaccmd", "outil d’extraction"),
        ("returncode=", "code = "),
        ("Workdir", "Dossier temporaire"),
        ("workdir", "dossier temporaire"),
    )
    soft = summary
    for a, b in replacements:
        soft = soft.replace(a, b)

    if has_code:
        # Retirer la mention de code du résumé utilisateur
        soft = re.sub(
            r"(?:freaccmd\s*)?(?:returncode|code(?:\s*d[’']extraction)?)\s*=\s*-?\d+",
            "",
            soft,
            flags=re.IGNORECASE,
        )
        soft = re.sub(r"\b4294967293\b", "", soft)
        soft = re.sub(r"\s{2,}", " ", soft).strip(" .;,—-")
        if not soft:
            soft = "L’extraction audio n’a pas abouti."
        elif "extraction" not in soft.casefold() and "échou" not in soft.casefold():
            soft = "L’extraction audio n’a pas abouti."
        if tech is None:
            tech = text
        return soft, tech

    if soft != summary and tech is None:
        tech = text
    return soft, tech
