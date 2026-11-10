"""Adaptateur CdRipper — extraction CD via freaccmd (sous-processus)."""

from __future__ import annotations

import os
import queue
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
NO_OUTPUT_STATUS_INTERVAL_SEC = 5.0

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
    r"\b(?:overall|total)\s+(?:progress|encoding)\s*[:=]\s*(\d{1,3})\s*%",
    re.IGNORECASE,
)


def _parse_progress_fraction(line: str) -> float | None:
    match = _PROGRESS_RE.search(line)
    if not match:
        return None
    try:
        pct = int(match.group(1))
    except ValueError:
        return None
    return max(0.0, min(1.0, pct / 100.0))


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
        existing_outputs = [
            path for path in workdir.iterdir() if path.name != ".avm-rip.lock"
        ]
        if existing_outputs:
            raise FileExistsError(
                f"Workdir non vide, refus d'écrasement : {workdir}"
            )

        argv = build_freaccmd_rip_argv(request)
        log.info("Démarrage rip argv=%s", argv)
        if on_progress:
            on_progress("Démarrage de fre:ac…", None)

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

        output_events: queue.Queue[tuple[str, str | None]] = queue.Queue()

        def _read_output(stream_name: str, stream) -> None:
            try:
                for line in stream:
                    output_events.put((stream_name, line))
            finally:
                output_events.put((stream_name, None))

        readers = [
            threading.Thread(
                target=_read_output,
                args=("stdout", proc.stdout),
                daemon=True,
            ),
            threading.Thread(
                target=_read_output,
                args=("stderr", proc.stderr),
                daemon=True,
            ),
        ]
        for reader in readers:
            reader.start()

        deadline = (
            time.monotonic() + request.timeout_sec
            if request.timeout_sec is not None
            else None
        )

        readers_done: set[str] = set()
        last_output_at = time.monotonic()
        last_status_at = last_output_at
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

                try:
                    stream_name, line = output_events.get(timeout=0.1)
                except queue.Empty:
                    now = time.monotonic()
                    if proc.poll() is not None and len(readers_done) == 2:
                        break
                    if (
                        proc.poll() is None
                        and now - last_output_at >= NO_OUTPUT_STATUS_INTERVAL_SEC
                        and now - last_status_at >= NO_OUTPUT_STATUS_INTERVAL_SEC
                    ):
                        silent_for = int(now - last_output_at)
                        if on_progress:
                            on_progress(
                                "fre:ac est actif; aucun nouvel événement observé depuis "
                                f"{silent_for} s.",
                                None,
                            )
                        last_status_at = now
                    continue

                if line is None:
                    readers_done.add(stream_name)
                    if proc.poll() is not None and len(readers_done) == 2:
                        break
                    continue

                last_output_at = time.monotonic()
                if stream_name == "stdout":
                    stdout_chunks.append(line)
                    fraction = _parse_progress_fraction(line)
                    if on_progress:
                        on_progress(line.rstrip("\r\n"), fraction)
                else:
                    stderr_chunks.append(line)
                    if on_progress:
                        on_progress(line.rstrip("\r\n"), None)
        finally:
            for reader in readers:
                reader.join(timeout=2)
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
                (
                    "Extraction fre:ac terminée; vérification des fichiers en cours…"
                    if success
                    else (error or "Échec de l’extraction fre:ac")
                ),
                None,
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
