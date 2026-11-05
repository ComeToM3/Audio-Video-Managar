"""Empreinte canonique de fiche approuvée (A3 / R3) — JSON UTF-8 trié."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from audio_video_manager.metadata.enums import ApprovalState
from audio_video_manager.metadata.models import DiscMetadata


def sheet_fingerprint_payload(sheet: DiscMetadata) -> dict[str, Any]:
    """Sous-ensemble stable des données d'identité + édition approuvables."""
    toc = sheet.identity.toc
    return {
        "disc_id": sheet.identity.disc_id,
        "toc": None
        if toc is None
        else {
            "first": toc.first_track,
            "last": toc.last_track,
            "count": toc.audio_track_count,
            "offsets": list(toc.track_offsets_sectors),
            "durations_ms": list(toc.track_durations_ms),
        },
        "edition": {
            "album_title": sheet.edition.album_title,
            "album_artist": sheet.edition.album_artist,
            "year": sheet.edition.year,
            "year_unavailable_justification": sheet.edition.year_unavailable_justification,
            "first_release_date": sheet.edition.first_release_date,
            "country": sheet.edition.country,
            "label": sheet.edition.label,
            "catalog_number": sheet.edition.catalog_number,
            "barcode": sheet.edition.barcode,
            "musicbrainz_release_id": sheet.edition.musicbrainz_release_id,
            "musicbrainz_release_group_id": sheet.edition.musicbrainz_release_group_id,
            "cover_status": sheet.edition.cover_status.value,
            "is_compilation": sheet.edition.is_compilation,
        },
        "disc": {
            "disc_number": sheet.disc.disc_number,
            "disc_total": sheet.disc.disc_total,
        },
        "tracks": [
            {
                "number": t.number,
                "title": t.title,
                "artist": t.artist,
                "duration_ms": t.duration_ms,
            }
            for t in sorted(sheet.tracks, key=lambda x: x.number)
        ],
    }


def compute_approval_fingerprint(sheet: DiscMetadata) -> str:
    """SHA-256 hex du JSON canonique (sort_keys, ensure_ascii=False, separators)."""
    payload = sheet_fingerprint_payload(sheet)
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def revoke_approval(sheet: DiscMetadata, *, note: str = "") -> None:
    """Repasse la fiche en Pending — protection métier A3 (pas seulement UI)."""
    sheet.approval = ApprovalState.PENDING
    sheet.approved_at = None
    sheet.approved_by_note = None
    if note:
        sheet.validation_warnings.append(note)
    sheet.touch()


def sync_approval_with_fingerprint(
    sheet: DiscMetadata,
    stored_fingerprint: str | None,
) -> tuple[bool, str | None]:
    """
    Si Approved et empreinte ≠ stockée → révoque.

    Retourne (still_approved, nouveau_message_ou_None).
    """
    if sheet.approval != ApprovalState.APPROVED:
        return False, None
    if not stored_fingerprint:
        return True, None
    current = compute_approval_fingerprint(sheet)
    if current == stored_fingerprint:
        return True, None
    msg = (
        "La fiche approuvée a été modifiée. "
        "Approuvez à nouveau avant d'extraire."
    )
    revoke_approval(sheet, note=msg)
    return False, msg
