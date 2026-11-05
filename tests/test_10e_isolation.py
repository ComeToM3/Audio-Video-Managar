from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path
from types import ModuleType
from types import SimpleNamespace

import pytest

from audio_video_manager import diag10e_isolation as isolation
from audio_video_manager.__main__ import main


@pytest.fixture()
def isolated_environment(tmp_path: Path) -> tuple[dict[str, str], Path]:
    repo = tmp_path / "repo"
    venv = repo / ".venv"
    interpreter = venv / "Scripts" / "python.exe"
    interpreter.parent.mkdir(parents=True)
    interpreter.write_bytes(b"python")

    local = tmp_path / "local"
    profile = tmp_path / "profile"
    data = local / "AudioVideoManager-10E"
    library = profile / "Music" / "AVM-10E-Test-Library"
    jobs = data / "jobs-10e"
    logs = data / "logs"
    for directory in (data, library, jobs, logs):
        directory.mkdir(parents=True)
    (data / "avm.sqlite3").write_bytes(b"10e database")
    program_files = tmp_path / "Program Files"
    freac_path = program_files / "freac" / "freaccmd.exe"
    freac_path.parent.mkdir(parents=True)
    freac_path.write_bytes(b"freac")
    (data / "config.json").write_text(
        json.dumps(
            {
                "library_root": str(library),
                "jobs_dir": str(jobs),
                "log_dir": str(logs),
                "freaccmd_path": str(freac_path),
            }
        ),
        encoding="utf-8",
    )
    production = local / "AudioVideoManager"
    (production / "jobs").mkdir(parents=True)
    (production / "logs").mkdir()
    (production / "config.json").write_text("{}", encoding="utf-8")
    (production / "avm.sqlite3").write_bytes(b"production database")
    queen = profile / "Music" / "AVM-06C-Test-Library" / "Queen" / "Greatest Hits (1992)"
    queen.mkdir(parents=True)
    (queen / "01.flac").write_bytes(b"Queen archive")

    env = {
        "AVM_10E_MODE": "1",
        "AVM_10E_REPO_ROOT": str(repo),
        "AVM_DATA_DIR": str(data),
        "AVM_LIBRARY_ROOT": str(library),
        "LOCALAPPDATA": str(local),
        "USERPROFILE": str(profile),
        "ProgramFiles": str(program_files),
        "VIRTUAL_ENV": str(venv),
    }
    return env, interpreter


def test_valid_isolated_environment_passes(isolated_environment) -> None:
    env, interpreter = isolated_environment
    paths = isolation.validate_10e_environment(env, executable=interpreter)
    assert paths.data_root == Path(env["AVM_DATA_DIR"])
    assert paths.library_root == Path(env["AVM_LIBRARY_ROOT"])
    assert paths.jobs_dir == Path(env["AVM_DATA_DIR"]) / "jobs-10e"


def test_missing_sqlite_blocks(isolated_environment) -> None:
    env, interpreter = isolated_environment
    (Path(env["AVM_DATA_DIR"]) / "avm.sqlite3").unlink()
    with pytest.raises(isolation.IsolationError, match="SQLite 10E"):
        isolation.validate_10e_environment(env, executable=interpreter)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("AVM_10E_MODE", None),
        ("AVM_DATA_DIR", None),
        ("AVM_LIBRARY_ROOT", None),
        ("VIRTUAL_ENV", None),
    ],
)
def test_missing_required_environment_blocks(isolated_environment, key, value) -> None:
    env, interpreter = isolated_environment
    if value is None:
        env.pop(key, None)
    with pytest.raises(isolation.IsolationError):
        isolation.validate_10e_environment(env, executable=interpreter)


def test_production_root_is_rejected(isolated_environment) -> None:
    env, interpreter = isolated_environment
    env["AVM_DATA_DIR"] = str(Path(env["LOCALAPPDATA"]) / "AudioVideoManager")
    with pytest.raises(isolation.IsolationError, match="allowlist"):
        isolation.validate_10e_environment(env, executable=interpreter)


