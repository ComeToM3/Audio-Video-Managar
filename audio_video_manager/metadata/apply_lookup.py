"""Appliquer un candidat MusicBrainz / TOC sur DiscMetadata — jamais auto-approve (AVM-04C)."""

from __future__ import annotations

from audio_video_manager.metadata.cover_art import CoverArtResult, fetch_cover_art_info
from audio_video_manager.metadata.edition_ranker import (
    SelectionDecision,
    rank_and_select_releases,
)
from audio_video_manager.metadata.enums import (
    ApprovalState,
    CoverStatus,
    FieldTrust,
    MetadataProvenance,
)
from audio_video_manager.metadata.models import (
    DiscMetadata,
    FieldMeta,
    TrackMetadata,
    build_sheet_from_toc,
)
from audio_video_manager.metadata.musicbrainz_client import (
    DiscLookupResult,
    ReleaseCandidate,
    lookup_releases_by_discid,
)
from audio_video_manager.metadata.path_preview import build_path_preview
from audio_video_manager.metadata.toc_reader import DiscReadResult, read_disc_toc
from audio_video_manager.metadata.validation import apply_validation


def _mb(trust: FieldTrust = FieldTrust.AMBIGUOUS) -> FieldMeta:
    """Valeur issue de MB : confirmed seulement si unique et choisie / smart-select."""
    return FieldMeta(trust=trust, provenance=MetadataProvenance.MUSICBRAINZ)


def _toc_meta() -> FieldMeta:
    return FieldMeta(trust=FieldTrust.CONFIRMED, provenance=MetadataProvenance.TOC)


def _is_user_locked(fm: FieldMeta | None) -> bool:
    """Ne pas écraser une correction manuelle confirmée."""
    if fm is None:
        return False
    return fm.provenance in (
        MetadataProvenance.MANUAL,
        MetadataProvenance.USER_CORRECTION,
    ) and fm.trust == FieldTrust.CONFIRMED


def sheet_from_disc_read(read: DiscReadResult) -> DiscMetadata:
    sheet = build_sheet_from_toc(read.toc, disc_id=read.disc_id)
    sheet.identity.field_meta["disc_id"] = _toc_meta()
    sheet.identity.field_meta["toc"] = _toc_meta()
    sheet.approval = ApprovalState.PENDING
    return sheet


def apply_release_candidate(
    sheet: DiscMetadata,
    candidate: ReleaseCandidate,
    *,
    cover: CoverArtResult | None = None,
    user_selected: bool = True,
) -> DiscMetadata:
    """
    Préremplit la fiche depuis un candidat.

    Si ``user_selected`` (ou sélection intelligente confirmée côté appelant) :
    champs édition en ``confirmed``. Sinon ``ambiguous``.
    N'approuve jamais la fiche.
    """
    if sheet.approval == ApprovalState.APPROVED:
        raise ValueError(
            "Une fiche approuvée ne peut pas être enrichie; révoquer l'approbation d'abord."
        )
    trust = FieldTrust.CONFIRMED if user_selected else FieldTrust.AMBIGUOUS
    ed = sheet.edition

    def set_ed(attr: str, value, meta_key: str | None = None) -> None:
        key = meta_key or attr
        if _is_user_locked(ed.field_meta.get(key)):
            return
        if value is None or value == "":
            return
        old = getattr(ed, attr)
        setattr(ed, attr, value)
        ed.field_meta[key] = _mb(trust)
        if old != value:
            sheet.record_correction(
                f"edition.{attr}",
                old,
                value,
                note="MusicBrainz apply",
                provenance=MetadataProvenance.MUSICBRAINZ,
            )

    set_ed("album_title", candidate.title)
    set_ed("album_artist", candidate.artist_credit)
    if candidate.year is not None:
        set_ed("year", candidate.year)
    set_ed("first_release_date", candidate.release_group_first_release_date)
    if candidate.country:
        set_ed("country", candidate.country)
    if candidate.barcode:
        set_ed("barcode", candidate.barcode)
    if candidate.labels:
        set_ed("label", candidate.labels[0])
    if candidate.catalog_numbers:
        set_ed("catalog_number", candidate.catalog_numbers[0])
    if candidate.disambiguation or candidate.status:
        notes = " / ".join(
            x for x in (candidate.status, candidate.disambiguation) if x
        )
        set_ed("edition_notes", notes)

    ed.musicbrainz_release_id = candidate.release_id or None
    ed.musicbrainz_release_group_id = candidate.release_group_id
    if not _is_user_locked(ed.field_meta.get("is_compilation")):
        if "Compilation" in candidate.release_group_secondary_types:
            ed.is_compilation = True
            ed.field_meta["is_compilation"] = FieldMeta(
                trust=FieldTrust.AMBIGUOUS,
                provenance=MetadataProvenance.MUSICBRAINZ,
                note=(
                    "Proposition release-group: Compilation — "
                    f"https://musicbrainz.org/release-group/{candidate.release_group_id}"
                ),
            )
        else:
            ed.field_meta.setdefault(
                "is_compilation",
                FieldMeta(trust=FieldTrust.MISSING),
            )

    if candidate.matched_medium_position is not None:
        if not _is_user_locked(sheet.disc.field_meta.get("disc_number")):
            sheet.disc.disc_number = int(candidate.matched_medium_position)
            sheet.disc.field_meta["disc_number"] = _mb(trust)
        if candidate.medium_count and not _is_user_locked(
            sheet.disc.field_meta.get("disc_total")
        ):
            sheet.disc.disc_total = int(candidate.medium_count)
            sheet.disc.field_meta["disc_total"] = _mb(trust)

    toc = sheet.identity.toc
    n = toc.audio_track_count if toc else len(sheet.tracks)
    new_tracks: list[TrackMetadata] = []
    for i in range(n):
        number = (toc.first_track + i) if toc else (i + 1)
        existing = next((t for t in sheet.tracks if t.number == number), None)
        title = (
            candidate.track_titles[i]
            if i < len(candidate.track_titles)
            else (existing.title if existing else "")
        )
        artist = (
            candidate.track_artists[i]
            if i < len(candidate.track_artists) and candidate.track_artists[i]
            else (existing.artist if existing else candidate.artist_credit)
        )
        duration = (
            toc.track_durations_ms[i]
            if toc and i < len(toc.track_durations_ms)
            else (existing.duration_ms if existing else 0)
        )
        rec_id = (
            candidate.track_recording_ids[i]
            if i < len(candidate.track_recording_ids)
            else None
        )

        title_meta = _mb(trust)
        artist_meta = _mb(trust)
        if existing and _is_user_locked(existing.field_meta.get("title")):
            title = existing.title
            title_meta = existing.field_meta["title"]
        if existing and _is_user_locked(existing.field_meta.get("artist")):
            artist = existing.artist
            artist_meta = existing.field_meta["artist"]

        new_tracks.append(
            TrackMetadata(
                number=number,
                title=title or "",
                artist=artist or "",
                duration_ms=duration,
                musicbrainz_recording_id=rec_id,
                field_meta={
                    "title": title_meta,
                    "artist": artist_meta,
                    "duration_ms": _toc_meta(),
                },
            )
        )
    sheet.tracks = new_tracks

    if cover is not None:
        if cover.status == "confirmed" and cover.front_url:
            if not _is_user_locked(ed.field_meta.get("cover_status")):
                ed.cover_status = CoverStatus.CONFIRMED
                ed.cover_path_or_url = cover.front_url
                ed.field_meta["cover_status"] = FieldMeta(
                    trust=trust,
                    provenance=MetadataProvenance.COVER_ART_ARCHIVE,
                )
        elif cover.status == "unavailable":
            if not _is_user_locked(ed.field_meta.get("cover_status")):
                ed.cover_status = CoverStatus.UNAVAILABLE
                ed.cover_path_or_url = None
                ed.field_meta["cover_status"] = FieldMeta(
                    trust=FieldTrust.UNAVAILABLE,
                    provenance=MetadataProvenance.COVER_ART_ARCHIVE,
                    note=cover.message,
                )

    # Jamais d'auto-approbation (même si auto_approve_high_confidence futur)
    sheet.approval = ApprovalState.PENDING
    sheet.approved_at = None
    sheet.path_preview = build_path_preview(sheet)
    apply_validation(sheet)
    sheet.touch()
    return sheet


