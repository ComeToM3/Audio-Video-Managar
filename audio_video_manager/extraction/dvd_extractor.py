"""DVD-Video vers MKV maître, par copie de flux et publication sans écrasement."""

from __future__ import annotations

import json
import math
import os
import queue
import re
import shutil
import subprocess
import tempfile
import threading
import time
from collections import Counter
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable

from audio_video_manager.extraction.dvd import DvdInspector
from audio_video_manager.metadata.video import (
    DvdInspectionResult,
    DvdTitleCandidate,
    DvdTitleInspection,
    VideoInspectionStatus,
    VideoStream,
)


ProgressCallback = Callable[[str, float | None], None]
_DVD_MAX_MUX_RATE = 10_080_000
_SPACE_MARGIN = 32 * 1024 * 1024
_FORMAT_RE = re.compile(r"\bmatroska\b", re.IGNORECASE)


class DvdExtractionError(RuntimeError):
    """The DVD extraction or its validation failed."""


class DvdExtractionCancelled(DvdExtractionError):
    """The caller cancelled the extraction before publication."""


class DvdExtractionConfirmationRequired(DvdExtractionError):
    """A human must confirm the selected title and angle before extraction."""


class DvdExtractionRightsRequired(DvdExtractionError):
    """The caller must record an explicit reproduction-rights attestation."""


@dataclass(frozen=True)
class DvdExtractionPlan:
    source: Path
    destination: Path
    inspection: DvdInspectionResult
    suggested_title_index: int | None
    estimated_output_bytes: int


@dataclass(frozen=True)
class DvdExtractionResult:
    output_path: Path
    title_index: int
    angle_index: int
    duration_seconds: float
    streams: tuple[VideoStream, ...]
    chapter_count: int
    size_bytes: int
    ffmpeg_version: str
    ffprobe_version: str
    warnings: tuple[str, ...] = ()
    cataloged: bool = False
    catalog_error: str = ""


