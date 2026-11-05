"""Worker Qt : identify_disc hors thread UI."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot

from audio_video_manager.metadata.apply_lookup import identify_disc
from audio_video_manager.metadata.enrichment import (
    build_enrichment_report,
    lookup_discogs_by_barcode,
)
from audio_video_manager.metadata.toc_reader import DiscReadResult


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
                fetch_cover=True,
            )
            selected = decision.selected
            discogs = (
                lookup_discogs_by_barcode(selected.barcode)
                if selected is not None
                else None
            )
            enrichment = (
                build_enrichment_report(
                    selected,
                    discogs,
                    toc_durations_ms=(
                        self._disc_read.toc.track_durations_ms
                        if self._disc_read is not None
                        else None
                    ),
                )
                if selected is not None
                else None
            )
            self.finished.emit(sheet, lookup, cover, decision, enrichment)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