def identify_disc(
    device: str | None = None,
    *,
    disc_read: DiscReadResult | None = None,
    lookup: DiscLookupResult | None = None,
    fetch_cover: bool = True,
    preferred_release_country: str = "CA",
    auto_approve_high_confidence: bool = False,
) -> tuple[DiscMetadata, DiscLookupResult | None, CoverArtResult | None, SelectionDecision]:
    """
    Pipeline : TOC → MB → classement intelligent → préremplissage éventuel.

    N'approuve jamais. ``auto_approve_high_confidence`` est ignoré (réservé futur).
    """
    _ = auto_approve_high_confidence  # préparé, désactivé (D-015)
    read = disc_read or read_disc_toc(device)
    sheet = sheet_from_disc_read(read)
    mb = lookup or lookup_releases_by_discid(
        read.disc_id,
        toc_durations_ms=read.toc.track_durations_ms,
    )
    decision = rank_and_select_releases(
        mb.candidates,
        preferred_country=preferred_release_country,
    )
    cover: CoverArtResult | None = None
    lookup_notes: list[str] = [decision.summary]
    lookup_notes.extend(decision.warnings)

    if decision.auto_selected and decision.selected is not None:
        cand = decision.selected
        if fetch_cover:
            cover = fetch_cover_art_info(cand.release_id)
        # Sélection intelligente = confiance confirmed sur champs appliqués,
        # mais approval reste Pending jusqu'à action utilisateur.
        apply_release_candidate(sheet, cand, cover=cover, user_selected=True)
        lookup_notes.append(
            "Sélection automatique d'édition appliquée — "
            "Approuver manuellement avant rip (pas d'auto-approve)."
        )
        if decision.selected.toc_match != "exact":
            lookup_notes.append(
                f"toc_match={decision.selected.toc_match} conservé "
                "(non transformé en exact)."
            )
    elif decision.require_manual_choice and mb.candidates:
        sheet.edition.field_meta["album_title"] = FieldMeta(
            trust=FieldTrust.AMBIGUOUS,
            provenance=MetadataProvenance.MUSICBRAINZ,
            note=decision.summary,
        )
    elif not mb.candidates:
        sheet.edition.field_meta.setdefault(
            "album_title",
            FieldMeta(trust=FieldTrust.MISSING, provenance=MetadataProvenance.MANUAL),
        )

    apply_validation(sheet)
    for note in lookup_notes:
        if note and note not in sheet.validation_warnings:
            sheet.validation_warnings.append(note)
    return sheet, mb, cover, decision
