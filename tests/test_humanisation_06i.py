"""AVM-06I — libellés lecteurs, progression titres, erreurs humanisées."""

from __future__ import annotations

from pathlib import Path

from audio_video_manager.extraction.drives import CdDrive
from audio_video_manager.storage.catalog import JobRow
from audio_video_manager.ui.progress_labels import (
    humanize_error_for_user,
    map_progress_message,
    parse_track_number_from_progress,
    progress_step_index,
)
from audio_video_manager.ui.sections.library_page import _album_cover_path


def test_drive_friendly_label_with_letter() -> None:
    d = CdDrive(number=0, device_path="1:0:0", designation="ATAPI iHAS324   C")
    assert d.friendly_label("D:") == "Lecteur CD/DVD (D:)"
    assert d.friendly_label("d") == "Lecteur CD/DVD (D:)"
    assert "ATAPI" not in d.friendly_label("D:")
    # Sans lettre fiable — pas d’invention
    assert d.friendly_label(None) == "Lecteur CD/DVD n°1"
    # Technique conservé pour info-bulle / logs
    assert "iHAS324" in d.label()


def test_parse_freac_track_file_lines() -> None:
    assert parse_track_number_from_progress("Processing file: 3.flac") == 3
    assert parse_track_number_from_progress("Processing file: track03.flac") == 3
    assert parse_track_number_from_progress("track 5 / 17") == 5
    assert parse_track_number_from_progress("01.flac") == 1
    assert parse_track_number_from_progress("hello") is None


def test_map_progress_uses_approved_titles() -> None:
    titles = ["We Will Rock You", "We Are the Champions", "Killer Queen"]
    msg = map_progress_message(
        "Processing file: 3.flac",
        track_titles=titles,
        track_total=17,
    )
    assert msg == "Piste 3/17 — Killer Queen"
    assert "flac" not in msg.casefold()
    assert "processing" not in msg.casefold()


def test_map_progress_honest_fallback_without_title() -> None:
    msg = map_progress_message(
        "Processing file: 9.flac",
        track_titles=["A", "B"],
        track_total=17,
    )
    assert msg.startswith("Piste 9/17")
    assert "non déterminé" in msg.casefold()


def test_map_progress_never_invents_percent_in_label() -> None:
    msg = map_progress_message("Processing file: 1.flac", track_titles=["X"], track_total=10)
    assert "%" not in msg


def test_progress_step_index_for_track_line() -> None:
    assert progress_step_index("Processing file: 2.flac") == 1  # Extraction audio


def test_humanize_error_separates_technical() -> None:
    raw = (
        "L’extraction audio a échoué.\n"
        "Action possible : consultez les journaux.\n"
        "Détail technique : freaccmd returncode=4294967293"
    )
    summary, tech = humanize_error_for_user(raw)
    assert "4294967293" not in summary
    assert tech and "4294967293" in tech
    assert "échoué" in summary.casefold() or "extraction" in summary.casefold()


def test_job_files_recoverable_flag() -> None:
    job = JobRow(
        id="x",
        state="Failed",
        step="Failed",
        workdir=str(Path.cwd()),  # exists
        started_at=None,
        finished_at=None,
        error_summary="err",
        mode="normal",
        collision_policy="rename",
        warnings_json=None,
        library_path=None,
    )
    assert job.files_recoverable is True
    job2 = JobRow(
        id="y",
        state="Completed",
        step="Completed",
        workdir=str(Path.cwd()),
        started_at=None,
        finished_at=None,
        error_summary=None,
        mode="normal",
        collision_policy=None,
        warnings_json=None,
        library_path=None,
    )
    assert job2.files_recoverable is False


def test_album_cover_path_detects_cover_jpg(tmp_path: Path) -> None:
    album = tmp_path / "Queen" / "Hits"
    album.mkdir(parents=True)
    cover = album / "cover.jpg"
    cover.write_bytes(b"\xff\xd8\xff\xd9")
    assert _album_cover_path(str(album)) == cover
    assert _album_cover_path(str(tmp_path / "missing")) is None
