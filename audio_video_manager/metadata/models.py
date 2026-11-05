"""Modèle DiscMetadata — identification disque vs édition physique exacte."""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from audio_video_manager.metadata.enums import (
    ApprovalState,
    CoverStatus,
    FieldTrust,
    JobMode,
    MediumFormat,
    MetadataProvenance,
)

SCHEMA_VERSION = 1
TOC_DURATION_TOLERANCE_MS = 500


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class FieldMeta:
    """Confiance + provenance pour un champ logique."""

    trust: FieldTrust = FieldTrust.MISSING
    provenance: MetadataProvenance = MetadataProvenance.MANUAL
    note: str = ""


@dataclass
class CorrectionEvent:
    field: str
    old_value: str
    new_value: str
    at: str
    note: str = ""
    provenance: MetadataProvenance = MetadataProvenance.USER_CORRECTION


@dataclass
class TocSnapshot:
    """TOC mesurée — jamais inventée."""

    first_track: int
    last_track: int
    track_offsets_sectors: list[int]
    track_durations_ms: list[int]
    audio_track_count: int
    raw_source: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TocSnapshot:
        return cls(
            first_track=int(data["first_track"]),
            last_track=int(data["last_track"]),
            track_offsets_sectors=[int(x) for x in data.get("track_offsets_sectors", [])],
            track_durations_ms=[int(x) for x in data.get("track_durations_ms", [])],
            audio_track_count=int(data["audio_track_count"]),
            raw_source=str(data.get("raw_source", "")),
        )


@dataclass
class TrackMetadata:
    number: int
    title: str = ""
    artist: str = ""
    duration_ms: int = 0
    isrc: str | None = None
    musicbrainz_recording_id: str | None = None
    musicbrainz_track_id: str | None = None
    field_meta: dict[str, FieldMeta] = field(default_factory=dict)

    def ensure_field_meta(self) -> None:
        for key in ("title", "artist", "duration_ms"):
            self.field_meta.setdefault(key, FieldMeta())


@dataclass
class DiscIdentity:
    """Identification du support lu (TOC / Disc ID) — distincte de l'édition commerciale."""

    disc_id: str | None = None
    toc: TocSnapshot | None = None
    medium_format: MediumFormat = MediumFormat.AUDIO_CD
    field_meta: dict[str, FieldMeta] = field(default_factory=dict)

    def ensure_field_meta(self) -> None:
        for key in ("disc_id", "toc", "medium_format"):
            self.field_meta.setdefault(key, FieldMeta())


@dataclass
class ReleaseEdition:
    """Édition physique exacte (pressage / réédition / pays / label)."""

    album_title: str = ""
    album_artist: str = ""
    sort_album_artist: str | None = None
    year: int | None = None
    first_release_date: str | None = None
    label: str | None = None
    catalog_number: str | None = None
    country: str | None = None
    barcode: str | None = None
    edition_notes: str | None = None
    # False is only a storage default; trust=MISSING/AMBIGUOUS means unknown.
    is_compilation: bool = False
    is_reissue: bool | None = None
    musicbrainz_release_id: str | None = None
    musicbrainz_release_group_id: str | None = None
    cover_status: CoverStatus = CoverStatus.MISSING
    cover_path_or_url: str | None = None
    year_unavailable_justification: str | None = None
    field_meta: dict[str, FieldMeta] = field(default_factory=dict)

    def ensure_field_meta(self) -> None:
        for key in (
            "album_title",
            "album_artist",
            "year",
            "first_release_date",
            "is_compilation",
            "cover_status",
            "label",
            "catalog_number",
            "country",
        ):
            self.field_meta.setdefault(key, FieldMeta())


@dataclass
class DiscUnit:
    """Position du disque dans un set (coffret)."""

    disc_number: int = 1
    disc_total: int = 1
    disc_title: str | None = None
    field_meta: dict[str, FieldMeta] = field(default_factory=dict)

    def ensure_field_meta(self) -> None:
        for key in ("disc_number", "disc_total"):
            self.field_meta.setdefault(key, FieldMeta())


