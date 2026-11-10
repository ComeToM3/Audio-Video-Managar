"""Téléchargement / cache local des pochettes (R1)."""

from __future__ import annotations

import hashlib
import urllib.request
from pathlib import Path

from PySide6.QtGui import QImage

from audio_video_manager.paths import default_cover_cache_dir


def cached_cover_path(url: str, cache_dir: Path | None = None) -> Path:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]
    ext = ".jpg"
    low = url.casefold()
    if ".png" in low:
        ext = ".png"
    root = cache_dir or default_cover_cache_dir()
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{digest}{ext}"


def fetch_cover_to_cache(
    url: str,
    *,
    cache_dir: Path | None = None,
    timeout: float = 60.0,
) -> Path | None:
    """Télécharge si absent ; retourne le chemin local ou None."""
    if not url:
        return None
    dest = cached_cover_path(url, cache_dir)
    if dest.is_file() and dest.stat().st_size > 0:
        try:
            if not QImage.fromData(dest.read_bytes()).isNull():
                return dest
        except OSError:
            pass
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "AudioVideoManager/0.5.0 (local; cover cache)"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
    except Exception:  # noqa: BLE001
        return None
    if not data or QImage.fromData(data).isNull():
        return None
    dest.write_bytes(data)
    return dest
