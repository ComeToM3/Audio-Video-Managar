"""Métadonnées de la source vidéo, indépendantes de ses futures versions."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class VideoStream:
    index: int
    kind: str
    codec: str | None = None
    language: str | None = None
    width: int | None = None
    height: int | None = None
    frame_rate: str | None = None
    aspect_ratio: str | None = None
    field_order: str | None = None
    channels: int | None = None
    sample_rate: int | None = None


@dataclass(frozen=True)
class VideoChapter:
    number: int
    start_seconds: float
    end_seconds: float
    title: str | None = None


@dataclass(frozen=True)
class VideoTitle:
    """Un titre DVD sélectionné, pas un inventaire exhaustif du disque.

    Ces flux décrivent la source : ils ne promettent pas une compatibilité MP4.
    Un futur MKV maître devra les conserver sans réencodage ; une version MP4
    restera une version distincte, jamais un remplacement du maître.
    """

    source: Path
    title_number: int
    duration_seconds: float | None
    streams: tuple[VideoStream, ...]
    chapters: tuple[VideoChapter, ...]
