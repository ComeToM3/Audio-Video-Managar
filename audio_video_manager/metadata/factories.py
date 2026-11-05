"""Helpers de construction de fiches (tests / UI manuelle)."""

from __future__ import annotations

from audio_video_manager.metadata.enums import (
    CoverStatus,
    FieldTrust,
    JobMode,
    MetadataProvenance,
)
from audio_video_manager.metadata.models import (
    DiscMetadata,
    FieldMeta,
    TocSnapshot,
    TrackMetadata,
    build_sheet_from_toc,
)


def confirmed(provenance: MetadataProvenance = MetadataProvenance.MANUAL) -> FieldMeta:
    return FieldMeta(trust=FieldTrust.CONFIRMED, provenance=provenance)


def make_demo_toc(track_count: int = 2, duration_ms: int = 180_000) -> TocSnapshot:
    return TocSnapshot(
        first_track=1,
        last_track=track_count,
        track_offsets_sectors=[0] * track_count,
        track_durations_ms=[duration_ms] * track_count,
        audio_track_count=track_count,
        raw_source="manual_test",
    )


def make_approvable_sheet(
    *,
    album: str = "Demo Album",
    artist: str = "Demo Artist",
    year: int = 1999,
    tracks: int = 2,
) -> DiscMetadata:
    toc = make_demo_toc(tracks)
    sheet = build_sheet_from_toc(toc, disc_id="demo.disc.id", mode=JobMode.NORMAL)
    sheet.edition.album_title = album
    sheet.edition.album_artist = artist
    sheet.edition.year = year
    sheet.edition.is_compilation = False
    sheet.edition.cover_status = CoverStatus.UNAVAILABLE
    sheet.edition.field_meta["album_title"] = confirmed()
    sheet.edition.field_meta["album_artist"] = confirmed()
    sheet.edition.field_meta["year"] = confirmed()
    sheet.edition.field_meta["is_compilation"] = confirmed()
    sheet.edition.field_meta["cover_status"] = FieldMeta(
        trust=FieldTrust.UNAVAILABLE,
        provenance=MetadataProvenance.MANUAL,
        note="Aucune pochette pour démo",
    )
    sheet.disc.disc_number = 1
    sheet.disc.disc_total = 1
    sheet.disc.field_meta["disc_number"] = confirmed()
    sheet.disc.field_meta["disc_total"] = confirmed()
    for i, t in enumerate(sheet.tracks):
        t.title = f"Song {i + 1}"
        t.artist = artist
        t.field_meta["title"] = confirmed()
        t.field_meta["artist"] = confirmed()
        t.field_meta["duration_ms"] = confirmed(MetadataProvenance.TOC)
    sheet.edition.year_unavailable_justification = None
    return sheet
