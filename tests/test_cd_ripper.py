from __future__ import annotations

import io
import threading
from pathlib import Path
from unittest.mock import patch

from audio_video_manager.extraction.cd_ripper import (
    FreacCdRipper,
    RipRequest,
    build_freaccmd_rip_argv,
    create_job_workdir,
)
from tests.flac_fixtures import write_minimal_flac


def test_build_argv_flac_no_eject_by_default(tmp_path: Path) -> None:
    exe = tmp_path / "freaccmd.exe"
    exe.write_text("", encoding="utf-8")
    out = tmp_path / "out"
    argv = build_freaccmd_rip_argv(
        RipRequest(freaccmd=exe, drive_number=0, workdir=out)
    )
    assert "--encoder=flac" in argv
    assert "--drive=0" in argv
    assert "--track=all" in argv
    assert "--eject" not in argv
    assert argv[argv.index("--") + 1 : argv.index("--") + 3] == ["-c", "5"]


def test_build_argv_pattern_equals_form_avm06c_f2(tmp_path: Path) -> None:
    """Régression F2 : un seul jeton --pattern=<track>, jamais « <track> » isolé."""
    exe = tmp_path / "freaccmd.exe"
    out = tmp_path / "ripdir"
    argv = build_freaccmd_rip_argv(
        RipRequest(
            freaccmd=exe,
            drive_number=0,
            workdir=out,
            pattern="<track>",
            flac_compression=5,
        )
    )
    assert argv == [
        str(exe),
        "--encoder=flac",
        "--drive=0",
        "--track=all",
        "-d",
        str(out),
        "--pattern=<track>",
        "--",
        "-c",
        "5",
    ]
    assert "--pattern" not in argv
    assert "<track>" not in argv


def test_build_argv_eject_when_enabled(tmp_path: Path) -> None:
    exe = tmp_path / "freaccmd.exe"
    req = RipRequest(
        freaccmd=exe,
        drive_number=1,
        workdir=tmp_path / "out",
        eject_after_rip=True,
    )
    argv = build_freaccmd_rip_argv(req)
    assert "--eject" in argv
    assert argv.index("--eject") < argv.index("--")
    assert "--pattern=<track>" in argv


def test_create_job_workdir_refuses_non_empty(tmp_path: Path) -> None:
    jid, rip_dir = create_job_workdir(tmp_path, job_id="abc123")
    assert jid == "abc123"
    (rip_dir / "existing.flac").write_text("x", encoding="utf-8")
    try:
        create_job_workdir(tmp_path, job_id="abc123")
        raise AssertionError("expected FileExistsError")
    except FileExistsError:
        pass


def test_rip_success_with_mocked_process(tmp_path: Path) -> None:
    exe = tmp_path / "freaccmd.exe"
    exe.write_text("", encoding="utf-8")
    workdir = tmp_path / "rip-out"
    workdir.mkdir()

    class FakeProc:
        def __init__(self) -> None:
            self.stdout = io.StringIO(
                "Encoding track 1/2 50%\nEncoding track 2/2 100%\n"
            )
            self.stderr = io.StringIO("")
            self.returncode = 0
            self._done = False

        def poll(self):
            if self.stdout.tell() >= len(self.stdout.getvalue()):
                self._done = True
                return 0
            return None

        def terminate(self) -> None:
            self._done = True
            self.returncode = -1

        def kill(self) -> None:
            self._done = True

        def wait(self, timeout=None) -> int:
            return int(self.returncode)

    def fake_popen(*args, **kwargs):
        write_minimal_flac(workdir / "01.flac")
        return FakeProc()

    ripper = FreacCdRipper(exe)
    with patch("audio_video_manager.extraction.cd_ripper.subprocess.Popen", fake_popen):
        result = ripper.rip(
            RipRequest(freaccmd=exe, drive_number=0, workdir=workdir),
        )

    assert result.success is True
    assert result.cancelled is False
    assert result.returncode == 0
    assert len(result.flac_files) == 1


def test_rip_refuses_non_empty_workdir(tmp_path: Path) -> None:
    exe = tmp_path / "freaccmd.exe"
    exe.write_text("", encoding="utf-8")
    workdir = tmp_path / "rip-out"
    workdir.mkdir()
    (workdir / "x.flac").write_text("nope", encoding="utf-8")
    ripper = FreacCdRipper(exe)
    try:
        ripper.rip(RipRequest(freaccmd=exe, drive_number=0, workdir=workdir))
        raise AssertionError("expected FileExistsError")
    except FileExistsError:
        pass


def test_rip_cancel(tmp_path: Path) -> None:
    exe = tmp_path / "freaccmd.exe"
    exe.write_text("", encoding="utf-8")
    workdir = tmp_path / "rip-out"
    workdir.mkdir()
    cancel = threading.Event()
    cancel.set()

    class FakeProc:
        def __init__(self) -> None:
            self.stdout = io.StringIO("")
            self.stderr = io.StringIO("")
            self.returncode: int | None = None
            self.terminated = False

        def poll(self):
            return -1 if self.terminated else None

        def terminate(self) -> None:
            self.terminated = True
            self.returncode = -1

        def kill(self) -> None:
            self.terminated = True
            self.returncode = -1

        def wait(self, timeout=None) -> int:
            return -1

    with patch(
        "audio_video_manager.extraction.cd_ripper.subprocess.Popen",
        return_value=FakeProc(),
    ):
        result = FreacCdRipper(exe).rip(
            RipRequest(freaccmd=exe, drive_number=0, workdir=workdir),
            cancel_event=cancel,
        )

    assert result.cancelled is True
    assert result.success is False
