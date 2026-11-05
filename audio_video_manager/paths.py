"""Chemins applicatifs locaux (Windows-first, portable via override)."""

from __future__ import annotations

import os
from pathlib import Path


APP_NAME = "AudioVideoManager"


def user_data_dir() -> Path:
    """Répertoire de données utilisateur (config, logs, DB, jobs)."""
    override = os.environ.get("AVM_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    local = os.environ.get("LOCALAPPDATA")
    if local:
        return Path(local) / APP_NAME
    return Path.home() / ".local" / "share" / APP_NAME


def default_config_path() -> Path:
    return user_data_dir() / "config.json"


def default_log_dir() -> Path:
    return user_data_dir() / "logs"


def default_db_path() -> Path:
    return user_data_dir() / "avm.sqlite3"


def default_jobs_dir() -> Path:
    return user_data_dir() / "jobs"


def default_cover_cache_dir() -> Path:
    """Cache local dédié des pochettes (R1 / A7) — hors jobs."""
    return user_data_dir() / "cache" / "covers"


def default_library_root() -> Path:
    override = os.environ.get("AVM_LIBRARY_ROOT")
    if override:
        return Path(override).expanduser().resolve()
    home = Path.home()
    return home / "Music" / "AudioVideoManager"


def ensure_app_dirs(
    *,
    data_dir: Path | None = None,
    log_dir: Path | None = None,
    jobs_dir: Path | None = None,
) -> None:
    """Crée les dossiers applicatifs (pas la bibliothèque musicale)."""
    base = data_dir or user_data_dir()
    base.mkdir(parents=True, exist_ok=True)
    (log_dir or default_log_dir()).mkdir(parents=True, exist_ok=True)
    (jobs_dir or default_jobs_dir()).mkdir(parents=True, exist_ok=True)
    default_cover_cache_dir().mkdir(parents=True, exist_ok=True)
