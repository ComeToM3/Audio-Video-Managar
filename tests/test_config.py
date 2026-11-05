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
