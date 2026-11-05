"""AVM-06G — journaux fre:ac, messages FR, décodage, géométrie pochette."""

from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import patch

from audio_video_manager.diagnostics.failure_kinds import (
    FailureKind,
    freac_signed_code,
    freac_user_message,
)
from audio_video_manager.diagnostics.freac_logs import persist_freac_logs
from audio_video_manager.extraction.cd_ripper import FreacCdRipper, RipRequest
from audio_video_manager.library.cover_geometry import analyze_cover_bytes, jpeg_dimensions
from audio_video_manager.library.tags import apply_flac_tags
from audio_video_manager.metadata.enums import CoverStatus, FieldTrust
from audio_video_manager.metadata.factories import make_approvable_sheet
from audio_video_manager.metadata.models import FieldMeta
from audio_video_manager.metadata.validation import approve_sheet
from audio_video_manager.orchestration.archive_job import match_flacs_to_tracks
from audio_video_manager.metadata.validation import ApprovalError
from audio_video_manager.verification.flac_decode import decode_flac_full, find_flac_decode_tool
from tests.flac_fixtures import write_minimal_flac

_JPEG = (
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t"
    b"\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e"
    b"\x1d\x1a\x1c\x1c $.\' \",#\x1c\x1c(7),01444\x1f\'9=82<.342"
    b"\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00"
    b"\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00"
    b"\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b"
    b"\xff\xc4\x00\xb5\x10\x00\x02\x01\x03\x03\x02\x04\x03\x05\x05\x04\x04"
    b"\x00\x00\x01}\x01\x02\x03\x00\x04\x11\x05\x12!1A\x06\x13Qa\x07\"q"
    b"\x142\x81\x91\xa1\x08#B\xb1\xc1\x15R\xd1\xf0$3br\x82\t\n\x16\x17"
    b"\x18\x19\x1a%&\'()*456789:CDEFGHIJSTUVWXYZcdefghijstuvwxyz"
    b"\x83\x84\x85\x86\x87\x88\x89\x8a\x92\x93\x94\x95\x96\x97\x98\x99"
    b"\x9a\xa2\xa3\xa4\xa5\xa6\xa7\xa8\xa9\xaa\xb2\xb3\xb4\xb5\xb6\xb7"
    b"\xb8\xb9\xba\xc2\xc3\xc4\xc5\xc6\xc7\xc8\xc9\xca\xd2\xd3\xd4\xd5"
    b"\xd6\xd7\xd8\xd9\xda\xe1\xe2\xe3\xe4\xe5\xe6\xe7\xe8\xe9\xea\xf1"
    b"\xf2\xf3\xf4\xf5\xf6\xf7\xf8\xf9\xfa"
    b"\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xaa\xff\xd9"
)


def test_freac_signed_code_and_user_message_keeps_technical() -> None:
    assert freac_signed_code(4294967293) == -3
    msg, tech = freac_user_message(4294967293, flac_count=17)
    assert "4294967293" in tech
    assert "17" in msg
    assert "récupérables" in msg.casefold() or "présents" in msg
    assert FailureKind.EXTRACTION.value == "extraction"
    assert "Action possible" in msg
    assert "Détail technique" in msg


def test_persist_freac_logs(tmp_path: Path) -> None:
    rip = tmp_path / "job" / "rip"
    rip.mkdir(parents=True)
    paths = persist_freac_logs(
        rip,
        argv=["freaccmd", "--encoder=flac"],
        returncode=4294967293,
        stdout="Processing...\n",
        stderr="File not found: <track>\n",
    )
    assert paths["stdout"].read_text(encoding="utf-8").startswith("Processing")
    assert "<track>" in paths["stderr"].read_text(encoding="utf-8")
    meta = paths["meta"].read_text(encoding="utf-8")
    assert "4294967293" in meta
    assert paths["stdout"].parent == tmp_path / "job"


