"""Inspection DVD-Video en lecture seule; aucune extraction n'est implémentée ici."""

from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable, Sequence

from audio_video_manager.metadata.video import (
    DvdBackendCapabilities,
    DvdInspectionResult,
    DvdTitleCandidate,
    DvdTitleInspection,
    VideoChapter,
    VideoInspectionStatus,
    VideoStream,
)
from audio_video_manager.extraction.dvd_navigation import DvdNavigationError, DvdNavigator


_VIDEO_TS_NAME = "VIDEO_TS"
_VMG_SIGNATURE = b"DVDVIDEO-VMG"
_VTS_SIGNATURE = b"DVDVIDEO-VTS"
_VTS_IFO_RE = re.compile(r"VTS_(\d{2})_0\.IFO\Z", re.IGNORECASE)
_DVDVIDEO_DEMUXER_RE = re.compile(r"^\s*D\s+dvdvideo\b", re.IGNORECASE | re.MULTILINE)
_PROTECTED_HINTS = ("encrypted dvd", "css protection", "scrambled sector", "copy protection")
_READ_ERROR_HINTS = ("unable to read next block of pgc", "error reading from dvd")
_DEFAULT_TIMEOUT_SECONDS = 30


CommandRunner = Callable[..., Any]


class DvdExtractionNotAvailableError(RuntimeError):
    """Retained for compatibility; AVM-11B adds inspection only, not extraction."""

    def __init__(self) -> None:
        super().__init__("L'extraction DVD est reportée (décision D-010).")


