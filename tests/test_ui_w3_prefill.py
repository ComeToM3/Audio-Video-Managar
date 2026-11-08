"""AVM-06C-F1 — préremplissage W3 depuis DiscMetadata (régression wipe Qt signals)."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from audio_video_manager.config import AppConfig
from audio_video_manager.metadata.approval_fingerprint import compute_approval_fingerprint
from audio_video_manager.metadata.enums import (
    ApprovalState,
    CoverStatus,
    FieldTrust,
    MetadataProvenance,
)
from audio_video_manager.metadata.enrichment import EnrichmentReport, MetadataEvidence
from audio_video_manager.metadata.factories import make_approvable_sheet
from audio_video_manager.metadata.models import FieldMeta
from audio_video_manager.metadata.validation import approve_sheet
from audio_video_manager.storage import Database
from audio_video_manager.ui.wizard.archive_wizard import ArchiveWizardPage


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture()
def page(qapp, tmp_path):
    cfg = AppConfig(
        library_root=str(tmp_path / "lib"),
        jobs_dir=str(tmp_path / "jobs"),
        log_dir=str(tmp_path / "logs"),
    )
    db = Database(tmp_path / "t.sqlite3")
    db.initialize()
    wizard = ArchiveWizardPage(cfg, db)
    yield wizard
    db.close()


def _queen_sheet(*, tracks: int = 17):
    sheet = make_approvable_sheet(
        album="Greatest Hits",
        artist="Queen",
        year=1992,
        tracks=tracks,
    )
    sheet.edition.country = "CA"
    sheet.edition.label = "Hollywood Records"
    sheet.edition.catalog_number = "CD 61265"
    sheet.tracks[0].title = "We Will Rock You"
    sheet.tracks[-1].title = "I Want to Break Free"
    sheet.validation_warnings.append("Piste 17: TOC 262000 ms vs MB 258733 ms")
    return sheet


def test_w2_to_w3_prefills_edition_and_tracks(page) -> None:
    sheet = _queen_sheet()
    sheet.disc.disc_number = 2
    sheet.disc.disc_total = 3
    page._sheet = sheet  # noqa: SLF001
    # Simule Continuer depuis Identification
    page._set_step(2)  # noqa: SLF001

    assert page.current_step() == 2
    assert page.edit_artist.text() == "Queen"
    assert page.edit_album.text() == "Greatest Hits"
    assert page.spin_year.value() == 1992
    assert page.edit_label.text() == "Hollywood Records"
    assert page.edit_catalog.text() == "CD 61265"
    assert page.edit_country.text() == "CA"
    assert page.spin_disc_number.value() == 2
    assert page.spin_disc_total.value() == 3
    assert page.table.rowCount() == 17
    assert page.table.item(0, 1).text() == "We Will Rock You"
    assert page.table.item(16, 1).text() == "I Want to Break Free"
    # La fiche métier n'a pas été vidée par les signaux Qt
    assert len(page.sheet().tracks) == 17
    assert page.sheet().edition.album_title == "Greatest Hits"
    page._advisory_warnings = ["Piste 17: TOC 262000 ms vs MB 258733 ms"]  # noqa: SLF001
    page._validate_ui()  # noqa: SLF001
    assert "Piste 17" in page.lbl_val.text()


def test_back_w3_to_w2_to_w3_keeps_data(page) -> None:
    page._sheet = _queen_sheet()  # noqa: SLF001
    page._set_step(2)  # noqa: SLF001
    page._set_step(1)  # noqa: SLF001 — retour Identification
    assert page.current_step() == 1
    page._set_step(2)  # noqa: SLF001
    assert page.edit_album.text() == "Greatest Hits"
    assert page.table.rowCount() == 17


def test_edition_change_refreshes_w3_fields(page) -> None:
    page._sheet = _queen_sheet()  # noqa: SLF001
    page._set_step(2)  # noqa: SLF001
    assert page.edit_country.text() == "CA"

    # Nouvelle édition (comme après apply_release_candidate)
    other = make_approvable_sheet(
        album="Greatest Hits",
        artist="Queen",
        year=1991,
        tracks=17,
    )
    other.edition.country = "US"
    other.edition.label = "Hollywood Records"
    other.edition.catalog_number = "HR 61265-2"
    other.tracks[0].title = "We Will Rock You"
    page._sheet = other  # noqa: SLF001
    page._refresh_w3()  # noqa: SLF001

    assert page.edit_country.text() == "US"
    assert page.edit_catalog.text() == "HR 61265-2"
    assert page.spin_year.value() == 1991
    assert page.table.rowCount() == 17
    assert page.sheet().edition.catalog_number == "HR 61265-2"


def test_manual_edit_after_prefill_updates_sheet(page) -> None:
    page._sheet = _queen_sheet()  # noqa: SLF001
    page._set_step(2)  # noqa: SLF001
    page.edit_album.setText("Greatest Hits (remaster)")
    page.spin_disc_number.setValue(2)
    page.spin_disc_total.setValue(3)
    assert page.sheet().edition.album_title == "Greatest Hits (remaster)"
    assert page.sheet().disc.disc_number == 2
    assert page.sheet().disc.disc_total == 3
    assert page.sheet().disc.field_meta["disc_number"].provenance == MetadataProvenance.USER_CORRECTION


def test_unrelated_edit_preserves_unconfirmed_compilation(page) -> None:
    sheet = _queen_sheet()
    sheet.edition.is_compilation = True
    sheet.edition.field_meta["is_compilation"] = FieldMeta(
        trust=FieldTrust.AMBIGUOUS,
        provenance=MetadataProvenance.MUSICBRAINZ,
        note="release-group Compilation",
    )
    page._sheet = sheet  # noqa: SLF001
    page._set_step(2)  # noqa: SLF001
    assert page.chk_compilation.checkState() == Qt.CheckState.PartiallyChecked
    page.edit_album.setText("Greatest Hits, édition test")
    assert page.sheet().edition.field_meta["is_compilation"].trust == FieldTrust.AMBIGUOUS
    assert page.sheet().edition.is_compilation is True


def test_user_can_mark_edition_year_unavailable_with_justification(page) -> None:
    sheet = _queen_sheet()
    sheet.edition.year = None
    sheet.edition.first_release_date = "2002"
    sheet.edition.field_meta["year"] = FieldMeta(trust=FieldTrust.MISSING)
    sheet.edition.field_meta["first_release_date"] = FieldMeta(
        trust=FieldTrust.CONFIRMED,
        provenance=MetadataProvenance.MUSICBRAINZ,
    )
    page._sheet = sheet  # noqa: SLF001
    page._set_step(2)  # noqa: SLF001
    assert page.spin_year.value() == 0
    assert page.chk_year_unavailable.isChecked() is False
    page.chk_year_unavailable.setChecked(True)
    page.edit_year_unavailable_reason.setText(
        "La date exacte de cette édition n'est pas renseignée dans les sources consultées."
    )
    page._apply_form_to_sheet()  # noqa: SLF001
    assert page.sheet().edition.year is None
    assert page.sheet().edition.first_release_date == "2002"
    assert page.sheet().edition.field_meta["year"].trust == FieldTrust.UNAVAILABLE
    assert page.sheet().edition.year_unavailable_justification
    assert not any(
        error.startswith("year:") or error.startswith("year unavailable:")
        for error in page.sheet().validation_errors
    )


def test_manual_metadata_correction_retains_proposal_source_url(page) -> None:
    sheet = _queen_sheet()
    page._sheet = sheet  # noqa: SLF001
    page._enrichment_report = EnrichmentReport(  # noqa: SLF001
        proposals=[
            MetadataEvidence(
                field="album_title",
                value="Greatest Hits (Canada)",
                source="MusicBrainz release",
                source_url="https://musicbrainz.org/release/example",
                confidence="élevée",
                note="release title",
                retrieved_at="2026-11-04T00:00:00+00:00",
            )
        ]
    )
    page._set_step(2)  # noqa: SLF001
    page.edit_album.setText("Greatest Hits (Canada)")
    note = page.sheet().edition.field_meta["album_title"].note
    assert "https://musicbrainz.org/release/example" in note


def test_prefill_then_a3_revoke_on_edit(page) -> None:
    sheet = _queen_sheet(tracks=2)
    sheet.edition.cover_status = CoverStatus.UNAVAILABLE
    sheet.edition.field_meta["cover_status"] = FieldMeta(trust=FieldTrust.UNAVAILABLE)
    page._sheet = sheet  # noqa: SLF001
    page._set_step(2)  # noqa: SLF001
    page.chk_compilation.setChecked(True)
    page._apply_form_to_sheet()  # noqa: SLF001
    approve_sheet(page.sheet(), note="test F1")
    page._approved_fp = compute_approval_fingerprint(page.sheet())  # noqa: SLF001
    assert page.sheet().approval == ApprovalState.APPROVED
    page.spin_disc_number.setValue(2)
    assert page.sheet().approval == ApprovalState.PENDING
    assert page.approval_fingerprint() is None
    page.edit_album.setText("Autre titre")
    assert page.sheet().approval == ApprovalState.PENDING
    assert page.approval_fingerprint() is None
