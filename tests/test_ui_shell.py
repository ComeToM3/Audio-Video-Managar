"""AVM-06 — UI-0 shell + UI-1 structure (sans rip réel)."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from audio_video_manager.config import AppConfig
from audio_video_manager.metadata.enums import ApprovalState, CoverStatus, FieldTrust
from audio_video_manager.metadata.factories import make_approvable_sheet
from audio_video_manager.metadata.models import FieldMeta
from audio_video_manager.metadata.approval_fingerprint import compute_approval_fingerprint
from audio_video_manager.metadata.validation import approve_sheet
from audio_video_manager.storage import Database
from audio_video_manager.ui.dvd_extraction_dialog import DvdArchivePanel
from audio_video_manager.ui.main_window import (
    NAV_ARCHIVE,
    MainWindow,
    NARROW_BREAKPOINT,
    _is_volume_device_change,
)
from audio_video_manager.ui.wizard.archive_wizard import STEP_LABELS, ArchiveWizardPage


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture()
def config(tmp_path):
    return AppConfig(
        library_root=str(tmp_path / "lib"),
        jobs_dir=str(tmp_path / "jobs"),
        log_dir=str(tmp_path / "logs"),
        freaccmd_path="",
        preferred_release_country="CA",
        auto_approve_high_confidence=False,
    )


@pytest.fixture()
def db(tmp_path):
    database = Database(tmp_path / "test.sqlite3")
    database.initialize()
    yield database
    database.close()


def test_main_window_four_sections(qapp, config, db) -> None:
    win = MainWindow(config, db)
    assert win.nav.count() == 4
    assert win.tab_bar.count() == 4
    assert win.stack.count() == 4
    assert win.current_section() == NAV_ARCHIVE
    assert not hasattr(win, "btn_dvd")
    assert "Archiver" in win.nav.item(0).text()
    # Pas de probes au lancement
    assert win.wizard.current_step() == 0


def test_native_device_filter_only_accepts_volume_arrival_and_removal() -> None:
    assert _is_volume_device_change(0x0219, 0x8000, 0x2)
    assert _is_volume_device_change(0x0219, 0x8004, 0x2)
    assert not _is_volume_device_change(0x0219, 0x8000, 0x5)
    assert not _is_volume_device_change(0x0210, 0x8000, 0x2)


def test_native_event_ignores_non_windows_message_before_reading_pointer(
    qapp, config, db, monkeypatch
) -> None:
    import audio_video_manager.ui.main_window as main_window_module

    monkeypatch.setattr(main_window_module.sys, "platform", "win32")
    win = MainWindow(config, db)

    assert win.nativeEvent(b"not-a-windows-message", 1) == (False, 0)


def test_native_event_schedules_scan_for_synthetic_volume_messages(
    qapp, config, db, monkeypatch
) -> None:
    import ctypes
    from ctypes import wintypes
    import audio_video_manager.ui.main_window as main_window_module

    class DeviceBroadcastHeader(ctypes.Structure):
        _fields_ = [
            ("size", wintypes.DWORD),
            ("device_type", wintypes.DWORD),
            ("reserved", wintypes.DWORD),
        ]

    header = DeviceBroadcastHeader(ctypes.sizeof(DeviceBroadcastHeader), 2, 0)
    message = wintypes.MSG()
    message.message = 0x0219
    message.lParam = ctypes.addressof(header)
    monkeypatch.setattr(main_window_module.sys, "platform", "win32")
    win = MainWindow(config, db)
    scans = []
    monkeypatch.setattr(
        win.wizard,
        "schedule_optical_scan",
        lambda **kwargs: scans.append(kwargs),
    )

    for event in (0x8000, 0x8004):
        message.wParam = event
        assert win.nativeEvent(
            b"windows_generic_MSG", ctypes.addressof(message)
        ) == (False, 0)
    assert scans == [{"auto_identify": True}, {"auto_identify": True}]

    win.navigate_to(1)
    message.wParam = 0x8000
    win.nativeEvent(b"windows_generic_MSG", ctypes.addressof(message))
    assert len(scans) == 2


def test_native_event_schedules_volume_scan_only_in_archive(
    qapp, config, db, monkeypatch
) -> None:
    import ctypes
    from ctypes import wintypes
    import audio_video_manager.ui.main_window as main_window_module

    class DeviceBroadcastHeader(ctypes.Structure):
        _fields_ = [
            ("size", wintypes.DWORD),
            ("device_type", wintypes.DWORD),
            ("reserved", wintypes.DWORD),
        ]

    header = DeviceBroadcastHeader(ctypes.sizeof(DeviceBroadcastHeader), 2, 0)
    message = wintypes.MSG()
    message.message = 0x0219
    message.wParam = 0x8000
    message.lParam = ctypes.addressof(header)
    monkeypatch.setattr(main_window_module.sys, "platform", "win32")
    win = MainWindow(config, db)
    scans = []
    monkeypatch.setattr(
        win.wizard,
        "schedule_optical_scan",
        lambda **kwargs: scans.append(kwargs),
    )

    assert win.nativeEvent(b"windows_generic_MSG", ctypes.addressof(message)) == (False, 0)
    assert scans == [{"auto_identify": True}]

    win.navigate_to(1)
    win.nativeEvent(b"windows_generic_MSG", ctypes.addressof(message))
    assert scans == [{"auto_identify": True}]


def test_ambiguous_reader_pair_requires_confirmation(qapp, config, db, monkeypatch) -> None:
    from PySide6.QtWidgets import QMessageBox
    from audio_video_manager.extraction.drives import CdDrive
    from audio_video_manager.metadata.toc_reader import DiscReadResult
    from audio_video_manager.ui.wizard.archive_wizard import ArchiveWizardPage

    wizard = ArchiveWizardPage(config, db)
    sheet = make_approvable_sheet()
    approve_sheet(sheet, note="synthetic reader-pair test")
    wizard._sheet = sheet  # noqa: SLF001
    wizard._disc_read = DiscReadResult(
        sheet.identity.disc_id,
        sheet.identity.toc,
        "D:",
    )  # type: ignore[arg-type]
    wizard._drives = [
        CdDrive(0, "1:0:0", "Optical drive one"),
        CdDrive(1, "2:0:0", "Optical drive two"),
    ]  # noqa: SLF001
    wizard._reader_pair_required = True  # noqa: SLF001
    wizard.chk_reader_pair.setChecked(False)
    warnings = []
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *_args: warnings.append(_args[2])
    )

    wizard._start_archive()  # noqa: SLF001

    assert len(warnings) == 1
    assert "Confirmez que le lecteur fre:ac choisi" in warnings[0]


def test_detected_cd_starts_identification_without_reading_hardware(
    qapp, config, db, monkeypatch
) -> None:
    from audio_video_manager.extraction.drives import CdDrive
    from audio_video_manager.metadata.models import TocSnapshot
    from audio_video_manager.metadata.toc_reader import DiscReadResult
    from audio_video_manager.ui.identify_worker import OpticalScanResult

    wizard = ArchiveWizardPage(config, db)
    toc = TocSnapshot(
        first_track=1,
        last_track=1,
        track_offsets_sectors=[0],
        track_durations_ms=[180_000],
        audio_track_count=1,
        raw_source="synthetic-test",
    )
    disc = DiscReadResult("disc-detected", toc, "D:")
    starts = []
    monkeypatch.setattr(wizard, "_start_identify", lambda: starts.append(True))
    wizard._active_scan_auto_identify = True  # noqa: SLF001

    wizard._on_optical_scan_finished(  # noqa: SLF001
        OpticalScanResult(
            drives=(CdDrive(0, "1:0:0", "Test optical drive"),),
            devices=("D:",),
            discs=(disc,),
            read_errors=(),
        )
    )

    assert wizard._disc_read == disc  # noqa: SLF001
    assert wizard.current_step() == 1
    assert starts == [True]


def test_cd_removal_invalidates_approved_sheet(qapp, config, db) -> None:
    from audio_video_manager.extraction.drives import CdDrive
    from audio_video_manager.metadata.approval_fingerprint import compute_approval_fingerprint
    from audio_video_manager.metadata.enums import ApprovalState
    from audio_video_manager.metadata.models import TocSnapshot
    from audio_video_manager.metadata.toc_reader import DiscReadResult
    from audio_video_manager.ui.identify_worker import OpticalScanResult

    wizard = ArchiveWizardPage(config, db)
    sheet = make_approvable_sheet()
    approve_sheet(sheet, note="synthetic removal test")
    wizard._sheet = sheet  # noqa: SLF001
    wizard._approved_fp = compute_approval_fingerprint(sheet)  # noqa: SLF001
    wizard._disc_read = DiscReadResult(  # noqa: SLF001
        sheet.identity.disc_id,
        TocSnapshot(
            first_track=1,
            last_track=1,
            track_offsets_sectors=[0],
            track_durations_ms=[180_000],
            audio_track_count=1,
            raw_source="synthetic-test",
        ),
        "D:",
    )
    wizard._set_step(2)  # noqa: SLF001

    wizard._on_optical_scan_finished(  # noqa: SLF001
        OpticalScanResult(
            drives=(CdDrive(0, "1:0:0", "Test optical drive"),),
            devices=("D:",),
            discs=(),
            read_errors=("D:: aucun disque",),
        )
    )

    assert wizard._disc_read is None  # noqa: SLF001
    assert wizard.sheet().approval == ApprovalState.PENDING
    assert wizard.approval_fingerprint() is None
    assert "retiré" in wizard.lbl_id_warn.text().casefold()


def test_identification_failure_keeps_cd_available_for_manual_metadata(
    qapp, config, db
) -> None:
    from audio_video_manager.metadata.toc_reader import DiscReadResult

    wizard = ArchiveWizardPage(config, db)
    wizard._disc_read = DiscReadResult(  # noqa: SLF001
        "offline-disc",
        make_approvable_sheet(tracks=1).identity.toc,
        "D:",
    )

    wizard._on_identify_fail("Réseau indisponible")  # noqa: SLF001

    assert wizard.sheet() is not None
    assert wizard.sheet().identity.disc_id == "offline-disc"
    assert "compléter la fiche manuellement" in wizard.lbl_id_status.text().casefold()


def test_video_library_displays_and_opens_indexed_file(qapp, config, db, tmp_path, monkeypatch) -> None:
    import json
    from types import SimpleNamespace
    from PySide6.QtGui import QDesktopServices
    from audio_video_manager.library.video_archive import finalize_video

    source = tmp_path / "source.mkv"
    source.write_bytes(b"video data")
    ffmpeg = tmp_path / "ffmpeg.exe"
    ffmpeg.touch()
    (tmp_path / "ffprobe.exe").touch()
    payload = {"format": {"format_name": "matroska", "duration": "20"},
               "streams": [{"codec_type": "video", "codec_name": "mpeg2video"}], "chapters": []}
    monkeypatch.setattr("audio_video_manager.library.video_archive.subprocess.run", lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr=""))
    destination = tmp_path / "archive.mkv"
    finalize_video(db, source, destination, ffmpeg)
    win = MainWindow(config, db)
    win.navigate_to(1)
    win.page_library.media_tabs.setCurrentIndex(1)
    page = win.page_library.video_page
    page.table.selectRow(0)
    assert page.table.item(0, 0).text() == "archive.mkv"
    assert "source non vérifiée" in page.table.item(0, 2).text()
    assert page.btn_open.isEnabled()
    opened = []
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: opened.append(url.toLocalFile()) or True)
    page.btn_open.click()
    assert opened == [str(destination).replace("\\", "/")]
    destination.unlink()
    page.refresh()
    assert page.table.item(0, 3).text() == "Fichier manquant"
    assert not page.btn_open.isEnabled()


def test_existing_video_requires_confirmation(qapp, config, db, tmp_path, monkeypatch) -> None:
    from PySide6.QtWidgets import QFileDialog, QMessageBox
    import audio_video_manager.ui.video_worker as video_worker
    import audio_video_manager.ui.wizard.archive_wizard as wizard_module

    win = MainWindow(config, db)
    wizard = win.wizard
    wizard.media_combo.setCurrentIndex(1)
    source = tmp_path / "original.mkv"
    destination = tmp_path / "published.mkv"
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *_args: (str(source), ""))
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *_args: (str(destination), ""))
    monkeypatch.setattr(QMessageBox, "question", lambda *_args: QMessageBox.StandardButton.No)
    wizard.dvd.btn_finalize_existing.click()
    assert not wizard.is_busy()

    class FakeWorker:
        def __init__(self, *args):
            self.args = args

    class FakeThread:
        def start(self):
            pass

    monkeypatch.setattr(QMessageBox, "question", lambda *_args: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(video_worker, "VideoFinalizeWorker", FakeWorker)
    monkeypatch.setattr(wizard_module, "attach_worker_thread", lambda *_args, **_kwargs: FakeThread())
    wizard.dvd.btn_finalize_existing.click()
    assert wizard.is_busy()
    assert wizard._worker.args[1:3] == (str(source), str(destination))
    assert not win._side_buttons[1].isEnabled()
    wizard._on_video_finalize_cleared()
    assert not wizard.is_busy()


def test_dvd_wizard_navigation_and_gates(qapp, config, db, tmp_path, monkeypatch) -> None:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QMessageBox
    from audio_video_manager.extraction.dvd_extractor import DvdExtractionResult
    from audio_video_manager.metadata.video import (
        DvdInspectionResult, DvdTitleCandidate, DvdTitleInspection,
        VideoInspectionStatus, VideoStream,
    )

    win = MainWindow(config, db)
    wizard = win.wizard
    wizard.media_combo.setCurrentIndex(1)
    assert win.current_section() == NAV_ARCHIVE
    assert wizard._stack.currentWidget() is wizard.dvd
    assert not wizard.dvd.isWindow()
    inspections = []
    monkeypatch.setattr(wizard.dvd, "_inspect", lambda: inspections.append("source"))
    wizard.btn_next.click()
    assert wizard.current_step() == 0
    assert inspections == ["source"]
    wizard.dvd._populate_inspection(DvdInspectionResult(
        source=tmp_path, status=VideoInspectionStatus.TITLE_SELECTION_REQUIRED,
        title_candidates=(DvdTitleCandidate(title_index=1, angle_count=1),),
    ))
    monkeypatch.setattr(wizard.dvd, "_inspect_selected_title", lambda: None)
    wizard.btn_next.click()
    assert wizard.current_step() == 1
    wizard.btn_next.click()
    assert wizard.current_step() == 1
    wizard.dvd._populate_title_inspection(DvdTitleInspection(
        title_index=1, angle_index=1,
        streams=(VideoStream(index=1, codec_type="audio", codec_name="ac3"),),
    ))
    wizard.btn_next.click()
    assert wizard.current_step() == 2
    wizard.dvd.radio_audio.setChecked(True)
    wizard.dvd.destination_edit.setText(str(tmp_path / "audio.mka"))
    wizard.dvd.rights_check.setChecked(True)
    wizard.dvd.audio_list.item(0).setCheckState(Qt.CheckState.Unchecked)
    wizard.btn_next.click()
    assert wizard.current_step() == 2
    wizard.dvd.audio_list.item(0).setCheckState(Qt.CheckState.Checked)
    wizard.btn_next.click()
    assert wizard.current_step() == 3
    started = []
    monkeypatch.setattr(wizard.dvd, "_start_worker", lambda **kwargs: started.append(kwargs))
    wizard.dvd.destination_edit.setText(str(tmp_path / "wrong.mkv"))
    wizard.btn_next.click()
    assert ".mka" in wizard.dvd.status_label.text()
    assert not started
    wizard.dvd.destination_edit.setText(str(tmp_path / "audio.mka"))
    monkeypatch.setattr(QMessageBox, "question", lambda *_args: QMessageBox.StandardButton.No)
    wizard.btn_next.click()
    assert not started
    monkeypatch.setattr(QMessageBox, "question", lambda *_args: QMessageBox.StandardButton.Yes)
    wizard.btn_next.click()
    assert started[0]["task"] == "audio"
    assert started[0]["audio_stream_indices"] == (1,)
    wizard.btn_back.click()
    assert wizard.current_step() == 2
    wizard.btn_back.click()
    wizard.btn_back.click()
    wizard.media_combo.setCurrentIndex(0)
    assert wizard.current_step() == 0
    assert wizard._stack.currentIndex() == 0

    wizard.media_combo.setCurrentIndex(1)
    wizard.dvd._on_worker_finished(DvdExtractionResult(
        output_path=tmp_path / "audio.mka", title_index=1, angle_index=1,
        duration_seconds=10, streams=(), chapter_count=0, size_bytes=1,
        ffmpeg_version="test", ffprobe_version="test",
    ))
    assert wizard.current_step() == 4
    wizard.btn_next.click()
    assert wizard.current_step() == 0
    assert wizard.dvd._inspection is None
    assert not wizard.dvd.rights_check.isChecked()


def test_dvd_worker_locks_navigation_and_cancels(qapp, config, db, monkeypatch, tmp_path) -> None:
    import audio_video_manager.ui.dvd_extraction_dialog as dvd_ui

    class WaitingWorker:
        def __init__(self, **_kwargs):
            self.cancelled = False

        def cancel(self):
            self.cancelled = True

    class WaitingThread:
        def start(self):
            pass

    monkeypatch.setattr(dvd_ui, "DvdTaskWorker", WaitingWorker)
    monkeypatch.setattr(dvd_ui, "attach_worker_thread", lambda *_args, **_kwargs: WaitingThread())
    win = MainWindow(config, db)
    wizard = win.wizard
    wizard.media_combo.setCurrentIndex(1)
    wizard.dvd.source_combo.setEditText(str(tmp_path))
    wizard.dvd.btn_inspect.click()
    assert wizard.is_busy()
    assert not win._side_buttons[1].isEnabled()
    assert not wizard.media_combo.isEnabled()
    assert not wizard.dvd.pages.isEnabled()
    worker = wizard.dvd._worker
    wizard.dvd.btn_cancel.click()
    assert worker.cancelled
    wizard.dvd._on_worker_failed("Annulée")
    wizard.dvd._on_worker_cleared()
    assert not wizard.is_busy()
    assert "Annulée" in wizard.dvd.status_label.text()
    assert win._side_buttons[1].isEnabled()
    assert wizard.dvd.pages.isEnabled()


def test_dvd_dialog_suggests_title_and_requires_fresh_angle_inspection(qapp, config, tmp_path) -> None:
    from PySide6.QtCore import Qt

    from audio_video_manager.metadata.video import (
        DvdInspectionResult,
        DvdTitleCandidate,
        DvdTitleInspection,
        VideoChapter,
        VideoInspectionStatus,
        VideoStream,
    )

    dialog = DvdArchivePanel(config)
    dialog._populate_inspection(
        DvdInspectionResult(
            source=tmp_path / "source",
            status=VideoInspectionStatus.TITLE_SELECTION_REQUIRED,
            title_candidates=(
                DvdTitleCandidate(title_index=1, angle_count=1, duration_seconds=30.0),
                DvdTitleCandidate(
                    title_index=2,
                    angle_count=2,
                    duration_seconds=300.0,
                    chapters=(VideoChapter(index=1, start_seconds=0.0, end_seconds=300.0),),
                ),
            ),
        )
    )

    assert dialog.title_combo.currentData() == 2
    assert "Suggestion durée" in dialog.title_combo.currentText()
    assert dialog.angle_spin.maximum() == 2

    dialog._populate_title_inspection(
        DvdTitleInspection(
            title_index=2,
            angle_index=1,
            duration_seconds=300.0,
            streams=(
                VideoStream(index=0, codec_type="video", codec_name="mpeg2video", width=720, height=480),
                VideoStream(index=1, codec_type="audio", codec_name="ac3", language="eng", channels=2),
                VideoStream(index=2, codec_type="subtitle", codec_name="dvd_subtitle", language="fra"),
            ),
            chapters=(VideoChapter(index=1, start_seconds=0.0, end_seconds=300.0),),
        )
    )
    dialog.destination_edit.setText(str(tmp_path / "master.mkv"))
    assert not dialog.btn_start.isEnabled()
    dialog.rights_check.setChecked(True)
    assert dialog.btn_start.isEnabled()
    assert dialog.audio_list.count() == 1
    assert not dialog.audio_list.isEnabled()
    assert dialog.chapter_list.count() == 1
    assert "Sous-titre dvd_subtitle" in dialog.stream_summary.text()

    dialog.radio_audio.setChecked(True)
    assert dialog.destination_edit.text().endswith("master.mka")
    assert dialog.audio_list.isEnabled()
    assert dialog.btn_start.isEnabled()
    dialog.audio_list.item(0).setCheckState(Qt.CheckState.Unchecked)
    assert not dialog.btn_start.isEnabled()
    dialog.audio_list.item(0).setCheckState(Qt.CheckState.Checked)
    assert dialog.btn_start.isEnabled()
    dialog.radio_master.setChecked(True)
    assert dialog.destination_edit.text().endswith("master.mkv")
    assert not dialog.audio_list.isEnabled()

    dialog.angle_spin.setValue(2)
    assert dialog._title_inspection is None
    assert not dialog.btn_start.isEnabled()
    dialog.close()


def test_dvd_pcm_conversion_requires_consent_and_explains_it(qapp, config, tmp_path, monkeypatch) -> None:
    from PySide6.QtWidgets import QMessageBox
    from audio_video_manager.metadata.video import (
        DvdInspectionResult, DvdTitleCandidate, DvdTitleInspection, VideoInspectionStatus, VideoStream,
    )

    panel = DvdArchivePanel(config)
    panel._populate_inspection(DvdInspectionResult(
        source=tmp_path, status=VideoInspectionStatus.TITLE_SELECTION_REQUIRED,
        title_candidates=(DvdTitleCandidate(title_index=1, angle_count=2),),
    ))
    panel._populate_title_inspection(DvdTitleInspection(
        title_index=1, angle_index=1,
        streams=(VideoStream(index=1, codec_type="audio", codec_name="pcm_dvd",
                             sample_rate=48000, channels=2, channel_layout="stereo",
                             bits_per_raw_sample=16),),
    ))
    panel.destination_edit.setText(str(tmp_path / "master.mkv"))
    panel.rights_check.setChecked(True)
    assert not panel.btn_start.isEnabled()
    panel.pcm_check.setChecked(True)
    assert panel.btn_start.isEnabled()
    messages = []
    monkeypatch.setattr(QMessageBox, "question", lambda _parent, _title, text: messages.append(text) or QMessageBox.StandardButton.No)
    panel._start_extraction()
    assert "converti sans perte" in messages[0]
    assert "échantillons vérifiés" in messages[0]
    panel.angle_spin.setValue(2)
    assert not panel.pcm_check.isChecked()
    assert not panel.btn_start.isEnabled()


@pytest.mark.parametrize("environment_ffmpeg", ["", "ffmpeg.exe"])
def test_dvd_worker_without_configured_ffmpeg(config, tmp_path, monkeypatch, environment_ffmpeg) -> None:
    from audio_video_manager.ui.dvd_worker import DvdTaskWorker

    monkeypatch.setenv("AVM_FFMPEG", environment_ffmpeg)
    monkeypatch.setenv("PATH", "")
    worker = DvdTaskWorker(config=config, task="inspect", source=str(tmp_path))
    errors = []
    worker.failed.connect(errors.append)

    inspector = worker._inspector()
    assert inspector is not None
    worker.run()

    assert len(errors) == 1
    assert "not defined" not in errors[0]


@pytest.mark.parametrize("task", ["mkv", "audio"])
@pytest.mark.parametrize("index_fails", [False, True])
def test_dvd_worker_indexes_or_preserves_published_output(config, tmp_path, monkeypatch, task, index_fails) -> None:
    from audio_video_manager.extraction.dvd_extractor import DvdExtractionResult
    from audio_video_manager.ui.dvd_worker import DvdTaskWorker

    output = tmp_path / ("archive.mkv" if task == "mkv" else "audio.mka")
    output.write_bytes(b"published")
    result = DvdExtractionResult(
        output_path=output, title_index=1, angle_index=1, duration_seconds=10,
        streams=(), chapter_count=0, size_bytes=9, ffmpeg_version="test", ffprobe_version="test",
    )

    class FakeService:
        def prepare(self, *_args):
            return object()

        def extract(self, *_args, **_kwargs):
            return result

        def extract_audio(self, *_args, **_kwargs):
            return result

    worker = DvdTaskWorker(config=config, task=task, source="synthetic", destination=str(output),
                           title_index=1, audio_stream_indices=(1,), db_path=tmp_path / "test.sqlite")
    monkeypatch.setattr(worker, "_inspector", lambda: None)
    monkeypatch.setattr(worker, "_service", lambda _inspector: FakeService())
    monkeypatch.setattr(worker, "_reserve_publication", lambda _path: 1)
    indexed = []

    def index(path, _service):
        indexed.append(path)
        if index_fails:
            raise RuntimeError("index inaccessible")

    monkeypatch.setattr(worker, "_index_published", index)
    finished, failed = [], []
    worker.finished.connect(finished.append)
    worker.failed.connect(failed.append)
    worker.run()
    assert not failed and len(finished) == 1
    assert indexed == [output] and output.read_bytes() == b"published"
    assert finished[0].cataloged is not index_fails
    assert ("index inaccessible" in finished[0].catalog_error) is index_fails


def test_dvd_suggests_free_destination_without_overwriting(qapp, config, tmp_path) -> None:
    from audio_video_manager.metadata.video import DvdInspectionResult, DvdTitleCandidate, VideoInspectionStatus

    root = tmp_path / "lib"
    root.mkdir()
    (root / "DVD-master.mkv").write_bytes(b"existing")
    panel = DvdArchivePanel(config)
    panel._populate_inspection(DvdInspectionResult(
        source=tmp_path, status=VideoInspectionStatus.TITLE_SELECTION_REQUIRED,
        title_candidates=(DvdTitleCandidate(title_index=1),),
    ))
    assert panel.destination_edit.text() == str(root / "DVD-master-2.mkv")
    assert (root / "DVD-master.mkv").read_bytes() == b"existing"


def test_multiple_audio_tracks_remain_explicit(qapp, config) -> None:
    from PySide6.QtCore import Qt
    from audio_video_manager.metadata.video import DvdTitleInspection, VideoStream

    panel = DvdArchivePanel(config)
    panel._populate_title_inspection(DvdTitleInspection(
        title_index=1, angle_index=1,
        streams=(VideoStream(index=1, codec_type="audio"), VideoStream(index=2, codec_type="audio")),
    ))
    assert all(panel.audio_list.item(index).checkState() == Qt.CheckState.Unchecked for index in range(2))


def test_dvd_failure_clears_unpublished_reservation(config, db, tmp_path, monkeypatch) -> None:
    from audio_video_manager.extraction.dvd_extractor import DvdExtractionCancelled
    from audio_video_manager.storage.catalog import list_videos
    from audio_video_manager.ui.dvd_worker import DvdTaskWorker

    class FakeService:
        def prepare(self, *_args):
            return object()

        def extract(self, *_args, **_kwargs):
            raise DvdExtractionCancelled("annulée")

    destination = tmp_path / "cancelled.mkv"
    worker = DvdTaskWorker(config=config, task="mkv", source="synthetic", destination=str(destination),
                           title_index=1, db_path=db.path)
    monkeypatch.setattr(worker, "_inspector", lambda: None)
    monkeypatch.setattr(worker, "_service", lambda _inspector: FakeService())
    errors = []
    worker.failed.connect(errors.append)
    worker.run()
    assert errors and "annulée" in errors[0]
    assert not destination.exists() and list_videos(db) == []


def test_dvd_failure_after_file_creation_reports_pending(config, db, tmp_path, monkeypatch) -> None:
    from audio_video_manager.storage.catalog import list_videos
    from audio_video_manager.ui.dvd_worker import DvdTaskWorker

    destination = tmp_path / "existing.mkv"

    class FakeService:
        def prepare(self, *_args):
            return object()

        def extract(self, *_args, **_kwargs):
            destination.write_bytes(b"keep")
            raise RuntimeError("publication incomplète")

    worker = DvdTaskWorker(config=config, task="mkv", source="synthetic", destination=str(destination),
                           title_index=1, db_path=db.path)
    monkeypatch.setattr(worker, "_inspector", lambda: None)
    monkeypatch.setattr(worker, "_service", lambda _inspector: FakeService())
    errors = []
    worker.failed.connect(errors.append)
    worker.run()
    assert errors and "entrée en attente" in errors[0]
    assert destination.read_bytes() == b"keep"
    assert list_videos(db)[0].publication_state == "pending"


def test_dvd_index_failure_keeps_file_and_recoverable_intent(config, db, tmp_path, monkeypatch) -> None:
    from audio_video_manager.extraction.dvd_extractor import DvdExtractionResult
    from audio_video_manager.storage.catalog import list_videos
    from audio_video_manager.ui.dvd_worker import DvdTaskWorker

    destination = tmp_path / "published.mkv"

    class FakeService:
        def prepare(self, *_args):
            return object()

        def extract(self, *_args, **_kwargs):
            destination.write_bytes(b"published")
            return DvdExtractionResult(
                output_path=destination, title_index=1, angle_index=1, duration_seconds=10,
                streams=(), chapter_count=0, size_bytes=9, ffmpeg_version="test", ffprobe_version="test",
            )

    worker = DvdTaskWorker(config=config, task="mkv", source="synthetic", destination=str(destination),
                           title_index=1, db_path=db.path)
    monkeypatch.setattr(worker, "_inspector", lambda: None)
    monkeypatch.setattr(worker, "_service", lambda _inspector: FakeService())
    monkeypatch.setattr(worker, "_index_published", lambda *_args: (_ for _ in ()).throw(RuntimeError("index inaccessible")))
    finished = []
    worker.finished.connect(finished.append)
    worker.run()
    assert destination.read_bytes() == b"published"
    assert not finished[0].cataloged and "index inaccessible" in finished[0].catalog_error
    row = list_videos(db)[0]
    assert row.path == str(destination) and row.publication_state == "pending"
    assert row.validation_status == "incomplete" and row.sha256.startswith("intent:")


def test_retry_index_preserves_result_until_thread_clears(qapp, config, tmp_path, monkeypatch) -> None:
    from audio_video_manager.extraction.dvd_extractor import DvdExtractionResult

    panel = DvdArchivePanel(config)
    panel._thread = object()
    result = DvdExtractionResult(
        output_path=tmp_path / "published.mkv", title_index=1, angle_index=1,
        duration_seconds=10, streams=(), chapter_count=0, size_bytes=9,
        ffmpeg_version="test", ffprobe_version="test", catalog_error="base inaccessible",
    )
    panel._on_worker_finished(result)
    assert not panel.btn_retry_index.isEnabled()
    panel._on_worker_cleared()
    assert panel.btn_retry_index.isEnabled()
    started = []
    monkeypatch.setattr(panel, "_start_worker", lambda **kwargs: started.append(kwargs))
    panel._retry_index()
    assert started == [{"task": "index", "source": str(result.output_path)}]


def test_dvd_result_opens_video_library(qapp, config, db, tmp_path) -> None:
    from audio_video_manager.extraction.dvd_extractor import DvdExtractionResult

    win = MainWindow(config, db)
    wizard = win.wizard
    wizard.media_combo.setCurrentIndex(1)
    wizard.dvd._on_worker_finished(DvdExtractionResult(
        output_path=tmp_path / "archive.mkv", title_index=1, angle_index=1,
        duration_seconds=10, streams=(), chapter_count=0, size_bytes=9,
        ffmpeg_version="test", ffprobe_version="test", cataloged=True,
    ))
    assert wizard.dvd._cataloged
    wizard.dvd.btn_open_library.click()
    assert win.current_section() == 1
    assert win.page_library.media_tabs.currentIndex() == 1


def test_interrupted_dvd_recovery_requires_confirmation(qapp, config, db, tmp_path, monkeypatch) -> None:
    from PySide6.QtWidgets import QMessageBox
    from audio_video_manager.library.video_archive import reserve_dvd_publication
    import audio_video_manager.ui.dvd_worker as dvd_worker
    import audio_video_manager.ui.thread_lifecycle as lifecycle

    destination = tmp_path / "pending.mkv"
    reserve_dvd_publication(db, destination)
    destination.write_bytes(b"published")
    win = MainWindow(config, db)
    win.navigate_to(1)
    win.page_library.media_tabs.setCurrentIndex(1)
    page = win.page_library.video_page
    page.table.selectRow(0)
    assert page.table.item(0, 2).text() == "Validation incomplète"
    monkeypatch.setattr(QMessageBox, "question", lambda *_args: QMessageBox.StandardButton.No)
    page._reconcile()
    assert not page.is_busy()

    class FakeWorker:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def cancel(self):
            pass

    class FakeThread:
        def start(self):
            pass

    monkeypatch.setattr(QMessageBox, "question", lambda *_args: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(dvd_worker, "DvdTaskWorker", FakeWorker)
    monkeypatch.setattr(lifecycle, "attach_worker_thread", lambda *_args, **_kwargs: FakeThread())
    page._reconcile()
    assert page.is_busy() and page._worker.kwargs["task"] == "index"
    assert page._worker.kwargs["source"] == str(destination)
    page._reconcile_cleared()


def test_navigate_preserves_wizard_approval(qapp, config, db) -> None:
    win = MainWindow(config, db)
    sheet = make_approvable_sheet()
    sheet.edition.cover_status = CoverStatus.UNAVAILABLE
    sheet.edition.field_meta["cover_status"] = FieldMeta(trust=FieldTrust.UNAVAILABLE)
    approve_sheet(sheet, note="ui")
    win.wizard._sheet = sheet  # noqa: SLF001 — injection test session
    win.wizard._approved_fp = compute_approval_fingerprint(sheet)  # noqa: SLF001
    assert win.wizard.sheet().approval == ApprovalState.APPROVED

    win.navigate_to(1)  # Bibliothèque
    assert win.current_section() == 1
    win.navigate_to(0)  # retour Archiver
    assert win.wizard.sheet().approval == ApprovalState.APPROVED
    assert win.wizard.approval_fingerprint() is not None


def test_wizard_four_cd_steps_and_no_dvd(qapp, config, db) -> None:
    page = ArchiveWizardPage(config, db)
    assert len(STEP_LABELS) == 4
    assert page.current_step() == 0
    text = page.lbl_disc.text().casefold()
    assert "dvd" not in text
    # stepper labels
    joined = " ".join(STEP_LABELS).casefold()
    assert "dvd" not in joined


def test_settings_tech_test_in_advanced_only(qapp, config, db) -> None:
    from PySide6.QtWidgets import QCheckBox, QLabel, QLineEdit, QPushButton

    win = MainWindow(config, db)
    settings = win.page_settings
    boxes = settings.findChildren(QCheckBox)
    auto = [b for b in boxes if "auto-approuver" in b.text().casefold()]
    assert not auto
    assert settings.chk_eject.text() == "Éjecter le CD après extraction"
    assert settings.advanced_content.isHidden()
    assert not settings.advanced_content.isAncestorOf(settings.edit_library)
    assert not settings.advanced_content.isAncestorOf(settings.chk_eject)
    tech = [
        b
        for b in settings.findChildren(QPushButton)
        if "test technique" in b.text().casefold()
    ]
    assert len(tech) == 1
    assert settings.advanced_content.isAncestorOf(tech[0])
    dvd_fields = [edit for edit in settings.findChildren(QLineEdit) if edit is settings.edit_ffmpeg or edit is settings.edit_dvdnav]
    assert len(dvd_fields) == 2
    assert settings.advanced_content.isAncestorOf(settings.edit_pref)
    assert settings.advanced_content.isAncestorOf(settings.edit_jobs)
    settings.advanced_toggle.click()
    assert not settings.advanced_content.isHidden()
    settings.advanced_toggle.click()
    assert settings.advanced_content.isHidden()


def test_narrow_shows_tabs(qapp, config, db) -> None:
    """AVM-08D.1 : rail compact en étroit ; shims nav/tab toujours masqués."""
    from PySide6.QtCore import QSize
    from PySide6.QtGui import QResizeEvent

    from audio_video_manager.ui.main_window import SIDE_NARROW, SIDE_WIDE

    win = MainWindow(config, db)
    win.show()
    qapp.processEvents()
    old = QSize(1100, 720)
    new = QSize(NARROW_BREAKPOINT - 40, 600)
    win.resize(new)
    win.resizeEvent(QResizeEvent(new, old))
    qapp.processEvents()
    assert not win.nav.isVisible()
    assert not win.tab_bar.isVisible()
    assert win._side.width() == SIDE_NARROW  # noqa: SLF001
    assert win._side_buttons[1].text() == "Bibl."  # noqa: SLF001

    wide = QSize(1100, 720)
    win.resize(wide)
    win.resizeEvent(QResizeEvent(wide, new))
    qapp.processEvents()
    assert not win.nav.isVisible()
    assert not win.tab_bar.isVisible()
    assert win._side.width() == SIDE_WIDE  # noqa: SLF001
    assert win._side_buttons[1].text() == "Bibliothèque"  # noqa: SLF001


def test_wizard_edit_after_approve_revokes(qapp, config, db) -> None:
    page = ArchiveWizardPage(config, db)
    sheet = make_approvable_sheet()
    sheet.edition.cover_status = CoverStatus.UNAVAILABLE
    sheet.edition.field_meta["cover_status"] = FieldMeta(trust=FieldTrust.UNAVAILABLE)
    approve_sheet(sheet, note="ui")
    page._sheet = sheet  # noqa: SLF001
    page._approved_fp = compute_approval_fingerprint(sheet)  # noqa: SLF001
    page._set_step(page.PAGE_REVIEW)  # noqa: SLF001
    page.edit_album.setText("Titre changé après approbation")
    qapp.processEvents()
    assert page.sheet().approval == ApprovalState.PENDING
    assert page.approval_fingerprint() is None
