"""Journalisation locale structurée avec rotation."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from audio_video_manager.paths import default_log_dir, ensure_app_dirs

_CONFIGURED = False


def setup_logging(
    log_dir: Path | None = None,
    *,
    level: int = logging.INFO,
    console: bool = True,
) -> Path:
    """Configure le logger racine `avm` une seule fois par processus."""
    global _CONFIGURED
    directory = log_dir or default_log_dir()
    ensure_app_dirs(log_dir=directory)
    log_file = directory / "avm.log"

    root = logging.getLogger("avm")
    root.setLevel(level)
    root.handlers.clear()

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=1_048_576,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)
    root.addHandler(file_handler)

    if console:
        stream = logging.StreamHandler()
        stream.setFormatter(formatter)
        stream.setLevel(level)
        root.addHandler(stream)

    _CONFIGURED = True
    root.debug("Logging initialisé → %s", log_file)
    return log_file


def get_logger(name: str = "avm") -> logging.Logger:
    if not name.startswith("avm"):
        name = f"avm.{name}"
    return logging.getLogger(name)
