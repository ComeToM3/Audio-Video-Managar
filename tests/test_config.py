from __future__ import annotations

from pathlib import Path

from audio_video_manager.config import AppConfig, load_config, save_config
from audio_video_manager.paths import default_config_path


def test_default_config_roundtrip(avm_home: Path) -> None:
    cfg = AppConfig(
        freaccmd_path="",
        library_root=str(avm_home / "Music"),
        jobs_dir=str(avm_home / "jobs"),
        log_dir=str(avm_home / "logs"),
    )
    path = save_config(cfg)
    assert path == default_config_path()
    assert path.is_file()

    loaded = load_config()
    assert loaded.library_root == cfg.library_root
    assert loaded.jobs_dir == cfg.jobs_dir
    assert loaded.filename_pattern.startswith("{AlbumArtist}/")


def test_load_missing_returns_defaults(avm_home: Path) -> None:
    cfg = load_config()
    assert isinstance(cfg, AppConfig)
    assert cfg.freaccmd_path == ""
    assert cfg.library_root


def test_legacy_qml_config_key_is_ignored(tmp_path: Path) -> None:
    cfg = AppConfig.from_dict({"library_root": str(tmp_path / "lib"), "library_ui_mode": "qml"})
    assert cfg.library_root == str(tmp_path / "lib")
    assert not hasattr(cfg, "library_ui_mode")


def test_new_library_uses_known_music_folder_and_existing_path_is_preserved(
    monkeypatch, tmp_path: Path
) -> None:
    import audio_video_manager.paths as paths

    monkeypatch.delenv("AVM_LIBRARY_ROOT", raising=False)
    music_dir = tmp_path / "Redirected Music"
    monkeypatch.setattr(paths, "_windows_known_music_dir", lambda: music_dir)

    assert paths.default_library_root() == music_dir / "AudioVideoManager"

    existing = tmp_path / "AVM-06C-Test-Library"
    config = AppConfig.from_dict({"library_root": str(existing)})
    assert config.library_root == str(existing)
    assert not existing.exists()