class DvdExtractionService:
    """Orchestrates DVD extraction, validation and atomic publication.

    The service never performs CSS decryption. ``prepare`` is read-only and returns
    a title suggestion; ``extract`` requires an explicit confirmation flag.
    """

    def __init__(
        self,
        *,
        ffmpeg_path: str | Path | None = None,
        inspector: DvdInspector | None = None,
        runner: Callable[..., Any] = subprocess.run,
        popen_factory: Callable[..., Any] = subprocess.Popen,
        inactivity_timeout_seconds: float = 180.0,
        terminate_grace_seconds: float = 3.0,
    ) -> None:
        configured_ffmpeg = ffmpeg_path or os.environ.get("AVM_FFMPEG", "").strip()
        found_ffmpeg = configured_ffmpeg or shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
        self._ffmpeg_path = Path(found_ffmpeg).expanduser() if found_ffmpeg else None
        ffprobe_path = os.environ.get("AVM_FFPROBE", "").strip()
        if not ffprobe_path and self._ffmpeg_path is not None:
            sibling = self._ffmpeg_path.with_name("ffprobe.exe" if os.name == "nt" else "ffprobe")
            if sibling.is_file():
                ffprobe_path = str(sibling)
        self._inspector = inspector or DvdInspector(ffprobe_path=ffprobe_path or None)
        self._runner = runner
        self._popen_factory = popen_factory
        self._inactivity_timeout_seconds = inactivity_timeout_seconds
        self._terminate_grace_seconds = terminate_grace_seconds
        self._ffmpeg_version: str | None = None

    def _run_capture(self, argv: list[str], *, timeout: float = 30.0) -> Any:
        return self._runner(
            argv,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0,
        )

    def _probe_ffmpeg(self) -> str:
        if self._ffmpeg_path is None or not self._ffmpeg_path.is_file():
            raise DvdExtractionError("ffmpeg introuvable; extraction DVD indisponible.")
        try:
            version_result = self._run_capture([str(self._ffmpeg_path), "-version"])
            demuxer_result = self._run_capture(
                [str(self._ffmpeg_path), "-hide_banner", "-demuxers"]
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise DvdExtractionError(f"Sonde ffmpeg impossible : {type(exc).__name__}.") from exc
        lines = (version_result.stdout or "").splitlines()
        version = lines[0].strip() if lines else ""
        demuxers = (demuxer_result.stdout or "") + "\n" + (demuxer_result.stderr or "")
        if version_result.returncode or demuxer_result.returncode or not re.search(
            r"^\s*D\s+dvdvideo\b", demuxers, re.IGNORECASE | re.MULTILINE
        ):
            raise DvdExtractionError("Le build ffmpeg ne fournit pas le démultiplexeur dvdvideo.")
        self._ffmpeg_version = version
        return version

    @staticmethod
    def _resolve_destination(destination: str | Path) -> Path:
        path = Path(destination).expanduser()
        if path.suffix.casefold() not in {".mkv", ".mka"}:
            raise ValueError("La destination DVD doit avoir l’extension .mkv ou .mka.")
        if not path.parent.is_dir():
            raise FileNotFoundError(f"Le dossier de destination n’existe pas : {path.parent}")
        resolved = path.parent.resolve() / path.name
        if resolved.exists():
            raise FileExistsError(f"Refus d’écraser un fichier existant : {resolved}")
        return resolved

    @staticmethod
    def _reject_destination_inside_source(source: Path, destination: Path) -> None:
        raw = str(source)
        if os.name == "nt" and re.fullmatch(r"[A-Za-z]:\\?", raw):
            if destination.drive.casefold() == source.drive.casefold():
                raise ValueError("La destination ne peut pas se trouver sur le DVD source.")
            return
        source_root = source.resolve()
        try:
            destination.relative_to(source_root)
        except ValueError:
            return
        raise ValueError("La destination ne peut pas être dans la structure DVD source.")

    @staticmethod
    def _suggested_title(candidates: tuple[DvdTitleCandidate, ...]) -> int | None:
        timed = [
            candidate
            for candidate in candidates
            if candidate.duration_seconds is not None and candidate.duration_seconds > 0
        ]
        if not timed:
            return None
        longest = max(candidate.duration_seconds or 0 for candidate in timed)
        winners = [
            candidate
            for candidate in timed
            if abs((candidate.duration_seconds or 0) - longest) <= 1.0
        ]
        return winners[0].title_index if len(winners) == 1 else None

    @staticmethod
    def _vob_bytes(video_ts: Path | None) -> int:
        if video_ts is None or not video_ts.is_dir():
            return 0
        return sum(
            path.stat().st_size
            for path in video_ts.iterdir()
            if path.is_file() and path.suffix.casefold() == ".vob"
        )

    @staticmethod
    def _estimate_output_bytes(candidate: DvdTitleCandidate, vob_bytes: int) -> int:
        duration = candidate.duration_seconds or 0.0
        bitrate_bound = math.ceil(duration * _DVD_MAX_MUX_RATE / 8 * 1.05)
        return max(vob_bytes, bitrate_bound) + _SPACE_MARGIN

    def prepare(
        self, source: str | Path, destination: str | Path
    ) -> DvdExtractionPlan:
        """Inspect a DVD and return available titles plus a non-binding suggestion."""
        if not self._inspector.probe_backend().dvdvideo_demuxer:
            raise DvdExtractionError("Le backend ffprobe dvdvideo/libdvdnav est indisponible.")
        ffmpeg_version = self._probe_ffmpeg()
        resolved_source = Path(source).expanduser()
        resolved_destination = self._resolve_destination(destination)
        self._reject_destination_inside_source(resolved_source, resolved_destination)
        inspection = self._inspector.inspect(resolved_source)
        if not inspection.title_candidates:
            raise DvdExtractionError(
                inspection.diagnostic or "Aucun titre DVD-Video n’a pu être énuméré."
            )
        if inspection.status not in (
            VideoInspectionStatus.TITLE_SELECTION_REQUIRED,
            VideoInspectionStatus.INSPECTED,
        ):
            raise DvdExtractionError(
                inspection.diagnostic or "Le DVD n’a pas passé l’inspection préalable."
            )
        required = max(
            self._estimate_output_bytes(candidate, self._vob_bytes(inspection.video_ts_path))
            for candidate in inspection.title_candidates
        )
        free_bytes = shutil.disk_usage(resolved_destination.parent).free
        if free_bytes < required:
            raise OSError(
                f"Espace insuffisant : {free_bytes} octets libres, {required} estimés requis."
            )
        if not ffmpeg_version:
            raise DvdExtractionError("La version ffmpeg n’a pas pu être déterminée.")
        return DvdExtractionPlan(
            source=resolved_source,
            destination=resolved_destination,
            inspection=inspection,
            suggested_title_index=self._suggested_title(inspection.title_candidates),
            estimated_output_bytes=required,
        )

    @staticmethod
    def _stream_key(stream: VideoStream) -> tuple[object, ...]:
        return (
            stream.codec_type,
            stream.codec_name,
            (stream.language or "").casefold(),
            stream.width,
            stream.height,
            stream.sample_rate,
            stream.channels,
            None if stream.codec_name == "pcm_s16le" and stream.channels == 2
            and stream.channel_layout in (None, "stereo") else stream.channel_layout,
        )

    @staticmethod
    def _payload_stream_key(stream: dict[str, Any]) -> tuple[object, ...]:
        tags = stream.get("tags") if isinstance(stream.get("tags"), dict) else {}
        language = tags.get("language")
        return (
            str(stream.get("codec_type") or "unknown"),
            stream.get("codec_name"),
            "" if language in (None, "", "und") else str(language).casefold(),
            DvdInspector._optional_int(stream.get("width")),
            DvdInspector._optional_int(stream.get("height")),
            DvdInspector._optional_int(stream.get("sample_rate")),
            DvdInspector._optional_int(stream.get("channels")),
            None if stream.get("codec_name") == "pcm_s16le"
            and DvdInspector._optional_int(stream.get("channels")) == 2
            and stream.get("channel_layout") in (None, "stereo") else stream.get("channel_layout"),
        )

    @staticmethod
    def _pcm_conversions(
        streams: tuple[VideoStream, ...], *, allowed: bool
    ) -> tuple[VideoStream, ...]:
        pcm = tuple(stream for stream in streams if stream.codec_type == "audio" and stream.codec_name == "pcm_dvd")
        if pcm and not allowed:
            raise DvdExtractionConfirmationRequired(
                "La conversion sans perte du PCM DVD doit être explicitement autorisée."
            )
        if any(
            stream.index is None or stream.bits_per_raw_sample != 16
            or stream.sample_rate != 48000 or stream.channels != 2
            or stream.channel_layout != "stereo"
            for stream in pcm
        ):
            raise DvdExtractionError("Seul le PCM DVD 16 bits, 48 kHz stéréo identifié est pris en charge.")
        return pcm

    def _verify_pcm_samples(
        self, *, source: Path, staged_path: Path, selected_streams: tuple[VideoStream, ...],
        converted_streams: tuple[VideoStream, ...], title_index: int, angle_index: int,
        duration: float, workdir: Path, cancel_event: threading.Event | None,
        on_progress: ProgressCallback | None,
    ) -> None:
        for stream in converted_streams:
            output_index = selected_streams.index(stream)
            hashes = []
            for name, input_args, stream_index in (
                ("source", ["-f", "dvdvideo", "-title", str(title_index), "-angle", str(angle_index),
                            "-i", str(self._inspector._dvd_device_path(source))], stream.index),
                ("sortie", ["-i", str(staged_path)], output_index),
            ):
                hash_path = workdir / f"pcm-{stream.index}-{name}.sha256"
                argv = [str(self._ffmpeg_path), "-hide_banner", "-nostdin", "-n", "-v", "warning",
                        "-progress", "pipe:1", "-stats_period", "0.5", *input_args,
                        "-map", f"0:{stream_index}", "-vn", "-sn", "-dn", "-c:a", "pcm_s16le",
                        "-f", "hash", "-hash", "sha256", str(hash_path)]
                code, stderr = self._run_monitored(
                    argv, duration_seconds=duration, cancel_event=cancel_event, on_progress=on_progress,
                    phase=f"Vérification PCM {name}", fraction_start=0.90, fraction_span=0.08,
                    working_directory=workdir,
                )
                if code != 0 or any(marker in stderr.casefold() for marker in ("unable to read next block of pgc", "error reading from dvd")):
                    raise DvdExtractionError(f"Vérification PCM {name} impossible : {stderr[-1000:]}")
                content = hash_path.read_text(encoding="ascii").strip()
                if not re.fullmatch(r"SHA256=[0-9a-fA-F]{64}", content):
                    raise DvdExtractionError("Empreinte PCM absente ou invalide.")
                if content.casefold() == "sha256=e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855":
                    raise DvdExtractionError("Aucun échantillon PCM à vérifier; publication refusée.")
                hashes.append(content.casefold())
            if hashes[0] != hashes[1]:
                raise DvdExtractionError("Les échantillons PCM source et sortie diffèrent; publication refusée.")

    def _probe_mkv(self, path: Path) -> dict[str, Any]:
        assert self._inspector.probe_backend().executable is not None
        ffprobe = self._inspector.probe_backend().executable
        try:
            result = self._run_capture(
                [
                    str(ffprobe),
                    "-v",
                    "error",
                    "-show_format",
                    "-show_streams",
                    "-show_chapters",
                    "-of",
                    "json",
                    str(path),
                ],
                timeout=max(30.0, self._inactivity_timeout_seconds),
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise DvdExtractionError(f"Validation ffprobe impossible : {type(exc).__name__}.") from exc
        if result.returncode != 0:
            raise DvdExtractionError(
                f"ffprobe a refusé le MKV temporaire : {(result.stderr or '').strip()[-1000:]}"
            )
        try:
            payload = json.loads(result.stdout or "{}")
        except json.JSONDecodeError as exc:
            raise DvdExtractionError("ffprobe a renvoyé un JSON invalide pour le MKV.") from exc
        return payload if isinstance(payload, dict) else {}

    def _validate_mkv(
        self,
        path: Path,
        expected: DvdTitleInspection,
        *,
        expected_streams: tuple[VideoStream, ...] | None = None,
    ) -> tuple[float, tuple[VideoStream, ...], int]:
        if not path.is_file() or path.stat().st_size <= 0:
            raise DvdExtractionError("ffmpeg n’a pas produit de MKV temporaire non vide.")
        payload = self._probe_mkv(path)
        fmt = payload.get("format") if isinstance(payload.get("format"), dict) else {}
        format_name = str(fmt.get("format_name") or "")
        if not _FORMAT_RE.search(format_name):
            raise DvdExtractionError(f"Le fichier produit n’est pas Matroska ({format_name or 'format inconnu'}).")
        actual_streams = [item for item in payload.get("streams", []) if isinstance(item, dict)]
        streams_to_validate = expected_streams if expected_streams is not None else expected.streams
        expected_keys = Counter(self._stream_key(stream) for stream in streams_to_validate)
        actual_keys = Counter(self._payload_stream_key(stream) for stream in actual_streams)
        if expected_keys != actual_keys:
            missing = list((expected_keys - actual_keys).elements())
            extra = list((actual_keys - expected_keys).elements())
            raise DvdExtractionError(
                f"Les flux du MKV diffèrent de l’inspection DVD (manquants={missing}, supplémentaires={extra})."
            )
        duration = DvdInspector._optional_float(fmt.get("duration"))
        if duration is None or duration <= 0:
            raise DvdExtractionError("Durée absente ou invalide dans le MKV.")
        if expected.duration_seconds is not None:
            tolerance = max(2.0, expected.duration_seconds * 0.005)
            if abs(duration - expected.duration_seconds) > tolerance:
                raise DvdExtractionError(
                    f"Durée MKV hors tolérance : DVD={expected.duration_seconds:.3f}s, MKV={duration:.3f}s."
                )
        expected_chapters = expected.chapters
        actual_chapters = [item for item in payload.get("chapters", []) if isinstance(item, dict)]
        if len(actual_chapters) != len(expected_chapters):
            raise DvdExtractionError(
                f"Nombre de chapitres différent : DVD={len(expected_chapters)}, MKV={len(actual_chapters)}."
            )
        for expected_chapter, actual_chapter in zip(expected_chapters, actual_chapters, strict=True):
            start = DvdInspector._optional_float(actual_chapter.get("start_time"))
            end = DvdInspector._optional_float(actual_chapter.get("end_time"))
            if (
                start is None
                or end is None
                or expected_chapter.start_seconds is None
                or expected_chapter.end_seconds is None
                or abs(start - expected_chapter.start_seconds) > 2.0
                or abs(end - expected_chapter.end_seconds) > 2.0
            ):
                raise DvdExtractionError(
                    f"Bornes de chapitre incompatibles au chapitre {expected_chapter.index}."
                )
        streams = tuple(
            VideoStream(
                index=DvdInspector._optional_int(item.get("index")),
                codec_type=str(item.get("codec_type") or "unknown"),
                codec_name=str(item["codec_name"]) if item.get("codec_name") else None,
                language=(
                    str(item.get("tags", {}).get("language"))
                    if isinstance(item.get("tags"), dict)
                    and item.get("tags", {}).get("language") not in (None, "", "und")
                    else None
                ),
                title=(
                    str(item.get("tags", {}).get("title"))
                    if isinstance(item.get("tags"), dict) and item.get("tags", {}).get("title")
                    else None
                ),
                width=DvdInspector._optional_int(item.get("width")),
                height=DvdInspector._optional_int(item.get("height")),
                sample_rate=DvdInspector._optional_int(item.get("sample_rate")),
                channels=DvdInspector._optional_int(item.get("channels")),
                channel_layout=(
                    str(item["channel_layout"]) if item.get("channel_layout") else None
                ),
            )
            for item in actual_streams
        )
        return duration, streams, len(actual_chapters)

    def _stop_process(self, process: Any) -> None:
        if process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=self._terminate_grace_seconds)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=self._terminate_grace_seconds)

    def _ffmpeg_child_environment(self, working_directory: Path) -> dict[str, str] | None:
        if os.name != "nt":
            return None
        if self._ffmpeg_path is None:
            raise DvdExtractionError("Chemin ffmpeg absent avant le démarrage du worker.")
        system_root = Path(os.environ.get("SystemRoot", r"C:\Windows"))
        search_dirs = tuple(
            dict.fromkeys(
                path.resolve()
                for path in (
                    self._ffmpeg_path.parent,
                    working_directory,
                    system_root / "System32",
                    system_root,
                )
            )
        )
        css_dll = next(
            (directory / "libdvdcss-2.dll" for directory in search_dirs if (directory / "libdvdcss-2.dll").is_file()),
            None,
        )
        if css_dll is not None:
            raise DvdExtractionError(
                f"FFmpeg pourrait charger un backend CSS interdit ({css_dll}); extraction refusée."
            )
        environment = os.environ.copy()
        environment["PATH"] = os.pathsep.join(str(directory) for directory in search_dirs)
        return environment

    def _run_monitored(
        self,
        argv: list[str],
        *,
        duration_seconds: float,
        cancel_event: threading.Event | None,
        on_progress: ProgressCallback | None,
        phase: str,
        fraction_start: float,
        fraction_span: float,
        working_directory: Path | None = None,
    ) -> tuple[int, str]:
        if cancel_event is not None and cancel_event.is_set():
            raise DvdExtractionCancelled("Extraction DVD annulée avant le démarrage du sous-processus.")
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        process_cwd = Path(working_directory or Path.cwd()).resolve()
        environment = self._ffmpeg_child_environment(process_cwd)
        try:
            process = self._popen_factory(
                argv,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=creationflags,
                cwd=str(process_cwd),
                env=environment,
            )
        except OSError as exc:
            raise DvdExtractionError(f"Impossible de démarrer ffmpeg : {exc}") from exc
        assert process.stdout is not None and process.stderr is not None
        events: queue.Queue[tuple[str, str | None]] = queue.Queue()

        def drain(name: str, stream: Any) -> None:
            try:
                for line in stream:
                    events.put((name, line.rstrip("\r\n")))
            finally:
                events.put((name, None))

        readers = [
            threading.Thread(target=drain, args=("stdout", process.stdout), daemon=True),
            threading.Thread(target=drain, args=("stderr", process.stderr), daemon=True),
        ]
        for reader in readers:
            reader.start()
        active = {"stdout", "stderr"}
        stderr_tail: list[str] = []
        progress_values: dict[str, str] = {}
        last_progress = time.monotonic()
        try:
            while active or process.poll() is None:
                if cancel_event is not None and cancel_event.is_set():
                    self._stop_process(process)
                    raise DvdExtractionCancelled("Extraction DVD annulée par l’utilisateur.")
                if process.poll() is None and time.monotonic() - last_progress > self._inactivity_timeout_seconds:
                    self._stop_process(process)
                    raise DvdExtractionError(
                        f"Timeout d’inactivité ({self._inactivity_timeout_seconds:.0f} s) pendant {phase}."
                    )
                try:
                    name, line = events.get(timeout=0.1)
                except queue.Empty:
                    continue
                if line is None:
                    active.discard(name)
                    continue
                if name == "stderr":
                    stderr_tail.append(line)
                    if len(stderr_tail) > 80:
                        del stderr_tail[: len(stderr_tail) - 80]
                    continue
                key, separator, value = line.partition("=")
                if not separator:
                    continue
                progress_values[key] = value
                if key != "progress":
                    continue
                last_progress = time.monotonic()
                out_time_us = DvdInspector._optional_int(progress_values.get("out_time_us"))
                fraction = None
                if out_time_us is not None and duration_seconds > 0:
                    local = max(0.0, min(1.0, out_time_us / (duration_seconds * 1_000_000)))
                    fraction = fraction_start + local * fraction_span
                if on_progress:
                    on_progress(f"{phase} : {progress_values.get('out_time', 'en cours')}", fraction)
                progress_values.clear()
            returncode = process.wait()
        except BaseException:
            if process.poll() is None:
                self._stop_process(process)
            raise
        finally:
            for reader in readers:
                reader.join(timeout=1.0)
        return int(returncode), "\n".join(stderr_tail)

    def _publish_no_replace(self, staged_path: Path, destination: Path) -> None:
        try:
            os.link(staged_path, destination)
        except FileExistsError:
            raise FileExistsError(f"Refus d’écraser un fichier existant : {destination}") from None
        except OSError as exc:
            raise DvdExtractionError(
                f"Publication atomique sans écrasement impossible sur ce système de fichiers : {exc}"
            ) from exc
        staged_path.unlink()

    def extract(
        self,
        plan: DvdExtractionPlan,
        *,
        title_index: int,
        angle_index: int = 1,
        confirmed: bool = False,
        rights_attested: bool = False,
        allow_pcm_conversion: bool = False,
        cancel_event: threading.Event | None = None,
        on_progress: ProgressCallback | None = None,
    ) -> DvdExtractionResult:
        """Copy all selected DVD streams to MKV; publish only after validation.

        ``confirmed`` must be set by the caller only after presenting the plan and
        receiving an explicit human confirmation.
        """
        if not confirmed:
            raise DvdExtractionConfirmationRequired(
                "Confirmation humaine explicite du titre, de l’angle et de la destination requise."
            )
        if not rights_attested:
            raise DvdExtractionRightsRequired(
                "Une attestation explicite des droits de reproduction est requise avant extraction."
            )
        if cancel_event is not None and cancel_event.is_set():
            raise DvdExtractionCancelled("Extraction DVD annulée avant le préflight final.")
        self._reject_destination_inside_source(plan.source, plan.destination)
        if plan.destination.suffix.casefold() != ".mkv" or not plan.destination.parent.is_dir():
            raise DvdExtractionError("Le chemin du master MKV n’est plus valide.")
        if plan.destination.exists():
            raise FileExistsError(f"Refus d’écraser un fichier existant : {plan.destination}")
        candidate = next(
            (item for item in plan.inspection.title_candidates if item.title_index == title_index),
            None,
        )
        if candidate is None:
            raise ValueError(f"Titre {title_index} absent du plan d’extraction.")
        if angle_index < 1 or (candidate.angle_count is not None and angle_index > candidate.angle_count):
            raise ValueError("L’angle demandé est hors de la plage énumérée.")
        required_bytes = self._estimate_output_bytes(
            candidate, self._vob_bytes(plan.inspection.video_ts_path)
        )
        free_bytes = shutil.disk_usage(plan.destination.parent).free
        if free_bytes < required_bytes:
            raise OSError(
                f"Espace insuffisant : {free_bytes} octets libres, {required_bytes} estimés requis."
            )
        ffmpeg_version = self._probe_ffmpeg()
        if on_progress:
            on_progress("Inspection du titre sélectionné…", 0.0)
        selected_result = self._inspector.inspect(
            plan.source, title_indices=(title_index,), angle_index=angle_index
        )
        if selected_result.status != VideoInspectionStatus.INSPECTED or not selected_result.titles:
            raise DvdExtractionError(
                selected_result.diagnostic or "Le titre sélectionné n’a pas passé l’inspection."
            )
        expected = selected_result.titles[0]
        if not expected.streams:
            raise DvdExtractionError("Aucun flux inspecté; extraction refusée pour éviter une perte silencieuse.")
        converted = self._pcm_conversions(expected.streams, allowed=allow_pcm_conversion)
        if on_progress:
            on_progress("Extraction DVD → MKV (copie de flux)…", 0.02)
        workdir = Path(tempfile.mkdtemp(prefix=".avm-dvd-", dir=plan.destination.parent))
        staged_path = workdir / "master.mkv"
        source_path = self._inspector._dvd_device_path(plan.source)
        argv = [
            str(self._ffmpeg_path),
            "-hide_banner",
            "-nostdin",
            "-n",
            "-v",
            "warning",
            "-progress",
            "pipe:1",
            "-stats_period",
            "0.5",
            "-f",
            "dvdvideo",
            "-title",
            str(title_index),
            "-angle",
            str(angle_index),
            "-i",
            str(source_path),
            "-map",
            "0",
            "-map_chapters",
            "0",
            "-map_metadata",
            "0",
            "-c",
            "copy",
        ]
        for stream in converted:
            argv.extend((f"-c:{expected.streams.index(stream)}", "pcm_s16le"))
        argv.extend([
            "-f",
            "matroska",
            str(staged_path),
        ])
        try:
            returncode, stderr = self._run_monitored(
                argv,
                duration_seconds=expected.duration_seconds or candidate.duration_seconds or 0.0,
                cancel_event=cancel_event,
                on_progress=on_progress,
                phase="Copie de flux",
                fraction_start=0.02,
                fraction_span=0.76,
                working_directory=workdir,
            )
            if returncode != 0:
                raise DvdExtractionError(
                    f"ffmpeg a échoué (code {returncode}) : {stderr[-1200:]}"
                )
            if on_progress:
                on_progress("Validation des pistes, chapitres et durée…", 0.80)
            expected_streams = tuple(
                replace(stream, codec_name="pcm_s16le") if stream in converted else stream
                for stream in expected.streams
            )
            duration, streams, chapter_count = self._validate_mkv(
                staged_path, expected, expected_streams=expected_streams
            )
            scan_argv = [
                str(self._ffmpeg_path),
                "-hide_banner",
                "-nostdin",
                "-v",
                "error",
                "-progress",
                "pipe:1",
                "-stats_period",
                "0.5",
                "-i",
                str(staged_path),
                "-map",
                "0",
                "-c",
                "copy",
                "-f",
                "null",
                "-",
            ]
            if on_progress:
                on_progress("Vérification intégrale du MKV…", 0.82)
            scan_code, scan_stderr = self._run_monitored(
                scan_argv,
                duration_seconds=duration,
                cancel_event=cancel_event,
                on_progress=on_progress,
                phase="Vérification MKV",
                fraction_start=0.82,
                fraction_span=0.08 if converted else 0.16,
                working_directory=workdir,
            )
            if scan_code != 0:
                raise DvdExtractionError(
                    f"La lecture complète du MKV a échoué (code {scan_code}) : {scan_stderr[-1200:]}"
                )
            if converted:
                self._verify_pcm_samples(
                    source=plan.source, staged_path=staged_path, selected_streams=expected.streams,
                    converted_streams=converted, title_index=title_index, angle_index=angle_index,
                    duration=duration, workdir=workdir, cancel_event=cancel_event, on_progress=on_progress,
                )
            if cancel_event is not None and cancel_event.is_set():
                raise DvdExtractionCancelled("Extraction DVD annulée avant publication.")
            size_bytes = staged_path.stat().st_size
            if on_progress:
                on_progress("Publication sans écrasement…", 0.99)
            self._publish_no_replace(staged_path, plan.destination)
            if on_progress:
                on_progress("MKV maître validé.", 1.0)
            return DvdExtractionResult(
                output_path=plan.destination,
                title_index=title_index,
                angle_index=angle_index,
                duration_seconds=duration,
                streams=streams,
                chapter_count=chapter_count,
                size_bytes=size_bytes,
                ffmpeg_version=ffmpeg_version,
                ffprobe_version=(
                    selected_result.backend.version
                    if selected_result.backend and selected_result.backend.version
                    else "inconnue"
                ),
                warnings=selected_result.warnings + (("PCM DVD converti sans perte; échantillons vérifiés.",) if converted else ()),
            )
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

    def extract_audio(
        self,
        plan: DvdExtractionPlan,
        *,
        title_index: int,
        angle_index: int = 1,
        audio_stream_indices: tuple[int, ...],
        confirmed: bool = False,
        rights_attested: bool = False,
        allow_pcm_conversion: bool = False,
        cancel_event: threading.Event | None = None,
        on_progress: ProgressCallback | None = None,
    ) -> DvdExtractionResult:
        """Extract selected DVD audio tracks to audio-only Matroska without encoding."""
        if not confirmed:
            raise DvdExtractionConfirmationRequired(
                "Confirmation humaine explicite du titre, de l’angle, des pistes et de la destination requise."
            )
        if not rights_attested:
            raise DvdExtractionRightsRequired(
                "Une attestation explicite des droits de reproduction est requise avant extraction audio."
            )
        if cancel_event is not None and cancel_event.is_set():
            raise DvdExtractionCancelled("Extraction audio DVD annulée avant le préflight final.")
        self._reject_destination_inside_source(plan.source, plan.destination)
        if plan.destination.suffix.casefold() != ".mka" or not plan.destination.parent.is_dir():
            raise DvdExtractionError("La destination audio doit être un fichier .mka dans un dossier existant.")
        if plan.destination.exists():
            raise FileExistsError(f"Refus d’écraser un fichier existant : {plan.destination}")
        if not audio_stream_indices:
            raise ValueError("Sélectionnez explicitement au moins une piste audio.")
        candidate = next(
            (item for item in plan.inspection.title_candidates if item.title_index == title_index),
            None,
        )
        if candidate is None:
            raise ValueError(f"Titre {title_index} absent du plan d’extraction.")
        if angle_index < 1 or (candidate.angle_count is not None and angle_index > candidate.angle_count):
            raise ValueError("L’angle demandé est hors de la plage énumérée.")
        required_bytes = self._estimate_output_bytes(
            candidate, self._vob_bytes(plan.inspection.video_ts_path)
        )
        free_bytes = shutil.disk_usage(plan.destination.parent).free
        if free_bytes < required_bytes:
            raise OSError(
                f"Espace insuffisant : {free_bytes} octets libres, {required_bytes} estimés requis."
            )
        ffmpeg_version = self._probe_ffmpeg()
        selected_result = self._inspector.inspect(
            plan.source, title_indices=(title_index,), angle_index=angle_index
        )
        if selected_result.status != VideoInspectionStatus.INSPECTED or not selected_result.titles:
            raise DvdExtractionError(
                selected_result.diagnostic or "Le titre sélectionné n’a pas passé l’inspection."
            )
        expected = selected_result.titles[0]
        audio_by_index = {
            stream.index: stream for stream in expected.audio_streams if stream.index is not None
        }
        if len(set(audio_stream_indices)) != len(audio_stream_indices):
            raise ValueError("La sélection contient des index audio en double.")
        if any(index not in audio_by_index for index in audio_stream_indices):
            raise ValueError("Un index sélectionné n’est pas une piste audio du titre choisi.")
        selected_audio = tuple(audio_by_index[index] for index in audio_stream_indices)
        converted = self._pcm_conversions(selected_audio, allowed=allow_pcm_conversion)
        if on_progress:
            on_progress("Inspection des pistes audio sélectionnées…", 0.0)
        workdir = Path(tempfile.mkdtemp(prefix=".avm-dvd-audio-", dir=plan.destination.parent))
        staged_path = workdir / "audio.mka"
        source_path = self._inspector._dvd_device_path(plan.source)
        argv = [
            str(self._ffmpeg_path),
            "-hide_banner",
            "-nostdin",
            "-n",
            "-v",
            "warning",
            "-progress",
            "pipe:1",
            "-stats_period",
            "0.5",
            "-f",
            "dvdvideo",
            "-title",
            str(title_index),
            "-angle",
            str(angle_index),
            "-i",
            str(source_path),
        ]
        for stream in selected_audio:
            argv.extend(("-map", f"0:{stream.index}"))
        argv.extend(
            (
                "-map_chapters",
                "0",
                "-map_metadata",
                "0",
                "-vn",
                "-c:a",
                "copy",
            )
        )
        for stream in converted:
            argv.extend((f"-c:{selected_audio.index(stream)}", "pcm_s16le"))
        argv.extend(("-f", "matroska", str(staged_path)))
        try:
            returncode, stderr = self._run_monitored(
                argv,
                duration_seconds=expected.duration_seconds or candidate.duration_seconds or 0.0,
                cancel_event=cancel_event,
                on_progress=on_progress,
                phase="Copie audio",
                fraction_start=0.02,
                fraction_span=0.76,
                working_directory=workdir,
            )
            if returncode != 0:
                raise DvdExtractionError(
                    "FFmpeg ne peut pas copier ces codecs audio dans Matroska sans transcodage : "
                    f"code {returncode}, {(stderr or 'aucun détail').strip()[-1000:]}"
                )
            if on_progress:
                on_progress("Validation des pistes audio et chapitres…", 0.80)
            duration, streams, chapter_count = self._validate_mkv(
                staged_path, expected,
                expected_streams=tuple(
                    replace(stream, codec_name="pcm_s16le") if stream in converted else stream
                    for stream in selected_audio
                ),
            )
            scan_argv = [
                str(self._ffmpeg_path),
                "-hide_banner",
                "-nostdin",
                "-v",
                "error",
                "-progress",
                "pipe:1",
                "-stats_period",
                "0.5",
                "-i",
                str(staged_path),
                "-map",
                "0",
                "-c",
                "copy",
                "-f",
                "null",
                "-",
            ]
            if on_progress:
                on_progress("Vérification intégrale du MKV audio…", 0.82)
            scan_code, scan_stderr = self._run_monitored(
                scan_argv,
                duration_seconds=duration,
                cancel_event=cancel_event,
                on_progress=on_progress,
                phase="Vérification audio",
                fraction_start=0.82,
                fraction_span=0.08 if converted else 0.16,
                working_directory=workdir,
            )
            if scan_code != 0:
                raise DvdExtractionError(
                    f"La lecture complète du MKV audio a échoué (code {scan_code}) : {scan_stderr[-1200:]}"
                )
            if converted:
                self._verify_pcm_samples(
                    source=plan.source, staged_path=staged_path, selected_streams=selected_audio,
                    converted_streams=converted, title_index=title_index, angle_index=angle_index,
                    duration=duration, workdir=workdir, cancel_event=cancel_event, on_progress=on_progress,
                )
            if cancel_event is not None and cancel_event.is_set():
                raise DvdExtractionCancelled("Extraction audio annulée avant publication.")
            size_bytes = staged_path.stat().st_size
            if on_progress:
                on_progress("Publication audio sans écrasement…", 0.99)
            self._publish_no_replace(staged_path, plan.destination)
            if on_progress:
                on_progress("Fichier audio validé.", 1.0)
            return DvdExtractionResult(
                output_path=plan.destination,
                title_index=title_index,
                angle_index=angle_index,
                duration_seconds=duration,
                streams=streams,
                chapter_count=chapter_count,
                size_bytes=size_bytes,
                ffmpeg_version=ffmpeg_version,
                ffprobe_version=(
                    selected_result.backend.version
                    if selected_result.backend and selected_result.backend.version
                    else "inconnue"
                ),
                warnings=selected_result.warnings + (("PCM DVD converti sans perte; échantillons vérifiés.",) if converted else ()),
            )
        finally:
            shutil.rmtree(workdir, ignore_errors=True)