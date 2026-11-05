"""Adaptateur CdRipper — extraction CD via freaccmd (sous-processus)."""

from __future__ import annotations

import os
import re
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Protocol

from audio_video_manager.diagnostics.failure_kinds import freac_user_message
from audio_video_manager.diagnostics.freac_logs import persist_freac_logs
from audio_video_manager.extraction.drives import CdDrive, list_cd_drives
from audio_video_manager.logging_setup import get_logger

log = get_logger("extraction.cd_ripper")

ProgressCallback = Callable[[str, float | None], None]
# message, fraction 0..1 or None if unknown


@dataclass(frozen=True)
class RipRequest:
    freaccmd: Path
    drive_number: int
    workdir: Path
    tracks: str = "all"
    flac_compression: int = 5
    eject_after_rip: bool = False
    pattern: str = "<track>"
    timeout_sec: float | None = None  # None = pas de timeout global


@dataclass
class RipResult:
    success: bool
    cancelled: bool
    returncode: int | None
    argv: tuple[str, ...]
    stdout: str
    stderr: str
    flac_files: list[Path] = field(default_factory=list)
    error: str | None = None
    workdir: Path | None = None


class CdRipper(Protocol):
    def list_drives(self) -> list[CdDrive]: ...

    def rip(
        self,
        request: RipRequest,
        *,
        on_progress: ProgressCallback | None = None,
        cancel_event: threading.Event | None = None,
    ) -> RipResult: ...


def create_job_workdir(jobs_root: Path, job_id: str | None = None) -> tuple[str, Path]:
    """
    Crée un dossier job neuf ``{jobs_root}/{job_id}/rip``.

    Refuse d'utiliser un dossier déjà peuplé (pas d'écrasement).
    """
    jid = job_id or uuid.uuid4().hex
    root = Path(jobs_root) / jid
    rip_dir = root / "rip"
    if rip_dir.exists() and any(rip_dir.iterdir()):
        raise FileExistsError(f"Workdir non vide, refus d'écrasement : {rip_dir}")
    rip_dir.mkdir(parents=True, exist_ok=True)
    return jid, rip_dir


def build_freaccmd_rip_argv(request: RipRequest) -> list[str]:
    """Construit la ligne de commande rip FLAC (sans DSP explicite côté CLI)."""
    if not 0 <= request.flac_compression <= 8:
        raise ValueError("flac_compression doit être entre 0 et 8")
    # freaccmd n'accepte que --pattern=<pat> ou -p <pat> (AVM-06C-F2) :
    # deux jetons « --pattern » + « <track> » font traiter « <track> » comme fichier.
    argv = [
        str(request.freaccmd),
        "--encoder=flac",
        f"--drive={request.drive_number}",
        f"--track={request.tracks}",
        "-d",
        str(request.workdir),
        f"--pattern={request.pattern}",
        "--",
        "-c",
        str(request.flac_compression),
    ]
    if request.eject_after_rip:
        # Inséré avant -- pour rester option freaccmd (pas encodeur).
        argv.insert(-3, "--eject")
    return argv


_PROGRESS_RE = re.compile(
    r"(\d{1,3})\s*%|track\s+(\d+)\s*/\s*(\d+)",
    re.IGNORECASE,
)


def _parse_progress_fraction(line: str) -> float | None:
    match = _PROGRESS_RE.search(line)
    if not match:
        return None
    if match.group(1) is not None:
        try:
            pct = int(match.group(1))
        except ValueError:
            return None
        return max(0.0, min(1.0, pct / 100.0))
    if match.group(2) and match.group(3):
        try:
            cur, total = int(match.group(2)), int(match.group(3))
        except ValueError:
            return None
        if total <= 0:
            return None
        return max(0.0, min(1.0, cur / total))
    return None


