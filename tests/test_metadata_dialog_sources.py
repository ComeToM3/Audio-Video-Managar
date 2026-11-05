from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from audio_video_manager.metadata.enums import (
    FieldTrust,
    MetadataProvenance,
)
from audio_video_manager.metadata.factories import make_approvable_sheet
from audio_video_manager.metadata.models import FieldMeta
from audio_video_manager.metadata.validation import approve_sheet
from audio_video_manager.storage import Database
from audio_video_manager.ui.metadata_dialog import DiscMetadataDialog


def test_dialog_validation_preserves_unconfirmed_source_fields(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    db = Database(tmp_path / "metadata-dialog.sqlite3")
    db.initialize()
    sheet = make_approvable_sheet()
    sheet.edition.is_compilation = True
    sheet.edition.field_meta["is_compilation"] = FieldMeta(
        trust=FieldTrust.AMBIGUOUS,
        provenance=MetadataProvenance.MUSICBRAINZ,
        note="release-group Compilation",
    )
    sheet.tracks[0].musicbrainz_recording_id = "recording-source-id"
    sheet.tracks[0].field_meta["title"] = FieldMeta(
        trust=FieldTrust.CONFIRMED,
        provenance=MetadataProvenance.MUSICBRAINZ,
    )
    dialog = DiscMetadataDialog(db, sheet)
    try:
        dialog._apply_form_to_sheet()  # noqa: SLF001
        assert dialog.sheet.edition.is_compilation is True
        assert dialog.sheet.edition.field_meta["is_compilation"].trust == FieldTrust.AMBIGUOUS
        assert dialog.sheet.tracks[0].musicbrainz_recording_id == "recording-source-id"
        assert dialog.sheet.tracks[0].field_meta["title"].provenance == MetadataProvenance.MUSICBRAINZ
    finally:
        dialog.close()
        db.close()
        del app


def test_dialog_explicit_compilation_choice_is_confirmed(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    db = Database(tmp_path / "metadata-dialog-choice.sqlite3")
    db.initialize()
    sheet = make_approvable_sheet()
    sheet.edition.is_compilation = True
    sheet.edition.field_meta["is_compilation"] = FieldMeta(
        trust=FieldTrust.AMBIGUOUS,
        provenance=MetadataProvenance.MUSICBRAINZ,
    )
    dialog = DiscMetadataDialog(db, sheet)
    try:
        assert dialog.chk_compilation.checkState() == Qt.CheckState.PartiallyChecked
        dialog.chk_compilation.setCheckState(Qt.CheckState.Unchecked)
        dialog._apply_form_to_sheet()  # noqa: SLF001
        assert dialog.sheet.edition.is_compilation is False
        assert dialog.sheet.edition.field_meta["is_compilation"].trust == FieldTrust.CONFIRMED
        assert (
            dialog.sheet.edition.field_meta["is_compilation"].provenance
            == MetadataProvenance.USER_CORRECTION
        )
    finally:
        dialog.close()
        db.close()
        del app


def test_dialog_keeps_approval_if_unchanged_and_revokes_after_edit(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    db = Database(tmp_path / "metadata-dialog-approved.sqlite3")
    db.initialize()
    sheet = make_approvable_sheet()
    approve_sheet(sheet)
    dialog = DiscMetadataDialog(db, sheet)
    try:
        dialog._apply_form_to_sheet()  # noqa: SLF001
        assert dialog.sheet.approval.value == "Approved"
        dialog.edit_album.setText("Edited after approval")
        dialog._apply_form_to_sheet()  # noqa: SLF001
        assert dialog.sheet.approval.value == "Pending"
        assert any("réapprobation" in warning for warning in dialog.sheet.validation_warnings)
    finally:
        dialog.close()
        db.close()
        del app
