"""Finalisation locale d'une vidéo existante, sans lecture du disque source."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from audio_video_manager.storage.database import Database


def _sha256(path: Path, cancel_event: threading.Event | None = None) -> str:
    digest = hashlib.sha256()
    if cancel_event is not None and cancel_event.is_set():
        raise InterruptedError("Indexation annulée; le fichier publié est conservé.")
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            if cancel_event is not None and cancel_event.is_set():
                raise InterruptedError("Indexation annulée; le fichier publié est conservé.")
            digest.update(block)
    return digest.hexdigest()


def _inspect_decodable(
    path: Path, ffmpeg: Path, ffprobe: Path, *, audio_only: bool = False,
    decode_runner: Callable[[list[str], float], tuple[int, str]] | None = None,
) -> tuple[dict, list, list, float]:
    probe = subprocess.run(
        [str(ffprobe), "-v", "error", "-show_format", "-show_streams", "-show_chapters", "-of", "json", str(path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180, check=False,
    )
    if probe.returncode:
        raise RuntimeError(f"Inspection vidéo impossible : {probe.stderr[-1000:]}")
    payload = json.loads(probe.stdout)
    streams = payload.get("streams", [])
    chapters = payload.get("chapters", [])
    info = payload.get("format", {})
    required = "audio" if audio_only else "video"
    if not isinstance(streams, list) or not any(item.get("codec_type") == required for item in streams):
        raise ValueError(f"Le fichier ne contient pas de flux {required} exploitable.")
    if audio_only and any(item.get("codec_type") == "video" for item in streams):
        raise ValueError("Le fichier audio contient un flux vidéo inattendu.")
    if not isinstance(chapters, list) or "matroska" not in str(info.get("format_name", "")):
        raise ValueError("Le fichier n'est pas un Matroska vidéo valide.")
    duration = float(info.get("duration") or 0)
    if not 0 < duration < float("inf"):
        raise ValueError("Durée vidéo absente ou invalide.")
    argv = [str(ffmpeg), "-hide_banner", "-nostdin", "-v", "error", "-xerror", "-i", str(path),
            "-map", "0:v?" if audio_only else "0:v", "-map", "0:a?", "-f", "null", "-"]
    if decode_runner is None:
        decode = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=4 * 3600, check=False)
        code, stderr = decode.returncode, decode.stderr
    else:
        code, stderr = decode_runner(argv, duration)
    if code:
        raise RuntimeError(f"Décodage incomplet : {stderr[-1000:]}")
    return info, streams, chapters, duration


def index_published_video(
    db: Database, path: Path, ffmpeg: Path, *, cancel_event: threading.Event | None = None,
    on_progress: Callable[[str, float | None], None] | None = None,
    decode_runner: Callable[[list[str], float], tuple[int, str]] | None = None,
    reservation_id: int | None = None,
) -> int:
    path = Path(path).expanduser().resolve(strict=True)
    if not path.is_file() or path.suffix.casefold() not in {".mkv", ".mka"}:
        raise ValueError("Fichier Matroska publié introuvable.")
    ffmpeg = Path(ffmpeg).expanduser().resolve(strict=True)
    ffprobe = ffmpeg.with_name("ffprobe.exe" if ffmpeg.suffix.casefold() == ".exe" else "ffprobe")
    if not ffprobe.is_file():
        raise FileNotFoundError("ffprobe doit être présent à côté de FFmpeg.")
    before = path.stat()
    if on_progress:
        on_progress("Vérification du fichier publié…", 0.85)
    digest = _sha256(path, cancel_event)
    info, streams, chapters, duration = _inspect_decodable(
        path, ffmpeg, ffprobe, audio_only=path.suffix.casefold() == ".mka", decode_runner=decode_runner,
    )
    if _sha256(path, cancel_event) != digest:
        raise RuntimeError("Le fichier a changé pendant sa validation; indexation refusée.")
    after = path.stat()
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
        raise RuntimeError("Le fichier a changé pendant sa validation; indexation refusée.")
    if cancel_event is not None and cancel_event.is_set():
        raise InterruptedError("Indexation annulée; le fichier publié est conservé.")
    conn = db.connect()
    try:
        values = (digest, after.st_size, after.st_mtime_ns, str(info["format_name"]), duration,
                  json.dumps(streams, ensure_ascii=False), json.dumps(chapters, ensure_ascii=False))
        if reservation_id is None:
            cursor = conn.execute(
                "INSERT INTO videos(sha256, size_bytes, mtime_ns, format, duration_seconds, streams_json, chapters_json, "
                "path, validation_status, publication_state, imported_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (*values, str(path), "decodable", "published", datetime.now(timezone.utc).isoformat()),
            )
            video_id = int(cursor.lastrowid)
        else:
            cursor = conn.execute(
                "UPDATE videos SET sha256 = ?, size_bytes = ?, mtime_ns = ?, format = ?, duration_seconds = ?, "
                "streams_json = ?, chapters_json = ?, validation_status = 'decodable', publication_state = 'published' "
                "WHERE id = ? AND path = ? AND publication_state = 'pending' AND sha256 LIKE 'intent:%'",
                (*values, reservation_id, str(path)),
            )
            if cursor.rowcount != 1:
                raise ValueError("La réservation de publication a changé; fichier conservé.")
            video_id = reservation_id
        conn.commit()
    except sqlite3.IntegrityError as exc:
        conn.rollback()
        raise ValueError("Cette vidéo ou destination est déjà indexée ou en attente.") from exc
    except Exception:
        conn.rollback()
        raise
    if on_progress:
        on_progress("Média ajouté à la bibliothèque.", 1.0)
    return video_id


def reserve_dvd_publication(db: Database, destination: Path) -> int:
    destination = Path(destination).expanduser()
    if not destination.is_absolute() or destination.suffix.casefold() not in {".mkv", ".mka"}:
        raise ValueError("Destination Matroska absolue requise.")
    destination = destination.parent.resolve(strict=True) / destination.name
    if destination.exists() or destination.is_symlink():
        raise FileExistsError("La destination existe déjà; aucun écrasement.")
    conn = db.connect()
    try:
        cursor = conn.execute(
            "INSERT INTO videos(path, sha256, size_bytes, mtime_ns, format, duration_seconds, streams_json, chapters_json, "
            "validation_status, publication_state, imported_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (str(destination), "intent:" + uuid.uuid4().hex, 0, 0, "matroska", 0, "[]", "[]",
             "incomplete", "pending", datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
    except sqlite3.IntegrityError as exc:
        conn.rollback()
        raise ValueError("Cette destination est déjà indexée ou en attente.") from exc
    except Exception:
        conn.rollback()
        raise
    return int(cursor.lastrowid)


def reconcile_video(db: Database, video_id: int) -> None:
    conn = db.connect()
    row = conn.execute("SELECT path, sha256, publication_state FROM videos WHERE id = ?", (video_id,)).fetchone()
    if row is None:
        raise ValueError("Entrée vidéo introuvable.")
    path = Path(row["path"])
    if not path.is_file():
        raise FileNotFoundError("Le fichier attendu est introuvable; aucune modification de l'index.")
    before = path.stat()
    if _sha256(path) != row["sha256"]:
        raise ValueError("Le fichier ne correspond pas à l'empreinte attendue; index inchangé.")
    stat = path.stat()
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns):
        raise ValueError("Le fichier a changé pendant sa vérification; index inchangé.")
    try:
        conn.execute("BEGIN IMMEDIATE")
        cursor = conn.execute(
            "UPDATE videos SET publication_state = 'published', size_bytes = ?, mtime_ns = ? "
            "WHERE id = ? AND path = ? AND sha256 = ?",
            (stat.st_size, stat.st_mtime_ns, video_id, row["path"], row["sha256"]),
        )
        if cursor.rowcount != 1:
            raise ValueError("L'entrée a changé pendant la vérification; index inchangé.")
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def remove_missing_pending_video(db: Database, video_id: int) -> None:
    conn = db.connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT path, publication_state FROM videos WHERE id = ?", (video_id,)).fetchone()
        if row is None or row["publication_state"] != "pending":
            raise ValueError("Aucune publication en attente pour cette entrée.")
        path = Path(row["path"])
        if path.exists() or path.is_symlink():
            raise ValueError("Un fichier existe à cet emplacement; entrée conservée.")
        conn.execute("DELETE FROM videos WHERE id = ? AND publication_state = 'pending'", (video_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def finalize_video(db: Database, source: Path, destination: Path, ffmpeg: Path) -> int:
    """Copie et valide un MKV avant publication et indexation sans écrasement."""
    source = Path(source).expanduser().resolve(strict=True)
    destination = Path(destination).expanduser()
    if source.suffix.casefold() != ".mkv" or not source.is_file():
        raise ValueError("Choisissez un fichier MKV existant.")
    if not destination.is_absolute() or destination.suffix.casefold() != ".mkv":
        raise ValueError("Choisissez une destination MKV absolue.")
    destination = destination.parent.resolve(strict=True) / destination.name
    if destination.exists() or destination.is_symlink():
        raise FileExistsError("La destination existe déjà; aucun écrasement.")
    ffmpeg = Path(ffmpeg).expanduser().resolve(strict=True)
    ffprobe = ffmpeg.with_name("ffprobe.exe" if ffmpeg.suffix.casefold() == ".exe" else "ffprobe")
    if not ffprobe.is_file():
        raise FileNotFoundError("ffprobe doit être présent à côté de FFmpeg.")

    with tempfile.TemporaryDirectory(prefix=".avm-video-", dir=destination.parent) as temp:
        staged = Path(temp) / "video.mkv"
        with source.open("rb") as input_file, staged.open("xb") as output_file:
            before = os.fstat(input_file.fileno())
            shutil.copyfileobj(input_file, output_file, length=1024 * 1024)
            after = os.fstat(input_file.fileno())
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise RuntimeError("La source a changé pendant la copie; publication refusée.")
        digest = _sha256(staged)
        info, streams, chapters, duration = _inspect_decodable(staged, ffmpeg, ffprobe)
        if _sha256(staged) != digest:
            raise RuntimeError("La copie a changé pendant la validation; publication refusée.")

        conn = db.connect()
        staged_stat = staged.stat()
        try:
            cursor = conn.execute(
                "INSERT INTO videos(path, sha256, size_bytes, mtime_ns, format, duration_seconds, streams_json, chapters_json, "
                "validation_status, publication_state, imported_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (str(destination), digest, staged_stat.st_size, staged_stat.st_mtime_ns, str(info["format_name"]), duration,
                 json.dumps(streams, ensure_ascii=False), json.dumps(chapters, ensure_ascii=False),
                 "decodable", "pending", datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()
        except sqlite3.IntegrityError as exc:
            conn.rollback()
            raise ValueError("Cette vidéo ou destination est déjà indexée ou en attente.") from exc
        except Exception:
            conn.rollback()
            raise
        video_id = int(cursor.lastrowid)
        try:
            conn.execute("BEGIN IMMEDIATE")
            reserved = conn.execute("SELECT 1 FROM videos WHERE id = ? AND publication_state = 'pending'", (video_id,)).fetchone()
            if reserved is None:
                raise RuntimeError("La réservation de publication a disparu; aucun fichier publié.")
            os.link(staged, destination)
        except Exception:
            conn.rollback()
            conn.execute("DELETE FROM videos WHERE id = ? AND publication_state = 'pending'", (video_id,))
            conn.commit()
            raise
        try:
            conn.execute("UPDATE videos SET publication_state = 'published' WHERE id = ?", (video_id,))
            conn.commit()
        except Exception as exc:
            conn.rollback()
            raise RuntimeError(
                f"Fichier publié mais indexation incomplète; vérifiez l'entrée en attente : {destination}"
            ) from exc
        return video_id