"""Worker Qt : identify_disc hors thread UI."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from audio_video_manager.config import AppConfig
from audio_video_manager.extraction.cd import probe_freaccmd
from audio_video_manager.extraction.cd_ripper import FreacCdRipper
from audio_video_manager.extraction.drives import CdDrive
from audio_video_manager.metadata.apply_lookup import identify_disc
from audio_video_manager.metadata.cover_art import CoverArtResult, fetch_cover_art_info
from audio_video_manager.metadata.enrichment import (
    build_enrichment_report,
    lookup_discogs_by_barcode,
    verified_discogs_cover_url,
)
from audio_video_manager.metadata.musicbrainz_client import ReleaseCandidate
from audio_video_manager.metadata.toc_reader import (
    DiscReadResult,
    list_cdrom_device_letters,
    read_disc_toc,
)
from audio_video_manager.logging_setup import get_logger
from audio_video_manager.ui.cover_cache import fetch_cover_to_cache

log = get_logger("ui.identify_worker")


@dataclass(frozen=True)
class OpticalScanResult:
    drives: tuple[CdDrive, ...]
    devices: tuple[str, ...]
    discs: tuple[DiscReadResult, ...]
    read_errors: tuple[str, ...]
    freaccmd_error: str | None = None


class OpticalMediaScanWorker(QObject):
    """Énumère fre:ac et lit les TOC Windows hors du thread d’interface."""

    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self._config = config
        self._cancel = threading.Event()

    def cancel(self) -> None:
        self._cancel.set()

    @Slot()
    def run(self) -> None:
        try:
            status = probe_freaccmd(
                configured_path=self._config.freaccmd_path or None,
                freac_install_dir=self._config.freac_install_dir or None,
                run_probes=False,
            )
            drives: list[CdDrive] = []
            freaccmd_error = None
            if status.found and status.path:
                try:
                    drives = FreacCdRipper(status.path).list_drives()
                except Exception as exc:  # noqa: BLE001
                    freaccmd_error = str(exc)
            else:
                freaccmd_error = status.message

            devices = list_cdrom_device_letters()
            discs: list[DiscReadResult] = []
            read_errors: list[str] = []
            for device in devices:
                if self._cancel.is_set():
                    break
                try:
                    discs.append(read_disc_toc(device))
                except Exception as exc:  # noqa: BLE001
                    read_errors.append(f"{device}: {exc}")
            self.finished.emit(
                OpticalScanResult(
                    drives=tuple(drives),
                    devices=tuple(devices),
                    discs=tuple(discs),
                    read_errors=tuple(read_errors),
                    freaccmd_error=freaccmd_error,
                )
            )
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))


class IdentifyWorker(QObject):
    finished = Signal(object, object, object, object, object)  # sheet, lookup, cover, decision, evidence
    failed = Signal(str)
    progress = Signal(str)

    def __init__(
        self,
        *,
        optical_device: str | None,
        preferred_country: str,
        disc_read: DiscReadResult | None = None,
    ) -> None:
        super().__init__()
        self._device = optical_device
        self._country = preferred_country
        self._disc_read = disc_read

    @Slot()
    def run(self) -> None:
        try:
            self.progress.emit("Recherche des informations…")
            sheet, lookup, cover, decision = identify_disc(
                self._device,
                disc_read=self._disc_read,
                preferred_release_country=self._country,
                fetch_cover=False,
            )
            candidates = list(lookup.candidates) if lookup is not None else []
            log.info(
                "AVM28E_TRACE candidates_received disc_id=%s count=%d releases=%s "
                "selected=%s auto=%s album=%r artist=%r year=%s tracks=%d",
                sheet.identity.disc_id,
                len(candidates),
                [
                    (candidate.selection_key, candidate.match_source)
                    for candidate in candidates
                ],
                decision.selected.release_id if decision.selected else None,
                decision.auto_selected,
                sheet.edition.album_title,
                sheet.edition.album_artist,
                sheet.edition.year,
                len(sheet.tracks),
            )
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
            return
        self.finished.emit(sheet, lookup, cover, decision, None)


class EditionEnrichmentWorker(QObject):
    """Charge la pochette et les sources secondaires hors du thread UI."""

    finished = Signal(str, object, object, object)
    failed = Signal(str, str)

    def __init__(
        self,
        candidate: ReleaseCandidate,
        *,
        toc_durations_ms: list[int] | None = None,
    ) -> None:
        super().__init__()
        self._candidate = candidate
        self._toc_durations_ms = toc_durations_ms

    @Slot()
    def run(self) -> None:
        candidate = self._candidate
        cover = CoverArtResult(
            release_id=candidate.release_id,
            status="error",
            front_url=None,
            thumbnail_url=None,
            message="Aucune source de pochette n’a répondu.",
        )
        cover_path = None
        try:
            cover = fetch_cover_art_info(candidate.release_id)
            if cover.status == "confirmed":
                for image_url in dict.fromkeys(
                    url for url in (cover.thumbnail_url, cover.front_url) if url
                ):
                    try:
                        cover_path = fetch_cover_to_cache(image_url)
                    except Exception as exc:  # noqa: BLE001
                        log.warning("Téléchargement CAA échoué release=%s : %s", candidate.release_id, exc)
                    if cover_path is not None:
                        break
                if cover_path is None:
                    cover = CoverArtResult(
                        release_id=candidate.release_id,
                        status="error",
                        front_url=cover.front_url,
                        thumbnail_url=cover.thumbnail_url,
                        message="CAA référence une image, mais aucune URL ne fournit un fichier décodable.",
                    )
        except Exception as exc:  # noqa: BLE001
            log.warning("Pochette indisponible release=%s: %s", candidate.release_id, exc)
            cover = CoverArtResult(
                release_id=candidate.release_id,
                status="error",
                front_url=None,
                thumbnail_url=None,
                message=f"Cover Art Archive indisponible : {type(exc).__name__}.",
            )

        try:
            discogs = lookup_discogs_by_barcode(candidate.barcode)
        except Exception as exc:  # noqa: BLE001
            log.warning("Enrichissement Discogs indisponible : %s", exc)
            discogs = None
        if cover_path is None:
            fallback_url = verified_discogs_cover_url(candidate, discogs)
            if fallback_url:
                try:
                    cover_path = fetch_cover_to_cache(fallback_url)
                except Exception as exc:  # noqa: BLE001
                    log.warning("Téléchargement pochette Discogs release=%s : %s", candidate.release_id, exc)
                cover = CoverArtResult(
                    release_id=candidate.release_id,
                    status="confirmed" if cover_path is not None else "error",
                    front_url=fallback_url,
                    thumbnail_url=fallback_url,
                    message=(
                        "Pochette Discogs vérifiée par code-barres, titre et tracklist."
                        if cover_path is not None
                        else "Discogs fournit une image, mais son téléchargement ou décodage a échoué."
                    ),
                    source="Discogs",
                )
        try:
            report = build_enrichment_report(
                candidate,
                discogs,
                toc_durations_ms=self._toc_durations_ms,
            )
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(candidate.release_id, str(exc))
            return
        self.finished.emit(candidate.release_id, cover, cover_path, report)