@dataclass
class DiscMetadata:
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    schema_version: int = SCHEMA_VERSION
    mode: JobMode = JobMode.NORMAL
    approval: ApprovalState = ApprovalState.PENDING
    approved_at: str | None = None
    approved_by_note: str | None = None
    identity: DiscIdentity = field(default_factory=DiscIdentity)
    edition: ReleaseEdition = field(default_factory=ReleaseEdition)
    disc: DiscUnit = field(default_factory=DiscUnit)
    tracks: list[TrackMetadata] = field(default_factory=list)
    path_preview: list[str] = field(default_factory=list)
    validation_errors: list[str] = field(default_factory=list)
    validation_warnings: list[str] = field(default_factory=list)
    corrections: list[CorrectionEvent] = field(default_factory=list)
    created_at: str = field(default_factory=_utc_now)
    updated_at: str = field(default_factory=_utc_now)

    def ensure_defaults(self) -> None:
        self.identity.ensure_field_meta()
        self.edition.ensure_field_meta()
        self.disc.ensure_field_meta()
        for t in self.tracks:
            t.ensure_field_meta()

    def touch(self) -> None:
        self.updated_at = _utc_now()

    def record_correction(
        self,
        field_name: str,
        old_value: Any,
        new_value: Any,
        *,
        note: str = "",
        provenance: MetadataProvenance = MetadataProvenance.USER_CORRECTION,
    ) -> None:
        self.corrections.append(
            CorrectionEvent(
                field=field_name,
                old_value="" if old_value is None else str(old_value),
                new_value="" if new_value is None else str(new_value),
                at=_utc_now(),
                note=note,
                provenance=provenance,
            )
        )
        self.touch()

    def to_dict(self) -> dict[str, Any]:
        self.ensure_defaults()

        def fm(meta: dict[str, FieldMeta]) -> dict[str, Any]:
            return {
                k: {"trust": v.trust.value, "provenance": v.provenance.value, "note": v.note}
                for k, v in meta.items()
            }

        return {
            "id": self.id,
            "schema_version": self.schema_version,
            "mode": self.mode.value,
            "approval": self.approval.value,
            "approved_at": self.approved_at,
            "approved_by_note": self.approved_by_note,
            "identity": {
                "disc_id": self.identity.disc_id,
                "toc": self.identity.toc.to_dict() if self.identity.toc else None,
                "medium_format": self.identity.medium_format.value,
                "field_meta": fm(self.identity.field_meta),
            },
            "edition": {
                **{
                    k: getattr(self.edition, k)
                    for k in (
                        "album_title",
                        "album_artist",
                        "sort_album_artist",
                        "year",
                        "first_release_date",
                        "label",
                        "catalog_number",
                        "country",
                        "barcode",
                        "edition_notes",
                        "is_compilation",
                        "is_reissue",
                        "musicbrainz_release_id",
                        "musicbrainz_release_group_id",
                        "cover_path_or_url",
                        "year_unavailable_justification",
                    )
                },
                "cover_status": self.edition.cover_status.value,
                "field_meta": fm(self.edition.field_meta),
            },
            "disc": {
                "disc_number": self.disc.disc_number,
                "disc_total": self.disc.disc_total,
                "disc_title": self.disc.disc_title,
                "field_meta": fm(self.disc.field_meta),
            },
            "tracks": [
                {
                    "number": t.number,
                    "title": t.title,
                    "artist": t.artist,
                    "duration_ms": t.duration_ms,
                    "isrc": t.isrc,
                    "musicbrainz_recording_id": t.musicbrainz_recording_id,
                    "musicbrainz_track_id": t.musicbrainz_track_id,
                    "field_meta": fm(t.field_meta),
                }
                for t in self.tracks
            ],
            "path_preview": list(self.path_preview),
            "validation_errors": list(self.validation_errors),
            "validation_warnings": list(self.validation_warnings),
            "corrections": [
                {
                    "field": c.field,
                    "old_value": c.old_value,
                    "new_value": c.new_value,
                    "at": c.at,
                    "note": c.note,
                    "provenance": c.provenance.value,
                }
                for c in self.corrections
            ],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DiscMetadata:
        def parse_fm(raw: dict[str, Any] | None) -> dict[str, FieldMeta]:
            out: dict[str, FieldMeta] = {}
            for k, v in (raw or {}).items():
                out[k] = FieldMeta(
                    trust=FieldTrust(v.get("trust", FieldTrust.MISSING.value)),
                    provenance=MetadataProvenance(
                        v.get("provenance", MetadataProvenance.MANUAL.value)
                    ),
                    note=str(v.get("note", "")),
                )
            return out

        identity_raw = data.get("identity") or {}
        toc_raw = identity_raw.get("toc")
        identity = DiscIdentity(
            disc_id=identity_raw.get("disc_id"),
            toc=TocSnapshot.from_dict(toc_raw) if toc_raw else None,
            medium_format=MediumFormat(
                identity_raw.get("medium_format", MediumFormat.AUDIO_CD.value)
            ),
            field_meta=parse_fm(identity_raw.get("field_meta")),
        )
        ed_raw = data.get("edition") or {}
        edition = ReleaseEdition(
            album_title=str(ed_raw.get("album_title", "")),
            album_artist=str(ed_raw.get("album_artist", "")),
            sort_album_artist=ed_raw.get("sort_album_artist"),
            year=ed_raw.get("year"),
            first_release_date=ed_raw.get("first_release_date"),
            label=ed_raw.get("label"),
            catalog_number=ed_raw.get("catalog_number"),
            country=ed_raw.get("country"),
            barcode=ed_raw.get("barcode"),
            edition_notes=ed_raw.get("edition_notes"),
            is_compilation=bool(ed_raw.get("is_compilation", False)),
            is_reissue=ed_raw.get("is_reissue"),
            musicbrainz_release_id=ed_raw.get("musicbrainz_release_id"),
            musicbrainz_release_group_id=ed_raw.get("musicbrainz_release_group_id"),
            cover_status=CoverStatus(
                ed_raw.get("cover_status", CoverStatus.MISSING.value)
            ),
            cover_path_or_url=ed_raw.get("cover_path_or_url"),
            year_unavailable_justification=ed_raw.get("year_unavailable_justification"),
            field_meta=parse_fm(ed_raw.get("field_meta")),
        )
        disc_raw = data.get("disc") or {}
        disc = DiscUnit(
            disc_number=int(disc_raw.get("disc_number", 1)),
            disc_total=int(disc_raw.get("disc_total", 1)),
            disc_title=disc_raw.get("disc_title"),
            field_meta=parse_fm(disc_raw.get("field_meta")),
        )
        tracks: list[TrackMetadata] = []
        for t in data.get("tracks") or []:
            tracks.append(
                TrackMetadata(
                    number=int(t["number"]),
                    title=str(t.get("title", "")),
                    artist=str(t.get("artist", "")),
                    duration_ms=int(t.get("duration_ms", 0)),
                    isrc=t.get("isrc"),
                    musicbrainz_recording_id=t.get("musicbrainz_recording_id"),
                    musicbrainz_track_id=t.get("musicbrainz_track_id"),
                    field_meta=parse_fm(t.get("field_meta")),
                )
            )
        corrections: list[CorrectionEvent] = []
        for c in data.get("corrections") or []:
            corrections.append(
                CorrectionEvent(
                    field=str(c["field"]),
                    old_value=str(c.get("old_value", "")),
                    new_value=str(c.get("new_value", "")),
                    at=str(c.get("at", "")),
                    note=str(c.get("note", "")),
                    provenance=MetadataProvenance(
                        c.get("provenance", MetadataProvenance.USER_CORRECTION.value)
                    ),
                )
            )
        sheet = cls(
            id=str(data.get("id") or uuid.uuid4().hex),
            schema_version=int(data.get("schema_version", SCHEMA_VERSION)),
            mode=JobMode(data.get("mode", JobMode.NORMAL.value)),
            approval=ApprovalState(data.get("approval", ApprovalState.PENDING.value)),
            approved_at=data.get("approved_at"),
            approved_by_note=data.get("approved_by_note"),
            identity=identity,
            edition=edition,
            disc=disc,
            tracks=tracks,
            path_preview=list(data.get("path_preview") or []),
            validation_errors=list(data.get("validation_errors") or []),
            validation_warnings=list(data.get("validation_warnings") or []),
            corrections=corrections,
            created_at=str(data.get("created_at") or _utc_now()),
            updated_at=str(data.get("updated_at") or _utc_now()),
        )
        sheet.ensure_defaults()
        return sheet


def build_sheet_from_toc(
    toc: TocSnapshot,
    *,
    disc_id: str | None = None,
    mode: JobMode = JobMode.NORMAL,
) -> DiscMetadata:
    """Amorce une fiche depuis une TOC mesurée (pistes sans titres inventés)."""
    tracks = [
        TrackMetadata(
            number=toc.first_track + i,
            title="",
            artist="",
            duration_ms=toc.track_durations_ms[i]
            if i < len(toc.track_durations_ms)
            else 0,
            field_meta={
                "duration_ms": FieldMeta(
                    trust=FieldTrust.CONFIRMED,
                    provenance=MetadataProvenance.TOC,
                ),
                "title": FieldMeta(trust=FieldTrust.MISSING),
                "artist": FieldMeta(trust=FieldTrust.MISSING),
            },
        )
        for i in range(toc.audio_track_count)
    ]
    sheet = DiscMetadata(
        mode=mode,
        identity=DiscIdentity(
            disc_id=disc_id,
            toc=toc,
            medium_format=MediumFormat.AUDIO_CD,
            field_meta={
                "toc": FieldMeta(
                    trust=FieldTrust.CONFIRMED,
                    provenance=MetadataProvenance.TOC,
                ),
                "disc_id": FieldMeta(
                    trust=FieldTrust.CONFIRMED
                    if disc_id
                    else FieldTrust.MISSING,
                    provenance=MetadataProvenance.TOC
                    if disc_id
                    else MetadataProvenance.MANUAL,
                ),
                "medium_format": FieldMeta(
                    trust=FieldTrust.CONFIRMED,
                    provenance=MetadataProvenance.MANUAL,
                ),
            },
        ),
        tracks=tracks,
    )
    sheet.ensure_defaults()
    return sheet
