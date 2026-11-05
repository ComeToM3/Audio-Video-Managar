"""Dialogue fiche DiscMetadata — saisie manuelle, validation, approbation."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
)

from audio_video_manager.metadata.apply_lookup import apply_release_candidate, identify_disc
from audio_video_manager.metadata.approval_fingerprint import (
    compute_approval_fingerprint,
    revoke_approval,
)
from audio_video_manager.metadata.cover_art import fetch_cover_art_info
from audio_video_manager.metadata.enums import (
    ApprovalState,
    CoverStatus,
    FieldTrust,
    JobMode,
    MetadataProvenance,
)
from audio_video_manager.metadata.libdiscid_loader import LibdiscidMissingError
from audio_video_manager.metadata.models import (
    DiscMetadata,
    FieldMeta,
    TocSnapshot,
    TrackMetadata,
    build_sheet_from_toc,
)
from audio_video_manager.metadata.musicbrainz_client import (
    DiscLookupResult,
    MusicBrainzError,
    ReleaseCandidate,
)
from audio_video_manager.metadata.path_preview import build_path_preview
from audio_video_manager.metadata.repository import DiscMetadataRepository
from audio_video_manager.metadata.toc_reader import diagnose_libdiscid
from audio_video_manager.metadata.validation import (
    ApprovalError,
    apply_validation,
    approve_sheet,
)
from audio_video_manager.storage.database import Database


def _confirmed() -> FieldMeta:
    return FieldMeta(
        trust=FieldTrust.CONFIRMED,
        provenance=MetadataProvenance.MANUAL,
    )


class DiscMetadataDialog(QDialog):
    def __init__(
        self,
        db: Database,
        sheet: DiscMetadata | None = None,
        parent=None,
        *,
        optical_device: str | None = None,
        preferred_release_country: str = "CA",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Fiche disque — DiscMetadata / MusicBrainz")
        self.resize(900, 720)
        self._db = db
        self._repo = DiscMetadataRepository(db)
        self.sheet = sheet or self._blank_sheet()
        self._optical_device = optical_device
        self._preferred_country = (preferred_release_country or "CA").strip().upper() or "CA"
        self._lookup: DiscLookupResult | None = None
        self._candidates: list[ReleaseCandidate] = []
        self._selection_summary = ""

        root = QVBoxLayout(self)
        root.addWidget(self._build_identify_group())
        root.addWidget(self._build_release_group())
        root.addWidget(self._build_disc_group())
        root.addWidget(self._build_tracks_group())
        root.addWidget(self._build_status_group())

        buttons = QHBoxLayout()
        self.btn_validate = QPushButton("Valider")
        self.btn_validate.clicked.connect(self.on_validate)
        self.btn_save = QPushButton("Enregistrer brouillon")
        self.btn_save.clicked.connect(self.on_save)
        self.btn_approve = QPushButton("Approuver la fiche")
        self.btn_approve.clicked.connect(self.on_approve)
        self.btn_reject = QPushButton("Refuser")
        self.btn_reject.clicked.connect(self.on_reject)
        buttons.addWidget(self.btn_validate)
        buttons.addWidget(self.btn_save)
        buttons.addWidget(self.btn_approve)
        buttons.addWidget(self.btn_reject)
        root.addLayout(buttons)

        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        box.rejected.connect(self.reject)
        box.accepted.connect(self.accept)
        root.addWidget(box)

        self._load_into_form()
        self.on_validate()

    def _build_identify_group(self) -> QGroupBox:
        box = QGroupBox("Identification CD (libdiscid + MusicBrainz)")
        v = QVBoxLayout(box)
        self.lbl_libdiscid = QLabel(diagnose_libdiscid())
        self.lbl_libdiscid.setWordWrap(True)
        row = QHBoxLayout()
        self.btn_identify = QPushButton("Lire TOC + chercher MusicBrainz")
        self.btn_identify.clicked.connect(self.on_identify)
        self.btn_apply_candidate = QPushButton("Appliquer l'édition sélectionnée")
        self.btn_apply_candidate.clicked.connect(self.on_apply_candidate)
        row.addWidget(self.btn_identify)
        row.addWidget(self.btn_apply_candidate)
        self.combo_candidates = QComboBox()
        self.combo_candidates.setMinimumWidth(480)
        self.lbl_cover = QLabel("Pochette: —")
        self.lbl_cover.setWordWrap(True)
        self.lbl_selection = QLabel(
            f"Préférence pays (départage): {self._preferred_country} — pas d'auto-approve"
        )
        self.lbl_selection.setWordWrap(True)
        v.addWidget(self.lbl_libdiscid)
        v.addLayout(row)
        v.addWidget(
            QLabel(
                "Éditions candidates (sélection intelligente si équivalentes ; "
                "Approuver reste manuel)"
            )
        )
        v.addWidget(self.combo_candidates)
        v.addWidget(self.lbl_selection)
        v.addWidget(self.lbl_cover)
        return box

    @staticmethod
    def _blank_sheet() -> DiscMetadata:
        toc = TocSnapshot(
            first_track=1,
            last_track=1,
            track_offsets_sectors=[0],
            track_durations_ms=[180000],
            audio_track_count=1,
            raw_source="manual_ui",
        )
        return build_sheet_from_toc(toc, mode=JobMode.NORMAL)

    def _build_release_group(self) -> QGroupBox:
        box = QGroupBox("Édition physique exacte")
        form = QFormLayout(box)
        self.edit_artist = QLineEdit()
        self.edit_album = QLineEdit()
        self.spin_year = QSpinBox()
        self.spin_year.setRange(0, 2100)
        self.spin_year.setSpecialValueText("(none)")
        self.chk_year_unavail = QCheckBox("Année unavailable (avec justification)")
        self.edit_year_just = QLineEdit()
        self.edit_label = QLineEdit()
        self.edit_catalog = QLineEdit()
        self.edit_country = QLineEdit()
        self.chk_compilation = QCheckBox("Compilation")
        self.chk_compilation.setTristate(True)
        self.combo_cover = QComboBox()
        for s in CoverStatus:
            self.combo_cover.addItem(s.value, s)
        self.edit_cover = QLineEdit()
        form.addRow("Album artist *", self.edit_artist)
        form.addRow("Album title *", self.edit_album)
        form.addRow("Année", self.spin_year)
        form.addRow("", self.chk_year_unavail)
        form.addRow("Justification année", self.edit_year_just)
        form.addRow("Label", self.edit_label)
        form.addRow("Catalogue", self.edit_catalog)
        form.addRow("Pays", self.edit_country)
        form.addRow("", self.chk_compilation)
        form.addRow("Pochette", self.combo_cover)
        form.addRow("Cover path/URL", self.edit_cover)
        return box

    def _build_disc_group(self) -> QGroupBox:
        box = QGroupBox("Disque (set) + identité")
        form = QFormLayout(box)
        self.spin_disc_n = QSpinBox()
        self.spin_disc_n.setRange(1, 99)
        self.spin_disc_total = QSpinBox()
        self.spin_disc_total.setRange(1, 99)
        self.edit_disc_id = QLineEdit()
        self.lbl_toc = QLabel("—")
        self.lbl_toc.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        form.addRow("Disc N°", self.spin_disc_n)
        form.addRow("Disc total", self.spin_disc_total)
        form.addRow("Disc ID", self.edit_disc_id)
        form.addRow("TOC", self.lbl_toc)
        return box

    def _build_tracks_group(self) -> QGroupBox:
        box = QGroupBox("Pistes")
        v = QVBoxLayout(box)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["N°", "Titre", "Artiste", "Durée ms"])
        self.table.horizontalHeader().setStretchLastSection(True)
        v.addWidget(self.table)
        return box

    def _build_status_group(self) -> QGroupBox:
        box = QGroupBox("Validation / aperçu chemins (zone C)")
        v = QVBoxLayout(box)
        self.lbl_approval = QLabel("—")
        self.txt_errors = QTextEdit()
        self.txt_errors.setReadOnly(True)
        self.txt_errors.setMaximumHeight(100)
        self.txt_preview = QTextEdit()
        self.txt_preview.setReadOnly(True)
        self.txt_preview.setMaximumHeight(120)
        v.addWidget(self.lbl_approval)
        v.addWidget(QLabel("Erreurs / avertissements"))
        v.addWidget(self.txt_errors)
        v.addWidget(QLabel("Aperçu chemins"))
        v.addWidget(self.txt_preview)
        return box

    def _load_into_form(self) -> None:
        s = self.sheet
        self.edit_artist.setText(s.edition.album_artist)
        self.edit_album.setText(s.edition.album_title)
        self.spin_year.setValue(s.edition.year or 0)
        yt = s.edition.field_meta.get("year")
        self.chk_year_unavail.setChecked(
            bool(yt and yt.trust == FieldTrust.UNAVAILABLE)
        )
        self.edit_year_just.setText(s.edition.year_unavailable_justification or "")
        self.edit_label.setText(s.edition.label or "")
        self.edit_catalog.setText(s.edition.catalog_number or "")
        self.edit_country.setText(s.edition.country or "")
        compilation_meta = s.edition.field_meta.get("is_compilation", FieldMeta())
        self.chk_compilation.setCheckState(
            Qt.CheckState.Checked
            if compilation_meta.trust == FieldTrust.CONFIRMED and s.edition.is_compilation
            else Qt.CheckState.Unchecked
            if compilation_meta.trust == FieldTrust.CONFIRMED
            else Qt.CheckState.PartiallyChecked
        )
        idx = self.combo_cover.findData(s.edition.cover_status)
        if idx >= 0:
            self.combo_cover.setCurrentIndex(idx)
        self.edit_cover.setText(s.edition.cover_path_or_url or "")
        self.spin_disc_n.setValue(s.disc.disc_number)
        self.spin_disc_total.setValue(s.disc.disc_total)
        self.edit_disc_id.setText(s.identity.disc_id or "")
        toc = s.identity.toc
        if toc:
            self.lbl_toc.setText(
                f"{toc.audio_track_count} pistes audio | source={toc.raw_source}"
            )
        self.table.setRowCount(len(s.tracks))
        for row, t in enumerate(sorted(s.tracks, key=lambda x: x.number)):
            self.table.setItem(row, 0, QTableWidgetItem(str(t.number)))
            self.table.setItem(row, 1, QTableWidgetItem(t.title))
            self.table.setItem(row, 2, QTableWidgetItem(t.artist))
            self.table.setItem(row, 3, QTableWidgetItem(str(t.duration_ms)))
            self.table.item(row, 0).setFlags(
                Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
            )

    def _apply_form_to_sheet(self) -> None:
        s = self.sheet
        approved_fingerprint = (
            compute_approval_fingerprint(s)
            if s.approval == ApprovalState.APPROVED
            else None
        )

        def apply_manual(attr: str, key: str, value) -> None:
            old = getattr(s.edition, attr)
            if old == value:
                return
            s.record_correction(
                f"edition.{attr}",
                old,
                value,
                note="Modification du formulaire",
                provenance=MetadataProvenance.USER_CORRECTION,
            )
            setattr(s.edition, attr, value)
            s.edition.field_meta[key] = FieldMeta(
                trust=FieldTrust.CONFIRMED,
                provenance=MetadataProvenance.USER_CORRECTION,
            )

        old_artist = s.edition.album_artist
        new_artist = self.edit_artist.text().strip()
        if old_artist != new_artist:
            apply_manual("album_artist", "album_artist", new_artist)

        old_album = s.edition.album_title
        new_album = self.edit_album.text().strip()
        if old_album != new_album:
            apply_manual("album_title", "album_title", new_album)

        if self.chk_year_unavail.isChecked():
            reason = self.edit_year_just.text().strip()
            if (
                s.edition.year is not None
                or s.edition.year_unavailable_justification != reason
                or s.edition.field_meta.get("year", FieldMeta()).trust
                != FieldTrust.UNAVAILABLE
            ):
                if s.edition.year is not None:
                    s.record_correction(
                        "edition.year",
                        s.edition.year,
                        None,
                        note="Année d’édition déclarée indisponible",
                        provenance=MetadataProvenance.USER_CORRECTION,
                    )
                s.edition.year = None
                s.edition.year_unavailable_justification = reason
                s.edition.field_meta["year"] = FieldMeta(
                    trust=FieldTrust.UNAVAILABLE,
                    provenance=MetadataProvenance.USER_CORRECTION,
                    note=reason,
                )
        else:
            y = self.spin_year.value()
            if y > 0:
                apply_manual("year", "year", y)
            elif s.edition.year is not None:
                apply_manual("year", "year", None)
                s.edition.field_meta["year"] = FieldMeta(trust=FieldTrust.MISSING)
            elif s.edition.field_meta.get("year", FieldMeta()).trust == FieldTrust.UNAVAILABLE:
                s.edition.field_meta["year"] = FieldMeta(trust=FieldTrust.MISSING)
            s.edition.year_unavailable_justification = None

        apply_manual("label", "label", self.edit_label.text().strip() or None)
        apply_manual(
            "catalog_number", "catalog_number", self.edit_catalog.text().strip() or None
        )
        apply_manual("country", "country", self.edit_country.text().strip() or None)
        if self.chk_compilation.checkState() != Qt.CheckState.PartiallyChecked:
            compilation = self.chk_compilation.checkState() == Qt.CheckState.Checked
            if (
                s.edition.is_compilation != compilation
                or s.edition.field_meta.get("is_compilation", FieldMeta()).trust
                != FieldTrust.CONFIRMED
            ):
                old = s.edition.is_compilation
                s.record_correction(
                    "edition.is_compilation",
                    old,
                    compilation,
                    note="Classification confirmée dans le dialogue",
                    provenance=MetadataProvenance.USER_CORRECTION,
                )
                s.edition.is_compilation = compilation
                s.edition.field_meta["is_compilation"] = FieldMeta(
                    trust=FieldTrust.CONFIRMED,
                    provenance=MetadataProvenance.USER_CORRECTION,
                )
        cover_status = self.combo_cover.currentData()
        cover_path = self.edit_cover.text().strip() or None
        if (
            cover_status != s.edition.cover_status
            or cover_path != s.edition.cover_path_or_url
        ):
            s.edition.cover_status = cover_status
            s.edition.cover_path_or_url = cover_path
            s.edition.field_meta["cover_status"] = FieldMeta(
                trust=(
                    FieldTrust.CONFIRMED
                    if cover_status == CoverStatus.CONFIRMED
                    else FieldTrust.UNAVAILABLE
                    if cover_status == CoverStatus.UNAVAILABLE
                    else FieldTrust.MISSING
                ),
                provenance=MetadataProvenance.USER_CORRECTION,
            )

        disc_number = self.spin_disc_n.value()
        if disc_number != s.disc.disc_number:
            s.record_correction("disc.disc_number", s.disc.disc_number, disc_number)
            s.disc.disc_number = disc_number
            s.disc.field_meta["disc_number"] = FieldMeta(
                trust=FieldTrust.CONFIRMED,
                provenance=MetadataProvenance.USER_CORRECTION,
            )
        disc_total = self.spin_disc_total.value()
        if disc_total != s.disc.disc_total:
            s.record_correction("disc.disc_total", s.disc.disc_total, disc_total)
            s.disc.disc_total = disc_total
            s.disc.field_meta["disc_total"] = FieldMeta(
                trust=FieldTrust.CONFIRMED,
                provenance=MetadataProvenance.USER_CORRECTION,
            )
        disc_id = self.edit_disc_id.text().strip() or None
        if disc_id != s.identity.disc_id:
            s.record_correction("identity.disc_id", s.identity.disc_id, disc_id)
            s.identity.disc_id = disc_id
            s.identity.field_meta["disc_id"] = FieldMeta(
                trust=FieldTrust.CONFIRMED if disc_id else FieldTrust.MISSING,
                provenance=MetadataProvenance.USER_CORRECTION,
            )

        new_tracks: list[TrackMetadata] = []
        for row in range(self.table.rowCount()):
            num = int(self.table.item(row, 0).text())
            title = self.table.item(row, 1).text().strip() if self.table.item(row, 1) else ""
            artist = self.table.item(row, 2).text().strip() if self.table.item(row, 2) else ""
            dur = int(self.table.item(row, 3).text()) if self.table.item(row, 3) else 0
            old = next((t for t in s.tracks if t.number == num), None)
            if old and old.title != title:
                s.record_correction(f"track[{num}].title", old.title, title)
            if old and old.artist != artist:
                s.record_correction(f"track[{num}].artist", old.artist, artist)
            if old and old.duration_ms != dur:
                s.record_correction(f"track[{num}].duration_ms", old.duration_ms, dur)
            field_meta = dict(old.field_meta) if old else {}
            for key, old_value, new_value in (
                ("title", old.title if old else "", title),
                ("artist", old.artist if old else "", artist),
                ("duration_ms", old.duration_ms if old else 0, dur),
            ):
                if old_value != new_value:
                    field_meta[key] = FieldMeta(
                        trust=FieldTrust.CONFIRMED,
                        provenance=MetadataProvenance.USER_CORRECTION,
                    )
                elif key not in field_meta:
                    field_meta[key] = (
                        FieldMeta(
                            trust=FieldTrust.CONFIRMED,
                            provenance=MetadataProvenance.TOC,
                        )
                        if key == "duration_ms"
                        else _confirmed()
                    )
            tm = TrackMetadata(
                number=num,
                title=title,
                artist=artist,
                duration_ms=dur,
                isrc=old.isrc if old else None,
                musicbrainz_recording_id=(old.musicbrainz_recording_id if old else None),
                musicbrainz_track_id=(old.musicbrainz_track_id if old else None),
                field_meta=field_meta,
            )
            new_tracks.append(tm)
        s.tracks = new_tracks
        s.mode = JobMode.NORMAL
        s.touch()
        if (
            approved_fingerprint is not None
            and compute_approval_fingerprint(s) != approved_fingerprint
        ):
            revoke_approval(
                s,
                note="La fiche approuvée a été modifiée; réapprobation requise.",
            )

    def on_validate(self) -> None:
        self._apply_form_to_sheet()
        result = apply_validation(self.sheet)
        self.sheet.path_preview = build_path_preview(self.sheet)
        self.lbl_approval.setText(
            f"État: {self.sheet.approval.value} | validation OK={result.ok}"
        )
        lines = ["ERREURS:"] + [f"- {e}" for e in result.errors]
        lines += ["", "AVERTISSEMENTS:"] + [f"- {w}" for w in result.warnings]
        self.txt_errors.setPlainText("\n".join(lines))
        self.txt_preview.setPlainText("\n".join(self.sheet.path_preview))

    def on_save(self) -> None:
        self.on_validate()
        self._repo.save(self.sheet)
        QMessageBox.information(self, "Brouillon", f"Fiche enregistrée: {self.sheet.id}")

    def _fill_candidates_combo(self) -> None:
        self.combo_candidates.clear()
        for c in self._candidates:
            label = (
                f"{c.artist_credit} — {c.title} "
                f"[{c.country or '?'} {c.date or ''}] "
                f"toc={c.toc_match} "
                f"{('/'.join(c.catalog_numbers)) if c.catalog_numbers else ''}"
            )
            self.combo_candidates.addItem(label.strip(), c.release_id)

    def on_identify(self) -> None:
        try:
            sheet, lookup, cover, decision = identify_disc(
                self._optical_device,
                preferred_release_country=self._preferred_country,
            )
        except LibdiscidMissingError as exc:
            QMessageBox.critical(self, "libdiscid", str(exc))
            return
        except MusicBrainzError as exc:
            QMessageBox.warning(self, "MusicBrainz", str(exc))
            return
        except RuntimeError as exc:
            QMessageBox.warning(self, "Lecture CD", str(exc))
            return
        self.sheet = sheet
        self._lookup = lookup
        self._candidates = list(lookup.candidates) if lookup else []
        self._selection_summary = decision.summary
        self._fill_candidates_combo()
        if decision.selected is not None:
            for i, c in enumerate(self._candidates):
                if c.release_id == decision.selected.release_id:
                    self.combo_candidates.setCurrentIndex(i)
                    break
        warn_txt = "\n".join(f"• {w}" for w in decision.warnings[:8]) or "(aucun)"
        self.lbl_selection.setText(
            f"{decision.summary}\n"
            f"auto={decision.auto_selected} | manuel requis={decision.require_manual_choice}\n"
            f"Écarts / notes:\n{warn_txt}"
        )
        if cover:
            self.lbl_cover.setText(
                f"Pochette: {cover.status} — {cover.message}\n{cover.thumbnail_url or ''}"
            )
        else:
            self.lbl_cover.setText("Pochette: (non récupérée — absente ou non demandée)")
        self._load_into_form()
        self.on_validate()
        QMessageBox.information(
            self,
            "Identification",
            decision.summary
            + "\n\nAucune approbation automatique — vérifiez puis Approuver.",
        )

    def on_apply_candidate(self) -> None:
        if not self._candidates:
            QMessageBox.information(self, "Édition", "Aucun candidat à appliquer.")
            return
        idx = self.combo_candidates.currentIndex()
        if idx < 0 or idx >= len(self._candidates):
            return
        cand = self._candidates[idx]
        cover = fetch_cover_art_info(cand.release_id)
        self.lbl_cover.setText(
            f"Pochette: {cover.status} — {cover.message}\n{cover.thumbnail_url or ''}"
        )
        if self.sheet.approval == ApprovalState.APPROVED:
            revoke_approval(self.sheet, note="Édition modifiée — réapprobation requise.")
        apply_release_candidate(self.sheet, cand, cover=cover, user_selected=True)
        self._load_into_form()
        self.on_validate()
        QMessageBox.information(
            self,
            "Édition appliquée",
            f"Release {cand.release_id} appliquée (confirmed).\n"
            "Approuvez manuellement si la validation est OK.",
        )

    def on_approve(self) -> None:
        self._apply_form_to_sheet()
        try:
            approve_sheet(self.sheet, note="UI Approuver la fiche")
        except ApprovalError as exc:
            apply_validation(self.sheet)
            self.on_validate()
            QMessageBox.warning(self, "Approbation refusée", str(exc))
            return
        self._repo.save(self.sheet)
        self.on_validate()
        QMessageBox.information(self, "Approuvé", "Fiche Approved — rip archive déverrouillé.")

    def on_reject(self) -> None:
        from audio_video_manager.metadata.enums import ApprovalState

        self._apply_form_to_sheet()
        self.sheet.approval = ApprovalState.REJECTED
        self.sheet.approved_at = None
        self._repo.save(self.sheet)
        self.on_validate()
        QMessageBox.information(self, "Refusé", "Fiche marquée Rejected.")
