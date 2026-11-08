"""Verrou fichier d’extraction — cycle de vie fre:ac (AVM-10B/10C).

AVM-10C : identité PID via create_time Windows pour détecter la réutilisation de PID.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from audio_video_manager.logging_setup import get_logger

log = get_logger("orchestration.rip_lock")

LOCK_FILENAME = ".avm-rip.lock"
RECOVERY_LOCK_FILENAME = ".avm-recovery.lock"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass(frozen=True)
class RipLockInfo:
    path: Path
    pid: int | None
    job_id: str | None
    started_at: str | None
    pid_alive: bool | None
    create_time: int | None = None
    identity_ok: bool | None = None


def job_root_from_workdir(workdir: Path) -> Path:
    p = Path(workdir)
    if p.name.lower() == "rip" and p.parent.name:
        return p.parent
    return p


def candidate_media_dirs(workdir: Path) -> list[Path]:
    root = Path(workdir)
    dirs: list[Path] = []
    if root.is_dir():
        dirs.append(root)
    rip = root / "rip"
    if rip.is_dir():
        dirs.append(rip)
    seen: set[str] = set()
    out: list[Path] = []
    for d in dirs:
        key = str(d.resolve()) if d.exists() else str(d)
        if key not in seen:
            seen.add(key)
            out.append(d)
    return out


def lock_path_for_rip_dir(rip_dir: Path) -> Path:
    return Path(rip_dir) / LOCK_FILENAME


def current_process_create_time() -> int | None:
    """FILETIME 64-bit de création du process courant (Windows), sinon None."""
    return process_create_time(os.getpid())


def process_create_time(pid: int) -> int | None:
    if pid <= 0:
        return None
    if os.name != "nt":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
        if not handle:
            return None

        class FILETIME(ctypes.Structure):
            _fields_ = [("dwLowDateTime", wintypes.DWORD), ("dwHighDateTime", wintypes.DWORD)]

        ctime = FILETIME()
        etime = FILETIME()
        ktime = FILETIME()
        utime = FILETIME()
        ok = kernel32.GetProcessTimes(
            handle,
            ctypes.byref(ctime),
            ctypes.byref(etime),
            ctypes.byref(ktime),
            ctypes.byref(utime),
        )
        kernel32.CloseHandle(handle)
        if not ok:
            return None
        return int(ctime.dwLowDateTime) | (int(ctime.dwHighDateTime) << 32)
    except Exception:  # noqa: BLE001
        return None


def _pid_alive(pid: int) -> bool | None:
    if pid <= 0:
        return False
    try:
        if os.name == "nt":
            import ctypes

            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = ctypes.windll.kernel32.OpenProcess(
                PROCESS_QUERY_LIMITED_INFORMATION, False, pid
            )
            if handle:
                ctypes.windll.kernel32.CloseHandle(handle)
                return True
            err = ctypes.windll.kernel32.GetLastError()
            if err == 5:
                return True
            return False
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return None


class RipLockHeldError(RuntimeError):
    """Un verrou de rip actif existe déjà pour ce dossier (autre processus vivant)."""


def write_rip_lock(rip_dir: Path, *, job_id: str) -> Path:
    """
    Acquiert le verrou de rip de façon atomique (``O_CREAT|O_EXCL``).

    AVM-19 (P1-3) : l'ancienne implémentation écrivait le verrou via
    ``Path.write_text`` sans exclusivité OS — deux processus pouvaient chacun
    écrire le fichier et se croire propriétaires. Un verrou existant dont le
    détenteur est mort (ou dont l'identité PID ne correspond plus, cf. réutilisation
    de PID) est repris automatiquement, comme pour le verrou de récupération
    (``try_acquire_recovery_file_lock``). Un verrou détenu par un processus
    actif lève ``RipLockHeldError`` plutôt que d'être silencieusement écrasé.
    """
    path = lock_path_for_rip_dir(rip_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "pid": os.getpid(),
        "job_id": job_id,
        "started_at": _utc_now(),
        "create_time": current_process_create_time(),
    }
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    try:
        fd = os.open(str(path), flags)
    except FileExistsError:
        info = _parse_lock_file(path)
        if is_lock_holder_active(info):
            raise RipLockHeldError(
                f"Verrou de rip déjà détenu (pid={info.pid}, job={info.job_id}) : {path}"
            ) from None
        try:
            path.unlink()
        except OSError:
            pass
        try:
            fd = os.open(str(path), flags)
        except FileExistsError:
            raise RipLockHeldError(
                f"Impossible d'acquérir le verrou de rip (contention) : {path}"
            ) from None
    try:
        os.write(fd, (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))
    finally:
        os.close(fd)
    return path


def clear_rip_lock(rip_dir: Path) -> None:
    path = lock_path_for_rip_dir(rip_dir)
    try:
        if path.is_file():
            path.unlink()
    except OSError as exc:
        log.warning("Impossible de retirer le verrou rip %s : %s", path, exc)


def _parse_lock_file(path: Path) -> RipLockInfo:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return RipLockInfo(path, None, None, None, None, None, None)
    pid = data.get("pid")
    try:
        pid_i = int(pid) if pid is not None else None
    except (TypeError, ValueError):
        pid_i = None
    alive = _pid_alive(pid_i) if pid_i is not None else None
    stored_ct = data.get("create_time")
    try:
        stored_ct_i = int(stored_ct) if stored_ct is not None else None
    except (TypeError, ValueError):
        stored_ct_i = None

    identity_ok: bool | None = None
    if alive is True and pid_i is not None:
        live_ct = process_create_time(pid_i)
        if stored_ct_i is not None and live_ct is not None:
            identity_ok = stored_ct_i == live_ct
            if identity_ok is False:
                # PID réutilisé → traiter comme mort pour la réconciliation
                alive = False
        elif stored_ct_i is None:
            # Verrou pré-10C : pas d’empreinte — on se fie au PID vivant
            identity_ok = True
        else:
            # create_time stocké mais illisible à chaud → incertain
            identity_ok = None

    return RipLockInfo(
        path=path,
        pid=pid_i,
        job_id=str(data["job_id"]) if data.get("job_id") else None,
        started_at=str(data["started_at"]) if data.get("started_at") else None,
        pid_alive=alive,
        create_time=stored_ct_i,
        identity_ok=identity_ok,
    )


def read_rip_lock(workdir: Path | str | None) -> RipLockInfo | None:
    if not workdir:
        return None
    root = Path(workdir)
    for d in candidate_media_dirs(root):
        path = lock_path_for_rip_dir(d)
        if path.is_file():
            return _parse_lock_file(path)
    job_root = job_root_from_workdir(root)
    path = job_root / LOCK_FILENAME
    if path.is_file():
        return _parse_lock_file(path)
    return None


def is_lock_holder_active(info: RipLockInfo | None) -> bool:
    """True seulement si process vivant *et* identité PID cohérente."""
    if info is None:
        return False
    if info.pid_alive is not True:
        return False
    if info.identity_ok is False:
        return False
    return True


# --- Verrou récupération inter-processus ---


def recovery_lock_path(lock_dir: Path) -> Path:
    return Path(lock_dir) / RECOVERY_LOCK_FILENAME


def try_acquire_recovery_file_lock(lock_dir: Path, *, job_id: str) -> Path | None:
    """
    Exclusion interprocessus pour une seule récupération.

    O_EXCL ; si fichier existant avec holder mort / PID réutilisé → reprise du verrou.
    """
    lock_dir = Path(lock_dir)
    lock_dir.mkdir(parents=True, exist_ok=True)
    path = recovery_lock_path(lock_dir)
    payload = {
        "pid": os.getpid(),
        "job_id": job_id,
        "started_at": _utc_now(),
        "create_time": current_process_create_time(),
    }
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    try:
        fd = os.open(str(path), flags)
    except FileExistsError:
        # Stale ?
        if path.is_file():
            info = _parse_lock_file(path)
            if is_lock_holder_active(info):
                return None
            try:
                path.unlink()
            except OSError:
                return None
            try:
                fd = os.open(str(path), flags)
            except FileExistsError:
                return None
        else:
            return None
    try:
        os.write(fd, (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))
    finally:
        os.close(fd)
    return path


def release_recovery_file_lock(lock_dir: Path, *, job_id: str) -> None:
    path = recovery_lock_path(Path(lock_dir))
    if not path.is_file():
        return
    try:
        info = _parse_lock_file(path)
        if info.job_id and info.job_id != job_id:
            # Ne pas voler le verrou d’un autre job
            if is_lock_holder_active(info):
                return
        path.unlink()
    except OSError as exc:
        log.warning("release recovery lock: %s", exc)
