"""Inspection DVD en lecture seule. L'extraction reste reportée (D-010)."""

from __future__ import annotations

import json
import math
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from audio_video_manager.extraction.cd import CommandProbe, _run_probe
from audio_video_manager.metadata.video import VideoChapter, VideoStream, VideoTitle
from audio_video_manager.verification.flac_decode import find_flac_decode_tool


class DvdExtractionNotAvailableError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("L'extraction DVD est reportée (décision D-010).")


@dataclass(frozen=True)
class DvdToolCapabilities:
    executable: Path | None
    status: str
    dvdvideo: bool = False
    title_option: bool = False
    probes: tuple[CommandProbe, ...] = ()


@dataclass(frozen=True)
class DvdStructure:
    video_ts: Path
    title_sets: tuple[int, ...]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class DvdInspection:
    status: str
    message: str
    structure: DvdStructure | None = None
    title: VideoTitle | None = None
    probe: CommandProbe | None = None
    capabilities: DvdToolCapabilities | None = None


def probe_dvd_tool(executable: Path | None) -> DvdToolCapabilities:
    """Interroge le binaire réel, jamais sa seule version ou sa buildconf."""
    if executable is None:
        return DvdToolCapabilities(None, "tool_missing")
    probes = []
    for args in (
        ("-version",),
        ("-buildconf",),
        ("-hide_banner", "-demuxers"),
        ("-hide_banner", "-h", "demuxer=dvdvideo"),
    ):
        probe = _run_probe(executable, *args)
        probes.append(probe)
        if probe.error or probe.returncode != 0:
            return DvdToolCapabilities(executable, "tool_error", probes=tuple(probes))
    demuxers = probes[2].stdout + "\n" + probes[2].stderr
    help_text = probes[3].stdout + "\n" + probes[3].stderr
    dvdvideo = bool(re.search(r"^\s*D\s+dvdvideo(?:\s|$)", demuxers, re.MULTILINE))
    title_option = bool(re.search(r"^\s*-title\s", help_text, re.MULTILINE))
    return DvdToolCapabilities(
        executable,
        "available" if dvdvideo and title_option else "dvdvideo_unavailable",
        dvdvideo,
        title_option,
        tuple(probes),
    )


def inspect_dvd_structure(source: Path) -> DvdStructure:
    """Vérifie les noms et signatures IFO, sans lire les secteurs vidéo."""
    source = source.resolve(strict=True)
    if not source.is_dir():
        raise ValueError("Une racine de DVD montée ou un dossier VIDEO_TS est requis.")
    if source.name.upper() == "VIDEO_TS":
        video_ts = source
    else:
        video_ts = next(
            (p for p in source.iterdir() if p.name.upper() == "VIDEO_TS" and p.is_dir()),
            None,
        )
        if video_ts is None:
            raise ValueError("Dossier VIDEO_TS absent : ce n'est pas une structure DVD-Video.")
    files = {p.name.upper(): p for p in video_ts.iterdir()}

    def check_ifo(name: str, signature: bytes) -> None:
        path = files.get(name)
        if path is None or not path.is_file():
            raise ValueError(f"Structure DVD incomplète : {name} absent.")
        with path.open("rb") as handle:
            if handle.read(12) != signature:
                raise ValueError(f"Signature IFO invalide : {name}.")

    check_ifo("VIDEO_TS.IFO", b"DVDVIDEO-VMG")
    title_sets = sorted(
        int(match.group(1))
        for name in files
        if (match := re.fullmatch(r"VTS_(0[1-9]|[1-9]\d)_0\.IFO", name))
    )
    if not title_sets:
        raise ValueError("Aucun ensemble VTS trouvé.")
    warnings = []
    for name in ("VIDEO_TS", *(f"VTS_{number:02d}_0" for number in title_sets)):
        if name != "VIDEO_TS":
            check_ifo(f"{name}.IFO", b"DVDVIDEO-VTS")
            vob = files.get(name[:-1] + "1.VOB")
            if vob is None or not vob.is_file():
                raise ValueError(f"Structure DVD incomplète : {name[:-1]}1.VOB absent.")
        backup = files.get(f"{name}.BUP")
        if backup is None or not backup.is_file():
            warnings.append(f"{name}.BUP absent.")
    return DvdStructure(video_ts, tuple(title_sets), tuple(warnings))


def _seconds(value: object) -> float | None:
    if value is None or value == "N/A":
        return None
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise ValueError("Durée vidéo invalide.")
    return result