@pytest.mark.parametrize("setting", ["jobs_dir", "log_dir", "library_root"])
def test_config_redirect_to_production_is_rejected(isolated_environment, setting) -> None:
    env, interpreter = isolated_environment
    config_path = Path(env["AVM_DATA_DIR"]) / "config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if setting == "library_root":
        redirected = Path(env["USERPROFILE"]) / "Music" / "AVM-06C-Test-Library"
    else:
        redirected = Path(env["LOCALAPPDATA"]) / "AudioVideoManager" / setting
    config[setting] = str(redirected)
    config_path.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(isolation.IsolationError):
        isolation.validate_10e_environment(env, executable=interpreter)


def test_unapproved_freaccmd_path_is_rejected(isolated_environment) -> None:
    env, interpreter = isolated_environment
    config_path = Path(env["AVM_DATA_DIR"]) / "config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    redirected = Path(env["AVM_DATA_DIR"]) / "freaccmd.exe"
    redirected.write_bytes(b"not approved")
    config["freaccmd_path"] = str(redirected)
    config_path.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(isolation.IsolationError, match="allowlist"):
        isolation.validate_10e_environment(env, executable=interpreter)


def test_hardlink_to_production_is_rejected(isolated_environment) -> None:
    env, interpreter = isolated_environment
    source = Path(env["LOCALAPPDATA"]) / "AudioVideoManager" / "avm.sqlite3"
    destination = Path(env["AVM_LIBRARY_ROOT"]) / "linked.sqlite3"
    try:
        os.link(source, destination)
    except OSError as exc:
        pytest.skip(f"Hardlinks indisponibles dans cet environnement : {exc}")
    with pytest.raises(isolation.IsolationError, match="lié aux données de production"):
        isolation.validate_10e_environment(env, executable=interpreter)


def test_reparse_attribute_is_detected() -> None:
    assert isolation._is_reparse_point(
        SimpleNamespace(st_mode=stat.S_IFDIR, st_file_attributes=0x400)
    )


def test_symlink_in_isolated_tree_is_rejected(isolated_environment) -> None:
    env, interpreter = isolated_environment
    target = Path(env["USERPROFILE"]) / "Music" / "AVM-06C-Test-Library"
    link = Path(env["AVM_LIBRARY_ROOT"]) / "linked-production"
    try:
        os.symlink(target, link, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"Creation de symlink indisponible : {exc}")
    with pytest.raises(isolation.IsolationError, match="Lien symbolique/jonction"):
        isolation.validate_10e_environment(env, executable=interpreter)
    assert isolation._is_reparse_point(
        SimpleNamespace(st_mode=stat.S_IFLNK, st_file_attributes=0)
    )


def test_noncanonical_path_is_rejected(isolated_environment) -> None:
    env, interpreter = isolated_environment
    env["AVM_DATA_DIR"] += "\\."
    with pytest.raises(isolation.IsolationError, match="non canonique"):
        isolation.validate_10e_environment(env, executable=interpreter)


def test_10e_entry_refuses_before_importing_ui(monkeypatch, capsys) -> None:
    monkeypatch.setenv("AVM_10E_MODE", "1")
    monkeypatch.delenv("AVM_10E_REPO_ROOT", raising=False)
    assert main([]) == 2
    assert "AVM-10E REFUS" in capsys.readouterr().err


def test_normal_entry_point_remains_unchanged(monkeypatch) -> None:
    monkeypatch.delenv("AVM_10E_MODE", raising=False)
    fake_ui = ModuleType("audio_video_manager.ui.main_window")
    fake_ui.run_app = lambda argv: 17
    monkeypatch.setitem(sys.modules, "audio_video_manager.ui.main_window", fake_ui)
    assert main(["avm"]) == 17