"""ADB export for published AVM FLAC tracks; no Android-wide scanning."""

from __future__ import annotations

import hashlib
import os
import re
import shlex
import shutil
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable

from audio_video_manager.metadata.path_preview import sanitize_segment
from audio_video_manager.storage.android_transfers import (
    AndroidTransferRow,
    begin_android_transfer,
    finish_android_transfer,
    list_android_transfers,
    mark_android_transfer_verified,
)
from audio_video_manager.storage.catalog import list_releases, list_tracks_for_release
from audio_video_manager.storage.database import Database

ANDROID_MUSIC_ROOT = "/sdcard/Music/AudioVideoManager"
_SHA256_RE = re.compile(r"\b([0-9a-fA-F]{64})\b")
_MISSING_REMOTE_RE = re.compile(r"No such file or directory|not found", re.IGNORECASE)


class AndroidExportError(RuntimeError):
    """ADB or safe-path operation failed."""


@dataclass(frozen=True)
class AndroidDevice:
    serial: str
    state: str
    details: str

    @property
    def label(self) -> str:
        model = re.search(r"\bmodel:([^\s]+)", self.details)
        suffix = f" ({model.group(1).replace('_', ' ')})" if model else ""
        return f"{self.serial}{suffix} — {self.state}"


@dataclass(frozen=True)
class AndroidCandidate:
    track_id: int
    release_id: int
    artist: str
    album: str
    year: int | None
    number: int
    title: str
    source_path: str
    source_size_bytes: int
    source_mtime_ns: int
    relative_path: str
    destination_path: str
    source_sha256: str | None
    status: str
    detail: str = ""

    @property
    def file_label(self) -> str:
        return f"{self.number:02d} - {self.title}"


@dataclass(frozen=True)
class TransferSummary:
    succeeded: int
    failed: int
    skipped: int


ProgressCallback = Callable[[str, int, int], None]


def find_adb_executable(manual_path: str | None = None) -> Path | None:
    if manual_path:
        candidate = Path(manual_path).expanduser()
        if candidate.is_file() and candidate.name.casefold() == "adb.exe":
            return candidate.resolve()

    roots = [
        os.environ.get("ANDROID_SDK_ROOT"),
        os.environ.get("ANDROID_HOME"),
    ]
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        roots.append(str(Path(local_app_data) / "Android" / "Sdk"))
    for root in roots:
        if root:
            candidate = Path(root) / "platform-tools" / "adb.exe"
            if candidate.is_file():
                return candidate.resolve()
    found = shutil.which("adb.exe") or shutil.which("adb")
    return Path(found).resolve() if found else None


def _creation_flags() -> int:
    return getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0