class DvdInspector:
    """Inspecte les structures VIDEO_TS et, si supporté, les flux d'un titre.

    FFmpeg/ffprobe est uniquement invoqué en mode probe. Aucune commande de sortie
    média n'est construite. La liste de titres doit être fournie explicitement:
    le démultiplexeur dvdvideo ne fournit pas de commande d'énumération fiable.
    """

    def __init__(
        self,
        ffprobe_path: str | Path | None = None,
        *,
        runner: CommandRunner = subprocess.run,
        timeout_seconds: int = _DEFAULT_TIMEOUT_SECONDS,
        dvdnav_directory: str | Path | None = None,
        navigator: Any | None = None,
    ) -> None:
        self._configured_path = Path(ffprobe_path) if ffprobe_path else None
        self._runner = runner
        self._timeout_seconds = timeout_seconds
        configured_dvdnav = dvdnav_directory or os.environ.get("AVM_DVDNAV_DIR", "").strip()
        self._dvdnav_directory = Path(configured_dvdnav) if configured_dvdnav else None
        self._navigator = navigator

    def _enumerate_titles(self, source: Path) -> tuple[DvdTitleCandidate, ...]:
        if self._navigator is None:
            if self._dvdnav_directory is None:
                return ()
            self._navigator = DvdNavigator(self._dvdnav_directory)
        return self._navigator.enumerate_titles(self._dvd_device_path(source))

    @staticmethod
    def _dvd_device_path(source: Path) -> Path:
        raw = str(source)
        if os.name == "nt" and (match := re.fullmatch(r"([A-Za-z]):\\?", raw)):
            return Path(f"\\\\.\\{match.group(1)}:")
        return source

    def _find_ffprobe(self) -> Path | None:
        if self._configured_path is not None:
            return self._configured_path if self._configured_path.is_file() else None
        configured = os.environ.get("AVM_FFPROBE", "").strip()
        if configured:
            candidate = Path(configured).expanduser()
            return candidate if candidate.is_file() else None
        found = shutil.which("ffprobe") or shutil.which("ffprobe.exe")
        return Path(found) if found else None

    def _run(self, argv: list[str]) -> Any:
        return self._runner(
            argv,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=self._timeout_seconds,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0,
        )

    def probe_backend(self) -> DvdBackendCapabilities:
        executable = self._find_ffprobe()
        if executable is None:
            return DvdBackendCapabilities(
                None, None, False, "ffprobe introuvable; aucun backend DVD-Video disponible."
            )
        try:
            version_result = self._run([str(executable), "-version"])
            version_lines = (version_result.stdout or "").splitlines()
            version = version_lines[0].strip() if version_lines else None
            if version_result.returncode != 0:
                return DvdBackendCapabilities(
                    executable,
                    version,
                    False,
                    "ffprobe ne répond pas correctement à la sonde de version.",
                )
            demuxers = self._run([str(executable), "-hide_banner", "-demuxers"])
        except (OSError, subprocess.TimeoutExpired) as exc:
            return DvdBackendCapabilities(
                executable, None, False, f"Sonde ffprobe impossible : {type(exc).__name__}."
            )
        demuxer_text = (demuxers.stdout or "") + "\n" + (demuxers.stderr or "")
        supported = demuxers.returncode == 0 and bool(
            _DVDVIDEO_DEMUXER_RE.search(demuxer_text)
        )
        diagnostic = (
            "ffprobe expose le démultiplexeur dvdvideo."
            if supported
            else "Ce build ffprobe n'expose pas dvdvideo; il peut manquer libdvdread/libdvdnav."
        )
        return DvdBackendCapabilities(executable, version, supported, diagnostic)

    @staticmethod
    def _source_and_video_ts(source: str | Path) -> tuple[Path, Path]:
        raw = str(source)
        if os.name == "nt" and len(raw) == 2 and raw[1] == ":":
            raw += "\\"
        path = Path(raw).expanduser()
        if path.name.casefold() == _VIDEO_TS_NAME.casefold():
            return path.parent, path
        if not path.is_dir():
            return path, path / _VIDEO_TS_NAME
        for child in path.iterdir():
            if child.is_dir() and child.name.casefold() == _VIDEO_TS_NAME.casefold():
                return path, child
        return path, path / _VIDEO_TS_NAME

    @staticmethod
    def _read_header(path: Path) -> bytes:
        with path.open("rb") as media_file:
            return media_file.read(12)

    @staticmethod
    def _optional_int(value: object) -> int | None:
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _optional_float(value: object) -> float | None:
        try:
            result = float(value) if value is not None else None
        except (TypeError, ValueError):
            return None
        return result if result is not None and math.isfinite(result) else None

    def _inspect_title(
        self,
        source: Path,
        title_index: int,
        angle_index: int,
        backend: DvdBackendCapabilities,
    ) -> tuple[DvdTitleInspection | None, str | None, str | None]:
        assert backend.executable is not None
        argv = [
            str(backend.executable),
            "-hide_banner",
            "-v",
            "error",
            "-f",
            "dvdvideo",
            "-title",
            str(title_index),
            "-angle",
            str(angle_index),
            "-show_format",
            "-show_streams",
            "-show_chapters",
            "-of",
            "json",
            "-i",
            str(source),
        ]
        try:
            result = self._run(argv)
        except subprocess.TimeoutExpired as exc:
            return None, "L'inspection du titre a dépassé le délai autorisé.", str(exc)
        except OSError as exc:
            return None, "Le lecteur n'a pas pu être lu par ffprobe.", str(exc)
        stderr = (result.stderr or "").strip()
        low = stderr.casefold()
        if result.returncode != 0 or any(hint in low for hint in _READ_ERROR_HINTS):
            if any(hint in low for hint in _PROTECTED_HINTS):
                return (
                    None,
                    "Le lecteur signale une protection ou un flux inaccessible; aucune méthode de contournement n'est utilisée.",
                    stderr or f"ffprobe returncode={result.returncode}",
                )
            return (
                None,
                "ffprobe n'a pas pu inspecter ce titre DVD.",
                stderr or f"ffprobe returncode={result.returncode}",
            )
        try:
            payload = json.loads(result.stdout or "{}")
        except json.JSONDecodeError as exc:
            return None, "ffprobe a renvoyé des métadonnées illisibles.", str(exc)
        return self._parse_title(payload, title_index, angle_index)

    def _parse_title(
        self, payload: dict[str, Any], title_index: int, angle_index: int
    ) -> tuple[DvdTitleInspection, str | None, str | None]:
        warnings: list[str] = []
        streams: list[VideoStream] = []
        for item in payload.get("streams", []):
            if not isinstance(item, dict):
                continue
            tags = item.get("tags") if isinstance(item.get("tags"), dict) else {}
            language = tags.get("language")
            if language in (None, "", "und"):
                language = None
            streams.append(
                VideoStream(
                    index=self._optional_int(item.get("index")),
                    codec_type=str(item.get("codec_type") or "unknown"),
                    codec_name=item.get("codec_name"),
                    language=str(language) if language is not None else None,
                    title=str(tags["title"]) if tags.get("title") else None,
                    width=self._optional_int(item.get("width")),
                    height=self._optional_int(item.get("height")),
                    sample_rate=self._optional_int(item.get("sample_rate")),
                    channels=self._optional_int(item.get("channels")),
                    channel_layout=item.get("channel_layout"),
                    bits_per_raw_sample=self._optional_int(item.get("bits_per_raw_sample")),
                )
            )
        chapters: list[VideoChapter] = []
        for index, item in enumerate(payload.get("chapters", []), start=1):
            if not isinstance(item, dict):
                continue
            tags = item.get("tags") if isinstance(item.get("tags"), dict) else {}
            chapters.append(
                VideoChapter(
                    index=index,
                    start_seconds=self._optional_float(item.get("start_time")),
                    end_seconds=self._optional_float(item.get("end_time")),
                    title=str(tags["title"]) if tags.get("title") else None,
                )
            )
        fmt = payload.get("format") if isinstance(payload.get("format"), dict) else {}
        duration = self._optional_float(fmt.get("duration"))
        if duration is None:
            warnings.append("Durée de titre non fournie par le backend.")
        if not streams:
            warnings.append("Aucun flux n'a été décrit par le backend.")
        elif any(
            stream.language is None
            or (stream.codec_type == "video" and (stream.width is None or stream.height is None))
            or (stream.codec_type == "audio" and stream.channels is None)
            for stream in streams
        ):
            warnings.append("Certaines métadonnées de flux sont indisponibles.")
        return (
            DvdTitleInspection(
                title_index=title_index,
                angle_index=angle_index,
                duration_seconds=duration,
                format_name=str(fmt["format_name"]) if fmt.get("format_name") else None,
                streams=tuple(streams),
                chapters=tuple(chapters),
            ),
            " ".join(warnings) if warnings else None,
            None,
        )

    def inspect(
        self,
        source: str | Path,
        *,
        title_indices: Sequence[int] = (),
        angle_index: int = 1,
        auto_select_main_title: bool = False,
    ) -> DvdInspectionResult:
        """Inspecte VIDEO_TS; l'auto-sélection choisit seulement le candidat le plus long."""
        source_path = Path(source).expanduser()
        try:
            source_path, video_ts = self._source_and_video_ts(source)
            vmg_path = video_ts / "VIDEO_TS.IFO"
            if not video_ts.is_dir() or not vmg_path.is_file():
                return DvdInspectionResult(
                    source_path,
                    VideoInspectionStatus.INVALID_STRUCTURE,
                    video_ts_path=video_ts,
                    diagnostic="VIDEO_TS/VIDEO_TS.IFO n'a pas été détecté.",
                )
            vmg = self._read_header(vmg_path)
            if not vmg.startswith(_VMG_SIGNATURE):
                return DvdInspectionResult(
                    source_path,
                    VideoInspectionStatus.INVALID_STRUCTURE,
                    video_ts_path=video_ts,
                    diagnostic="VIDEO_TS.IFO est absent ou ne porte pas la signature DVD-Video attendue.",
                )
            title_sets = sorted(
                {
                    int(match.group(1))
                    for entry in video_ts.iterdir()
                    if (match := _VTS_IFO_RE.fullmatch(entry.name)) and entry.is_file()
                }
            )
        except OSError as exc:
            return DvdInspectionResult(
                Path(source),
                VideoInspectionStatus.READ_ERROR,
                diagnostic="La structure DVD ne peut pas être lue.",
                technical_detail=f"{type(exc).__name__}: {exc}",
            )
        if not title_sets:
            return DvdInspectionResult(
                source_path,
                VideoInspectionStatus.INVALID_STRUCTURE,
                video_ts_path=video_ts,
                diagnostic="Aucun fichier IFO de jeu de titres valide n'a été détecté.",
            )
        backend = self.probe_backend()
        title_candidates: tuple[DvdTitleCandidate, ...] = ()
        navigation_detail: str | None = None
        if self._navigator is not None or self._dvdnav_directory is not None:
            try:
                title_candidates = self._enumerate_titles(source_path)
            except (OSError, DvdNavigationError, ValueError, AttributeError) as exc:
                navigation_detail = f"{type(exc).__name__}: {exc}"
        auto_selection_warning: str | None = None
        if not title_indices:
            if navigation_detail:
                return DvdInspectionResult(
                    source_path,
                    VideoInspectionStatus.READ_ERROR,
                    video_ts_path=video_ts,
                    title_set_numbers=tuple(sorted(set(title_sets))),
                    backend=backend,
                    diagnostic="libdvdnav n'a pas pu énumérer les titres; aucune protection n'est déduite.",
                    technical_detail=navigation_detail,
                )
            if not backend.dvdvideo_demuxer:
                return DvdInspectionResult(
                    source_path,
                    VideoInspectionStatus.BACKEND_UNAVAILABLE,
                    video_ts_path=video_ts,
                    title_set_numbers=tuple(sorted(set(title_sets))),
                    title_candidates=title_candidates,
                    backend=backend,
                    diagnostic=backend.diagnostic,
                )
            if auto_select_main_title and title_candidates:
                timed_candidates = [
                    candidate
                    for candidate in title_candidates
                    if candidate.duration_seconds is not None
                    and candidate.duration_seconds > 0
                ]
                if not timed_candidates:
                    return DvdInspectionResult(
                        source_path,
                        VideoInspectionStatus.TITLE_SELECTION_REQUIRED,
                        video_ts_path=video_ts,
                        title_set_numbers=tuple(sorted(set(title_sets))),
                        title_candidates=title_candidates,
                        backend=backend,
                        diagnostic="Sélection automatique impossible : aucune durée de titre valide.",
                    )
                longest_duration = max(
                    candidate.duration_seconds or 0 for candidate in timed_candidates
                )
                longest = [
                    candidate
                    for candidate in timed_candidates
                    if abs((candidate.duration_seconds or 0) - longest_duration) <= 1.0
                ]
                if len(longest) != 1:
                    return DvdInspectionResult(
                        source_path,
                        VideoInspectionStatus.TITLE_SELECTION_REQUIRED,
                        video_ts_path=video_ts,
                        title_set_numbers=tuple(sorted(set(title_sets))),
                        title_candidates=title_candidates,
                        backend=backend,
                        diagnostic="Sélection automatique ambiguë : plusieurs titres ont une durée maximale équivalente.",
                    )
                selected = longest[0]
                title_indices = (selected.title_index,)
                auto_selection_warning = (
                    f"Titre {selected.title_index} choisi par heuristique de durée maximale "
                    f"({selected.duration_seconds:.1f} s); ce choix n'identifie pas forcément le titre principal éditorial."
                )
                if selected.angle_count and selected.angle_count > 1:
                    auto_selection_warning += (
                        f" Seul l'angle 1 sur {selected.angle_count} sera sondé."
                    )
            else:
                return DvdInspectionResult(
                    source_path,
                    VideoInspectionStatus.TITLE_SELECTION_REQUIRED,
                    video_ts_path=video_ts,
                    title_set_numbers=tuple(sorted(set(title_sets))),
                    title_candidates=title_candidates,
                    backend=backend,
                    diagnostic=(
                        f"{len(title_candidates)} titre(s) énuméré(s); choisissez explicitement "
                        "les titres à inspecter par ffprobe."
                        if title_candidates
                        else "FFmpeg n'énumère pas les titres DVD; un numéro de titre explicite est requis."
                    ),
                )
        if angle_index < 1 or any(index < 1 for index in title_indices):
            raise ValueError("Les numéros de titre et d'angle doivent être positifs.")
        if title_candidates and any(index > len(title_candidates) for index in title_indices):
            raise ValueError("Un numéro de titre dépasse la liste énumérée par libdvdnav.")
        if not backend.dvdvideo_demuxer:
            return DvdInspectionResult(
                source_path,
                VideoInspectionStatus.BACKEND_UNAVAILABLE,
                video_ts_path=video_ts,
                title_set_numbers=tuple(sorted(set(title_sets))),
                title_candidates=title_candidates,
                backend=backend,
                diagnostic=backend.diagnostic,
                technical_detail=navigation_detail,
            )
        titles: list[DvdTitleInspection] = []
        warnings: list[str] = [auto_selection_warning] if auto_selection_warning else []
        for title_index in dict.fromkeys(title_indices):
            title, warning, detail = self._inspect_title(
                self._dvd_device_path(source_path), title_index, angle_index, backend
            )
            if title is None:
                status = (
                    VideoInspectionStatus.PROTECTED_OR_UNSUPPORTED
                    if warning and "protection" in warning.casefold()
                    else VideoInspectionStatus.READ_ERROR
                )
                return DvdInspectionResult(
                    source_path,
                    status,
                    video_ts_path=video_ts,
                    title_set_numbers=tuple(sorted(set(title_sets))),
                    title_candidates=title_candidates,
                    titles=tuple(titles),
                    backend=backend,
                    diagnostic=warning or "Échec de l'inspection DVD.",
                    technical_detail=detail,
                    warnings=tuple(warnings),
                )
            titles.append(title)
            if warning:
                warnings.append(f"Titre {title_index} : {warning}")
        return DvdInspectionResult(
            source_path,
            VideoInspectionStatus.INSPECTED,
            video_ts_path=video_ts,
            title_set_numbers=tuple(sorted(set(title_sets))),
            title_candidates=title_candidates,
            titles=tuple(titles),
            backend=backend,
            diagnostic=(
                "Inspection ffprobe terminée; aucun média n'a été extrait."
                if auto_selection_warning is None
                else "Titre candidat le plus long inspecté automatiquement; ce classement reste une heuristique."
            ),
            warnings=tuple(warnings),
        )
