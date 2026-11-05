"""Configuration locale persistante (JSON)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from audio_video_manager.paths import (
    default_config_path,
    default_jobs_dir,
    default_library_root,
    default_log_dir,
)


@dataclass
class AppConfig:
    """Paramètres persistés côté utilisateur."""

    freaccmd_path: str = ""
    freac_install_dir: str = ""
    library_root: str = field(default_factory=lambda: str(default_library_root()))
    jobs_dir: str = field(default_factory=lambda: str(default_jobs_dir()))
    log_dir: str = field(default_factory=lambda: str(default_log_dir()))
    filename_pattern: str = "{AlbumArtist}/{Album} ({Year})/{NN} - {Title}"
    flac_compression: int = 5
    eject_after_rip: bool = False
    last_drive_number: int = 0
    # AVM-04C — départage éditions MB (jamais une preuve de provenance)
    preferred_release_country: str = "CA"
    # Futur : auto-approbation haute confiance — désactivé par défaut (D-015)
    auto_approve_high_confidence: bool = False
    # AVM-08B — bibliothèque : "qml" (défaut) ou "widgets" (repli)
    library_ui_mode: str = "qml"

    def resolved_freaccmd(self) -> Path | None:
        raw = (self.freaccmd_path or "").strip()
        if not raw:
            return None
        path = Path(raw)
        return path if path.is_file() else None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AppConfig:
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        filtered = {k: v for k, v in data.items() if k in known}
        base = cls()
        for key, value in filtered.items():
            setattr(base, key, value)
        return base


def load_config(path: Path | None = None) -> AppConfig:
    cfg_path = path or default_config_path()
    if not cfg_path.is_file():
        return AppConfig()
    try:
        raw = json.loads(cfg_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return AppConfig()
    if not isinstance(raw, dict):
        return AppConfig()
    return AppConfig.from_dict(raw)


def save_config(config: AppConfig, path: Path | None = None) -> Path:
    cfg_path = path or default_config_path()
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(
        json.dumps(config.to_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return cfg_path
