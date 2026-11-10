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


def _windows_known_music_dir() -> Path | None:
    if os.name != "nt":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class Guid(ctypes.Structure):
            _fields_ = [
                ("data1", wintypes.DWORD),
                ("data2", wintypes.WORD),
                ("data3", wintypes.WORD),
                ("data4", wintypes.BYTE * 8),
            ]

        folder_id = Guid(
            0x4BD8D571,
            0x6D19,
            0x48D3,
            (wintypes.BYTE * 8)(0xBE, 0x97, 0x42, 0x22, 0x20, 0x08, 0x0E, 0x43),
        )
        music_path = ctypes.c_wchar_p()
        shell32 = ctypes.windll.shell32
        shell32.SHGetKnownFolderPath.argtypes = [
            ctypes.POINTER(Guid),
            wintypes.DWORD,
            wintypes.HANDLE,
            ctypes.POINTER(ctypes.c_wchar_p),
        ]
        shell32.SHGetKnownFolderPath.restype = ctypes.c_long
        result = shell32.SHGetKnownFolderPath(
            ctypes.byref(folder_id), 0, None, ctypes.byref(music_path)
        )
        try:
            if result == 0 and music_path.value:
                return Path(music_path.value)
        finally:
            if ctypes.cast(music_path, ctypes.c_void_p).value:
                ole32 = ctypes.windll.ole32
                ole32.CoTaskMemFree.argtypes = [ctypes.c_void_p]
                ole32.CoTaskMemFree.restype = None
                ole32.CoTaskMemFree(ctypes.cast(music_path, ctypes.c_void_p))
    except (AttributeError, OSError, TypeError, ValueError):
        return None
    return None


def default_library_root() -> Path:
    override = os.environ.get("AVM_LIBRARY_ROOT")
    if override:
        return Path(override).expanduser().resolve()
    music_dir = _windows_known_music_dir() or (Path.home() / "Music")
    return music_dir / APP_NAME


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
