"""Manual track selection and progress for Android ADB exports."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from audio_video_manager.library.android_export import (
    AndroidCandidate,
    AndroidDevice,
    find_adb_executable,
)
from audio_video_manager.ui.android_export_worker import AndroidExportWorker
from audio_video_manager.ui.thread_lifecycle import attach_worker_thread

_SELECTABLE = {"new", "missing", "modified", "failed"}
_STATUS_LABELS = {
    "new": "À envoyer",
    "missing": "À renvoyer",
    "modified": "Modifiée",
    "failed": "Échec précédent",
    "transferred": "Transféré",
    "conflict": "Conflit",
    "source_missing": "Source absente",
    "source_invalid": "Source invalide",
}


def _size_label(size: int) -> str:
    value = float(size)
    for unit in ("o", "Kio", "Mio", "Gio"):
        if value < 1024 or unit == "Gio":
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} Gio"


class AndroidExportPage(QWidget):
    back_requested = Signal()

    def __init__(self, db_path: Path, library_root: Path, parent=None) -> None:
        super().__init__(parent)
        self._db_path = db_path
        self._library_root = library_root
        self._adb_path = find_adb_executable()
        self._thread = None
        self._worker = None
        self._task: str | None = None
        self._candidates: list[AndroidCandidate] = []
        self._ignored_count = 0
        self._last_transfer_summary = ""
        self._scan_after_transfer = False

        self.setAccessibleName("Exporter vers Android")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setObjectName("androidExportScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setAccessibleName("Export Android — défilement")
        content = QWidget()
        root = QVBoxLayout(content)
        root.setContentsMargins(28, 20, 28, 20)
        root.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("Exporter vers Android")
        title.setObjectName("pageTitle")
        title.setAccessibleName("Exporter vers Android")
        header.addWidget(title, 1)
        self.btn_back = QPushButton("Retour à la bibliothèque")
        self.btn_back.setProperty("ghost", True)
        self.btn_back.clicked.connect(self.back_requested.emit)
        header.addWidget(self.btn_back)
        root.addLayout(header)

        device_row = QHBoxLayout()
        device_row.addWidget(QLabel("Appareil"))
        self.device_combo = QComboBox()
        self.device_combo.setAccessibleName("Appareil Android")
        self.device_combo.currentIndexChanged.connect(self._device_changed)
        device_row.addWidget(self.device_combo, 1)
        self.btn_browse_adb = QPushButton("Choisir adb.exe…")
        self.btn_browse_adb.clicked.connect(self._browse_adb)
        self.btn_browse_adb.setVisible(self._adb_path is None)
        device_row.addWidget(self.btn_browse_adb)
        self.btn_refresh_devices = QPushButton("Rechercher les appareils")
        self.btn_refresh_devices.clicked.connect(self._refresh_devices)
        device_row.addWidget(self.btn_refresh_devices)
        root.addLayout(device_row)

        self.lbl_status = QLabel("Recherchez un appareil, puis analysez ses transferts AVM.")
        self.lbl_status.setWordWrap(True)
        root.addWidget(self.lbl_status)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels(["Album / piste", "État", "Taille"])
        self.tree.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.itemChanged.connect(self._item_changed)
        root.addWidget(self.tree, 1)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.hide()
        root.addWidget(self.progress)

        bottom = QHBoxLayout()
        self.lbl_selection = QLabel("0 fichiers sélectionnés · 0 o")
        bottom.addWidget(self.lbl_selection, 1)
        self.btn_scan = QPushButton("Analyser les pistes")
        self.btn_scan.clicked.connect(self._scan)
        self.btn_scan.setEnabled(False)
        bottom.addWidget(self.btn_scan)
        self.btn_transfer = QPushButton("Transférer la sélection")
        self.btn_transfer.setProperty("primary", True)
        self.btn_transfer.clicked.connect(self._confirm_transfer)
        self.btn_transfer.setEnabled(False)
        bottom.addWidget(self.btn_transfer)
        root.addLayout(bottom)
        root.addStretch(1)
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)

    def is_busy(self) -> bool:
        return self._thread is not None

    def set_library_root(self, library_root: Path) -> None:
        self._library_root = library_root

    def shutdown_background_work(self, *, timeout_ms: int = 12_000) -> bool:
        from audio_video_manager.ui.thread_lifecycle import shutdown_worker_thread

        return shutdown_worker_thread(self._thread, self._worker, timeout_ms=timeout_ms)

    def _browse_adb(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Sélectionner Android Debug Bridge", "", "adb.exe (adb.exe)"
        )
        if path:
            self._adb_path = Path(path)
            self.btn_browse_adb.hide()

    def _refresh_devices(self) -> None:
        if self._adb_path is None:
            self._browse_adb()
        if self._adb_path is None:
            return
        self._start_worker("devices")

    def _device_changed(self, _index: int) -> None:
        device = self.device_combo.currentData()
        self._candidates.clear()
        self.tree.clear()
        self._last_transfer_summary = ""
        self.btn_scan.setEnabled(
            isinstance(device, AndroidDevice)
            and device.state == "device"
            and not self.is_busy()
        )
        self.btn_transfer.setEnabled(False)
        self._update_selection()

    def _scan(self) -> None:
        device = self.device_combo.currentData()
        if not isinstance(device, AndroidDevice) or device.state != "device":
            return
        self._start_worker("scan", serial=device.serial)

    def _confirm_transfer(self) -> None:
        selected = self._selected_candidates()
        if not selected:
            return
        self._ignored_count = max(0, len(self._candidates) - len(selected))
        device = self.device_combo.currentData()
        if not isinstance(device, AndroidDevice):
            return
        total_size = sum(item.source_size_bytes for item in selected)
        reply = QMessageBox.question(
            self,
            "Confirmer le transfert",
            f"Envoyer {len(selected)} fichier(s) ({_size_label(total_size)}) vers\n"
            f"{device.serial} : /sdcard/Music/AudioVideoManager ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._start_worker("transfer", serial=device.serial, candidates=selected)

    def _start_worker(
        self,
        task: str,
        *,
        serial: str | None = None,
        candidates: list[AndroidCandidate] | None = None,
    ) -> None:
        if self.is_busy() or self._adb_path is None:
            return
        self._task = task
        worker = AndroidExportWorker(
            task=task,
            adb_path=self._adb_path,
            db_path=self._db_path,
            library_root=self._library_root,
            serial=serial,
            candidates=candidates,
        )
        worker.devices_found.connect(self._devices_found)
        worker.scan_finished.connect(self._scan_finished)
        worker.transfer_finished.connect(self._transfer_finished)
        self._worker = worker
        self._thread = attach_worker_thread(
            worker,
            on_failed=self._worker_failed,
            on_cleared=self._worker_cleared,
            progress_slot=self._on_progress,
        )
        self._set_busy(True)
        self._thread.start()

    def _set_busy(self, busy: bool) -> None:
        self.btn_refresh_devices.setEnabled(not busy)
        self.btn_scan.setEnabled(not busy and self.device_combo.currentData() is not None)
        self.btn_transfer.setEnabled(not busy and bool(self._selected_candidates()))
        self.btn_back.setEnabled(not busy)
        self.btn_browse_adb.setEnabled(not busy)
        self.progress.setVisible(busy)
        self.progress.setRange(0, 0 if self._task in {"devices", "scan"} else max(1, len(self._selected_candidates())))
        if not busy:
            device = self.device_combo.currentData()
            self.btn_scan.setEnabled(
                isinstance(device, AndroidDevice) and device.state == "device"
            )
            self._update_selection()

    def _devices_found(self, devices: list[AndroidDevice]) -> None:
        previous = self.device_combo.currentData()
        previous_serial = previous.serial if isinstance(previous, AndroidDevice) else None
        self.device_combo.blockSignals(True)
        self.device_combo.clear()
        for device in devices:
            self.device_combo.addItem(device.label, device)
        if not devices:
            self.device_combo.addItem("Aucun appareil détecté", None)
        if previous_serial:
            for index in range(self.device_combo.count()):
                device = self.device_combo.itemData(index)
                if isinstance(device, AndroidDevice) and device.serial == previous_serial:
                    self.device_combo.setCurrentIndex(index)
                    break
        self.device_combo.blockSignals(False)
        self._device_changed(self.device_combo.currentIndex())
        if devices:
            self.lbl_status.setText("Sélectionnez un appareil autorisé, puis analysez les pistes.")
        else:
            self.lbl_status.setText("Aucun appareil ADB détecté.")

    def _scan_finished(self, candidates: list[AndroidCandidate]) -> None:
        self._candidates = candidates
        self._populate_tree(candidates)
        if self._scan_after_transfer:
            self.lbl_status.setText(
                f"{self._last_transfer_summary} État actualisé : {len(candidates)} pistes."
            )
            self._scan_after_transfer = False
        else:
            self.lbl_status.setText(
                f"Analyse terminée : {len(candidates)} pistes du catalogue AVM."
            )
        self._update_selection()

    def _populate_tree(self, candidates: list[AndroidCandidate]) -> None:
        self.tree.blockSignals(True)
        self.tree.clear()
        albums: dict[int, QTreeWidgetItem] = {}
        for candidate in candidates:
            album_item = albums.get(candidate.release_id)
            if album_item is None:
                label = f"{candidate.artist} — {candidate.album}"
                if candidate.year:
                    label += f" ({candidate.year})"
                album_item = QTreeWidgetItem([label, "", ""])
                album_item.setFlags(album_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                album_item.setCheckState(0, Qt.CheckState.Unchecked)
                self.tree.addTopLevelItem(album_item)
                albums[candidate.release_id] = album_item

            track_item = QTreeWidgetItem([
                candidate.file_label,
                _STATUS_LABELS.get(candidate.status, candidate.status),
                _size_label(candidate.source_size_bytes),
            ])
            track_item.setData(0, Qt.ItemDataRole.UserRole, candidate)
            if candidate.detail:
                track_item.setToolTip(1, candidate.detail)
            if candidate.status in _SELECTABLE:
                track_item.setFlags(track_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                track_item.setCheckState(0, Qt.CheckState.Unchecked)
                album_item.setFlags(album_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            else:
                track_item.setFlags(track_item.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
            album_item.addChild(track_item)
        self.tree.expandAll()
        self.tree.resizeColumnToContents(1)
        self.tree.resizeColumnToContents(2)
        self.tree.blockSignals(False)

    def _item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        if column != 0:
            return
        self.tree.blockSignals(True)
        if item.parent() is None:
            state = item.checkState(0)
            for index in range(item.childCount()):
                child = item.child(index)
                candidate = child.data(0, Qt.ItemDataRole.UserRole)
                if isinstance(candidate, AndroidCandidate) and candidate.status in _SELECTABLE:
                    child.setCheckState(0, state)
        else:
            parent = item.parent()
            selectable = [
                parent.child(index)
                for index in range(parent.childCount())
                if parent.child(index).flags() & Qt.ItemFlag.ItemIsUserCheckable
            ]
            checked = sum(child.checkState(0) == Qt.CheckState.Checked for child in selectable)
            if checked == 0:
                parent.setCheckState(0, Qt.CheckState.Unchecked)
            elif checked == len(selectable):
                parent.setCheckState(0, Qt.CheckState.Checked)
            else:
                parent.setCheckState(0, Qt.CheckState.PartiallyChecked)
        self.tree.blockSignals(False)
        self._update_selection()

    def _selected_candidates(self) -> list[AndroidCandidate]:
        selected: list[AndroidCandidate] = []
        for album_index in range(self.tree.topLevelItemCount()):
            album = self.tree.topLevelItem(album_index)
            for track_index in range(album.childCount()):
                item = album.child(track_index)
                candidate = item.data(0, Qt.ItemDataRole.UserRole)
                if (
                    isinstance(candidate, AndroidCandidate)
                    and candidate.status in _SELECTABLE
                    and item.checkState(0) == Qt.CheckState.Checked
                ):
                    selected.append(candidate)
        return selected

    def _update_selection(self) -> None:
        selected = self._selected_candidates()
        total = sum(item.source_size_bytes for item in selected)
        noun = "fichier sélectionné" if len(selected) == 1 else "fichiers sélectionnés"
        self.lbl_selection.setText(
            f"{len(selected)} {noun} · {_size_label(total)}"
        )
        device = self.device_combo.currentData()
        self.btn_transfer.setEnabled(
            not self.is_busy()
            and bool(selected)
            and isinstance(device, AndroidDevice)
            and device.state == "device"
        )

    def _on_progress(self, message: str, completed: int, total: int) -> None:
        if self._task == "transfer":
            self.progress.setRange(0, max(1, total))
            self.progress.setValue(completed)
            self.lbl_status.setText(f"{message} · {completed}/{total} fichiers terminés")
        else:
            self.lbl_status.setText(message)

    def _transfer_finished(self, summary) -> None:
        ignored = summary.skipped + self._ignored_count
        self._last_transfer_summary = (
            f"Bilan : {summary.succeeded} réussis, {summary.failed} échoués, "
            f"{ignored} ignorés."
        )
        self.lbl_status.setText(self._last_transfer_summary)

    def _worker_failed(self, message: str) -> None:
        self.lbl_status.setText(message)
        QMessageBox.warning(self, "Exporter vers Android", message)

    def _worker_cleared(self) -> None:
        task = self._task
        self._thread = None
        self._worker = None
        self._set_busy(False)
        if task == "transfer":
            self._candidates.clear()
            self._scan_after_transfer = True
            self._scan()
