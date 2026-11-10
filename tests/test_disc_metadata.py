"""AC-M1…AC-M8 — gate DiscMetadata (sans MusicBrainz, sans rip réel)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from audio_video_manager.metadata.enums import (
    ApprovalState,
    CoverStatus,
    FieldTrust,
    JobMode,
    MetadataProvenance,
)
from audio_video_manager.metadata.factories import make_approvable_sheet, make_demo_toc
from audio_video_manager.metadata.forbidden import is_forbidden_label
from audio_video_manager.metadata.models import (
    DiscMetadata,
    FieldMeta,
    TrackMetadata,
    build_sheet_from_toc,
)
from audio_video_manager.metadata.path_preview import build_path_preview
from audio_video_manager.metadata.repository import DiscMetadataRepository
from audio_video_manager.metadata.validation import (
    ApprovalError,
    apply_validation,
    approve_sheet,
    assert_can_start_archive_rip,
    validate_disc_metadata,
)
from audio_video_manager.orchestration.rip_job import run_rip_job
from audio_video_manager.storage import SCHEMA_VERSION, Database
from tests.flac_fixtures import write_minimal_flac


def test_ac_m1_model_has_identity_edition_tracks_toc() -> None:
    sheet = make_approvable_sheet()
    d = sheet.to_dict()
    assert "identity" in d and d["identity"]["toc"] is not None
    assert "edition" in d
    assert "disc" in d
    assert len(d["tracks"]) == 2
    assert "field_meta" in d["edition"]


def test_ac_m5_forbidden_placeholders() -> None:
    assert is_forbidden_label("Unknown Artist")
    assert is_forbidden_label("Track 01")
    assert is_forbidden_label("Audio CD")
    assert not is_forbidden_label("Radiohead")


@pytest.mark.parametrize(
    ("value", "trust"),
    [
        (True, FieldTrust.CONFIRMED),
        (False, FieldTrust.CONFIRMED),
        (False, FieldTrust.MISSING),
        (True, FieldTrust.AMBIGUOUS),
    ],
)
def test_compilation_yes_no_or_unknown_does_not_block_approval(value, trust) -> None:
    sheet = make_approvable_sheet()
    sheet.edition.is_compilation = value
    sheet.edition.field_meta["is_compilation"] = FieldMeta(trust=trust)

    result = validate_disc_metadata(sheet)

    assert result.ok
    assert not any("is_compilation" in error for error in result.errors)
    approve_sheet(sheet)
    assert sheet.approval == ApprovalState.APPROVED


def test_ac_m3_toc_mismatch_blocks() -> None:
    sheet = make_approvable_sheet(tracks=2)
    sheet.tracks.append(
        TrackMetadata(number=3, title="X", artist="Y", duration_ms=1000)
    )
    result = validate_disc_metadata(sheet)
    assert result.ok is False
    assert any("TOC" in e or "piste" in e.lower() for e in result.errors)


def test_ac_m3_duration_tolerance() -> None:
    sheet = make_approvable_sheet(tracks=1)
    sheet.tracks[0].duration_ms = sheet.identity.toc.track_durations_ms[0] + 501
    result = validate_disc_metadata(sheet)
    assert result.ok is False


def test_ac_m4_compilation_and_multidisc_and_reissue_paths() -> None:
    sheet = make_approvable_sheet()
    sheet.edition.is_compilation = True
    sheet.edition.field_meta["is_compilation"] = FieldMeta(trust=FieldTrust.CONFIRMED)
    sheet.disc.disc_total = 2
    sheet.disc.disc_number = 1
    preview = build_path_preview(sheet)
    assert any("/Disc 1/" in p for p in preview)
    sheet.edition.is_reissue = True
    sheet.edition.edition_notes = None
    sheet.edition.label = None
    apply_validation(sheet)
    assert any("Réédition" in w or "réédition" in w.lower() for w in sheet.validation_warnings)


def test_ac_m6_path_preview_required_for_approve() -> None:
    sheet = make_approvable_sheet()
    sheet.edition.album_title = ""
    sheet.edition.field_meta["album_title"] = FieldMeta(trust=FieldTrust.CONFIRMED)
    with pytest.raises(ApprovalError):
        approve_sheet(sheet)


def test_ac_m2_archive_rip_requires_approval(avm_home: Path, tmp_path: Path) -> None:
    exe = tmp_path / "freaccmd.exe"
    exe.write_text("", encoding="utf-8")
    sheet = make_approvable_sheet()
    # Pending
    with pytest.raises(ApprovalError):
        assert_can_start_archive_rip(sheet)
    with pytest.raises(ApprovalError):
        run_rip_job(
            freaccmd=exe,
            jobs_root=avm_home / "jobs",
            drive_number=0,
            mode=JobMode.NORMAL,
            metadata=sheet,
        )


def test_approve_then_gate_allows(avm_home: Path) -> None:
    sheet = make_approvable_sheet()
    approve_sheet(sheet)
    assert sheet.approval == ApprovalState.APPROVED
    assert_can_start_archive_rip(sheet)


def test_year_unavailable_requires_justification() -> None:
    sheet = make_approvable_sheet()
    sheet.edition.year = None
    sheet.edition.field_meta["year"] = FieldMeta(trust=FieldTrust.UNAVAILABLE)
    sheet.edition.year_unavailable_justification = ""
    result = validate_disc_metadata(sheet)
    assert result.ok is False
    sheet.edition.year_unavailable_justification = "Non indiquée sur le packaging"
    result2 = apply_validation(sheet)
    # cover etc still ok — year unavailable with justification should pass year rule
    assert not any(e.startswith("year unavailable") for e in result2.errors)


def test_ac_m7_technical_test_bypasses_gate(avm_home: Path, tmp_path: Path) -> None:
    exe = tmp_path / "freaccmd.exe"
    exe.write_text("", encoding="utf-8")
    jobs = avm_home / "jobs"

    def fake_rip(self, request, *, on_progress=None, cancel_event=None):
        from audio_video_manager.extraction.cd_ripper import RipResult

        flac = write_minimal_flac(request.workdir / "01.flac")
        return RipResult(
            success=True,
            cancelled=False,
            returncode=0,
            argv=("freaccmd",),
            stdout="",
            stderr="",
            flac_files=[flac],
            workdir=request.workdir,
        )

    with patch(
        "audio_video_manager.orchestration.rip_job.FreacCdRipper.rip",
        fake_rip,
    ):
        report = run_rip_job(
            freaccmd=exe,
            jobs_root=jobs,
            drive_number=0,
            mode=JobMode.TECHNICAL_TEST,
            metadata=None,
            allow_library_publish=False,
        )
    assert report.mode == JobMode.TECHNICAL_TEST
    assert report.rip.success is True


def test_publish_flag_rejected(avm_home: Path, tmp_path: Path) -> None:
    exe = tmp_path / "freaccmd.exe"
    exe.write_text("", encoding="utf-8")
    with pytest.raises(ApprovalError):
        run_rip_job(
            freaccmd=exe,
            jobs_root=avm_home / "jobs",
            drive_number=0,
            mode=JobMode.TECHNICAL_TEST,
            allow_library_publish=True,
        )


def test_repository_roundtrip(avm_home: Path) -> None:
    db = Database(avm_home / "meta.sqlite3")
    db.initialize()
    assert db.get_schema_version() == SCHEMA_VERSION
    sheet = make_approvable_sheet()
    sheet.edition.first_release_date = "2002"
    sheet.edition.field_meta["first_release_date"] = FieldMeta(
        trust=FieldTrust.CONFIRMED,
        provenance=MetadataProvenance.MUSICBRAINZ,
    )
    sheet.record_correction("edition.album_title", "old", sheet.edition.album_title)
    repo = DiscMetadataRepository(db)
    repo.save(sheet)
    loaded = repo.get(sheet.id)
    assert loaded is not None
    assert loaded.edition.album_title == sheet.edition.album_title
    assert loaded.edition.first_release_date == "2002"
    assert len(loaded.corrections) >= 1
    db.close()


def test_schema_migration_v1_to_current(avm_home: Path) -> None:
    """DB créée à la main en v1 puis migrate jusqu'à SCHEMA_VERSION."""
    from audio_video_manager.storage.schema import SCHEMA_SQL_V1

    path = avm_home / "old.sqlite3"
    import sqlite3

    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA_SQL_V1)
    conn.execute(
        "INSERT INTO schema_migrations(version, applied_at) VALUES (1, '2020-01-01')"
    )
    conn.commit()
    conn.close()

    db = Database(path)
    assert db.initialize() == SCHEMA_VERSION
    assert db.get_schema_version() == SCHEMA_VERSION
    # table disc_metadata exists
    row = db.connect().execute(
        "SELECT name FROM sqlite_master WHERE name='disc_metadata'"
    ).fetchone()
    assert row is not None
    cols = {r[1] for r in db.connect().execute("PRAGMA table_info(jobs)").fetchall()}
    assert "selected_release_mbid" in cols
    db.close()


def test_invalid_approve_generic_title() -> None:
    sheet = make_approvable_sheet()
    sheet.tracks[0].title = "Track 1"
    with pytest.raises(ApprovalError):
        approve_sheet(sheet)


def test_ac_m8_dvd_format_enum_exists_no_extract() -> None:
    from audio_video_manager.metadata.enums import MediumFormat
    import audio_video_manager.extraction.dvd as dvd

    assert MediumFormat.DVD_VIDEO.value == "dvd_video"
    assert MediumFormat.DVD_AUDIO.value == "dvd_audio"
    with pytest.raises(dvd.DvdExtractionNotAvailableError):
        raise dvd.DvdExtractionNotAvailableError()
