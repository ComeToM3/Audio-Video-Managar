"""Lecture TOC réelle via libdiscid / python-discid."""

from __future__ import annotations

import string
from dataclasses import dataclass

from audio_video_manager.logging_setup import get_logger
from audio_video_manager.metadata.libdiscid_loader import LibdiscidMissingError, import_discid
from audio_video_manager.metadata.models import TocSnapshot

log = get_logger("metadata.toc_reader")

# 1 secteur CDDA = 1/75 s
_MS_PER_SECTOR = 1000 / 75
_DRIVE_CDROM = 5


def list_cdrom_device_letters() -> list[str]:
    """
    Lettres des lecteurs CD-ROM Windows via ``GetDriveTypeW``.

    Retourne des chemins style ``D:`` (sans backslash). Hors Windows → [].
    """
    try:
        import ctypes
    except ImportError:
        return []
    if not hasattr(ctypes, "windll"):
        return []
    kernel = ctypes.windll.kernel32
    out: list[str] = []
    for letter in string.ascii_uppercase:
        root = f"{letter}:\\"
        try:
            if int(kernel.GetDriveTypeW(root)) == _DRIVE_CDROM:
                out.append(f"{letter}:")
        except OSError:
            continue
    return out


def resolve_optical_device_for_discid(
    freac_designation: str | None = None,
) -> tuple[str | None, str]:
    """
    Choisit un périphérique libdiscid sans se fier au suffixe modèle fre:ac.

    fre:ac expose souvent ``ATAPI iHAS324   C`` où ``C`` est un suffixe modèle,
    pas la lettre lecteur — d'où l'incertitude de mapping documentée AVM-04B.
    """
    cdroms = list_cdrom_device_letters()
    if len(cdroms) == 1:
        return cdroms[0], f"Unique CD-ROM Windows: {cdroms[0]}"
    if len(cdroms) > 1:
        # Ne pas inventer : laisser libdiscid défaut, signaler multi
        return None, (
            f"Plusieurs CD-ROM Windows {cdroms} — "
            "sélection explicite requise (pas d'heuristique fre:ac)."
        )
    # Pas de détection Win32 : tenter lettre en fin de designation seulement
    # si c'est aussi un CD-ROM connu — sinon None
    if freac_designation:
        parts = freac_designation.strip().split()
        if parts and len(parts[-1]) == 1 and parts[-1].isalpha():
            guess = f"{parts[-1].upper()}:"
            return (
                None,
                f"Aucun CD-ROM Win32 listé ; suffixe fre:ac « {guess} » "
                "non fiable (souvent suffixe modèle, ex. iHAS324 C).",
            )
    return None, "Aucun CD-ROM détecté ; libdiscid utilisera son périphérique par défaut."


@dataclass(frozen=True)
class DiscReadResult:
    disc_id: str
    toc: TocSnapshot
    device: str
    submission_url: str | None = None


def read_disc_toc(device: str | None = None) -> DiscReadResult:
    """
    Lit le lecteur optique et construit TocSnapshot + Disc ID.

    ``device`` : lettre/chemin OS (ex. ``D:``) ou None = défaut libdiscid.
    """
    discid = import_discid()
    try:
        disc = discid.read(device) if device else discid.read()
    except discid.DiscError as exc:  # type: ignore[attr-defined]
        raise RuntimeError(f"Lecture CD impossible: {exc}") from exc

    first = int(disc.first_track_num)
    last = int(disc.last_track_num)
    tracks = list(disc.tracks)
    # python-discid: track.offset in sectors; length in sectors
    offsets: list[int] = []
    durations_ms: list[int] = []
    for t in tracks:
        offsets.append(int(t.offset))
        seconds = getattr(t, "seconds", None)
        if seconds is not None:
            durations_ms.append(int(round(float(seconds) * 1000)))
        else:
            length_sectors = int(
                getattr(t, "sectors", None) or getattr(t, "length", 0) or 0
            )
            durations_ms.append(int(round(length_sectors * _MS_PER_SECTOR)))

    audio_count = last - first + 1
    if len(durations_ms) != audio_count:
        # Certains bindings exposent leadout — tronquer / aligner
        durations_ms = durations_ms[:audio_count]
        offsets = offsets[:audio_count]

    toc = TocSnapshot(
        first_track=first,
        last_track=last,
        track_offsets_sectors=offsets,
        track_durations_ms=durations_ms,
        audio_track_count=audio_count,
        raw_source="libdiscid",
    )
    result = DiscReadResult(
        disc_id=str(disc.id),
        toc=toc,
        device=str(device or discid.get_default_device()),
        submission_url=getattr(disc, "submission_url", None),
    )
    log.info(
        "TOC lue device=%s disc_id=%s tracks=%s",
        result.device,
        result.disc_id,
        toc.audio_track_count,
    )
    return result


def diagnose_libdiscid() -> str:
    """Message diagnostique pour l'UI."""
    try:
        discid = import_discid()
        dev = discid.get_default_device()
        return f"libdiscid OK — périphérique par défaut: {dev}"
    except LibdiscidMissingError as exc:
        return str(exc)
