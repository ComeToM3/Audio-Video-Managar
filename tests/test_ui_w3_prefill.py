"""AVM-06C-F1 — préremplissage W3 depuis DiscMetadata (régression wipe Qt signals)."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtTest import QTest
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton, QScrollArea

from audio_video_manager.config import AppConfig
from audio_video_manager.metadata.approval_fingerprint import compute_approval_fingerprint
from audio_video_manager.metadata.apply_lookup import identify_disc
from audio_video_manager.metadata.cover_art import CoverArtResult
from audio_video_manager.metadata.enums import (
    ApprovalState,
    CoverStatus,
    FieldTrust,
    MetadataProvenance,
)
from audio_video_manager.metadata.enrichment import (
    DiscogsLookup,
    DiscogsReleaseEvidence,
    DiscogsTrack,
    EnrichmentReport,
    MetadataEvidence,
)
from audio_video_manager.metadata.factories import make_approvable_sheet
from audio_video_manager.metadata.models import FieldMeta
from audio_video_manager.metadata.musicbrainz_client import (
    DiscLookupResult,
    ReleaseCandidate,
)
from audio_video_manager.metadata.toc_reader import DiscReadResult
from audio_video_manager.ui.wizard import archive_wizard as wizard_module
from audio_video_manager.metadata.validation import approve_sheet
from audio_video_manager.storage import Database
from audio_video_manager.ui.identify_worker import (
    EditionEnrichmentWorker,
    IdentifyWorker,
)
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


def _deliver_identification_result(page, result, qapp) -> None:
    class IdentifyResultSource(QObject):
        finished = Signal(object, object, object, object, object)

    source = IdentifyResultSource(page)
    page._start_edition_enrichment = lambda _candidate: None  # noqa: SLF001
    source.finished.connect(
        page._on_identify_ok,  # noqa: SLF001
        Qt.ConnectionType.QueuedConnection,
    )
    page._identify_result_source = source  # noqa: SLF001
    page._set_step(page.PAGE_REVIEW)  # noqa: SLF001
    page.show()
    page.resize(1000, 700)
    qapp.processEvents()
    source.finished.emit(*result)
    qapp.processEvents()


def _synthetic_read(tracks: int = 2) -> DiscReadResult:
    sheet = make_approvable_sheet(album="", artist="", year=None, tracks=tracks)
    return DiscReadResult("synthetic-disc-id", sheet.identity.toc, "D:")


def _identify_with_candidates(read, candidates, *, fetch_cover=False):
    lookup = DiscLookupResult(
        disc_id=read.disc_id,
        candidates=candidates,
        raw_release_count=len(candidates),
        message=f"{len(candidates)} candidates",
        ambiguous=len(candidates) > 1,
    )
    return identify_disc(
        disc_read=read,
        lookup=lookup,
        fetch_cover=fetch_cover,
        preferred_release_country="CA",
    ) + (None,)


def test_review_page_prefills_edition_and_tracks(page) -> None:
    sheet = _queen_sheet()
    sheet.disc.disc_number = 2
    sheet.disc.disc_total = 3
    page._sheet = sheet  # noqa: SLF001
    page._set_step(page.PAGE_REVIEW)  # noqa: SLF001

    assert page.current_step() == page.PAGE_REVIEW
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
    assert page.table.item(0, 3).text() == "3:00"
    assert page.table.item(16, 1).text() == "I Want to Break Free"
    # La fiche métier n'a pas été vidée par les signaux Qt
    assert len(page.sheet().tracks) == 17
    assert page.sheet().edition.album_title == "Greatest Hits"
    page._advisory_warnings = ["Piste 17: TOC 262000 ms vs MB 258733 ms"]  # noqa: SLF001
    page._validate_ui()  # noqa: SLF001
    assert "Piste 17" in page.lbl_val.text()


def test_return_to_disc_and_review_keeps_data(page) -> None:
    page._sheet = _queen_sheet()  # noqa: SLF001
    page._set_step(page.PAGE_REVIEW)  # noqa: SLF001
    page._set_step(page.PAGE_DISC)  # noqa: SLF001
    assert page.current_step() == page.PAGE_DISC
    page._set_step(page.PAGE_REVIEW)  # noqa: SLF001
    assert page.edit_album.text() == "Greatest Hits"
    assert page.table.rowCount() == 17


def test_edition_change_refreshes_w3_fields(page) -> None:
    page._sheet = _queen_sheet()  # noqa: SLF001
    page._set_step(page.PAGE_REVIEW)  # noqa: SLF001
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
    page._set_step(page.PAGE_REVIEW)  # noqa: SLF001
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
    page._set_step(page.PAGE_REVIEW)  # noqa: SLF001
    assert page.chk_compilation.checkState() == Qt.CheckState.PartiallyChecked
    assert page.chk_compilation.text() == "Compilation à confirmer"
    page.edit_album.setText("Greatest Hits, édition test")
    assert page.sheet().edition.field_meta["is_compilation"].trust == FieldTrust.AMBIGUOUS
    assert page.sheet().edition.is_compilation is True
    page.chk_compilation.setCheckState(Qt.CheckState.Checked)
    assert page.sheet().edition.field_meta["is_compilation"].trust == FieldTrust.CONFIRMED
    assert page.chk_compilation.text() == "Compilation"


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
    page._set_step(page.PAGE_REVIEW)  # noqa: SLF001
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
    page._set_step(page.PAGE_REVIEW)  # noqa: SLF001
    page.edit_album.setText("Greatest Hits (Canada)")
    note = page.sheet().edition.field_meta["album_title"].note
    assert "https://musicbrainz.org/release/example" in note


def test_prefill_then_a3_revoke_on_edit(page) -> None:
    sheet = _queen_sheet(tracks=2)
    sheet.edition.cover_status = CoverStatus.UNAVAILABLE
    sheet.edition.field_meta["cover_status"] = FieldMeta(trust=FieldTrust.UNAVAILABLE)
    page._sheet = sheet  # noqa: SLF001
    page._set_step(page.PAGE_REVIEW)  # noqa: SLF001
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


def test_review_uses_one_scroll_area_and_no_approval_button(page) -> None:
    page._sheet = _queen_sheet()  # noqa: SLF001
    page._set_step(page.PAGE_REVIEW)  # noqa: SLF001

    assert page.findChild(QScrollArea, "archiveReviewScroll") is not None
    assert page.table.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    assert not any(
        "appliquer l’édition" in button.text().casefold()
        or "approuver la fiche" in button.text().casefold()
        for button in page.findChildren(QPushButton)
    )
    assert page.btn_next.text() == "Continuer"


def test_cover_preview_uses_cache_without_blocking_network(page, monkeypatch, tmp_path) -> None:
    import audio_video_manager.ui.wizard.archive_wizard as wizard_module

    monkeypatch.setattr(
        wizard_module,
        "cached_cover_path",
        lambda _url: tmp_path / "not-cached.jpg",
    )
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("network call")),
    )

    page._load_cover("https://example.test/cover.jpg")  # noqa: SLF001

    assert page.cover_label.pixmap().isNull()


def test_candidate_selection_updates_sheet_and_confirms_manual_replacement(page, monkeypatch) -> None:
    sheet = _queen_sheet(tracks=2)
    first = ReleaseCandidate(
        release_id="first",
        title="Greatest Hits",
        artist_credit="Queen",
        year=1992,
        country="CA",
    )
    alternate = ReleaseCandidate(
        release_id="alternate",
        title="Greatest Hits (Deluxe)",
        artist_credit="Queen",
        year=2000,
        country="US",
    )
    page._sheet = sheet  # noqa: SLF001
    page._start_edition_enrichment = lambda _candidate: None  # noqa: SLF001
    page._candidates = [first, alternate]  # noqa: SLF001
    page._selected_candidate_id = first.release_id  # noqa: SLF001
    page._set_step(page.PAGE_REVIEW)  # noqa: SLF001
    page._start_edition_enrichment = lambda _candidate: None  # noqa: SLF001
    page.combo_editions.addItem("Queen — Greatest Hits", first.release_id)
    page.combo_editions.addItem("Queen — Greatest Hits (Deluxe)", alternate.release_id)
    page.combo_editions.setCurrentIndex(0)
    page.edit_album.setText("Greatest Hits, correction manuelle")

    answers = iter((QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes))
    monkeypatch.setattr(QMessageBox, "question", lambda *_args: next(answers))
    page.combo_editions.setCurrentIndex(1)
    assert page.sheet().edition.album_title == "Greatest Hits, correction manuelle"
    assert page.combo_editions.currentData() == first.release_id

    page.combo_editions.setCurrentIndex(1)
    assert page.sheet().edition.album_title == "Greatest Hits (Deluxe)"
    assert page.edit_album.text() == "Greatest Hits (Deluxe)"
    assert page.sheet().edition.field_meta["album_title"].provenance == MetadataProvenance.MUSICBRAINZ
    assert any(
        correction.field == "edition.album_title"
        and correction.provenance == MetadataProvenance.USER_CORRECTION
        for correction in page.sheet().corrections
    )


def test_continue_approves_but_does_not_start_rip(page, monkeypatch) -> None:
    sheet = _queen_sheet(tracks=2)
    sheet.edition.cover_status = CoverStatus.UNAVAILABLE
    sheet.edition.field_meta["cover_status"] = FieldMeta(trust=FieldTrust.UNAVAILABLE)
    page._sheet = sheet  # noqa: SLF001
    page._set_step(page.PAGE_REVIEW)  # noqa: SLF001
    starts = []
    monkeypatch.setattr(page, "_start_archive", lambda: starts.append(True))

    page.btn_next.setFocus()
    QTest.keyClick(page.btn_next, Qt.Key.Key_Space)

    assert page.sheet().approval == ApprovalState.APPROVED
    assert page.approval_fingerprint() is not None
    assert page.current_step() == page.PAGE_EXTRACT
    assert page.btn_next.text() == "Extraire"
    assert starts == []


def test_unique_musicbrainz_release_populates_visible_review_and_approval(
    page, qapp, monkeypatch, tmp_path
) -> None:
    read = _synthetic_read()
    cover = CoverArtResult(
        release_id="unique-release",
        status="confirmed",
        front_url="https://cover.example/front.jpg",
        thumbnail_url="https://cover.example/thumb.jpg",
        message="cover available",
    )
    image_path = tmp_path / "cover.png"
    image = QPixmap(12, 12)
    image.fill(QColor("#c44855"))
    assert image.save(str(image_path))
    monkeypatch.setattr(
        "audio_video_manager.metadata.apply_lookup.fetch_cover_art_info",
        lambda _release_id: cover,
    )
    monkeypatch.setattr(
        wizard_module,
        "cached_cover_path",
        lambda _url: image_path,
    )
    candidate = ReleaseCandidate(
        release_id="unique-release",
        title="Night Drive",
        artist_credit="The Example",
        year=2021,
        country="CA",
        labels=["North Records"],
        catalog_numbers=["NR-021"],
        matched_medium_position=1,
        medium_count=1,
        track_titles=["Blue Hour", "Last Stop"],
        track_artists=["The Example", "The Example"],
        track_durations_ms=[180_000, 201_000],
        release_group_secondary_types=["Compilation"],
        toc_match="exact",
    )
    result = _identify_with_candidates(read, [candidate], fetch_cover=True)

    _deliver_identification_result(page, result, qapp)

    assert page.combo_editions.count() == 1
    assert page.combo_editions.currentData() == candidate.release_id
    assert page.edit_album.text() == "Night Drive"
    assert page.edit_artist.text() == "The Example"
    assert page.spin_year.value() == 2021
    assert page.edit_label.text() == "North Records"
    assert page.edit_catalog.text() == "NR-021"
    assert page.edit_country.text() == "CA"
    assert page.table.item(0, 1).text() == "Blue Hour"
    assert page.table.item(0, 3).text() == "3:00"
    assert not page.cover_label.pixmap().isNull()
    assert "Night Drive" in page.lbl_path_preview.text()
    assert page.chk_compilation.text() == "Compilation à confirmer"
    assert page.sheet().approval == ApprovalState.PENDING

    page.chk_compilation.setCheckState(Qt.CheckState.Checked)
    page.btn_next.click()

    assert page.sheet().approval == ApprovalState.APPROVED
    assert page.approval_fingerprint() == compute_approval_fingerprint(page.sheet())
    assert page.edit_album.text() == page.sheet().edition.album_title
    assert page.current_step() == page.PAGE_EXTRACT


def test_ambiguous_musicbrainz_choices_apply_through_visible_combo_signals(
    page, qapp, monkeypatch
) -> None:
    read = _synthetic_read()
    common = dict(
        artist_credit="The Example",
        track_artists=["The Example", "The Example"],
        track_durations_ms=[180_000, 201_000],
        toc_match="exact",
    )
    first = ReleaseCandidate(
        release_id="release-ca",
        title="Night Drive",
        year=2021,
        country="CA",
        track_titles=["Blue Hour", "Last Stop"],
        **common,
    )
    alternate = ReleaseCandidate(
        release_id="release-us",
        title="Night Drive (Alternate)",
        year=2022,
        country="US",
        track_titles=["Red Hour", "Last Stop"],
        **common,
    )
    result = _identify_with_candidates(read, [first, alternate])
    assert result[3].require_manual_choice
    assert result[3].selected is first
    _deliver_identification_result(page, result, qapp)

    assert page.combo_editions.currentData() == first.release_id
    assert page.edit_album.text() == first.title
    assert page.sheet().edition.album_title == first.title
    assert "Proposition présélectionnée" in page.lbl_id_status.text()
    page.combo_editions.setCurrentIndex(0)
    qapp.processEvents()
    assert page.edit_album.text() == "Night Drive"
    assert page.edit_artist.text() == "The Example"
    assert page.spin_year.value() == 2021
    assert page.table.item(0, 1).text() == "Blue Hour"

    page.edit_album.setText("Night Drive, correction utilisateur")
    answers = iter((QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes))
    monkeypatch.setattr(QMessageBox, "question", lambda *_args: next(answers))
    page.combo_editions.setCurrentIndex(1)
    qapp.processEvents()
    assert page.combo_editions.currentData() == first.release_id
    assert page.sheet().edition.album_title == "Night Drive, correction utilisateur"

    page.combo_editions.setCurrentIndex(1)
    qapp.processEvents()
    assert page.combo_editions.currentData() == alternate.release_id
    assert page.edit_album.text() == "Night Drive (Alternate)"
    assert page.edit_country.text() == "US"
    assert page.table.item(0, 1).text() == "Red Hour"
    assert "Night Drive (Alternate)" in page.lbl_path_preview.text()
    assert any(
        correction.field == "edition.album_title"
        and correction.new_value == "Night Drive, correction utilisateur"
        for correction in page.sheet().corrections
    )


def test_cdstub_is_visible_and_prefills_without_confirming_release(page, qapp) -> None:
    read = _synthetic_read()
    stub = ReleaseCandidate(
        release_id="",
        title="Stub Album",
        artist_credit="Stub Artist",
        track_titles=["Stub Track 1", "Stub Track 2"],
        track_artists=["", ""],
        is_cdstub=True,
        match_source="cdstub",
        disc_id=read.disc_id,
        medium_track_count=2,
    )
    _deliver_identification_result(
        page,
        _identify_with_candidates(read, [stub]),
        qapp,
    )

    assert page.combo_editions.count() == 1
    assert page.combo_editions.currentData() == stub.selection_key
    assert "CD stub non confirmé" in page.combo_editions.currentText()
    assert page.edit_artist.text() == "Stub Artist"
    assert page.edit_album.text() == "Stub Album"
    assert page.sheet().edition.musicbrainz_release_id is None
    assert page.sheet().edition.field_meta["album_title"].trust == FieldTrust.AMBIGUOUS
    assert page.sheet().approval == ApprovalState.PENDING


def test_switching_to_incomplete_edition_clears_old_visible_metadata(page, qapp) -> None:
    read = _synthetic_read()
    common = dict(
        artist_credit="The Example",
        track_durations_ms=[180_000, 201_000],
        toc_match="exact",
    )
    complete = ReleaseCandidate(
        release_id="complete-release",
        title="Complete Album",
        year=2004,
        country="CA",
        labels=["Old Label"],
        catalog_numbers=["OLD-1"],
        track_titles=["Old Track 1", "Old Track 2"],
        track_artists=["The Example", "The Example"],
        **common,
    )
    incomplete = ReleaseCandidate(
        release_id="incomplete-release",
        title="Incomplete Album",
        **common,
    )
    _deliver_identification_result(
        page,
        _identify_with_candidates(read, [complete, incomplete]),
        qapp,
    )
    assert page.edit_album.text() == "Complete Album"
    page.sheet().edition.cover_status = CoverStatus.CONFIRMED
    page.sheet().edition.cover_path_or_url = "https://example.test/old-cover.jpg"
    page.sheet().edition.field_meta["cover_status"] = FieldMeta(
        trust=FieldTrust.CONFIRMED,
        provenance=MetadataProvenance.COVER_ART_ARCHIVE,
    )
    old_cover = QPixmap(8, 8)
    old_cover.fill(QColor("red"))
    page.cover_label.setPixmap(old_cover)
    page.cover_label.setText("")

    page.combo_editions.setCurrentIndex(1)
    qapp.processEvents()

    assert page.combo_editions.currentData() == incomplete.release_id
    assert page.edit_album.text() == "Incomplete Album"
    assert page.spin_year.value() == 0
    assert page.edit_country.text() == ""
    assert page.edit_label.text() == ""
    assert page.edit_catalog.text() == ""
    assert page.table.item(0, 1).text() == ""
    assert page.cover_label.text() == "—"
    assert page.cover_label.pixmap().isNull()
    assert page.sheet().edition.cover_path_or_url is None


def test_cdstub_option_is_selected_by_stable_key_and_remains_provisional(
    page, qapp
) -> None:
    read = _synthetic_read()
    stub = ReleaseCandidate(
        release_id="",
        title="Stub Album",
        artist_credit="Stub Artist",
        track_titles=["Stub Track 1", "Stub Track 2"],
        track_artists=["", ""],
        is_cdstub=True,
        match_source="cdstub",
        disc_id=read.disc_id,
        medium_track_count=2,
    )
    result = _identify_with_candidates(read, [stub])
    _deliver_identification_result(page, result, qapp)

    assert page.combo_editions.count() == 1
    assert page.combo_editions.currentData() == stub.selection_key
    assert "CD stub non confirmé" in page.combo_editions.currentText()
    assert page.edit_album.text() == "Stub Album"
    assert page.edit_artist.text() == "Stub Artist"
    assert page.sheet().edition.musicbrainz_release_id is None
    assert page.sheet().edition.field_meta["album_title"].trust == FieldTrust.AMBIGUOUS
    assert page.sheet().approval == ApprovalState.PENDING


def test_no_musicbrainz_results_keeps_toc_and_manual_fields_visible(page, qapp) -> None:
    result = _identify_with_candidates(_synthetic_read(), [])
    _deliver_identification_result(page, result, qapp)

    assert page.combo_editions.count() == 0
    assert "Aucune édition trouvée" in page.lbl_id_status.text()
    assert page.edit_album.text() == ""
    assert page.table.rowCount() == 2
    assert page.sheet().identity.disc_id == "synthetic-disc-id"


def test_cover_timeout_does_not_prevent_selected_release_application(monkeypatch) -> None:
    read = _synthetic_read()
    candidate = ReleaseCandidate(
        release_id="cover-timeout-release",
        title="Night Drive",
        artist_credit="The Example",
        year=2021,
        track_titles=["Blue Hour", "Last Stop"],
        toc_match="exact",
    )
    monkeypatch.setattr(
        "audio_video_manager.metadata.apply_lookup.fetch_cover_art_info",
        lambda _release_id: (_ for _ in ()).throw(TimeoutError("CAA timeout")),
    )

    sheet, lookup, cover, decision, _ = _identify_with_candidates(
        read, [candidate], fetch_cover=True
    )

    assert decision.selected.release_id == candidate.release_id
    assert cover is None
    assert sheet.edition.album_title == "Night Drive"
    assert sheet.edition.album_artist == "The Example"
    assert sheet.edition.year == 2021
    assert [track.title for track in sheet.tracks] == ["Blue Hour", "Last Stop"]


def test_optional_discogs_failure_still_delivers_identification_to_visible_widgets(
    page, qapp, monkeypatch
) -> None:
    candidate = ReleaseCandidate(
        release_id="discogs-error-release",
        title="Night Drive",
        artist_credit="The Example",
        barcode="1234567890123",
        year=2021,
        track_titles=["Blue Hour", "Last Stop"],
        toc_match="exact",
    )
    result = _identify_with_candidates(_synthetic_read(), [candidate])
    monkeypatch.setattr(
        "audio_video_manager.ui.identify_worker.identify_disc",
        lambda *_args, **_kwargs: result[:4],
    )
    monkeypatch.setattr(
        "audio_video_manager.ui.identify_worker.lookup_discogs_by_barcode",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("optional Discogs failure")
        ),
    )
    page._set_step(page.PAGE_REVIEW)  # noqa: SLF001
    page._start_edition_enrichment = lambda _candidate: None  # noqa: SLF001
    page.show()
    page._busy = True  # noqa: SLF001
    worker = IdentifyWorker(optical_device="D:", preferred_country="CA")
    worker.finished.connect(page._on_identify_ok)  # noqa: SLF001
    worker.failed.connect(page._on_identify_fail)  # noqa: SLF001

    worker.run()
    qapp.processEvents()

    assert page.sheet().edition.album_title == "Night Drive"
    assert page.edit_album.text() == "Night Drive"
    assert page.edit_artist.text() == "The Example"
    assert page.table.item(0, 1).text() == "Blue Hour"
    assert page.current_step() == page.PAGE_REVIEW


def test_edition_enrichment_updates_cover_for_current_visible_selection(
    page, qapp, monkeypatch, tmp_path
) -> None:
    candidate = ReleaseCandidate(
        release_id="cover-release",
        title="Night Drive",
        artist_credit="The Example",
        year=2021,
    )
    sheet = _queen_sheet(tracks=2)
    sheet.edition.musicbrainz_release_id = candidate.release_id
    page._sheet = sheet  # noqa: SLF001
    page._candidates = [candidate]  # noqa: SLF001
    page._selected_candidate_id = candidate.release_id  # noqa: SLF001
    page._set_step(page.PAGE_REVIEW)  # noqa: SLF001
    image_path = tmp_path / "cover.png"
    image = QPixmap(12, 12)
    image.fill(QColor("#c44855"))
    assert image.save(str(image_path))
    cover = CoverArtResult(
        release_id=candidate.release_id,
        status="confirmed",
        front_url="https://cover.example/front.jpg",
        thumbnail_url="https://cover.example/thumb.jpg",
        message="cover available",
    )
    monkeypatch.setattr(
        "audio_video_manager.ui.identify_worker.fetch_cover_art_info",
        lambda _release_id: cover,
    )
    monkeypatch.setattr(
        "audio_video_manager.ui.identify_worker.fetch_cover_to_cache",
        lambda _url: image_path,
    )
    monkeypatch.setattr(
        wizard_module,
        "cached_cover_path",
        lambda _url: image_path,
    )
    monkeypatch.setattr(
        "audio_video_manager.ui.identify_worker.lookup_discogs_by_barcode",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("optional lookup")),
    )
    worker = EditionEnrichmentWorker(candidate)
    worker.finished.connect(page._on_edition_enrichment_ready)  # noqa: SLF001
    worker.run()
    qapp.processEvents()

    assert page.sheet().edition.cover_status == CoverStatus.CONFIRMED
    assert page.sheet().edition.cover_path_or_url == cover.front_url
    assert page._enrichment_report is not None  # noqa: SLF001
    assert not page.cover_label.pixmap().isNull()


def test_undecodable_cover_is_reported_unavailable(page, qapp, monkeypatch, tmp_path) -> None:
    candidate = ReleaseCandidate(
        release_id="broken-cover-release",
        title="Night Drive",
        artist_credit="The Example",
    )
    sheet = _queen_sheet(tracks=2)
    sheet.edition.musicbrainz_release_id = candidate.release_id
    page._sheet = sheet  # noqa: SLF001
    page._candidates = [candidate]  # noqa: SLF001
    page._selected_candidate_id = candidate.release_id  # noqa: SLF001
    page._set_step(page.PAGE_REVIEW)  # noqa: SLF001

    invalid_image = tmp_path / "not-an-image.jpg"
    invalid_image.write_bytes(b"not an image")
    cover = CoverArtResult(
        release_id=candidate.release_id,
        status="confirmed",
        front_url="https://cover.example/front.jpg",
        thumbnail_url="https://cover.example/thumb.jpg",
        message="CAA URL exists",
    )
    monkeypatch.setattr(
        wizard_module,
        "cached_cover_path",
        lambda _url: invalid_image,
    )

    page._on_edition_enrichment_ready(
        candidate.release_id,
        cover,
        invalid_image,
        None,
    )
    qapp.processEvents()

    assert page.sheet().edition.cover_status == CoverStatus.UNAVAILABLE
    assert page.sheet().edition.cover_path_or_url is None
    assert page.sheet().edition.field_meta["cover_status"].trust == FieldTrust.UNAVAILABLE
    assert "pochette indisponible" in page.lbl_id_status.text().casefold()
    assert page.cover_label.pixmap().isNull()


def test_discogs_exact_edition_cover_fallback_reaches_visible_page(
    page, qapp, monkeypatch, tmp_path
) -> None:
    candidate = ReleaseCandidate(
        release_id="mb-cover-release",
        title="Night Drive",
        artist_credit="The Example",
        barcode="1234567890123",
        year=2021,
        track_titles=["Blue Hour", "Last Stop"],
        toc_match="exact",
    )
    discogs_release = DiscogsReleaseEvidence(
        release_id=42,
        source_url="https://www.discogs.com/release/42",
        title=candidate.title,
        country="US",
        barcode=candidate.barcode,
        year=2021,
        labels=(),
        catalog_numbers=(),
        formats=("CD",),
        tracks=(
            DiscogsTrack(1, "Blue Hour", 180_000),
            DiscogsTrack(2, "Last Stop", 201_000),
        ),
        data_quality="Complete and Correct",
        cover_url="https://i.discogs.com/night-drive.jpg",
    )
    sheet = _queen_sheet(tracks=2)
    sheet.edition.musicbrainz_release_id = candidate.release_id
    page._sheet = sheet  # noqa: SLF001
    page._candidates = [candidate]  # noqa: SLF001
    page._selected_candidate_id = candidate.release_id  # noqa: SLF001
    page._set_step(page.PAGE_REVIEW)  # noqa: SLF001

    image_path = tmp_path / "discogs-cover.png"
    image = QPixmap(12, 12)
    image.fill(QColor("#c44855"))
    assert image.save(str(image_path))
    monkeypatch.setattr(
        "audio_video_manager.ui.identify_worker.fetch_cover_art_info",
        lambda _release_id: CoverArtResult(
            release_id=candidate.release_id,
            status="unavailable",
            front_url=None,
            thumbnail_url=None,
            message="CAA 404",
        ),
    )
    monkeypatch.setattr(
        "audio_video_manager.ui.identify_worker.lookup_discogs_by_barcode",
        lambda _barcode: DiscogsLookup("matched", discogs_release),
    )
    monkeypatch.setattr(
        "audio_video_manager.ui.identify_worker.fetch_cover_to_cache",
        lambda _url: image_path,
    )
    monkeypatch.setattr(
        wizard_module,
        "cached_cover_path",
        lambda _url: image_path,
    )

    worker = EditionEnrichmentWorker(candidate)
    worker.finished.connect(page._on_edition_enrichment_ready)  # noqa: SLF001
    worker.run()
    qapp.processEvents()

    assert page.sheet().edition.cover_status == CoverStatus.CONFIRMED
    assert page.sheet().edition.cover_path_or_url == discogs_release.cover_url
    assert page.sheet().edition.field_meta["cover_status"].provenance == MetadataProvenance.DISCOGS
    assert not page.cover_label.pixmap().isNull()
