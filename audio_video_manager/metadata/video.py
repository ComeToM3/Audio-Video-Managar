"""Résultats d'inspection DVD-Video; distincts des pistes audio CD."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class VideoInspectionStatus(str, Enum):
    INSPECTED = "inspected"
    BACKEND_UNAVAILABLE = "backend_unavailable"
    TITLE_SELECTION_REQUIRED = "title_selection_required"
    INVALID_STRUCTURE = "invalid_structure"
    READ_ERROR = "read_error"
    PROTECTED_OR_UNSUPPORTED = "protected_or_unsupported"
    BACKEND_ERROR = "backend_error"


@dataclass(frozen=True)
class DvdBackendCapabilities:
    executable: Path | None
    version: str | None
    dvdvideo_demuxer: bool
    diagnostic: str


@dataclass(frozen=True)
class VideoStream:
    index: int | None
    codec_type: str
    codec_name: str | None = None
    language: str | None = None
    title: str | None = None
    width: int | None = None
    height: int | None = None
    sample_rate: int | None = None
    channels: int | None = None
    channel_layout: str | None = None
    bits_per_raw_sample: int | None = None


@dataclass(frozen=True)
class VideoChapter:
    index: int
    start_seconds: float | None = None
    end_seconds: float | None = None
    title: str | None = None


@dataclass(frozen=True)
class DvdTitleInspection:
    title_index: int
    angle_index: int
    duration_seconds: float | None = None
    format_name: str | None = None
    streams: tuple[VideoStream, ...] = ()
    chapters: tuple[VideoChapter, ...] = ()

    @property
    def video_streams(self) -> tuple[VideoStream, ...]:
        return tuple(stream for stream in self.streams if stream.codec_type == "video")

    @property
    def audio_streams(self) -> tuple[VideoStream, ...]:
        return tuple(stream for stream in self.streams if stream.codec_type == "audio")

    @property
    def subtitle_streams(self) -> tuple[VideoStream, ...]:
        return tuple(stream for stream in self.streams if stream.codec_type == "subtitle")


@dataclass(frozen=True)
class DvdTitleCandidate:
    title_index: int
    part_count: int | None = None
    angle_count: int | None = None
    duration_seconds: float | None = None
    chapters: tuple[VideoChapter, ...] = ()


@dataclass(frozen=True)
class DvdInspectionResult:
    source: Path
    status: VideoInspectionStatus
    video_ts_path: Path | None = None
    title_set_numbers: tuple[int, ...] = ()
    title_candidates: tuple[DvdTitleCandidate, ...] = ()
    titles: tuple[DvdTitleInspection, ...] = ()
    backend: DvdBackendCapabilities | None = None
    diagnostic: str = ""
    technical_detail: str | None = None
    warnings: tuple[str, ...] = field(default_factory=tuple)