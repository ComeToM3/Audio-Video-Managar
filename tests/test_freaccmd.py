from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from audio_video_manager.extraction.cd import (
    CommandProbe,
    discover_freaccmd_candidates,
    probe_freaccmd,
    validate_freaccmd,
)


def test_probe_absent_when_no_candidates(avm_home: Path, tmp_path: Path) -> None:
    missing = tmp_path / "no-such" / "freaccmd.exe"
    status = probe_freaccmd(
        configured_path=missing,
        freac_install_dir=tmp_path / "empty-freac",
        run_probes=True,
        include_system_defaults=False,
        include_path_lookup=False,
    )
    assert status.found is False
    assert status.path is None
    assert status.help_probe is None
    assert status.list_drives_probe is None
    assert "introuvable" in status.message.lower()
    assert status.ok_for_phase1 is False


def test_discover_ignores_missing_files(tmp_path: Path) -> None:
    ghost = tmp_path / "freaccmd.exe"
    found = discover_freaccmd_candidates(
        configured_path=ghost,
        include_system_defaults=False,
        include_path_lookup=False,
    )
    assert ghost not in found


def test_discover_finds_configured_file(tmp_path: Path) -> None:
    exe = tmp_path / "freaccmd.exe"
    exe.write_bytes(b"not-a-real-binary")
    found = discover_freaccmd_candidates(
        configured_path=exe,
        include_system_defaults=False,
        include_path_lookup=False,
    )
    assert found == [exe]


def test_validate_captures_real_subprocess_result(tmp_path: Path) -> None:
    """Ne pas inventer stdout : on mocke subprocess.run pour un retour contrôlé."""
    exe = tmp_path / "freaccmd.exe"
    exe.write_text("", encoding="utf-8")

    class FakeCompleted:
        returncode = 0
        stdout = "FAKE_HELP_OUTPUT_FOR_TEST"
        stderr = ""

    with patch("audio_video_manager.extraction.cd.subprocess.run", return_value=FakeCompleted()):
        help_probe, drives_probe = validate_freaccmd(exe)

    assert isinstance(help_probe, CommandProbe)
    assert help_probe.stdout == "FAKE_HELP_OUTPUT_FOR_TEST"
    assert help_probe.returncode == 0
    assert drives_probe.argv[-1] == "--list-drives"


def test_probe_found_runs_probes(tmp_path: Path) -> None:
    exe = tmp_path / "freaccmd.exe"
    exe.write_text("", encoding="utf-8")

    class FakeCompleted:
        returncode = 0
        stdout = "list"
        stderr = ""

    with patch("audio_video_manager.extraction.cd.subprocess.run", return_value=FakeCompleted()):
        status = probe_freaccmd(configured_path=exe, run_probes=True)

    assert status.found is True
    assert status.path == exe
    assert status.help_probe is not None
    assert status.help_probe.stdout == "list"
