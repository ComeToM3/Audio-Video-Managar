"""Cover Art Archive — aperçu / statut, sans invention."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable

from audio_video_manager.logging_setup import get_logger
from audio_video_manager.metadata.musicbrainz_client import _rate_limit

log = get_logger("metadata.cover_art")

CAA_BASE = "https://coverartarchive.org"


@dataclass(frozen=True)
class CoverArtResult:
    release_id: str
    status: str  # confirmed | unavailable | error
    front_url: str | None
    thumbnail_url: str | None
    message: str
    source: str = "Cover Art Archive"


def fetch_cover_art_info(
    release_mbid: str,
    *,
    urlopen_fn: Callable[..., object] | None = None,
) -> CoverArtResult:
    """
    GET /release/{mbid}/ — suit les redirections CAA.

    Pas de téléchargement binaire obligatoire ; URLs pour aperçu UI.
    """
    url = f"{CAA_BASE}/release/{release_mbid}"
    opener = urlopen_fn or urllib.request.urlopen
    _rate_limit()
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "AudioVideoManager/0.4.0 (local; music archive)",
            "Accept": "application/json",
        },
        method="GET",
    )
    try:
        with opener(req, timeout=30) as resp:  # type: ignore[arg-type]
            raw = resp.read()
            status_code = getattr(resp, "status", None) or getattr(resp, "code", 200)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return CoverArtResult(
                release_id=release_mbid,
                status="unavailable",
                front_url=None,
                thumbnail_url=None,
                message="Aucune pochette Cover Art Archive (404).",
            )
        return CoverArtResult(
            release_id=release_mbid,
            status="error",
            front_url=None,
            thumbnail_url=None,
            message=f"CAA HTTP {exc.code}: {exc.reason}",
        )
    except urllib.error.URLError as exc:
        return CoverArtResult(
            release_id=release_mbid,
            status="error",
            front_url=None,
            thumbnail_url=None,
            message=f"CAA réseau: {exc.reason}",
        )

    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return CoverArtResult(
            release_id=release_mbid,
            status="error",
            front_url=None,
            thumbnail_url=None,
            message=f"CAA JSON invalide: {exc}",
        )

    images = data.get("images") or []
    front_url = None
    thumb = None
    for img in images:
        if img.get("front"):
            front_url = img.get("image")
            thumbs = img.get("thumbnails") or {}
            thumb = thumbs.get("500") or thumbs.get("250") or thumbs.get("large")
            break
    if front_url is None and images:
        img0 = images[0]
        front_url = img0.get("image")
        thumbs = img0.get("thumbnails") or {}
        thumb = thumbs.get("500") or thumbs.get("250")

    if front_url:
        log.info("CAA cover OK release=%s", release_mbid)
        return CoverArtResult(
            release_id=release_mbid,
            status="confirmed",
            front_url=str(front_url),
            thumbnail_url=str(thumb) if thumb else str(front_url),
            message=f"Pochette CAA trouvée (HTTP {status_code}).",
        )
    return CoverArtResult(
        release_id=release_mbid,
        status="unavailable",
        front_url=None,
        thumbnail_url=None,
        message="Réponse CAA sans image front.",
    )