def test_ripper_persists_logs_and_french_error_on_nonzero(tmp_path: Path) -> None:
    empty = tmp_path / "rip"
    empty.mkdir()
    exe = tmp_path / "freaccmd.exe"
    exe.write_text("", encoding="utf-8")

    class FakeStream:
        def __init__(self, text: str) -> None:
            self._io = io.StringIO(text)

        def readline(self) -> str:
            return self._io.readline()

        def read(self) -> str:
            return self._io.read()

        def __iter__(self):
            return self._io

    class FakeProc2:
        def __init__(self) -> None:
            self.stdout = FakeStream("done\n")
            self.stderr = FakeStream("File not found: <track>\n")
            self.returncode = 4294967293

        def poll(self) -> int:
            return 4294967293

        def wait(self, timeout=None) -> int:
            return 4294967293

    with patch(
        "audio_video_manager.extraction.cd_ripper.subprocess.Popen",
        return_value=FakeProc2(),
    ):
        result = FreacCdRipper(exe).rip(
            RipRequest(freaccmd=exe, drive_number=0, workdir=empty)
        )
    assert result.success is False
    assert result.returncode == 4294967293
    assert result.error is not None
    assert "returncode=4294967293" in result.error
    assert "extraction" in result.error.casefold() or "fre:ac" in result.error.casefold()
    # workdir named rip → logs on parent (job root)
    assert (tmp_path / "freac_stderr.txt").is_file()
    assert (tmp_path / "freac_meta.json").is_file()
    assert "<track>" in (tmp_path / "freac_stderr.txt").read_text(encoding="utf-8")


def test_match_rejects_duplicate_track_numbers(tmp_path: Path) -> None:
    a = write_minimal_flac(tmp_path / "01.flac")
    b = write_minimal_flac(tmp_path / "1 - copy.flac")
    try:
        match_flacs_to_tracks([a, b], 2)
        raise AssertionError("expected ApprovalError")
    except ApprovalError as exc:
        assert "piste" in str(exc).casefold()


def test_cover_geometry_square_thumbnail() -> None:
    dims = jpeg_dimensions(_JPEG)
    assert dims == (1, 1)
    geom = analyze_cover_bytes(_JPEG)
    assert geom.square is True
    assert any("1×1" in n or "vignette" in n or "carré" in n for n in geom.notes)


def test_embedded_cover_sets_dimensions(tmp_path: Path) -> None:
    sheet = make_approvable_sheet(tracks=1)
    sheet.edition.cover_status = CoverStatus.CONFIRMED
    sheet.edition.cover_path_or_url = "https://example.test/cover.jpg"
    sheet.edition.field_meta["cover_status"] = FieldMeta(trust=FieldTrust.CONFIRMED)
    approve_sheet(sheet, note="t")
    flac = write_minimal_flac(tmp_path / "t.flac")
    apply_flac_tags(flac, sheet, sheet.tracks[0], cover_image=_JPEG, cover_mime="image/jpeg")
    from mutagen.flac import FLAC

    audio = FLAC(str(flac))
    assert audio.pictures
    assert audio.pictures[0].width == 1
    assert audio.pictures[0].height == 1


def test_decode_skips_explicitly_without_tool(tmp_path: Path, monkeypatch) -> None:
    flac = write_minimal_flac(tmp_path / "a.flac")
    monkeypatch.delenv("AVM_FFMPEG", raising=False)
    with patch(
        "audio_video_manager.verification.flac_decode.find_flac_decode_tool",
        return_value=None,
    ):
        r = decode_flac_full(flac)
    assert r.attempted is False
    assert r.ok is False  # AVM-10D : absence ≠ succès
    assert "ffmpeg introuvable" in r.message


def test_decode_ok_when_ffmpeg_present(tmp_path: Path) -> None:
    tool = find_flac_decode_tool()
    if tool is None:
        return
    flac = write_minimal_flac(tmp_path / "b.flac")
    r = decode_flac_full(flac, tool=tool)
    assert r.attempted is True
    assert r.ok is True


def test_publish_runtime_error_classified_as_publish(tmp_path: Path) -> None:
    from audio_video_manager.library.publish import CollisionPolicy
    from audio_video_manager.orchestration.archive_job import run_archive_job
    from audio_video_manager.storage import Database

    sheet = make_approvable_sheet(tracks=1)
    approve_sheet(sheet, note="t")
    jobs = tmp_path / "jobs"
    lib = tmp_path / "Music"
    src = tmp_path / "src"
    src.mkdir()
    staged = [write_minimal_flac(src / "01.flac")]
    db = Database(tmp_path / "avm.sqlite3")
    db.initialize()
    with patch(
        "audio_video_manager.orchestration.archive_job.publish_album",
        side_effect=RuntimeError("Publish échoué, rollback tenté: boom"),
    ):
        report = run_archive_job(
            metadata=sheet,
            library_root=lib,
            jobs_root=jobs,
            db=db,
            confirm_publish=True,
            collision_policy=CollisionPolicy.RENAME,
            staged_flac_files=staged,
            cover_bytes=None,
        )
    assert report.state == "Failed"
    assert report.failure_kind == FailureKind.PUBLISH
    err = (report.error or "").casefold()
    assert "publication" in err or "interrompue" in err
    assert "Détail technique" in (report.error or "")