def _run(
    arguments: list[str], *, timeout: float = 30
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            arguments,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=_creation_flags(),
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise AndroidExportError(str(exc)) from exc


def list_android_devices(adb_path: Path) -> list[AndroidDevice]:
    result = _run([str(adb_path), "devices", "-l"], timeout=15)
    if result.returncode:
        raise AndroidExportError((result.stderr or result.stdout).strip())
    devices: list[AndroidDevice] = []
    for line in result.stdout.splitlines():
        fields = line.strip().split(maxsplit=2)
        if len(fields) >= 2 and fields[0] != "List":
            devices.append(AndroidDevice(fields[0], fields[1], fields[2] if len(fields) > 2 else ""))
    return devices


def _adb_serial(
    adb_path: Path, serial: str, *arguments: str, timeout: float = 30
) -> subprocess.CompletedProcess[str]:
    return _run(
        [str(adb_path), "-s", serial, *arguments],
        timeout=timeout,
    )


def _ensure_device(adb_path: Path, serial: str) -> None:
    matching = next(
        (device for device in list_android_devices(adb_path) if device.serial == serial),
        None,
    )
    if matching is None:
        raise AndroidExportError("L’appareil sélectionné est déconnecté.")
    if matching.state != "device":
        raise AndroidExportError(
            f"L’appareil {serial} est à l’état « {matching.state} »; transfert arrêté."
        )


def _shell(
    adb_path: Path, serial: str, command: str, *, timeout: float = 30
) -> subprocess.CompletedProcess[str]:
    return _adb_serial(adb_path, serial, "shell", command, timeout=timeout)


def _remote_size(adb_path: Path, serial: str, remote_path: str) -> int | None:
    command = f"toybox stat -c %s -- {shlex.quote(remote_path)}"
    result = _shell(adb_path, serial, command)
    output = result.stdout.strip()
    if result.returncode:
        error = (result.stderr or output).strip()
        if _MISSING_REMOTE_RE.search(error):
            return None
        raise AndroidExportError(error or "Impossible de vérifier la destination Android.")
    try:
        return int(output.splitlines()[-1])
    except (ValueError, IndexError) as exc:
        raise AndroidExportError(f"Taille distante invalide : {output!r}") from exc


def _remote_sha256(adb_path: Path, serial: str, remote_path: str) -> str:
    command = f"toybox sha256sum {shlex.quote(remote_path)}"
    result = _shell(adb_path, serial, command)
    if result.returncode:
        raise AndroidExportError((result.stderr or result.stdout).strip())
    match = _SHA256_RE.search(result.stdout)
    if not match:
        raise AndroidExportError("SHA-256 distant illisible.")
    return match.group(1).lower()


def _remote_info(
    adb_path: Path, serial: str, remote_path: str
) -> tuple[int, str] | None:
    size = _remote_size(adb_path, serial, remote_path)
    if size is None:
        return None
    return size, _remote_sha256(adb_path, serial, remote_path)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _source_relative_path(source_path: str, library_root: Path) -> PurePosixPath:
    source = Path(source_path).resolve(strict=True)
    root = library_root.resolve(strict=True)
    try:
        relative = source.relative_to(root)
    except ValueError as exc:
        raise AndroidExportError("Le FLAC indexé est hors de la bibliothèque configurée.") from exc
    parts = relative.parts
    if not parts or any(
        part in {"", ".", ".."}
        or any(ord(char) < 32 for char in part)
        or "/" in part
        or "\\" in part
        for part in parts
    ):
        raise AndroidExportError("Chemin FLAC non sûr pour la destination Android.")
    return PurePosixPath(*parts)


def _remote_destination(relative_path: str) -> str:
    return f"{ANDROID_MUSIC_ROOT}/{relative_path}"


def _versioned_relative(relative_path: str, sha256: str) -> str:
    path = PurePosixPath(relative_path)
    return str(path.with_name(f"{path.stem} (AVM-{sha256[:8]}){path.suffix}"))


def _free_bytes(adb_path: Path, serial: str) -> int:
    result = _shell(adb_path, serial, "df -k /sdcard/Music")
    if result.returncode:
        raise AndroidExportError((result.stderr or result.stdout).strip())
    for line in reversed(result.stdout.splitlines()):
        fields = line.split()
        if len(fields) >= 5 and fields[-3].isdigit():
            return int(fields[-3]) * 1024
    raise AndroidExportError("Espace libre Android illisible.")


def _latest_per_track(
    transfers: list[AndroidTransferRow],
) -> dict[int, AndroidTransferRow]:
    latest: dict[int, AndroidTransferRow] = {}
    for transfer in transfers:
        if transfer.track_id not in latest:
            latest[transfer.track_id] = transfer
    return latest


def scan_android_candidates(
    db: Database,
    *,
    adb_path: Path,
    serial: str,
    library_root: Path,
    progress: ProgressCallback | None = None,
) -> list[AndroidCandidate]:
    _ensure_device(adb_path, serial)
    releases = list_releases(db, limit=500)
    transfers = list_android_transfers(db, serial)
    latest = _latest_per_track(transfers)
    tracks_by_release = {
        release.id: list_tracks_for_release(db, release.id) for release in releases
    }
    total = sum(len(items) for items in tracks_by_release.values())
    candidates: list[AndroidCandidate] = []
    checked = 0

    for release in releases:
        for track in tracks_by_release[release.id]:
            checked += 1
            if progress:
                progress(f"Vérification : {track.title or track.number}", checked, total)
            if track.id is None or not track.path:
                continue
            source = Path(track.path)
            history = latest.get(track.id)
            if not source.is_file():
                candidates.append(AndroidCandidate(
                    track.id, release.id, release.album_artist or "Artiste inconnu",
                    release.album or "Album sans titre", release.year, track.number,
                    track.title or "Sans titre", str(source), 0, 0,
                    history.destination_path.removeprefix(ANDROID_MUSIC_ROOT + "/")
                    if history else "",
                    history.destination_path if history else "",
                    history.source_sha256 if history else None,
                    "source_missing", "Fichier FLAC source absent",
                ))
                continue

            try:
                relative = _source_relative_path(track.path, library_root)
            except (OSError, AndroidExportError) as exc:
                stat = source.stat()
                candidates.append(AndroidCandidate(
                    track.id, release.id, release.album_artist or "Artiste inconnu",
                    release.album or "Album sans titre", release.year, track.number,
                    track.title or "Sans titre", str(source), stat.st_size, stat.st_mtime_ns,
                    "", "", None, "source_invalid", str(exc),
                ))
                continue

            stat = source.stat()
            source_sha = None
            if history:
                if (
                    history.source_path == str(source)
                    and history.source_size_bytes == stat.st_size
                    and history.source_mtime_ns == stat.st_mtime_ns
                ):
                    source_sha = history.source_sha256
                else:
                    source_sha = _sha256_file(source)

            changed = bool(history and source_sha != history.source_sha256)
            current_relative = (
                _versioned_relative(str(relative), source_sha)
                if changed and source_sha
                else str(relative)
            )
            destination = _remote_destination(current_relative)
            status = "new"
            detail = "Jamais transféré"

            if history:
                old_info = _remote_info(adb_path, serial, history.destination_path)
                old_matches = old_info == (
                    history.source_size_bytes,
                    history.source_sha256,
                )
                if old_info is not None and not old_matches and not changed:
                    status, detail = "conflict", "Le fichier Android diffère de l’historique"
                    destination = history.destination_path
                elif changed:
                    new_info = _remote_info(adb_path, serial, destination)
                    if new_info is not None:
                        if new_info == (stat.st_size, source_sha):
                            matching_history = next(
                                (item for item in transfers
                                 if item.track_id == track.id
                                 and item.source_sha256 == source_sha
                                 and item.destination_path == destination),
                                None,
                            )
                            if matching_history and matching_history.status != "succeeded":
                                mark_android_transfer_verified(
                                    db, device_serial=serial,
                                    transfer_id=matching_history.id,
                                )
                            status, detail = "transferred", "Cette version est vérifiée"
                        else:
                            status, detail = "conflict", "La destination de cette version est occupée"
                    else:
                        status, detail = "modified", "Version source modifiée"
                elif old_matches:
                    if history.status != "succeeded":
                        mark_android_transfer_verified(
                            db, device_serial=serial, transfer_id=history.id
                        )
                    status, detail = "transferred", "Présent et vérifié sur Android"
                    destination = history.destination_path
                else:
                    status, detail = "missing", "Transfert précédent absent"
                    destination = history.destination_path
            else:
                remote_size = _remote_size(adb_path, serial, destination)
                if remote_size is not None:
                    status, detail = "conflict", "Un fichier inconnu occupe cette destination"

            if history and not changed and status in {"new", "missing"}:
                if history.status == "failed":
                    status, detail = "failed", history.error_summary or "Échec précédent"
                elif history.status == "pending":
                    status, detail = "failed", "Transfert interrompu; reprise manuelle possible"

            candidates.append(AndroidCandidate(
                track.id, release.id, release.album_artist or "Artiste inconnu",
                release.album or "Album sans titre", release.year, track.number,
                track.title or "Sans titre", str(source), stat.st_size, stat.st_mtime_ns,
                current_relative, destination, source_sha, status, detail,
            ))
    return candidates


def _push_file(adb_path: Path, serial: str, source: Path, staging_path: str) -> None:
    result = _run(
        [str(adb_path), "-s", serial, "push", str(source), staging_path],
        timeout=3600,
    )
    if result.returncode:
        raise AndroidExportError((result.stderr or result.stdout).strip())


def transfer_android_candidates(
    db: Database,
    *,
    adb_path: Path,
    serial: str,
    library_root: Path,
    candidates: list[AndroidCandidate],
    progress: ProgressCallback | None = None,
) -> TransferSummary:
    selected = [
        item for item in candidates
        if item.status in {"new", "missing", "modified", "failed"}
    ]
    skipped = len(candidates) - len(selected)
    succeeded = 0
    failed = 0
    if not selected:
        return TransferSummary(0, 0, skipped)

    total_bytes = sum(Path(item.source_path).stat().st_size for item in selected)
    _ensure_device(adb_path, serial)
    if _free_bytes(adb_path, serial) < total_bytes:
        raise AndroidExportError("Espace libre Android insuffisant pour la sélection.")

    for index, item in enumerate(selected, start=1):
        if progress:
            progress(f"Transfert : {item.artist} — {item.file_label}", index - 1, len(selected))
        source = Path(item.source_path)
        staging_path: str | None = None
        source_sha: str | None = None
        attempt_started = False
        try:
            _ensure_device(adb_path, serial)
            if not source.is_file():
                raise AndroidExportError("Fichier FLAC source absent.")
            relative = _source_relative_path(str(source), library_root)
            stat = source.stat()
            source_sha = _sha256_file(source)
            relative_name = item.relative_path or str(relative)
            if item.source_sha256 and source_sha != item.source_sha256:
                relative_name = _versioned_relative(str(relative), source_sha)
            destination = _remote_destination(relative_name)

            if _remote_size(adb_path, serial, destination) is not None:
                raise AndroidExportError("Conflit : la destination existe; aucun écrasement effectué.")

            parent = str(PurePosixPath(destination).parent)
            result = _shell(adb_path, serial, f"mkdir -p {shlex.quote(parent)}")
            if result.returncode:
                raise AndroidExportError((result.stderr or result.stdout).strip())

            while True:
                staging_path = f"{destination}.avm-{uuid.uuid4().hex}.partial"
                if _remote_size(adb_path, serial, staging_path) is None:
                    break

            begin_android_transfer(
                db,
                device_serial=serial,
                track_id=item.track_id,
                source_path=str(source),
                source_sha256=source_sha,
                source_size_bytes=stat.st_size,
                source_mtime_ns=stat.st_mtime_ns,
                destination_path=destination,
                staging_path=staging_path,
            )
            attempt_started = True
            _push_file(adb_path, serial, source, staging_path)
            staged_info = _remote_info(adb_path, serial, staging_path)
            if staged_info != (stat.st_size, source_sha):
                raise AndroidExportError("Le fichier temporaire ne correspond pas au FLAC source.")

            _ensure_device(adb_path, serial)
            if _remote_size(adb_path, serial, destination) is not None:
                raise AndroidExportError("Conflit apparu avant promotion; le temporaire est conservé.")
            move = _shell(
                adb_path,
                serial,
                f"toybox mv -n -- {shlex.quote(staging_path)} {shlex.quote(destination)}",
            )
            if move.returncode:
                raise AndroidExportError((move.stderr or move.stdout).strip())
            final_info = _remote_info(adb_path, serial, destination)
            staged_remaining = _remote_size(adb_path, serial, staging_path)
            if final_info != (stat.st_size, source_sha) or staged_remaining is not None:
                raise AndroidExportError(
                    "La promotion sans remplacement n’est pas confirmée; aucun succès enregistré."
                )
            finish_android_transfer(
                db,
                device_serial=serial,
                track_id=item.track_id,
                source_sha256=source_sha,
                succeeded=True,
                staging_path=None,
            )
            succeeded += 1
        except Exception as exc:  # noqa: BLE001
            failed += 1
            if attempt_started and source_sha is not None:
                try:
                    finish_android_transfer(
                        db,
                        device_serial=serial,
                        track_id=item.track_id,
                        source_sha256=source_sha,
                        succeeded=False,
                        staging_path=staging_path,
                        error_summary=str(exc),
                    )
                except Exception:
                    pass
            if progress:
                progress(f"Échec : {item.file_label} — {exc}", index, len(selected))
            continue
        if progress:
            progress(f"Vérifié : {item.file_label}", index, len(selected))
    return TransferSummary(succeeded, failed, skipped)