def collect_flac_files(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    return sorted(p for p in directory.rglob("*.flac") if p.is_file())


class FreacCdRipper:
    """Implémentation CdRipper basée sur freaccmd."""

    def __init__(self, freaccmd: Path) -> None:
        self.freaccmd = Path(freaccmd)

    def list_drives(self) -> list[CdDrive]:
        drives, probe = list_cd_drives(self.freaccmd)
        if probe.error:
            log.warning("list-drives error: %s", probe.error)
        log.info("Lecteurs détectés : %s", [d.label() for d in drives])
        return drives

    def rip(
        self,
        request: RipRequest,
        *,
        on_progress: ProgressCallback | None = None,
        cancel_event: threading.Event | None = None,
    ) -> RipResult:
        workdir = Path(request.workdir)
        if not workdir.is_dir():
            raise FileNotFoundError(f"Workdir inexistant : {workdir}")
        if any(workdir.iterdir()):
            raise FileExistsError(
                f"Workdir non vide, refus d'écrasement : {workdir}"
            )

        argv = build_freaccmd_rip_argv(request)
        log.info("Démarrage rip argv=%s", argv)
        if on_progress:
            on_progress("Démarrage freaccmd…", 0.0)

        creationflags = 0
        if os.name == "nt":
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        stdout_chunks: list[str] = []
        stderr_chunks: list[str] = []
        cancelled = False
        returncode: int | None = None
        error: str | None = None

        try:
            proc = subprocess.Popen(
                argv,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=creationflags,
            )
        except OSError as exc:
            return RipResult(
                success=False,
                cancelled=False,
                returncode=None,
                argv=tuple(argv),
                stdout="",
                stderr="",
                error=str(exc),
                workdir=workdir,
            )

        assert proc.stdout is not None
        assert proc.stderr is not None

        def _read_stderr() -> None:
            for line in proc.stderr:
                stderr_chunks.append(line)
                if on_progress:
                    on_progress(line.rstrip("\n"), None)

        stderr_thread = threading.Thread(target=_read_stderr, daemon=True)
        stderr_thread.start()

        deadline = (
            time.monotonic() + request.timeout_sec
            if request.timeout_sec is not None
            else None
        )

        try:
            while True:
                if cancel_event is not None and cancel_event.is_set():
                    cancelled = True
                    log.warning("Annulation demandée — terminaison freaccmd")
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait(timeout=5)
                    break

                if deadline is not None and time.monotonic() > deadline:
                    error = f"timeout after {request.timeout_sec}s"
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait(timeout=5)
                    break

                line = proc.stdout.readline()
                if line:
                    stdout_chunks.append(line)
                    frac = _parse_progress_fraction(line)
                    if on_progress:
                        on_progress(line.rstrip("\n"), frac)
                    continue

                returncode = proc.poll()
                if returncode is not None:
                    rest = proc.stdout.read()
                    if rest:
                        stdout_chunks.append(rest)
                    break
                time.sleep(0.05)
        finally:
            stderr_thread.join(timeout=2)
            if returncode is None:
                returncode = proc.poll()
                if returncode is None and proc.returncode is not None:
                    returncode = proc.returncode

        stdout = "".join(stdout_chunks)
        stderr = "".join(stderr_chunks)
        flacs = collect_flac_files(workdir)

        try:
            persist_freac_logs(
                workdir,
                argv=tuple(argv),
                returncode=returncode,
                stdout=stdout,
                stderr=stderr,
                extra={"flac_count": len(flacs), "cancelled": cancelled},
            )
        except OSError as exc:
            log.warning("Impossible d’écrire les journaux fre:ac : %s", exc)

        # Politique stricte : returncode == 0 requis (AVM-06E/F/G — pas d’assouplissement).
        ok_code = returncode == 0
        success = (not cancelled) and ok_code and bool(flacs) and error is None
        if cancelled:
            error = error or (
                "Extraction annulée. "
                f"Détail technique : cancelled returncode={returncode}"
            )
        elif not ok_code and error is None:
            user_msg, _tech = freac_user_message(
                returncode,
                flac_count=len(flacs),
                stderr_tail=stderr[-500:] if stderr else "",
            )
            error = user_msg
        elif ok_code and not flacs:
            error = (
                "L’extraction s’est terminée sans fichier FLAC dans le dossier temporaire.\n"
                "Action possible : vérifiez le lecteur et freac_stdout.txt du job.\n"
                f"Détail technique : freaccmd returncode=0, flac_count=0"
            )
            success = False

        if on_progress:
            on_progress(
                "Terminé" if success else (error or "Échec"),
                1.0 if success else None,
            )

        return RipResult(
            success=success,
            cancelled=cancelled,
            returncode=returncode,
            argv=tuple(argv),
            stdout=stdout,
            stderr=stderr,
            flac_files=flacs,
            error=error,
            workdir=workdir,
        )