def parse_dvd_probe(text: str, source: Path, title_number: int) -> VideoTitle:
    """Interprète le JSON ffprobe sans inventer les champs absents."""
    data = json.loads(text)
    if not isinstance(data, dict) or data.get("error"):
        raise ValueError("Réponse ffprobe invalide.")
    streams = []
    for stream in data["streams"]:
        tags = stream.get("tags", {})
        streams.append(
            VideoStream(
                index=int(stream["index"]),
                kind=stream["codec_type"],
                codec=stream.get("codec_name"),
                language=tags.get("language"),
                width=int(stream["width"]) if "width" in stream else None,
                height=int(stream["height"]) if "height" in stream else None,
                frame_rate=stream.get("avg_frame_rate"),
                aspect_ratio=stream.get("display_aspect_ratio"),
                field_order=stream.get("field_order"),
                channels=int(stream["channels"]) if "channels" in stream else None,
                sample_rate=int(stream["sample_rate"]) if "sample_rate" in stream else None,
            )
        )
    if not any(s.kind == "video" for s in streams):
        raise ValueError("Aucun flux vidéo trouvé.")
    chapters = []
    for number, chapter in enumerate(data.get("chapters", []), 1):
        start = _seconds(chapter["start_time"])
        end = _seconds(chapter["end_time"])
        if start is None or end is None or end < start:
            raise ValueError("Chapitre DVD invalide.")
        chapters.append(VideoChapter(number, start, end, chapter.get("tags", {}).get("title")))
    return VideoTitle(
        source,
        title_number,
        _seconds(data.get("format", {}).get("duration")),
        tuple(streams),
        tuple(chapters),
    )


class DvdInspector:
    """Inspection synchrone bornée, à appeler hors du thread UI.

    Par défaut, seuls les noms/signatures sont lus. La sonde de métadonnées
    exige une source indépendamment connue comme non protégée : libdvdread
    peut charger libdvdcss automatiquement. Ne pas l'activer pour un DVD
    commercial dont la protection est inconnue.
    """

    def __init__(
        self,
        *,
        ffprobe: Path | None = None,
        ffmpeg: Path | None = None,
        no_css_environment: bool = False,
    ) -> None:
        # Attestation externe d'une pile auditée incapable de charger libdvdcss.
        # Les options d'aide de FFmpeg ne permettent pas de la vérifier.
        self.no_css_environment = no_css_environment
        self.ffmpeg = ffmpeg if ffmpeg is not None else find_flac_decode_tool()
        sibling = self.ffmpeg.with_name("ffprobe" + self.ffmpeg.suffix) if self.ffmpeg else None
        discovered = shutil.which("ffprobe")
        self.ffprobe = ffprobe if ffprobe is not None else (
            sibling if sibling is not None and sibling.is_file()
            else Path(discovered) if discovered else None
        )

    def inspect(
        self,
        source: Path,
        *,
        title_number: int = 1,
        known_unprotected: bool = False,
    ) -> DvdInspection:
        if isinstance(title_number, bool) or not isinstance(title_number, int) or not 1 <= title_number <= 99:
            return DvdInspection("invalid_title", "Le numéro de titre doit être entre 1 et 99.")
        try:
            structure = inspect_dvd_structure(Path(source))
        except FileNotFoundError as exc:
            return DvdInspection("source_missing", f"Support absent ou chemin introuvable : {exc}")
        except OSError as exc:
            return DvdInspection("read_error", f"Accès au support impossible : {exc}")
        except ValueError as exc:
            return DvdInspection("invalid_structure", str(exc))
        if known_unprotected is not True:
            return DvdInspection(
                "structure_only",
                "Structure reconnue ; lisibilité vidéo et protection indéterminées. "
                "Sonde non lancée sans source connue non protégée.",
                structure,
            )
        if self.no_css_environment is not True:
            return DvdInspection(
                "backend_unverified",
                "Sonde non lancée : absence de CSS dans la pile de dépendances non vérifiée. "
                "Aucune option runtime de désactivation fiable n'est présumée.",
                structure,
            )
        capabilities = probe_dvd_tool(self.ffprobe)
        if capabilities.status != "available":
            return DvdInspection(
                capabilities.status,
                "ffprobe absent, défaillant ou sans démultiplexeur dvdvideo/options requis. "
                "Cela ne démontre ni erreur du disque ni protection.",
                structure,
                capabilities=capabilities,
            )
        probe = _run_probe(
            self.ffprobe,
            "-v", "error",
            "-f", "dvdvideo",
            "-title", str(title_number),
            "-show_streams", "-show_chapters", "-show_format",
            "-of", "json",
            "-i", str(structure.video_ts),
        )
        if probe.error or probe.returncode != 0:
            detail = probe.stderr or probe.error or probe.stdout
            return DvdInspection(
                "probe_error" if probe.error else "read_error",
                f"Lecture non validée : {detail}. "
                "Une erreur de lecture seule ne prouve pas une protection.",
                structure, probe=probe, capabilities=capabilities,
            )
        try:
            title = parse_dvd_probe(probe.stdout, structure.video_ts, title_number)
        except (ValueError, KeyError, TypeError, AttributeError, OverflowError) as exc:
            return DvdInspection(
                "invalid_metadata", f"Métadonnées ffprobe invalides : {exc}",
                structure, probe=probe, capabilities=capabilities,
            )
        return DvdInspection(
            "inspected",
            "Métadonnées du titre sélectionné lues ; ni inventaire complet ni décodage intégral.",
            structure, title, probe, capabilities,
        )
