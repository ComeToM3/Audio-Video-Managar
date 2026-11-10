"""Ma bibliothèque — grille de pochettes responsive (pas de lecteur audio)."""

from __future__ import annotations

import uuid
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QIcon, QImage, QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from audio_video_manager.config import AppConfig
from audio_video_manager.storage.catalog import ReleaseRow, list_releases, list_tracks_for_release, list_videos
from audio_video_manager.storage.database import Database
from audio_video_manager.ui.path_labels import friendly_path_label, path_tooltip
from audio_video_manager.ui.widgets import empty_state_card, make_card, make_chip

_COVER_NAMES = ("cover.jpg", "cover.png", "folder.jpg", "Folder.jpg")
_NARROW = 900
_WIDE = 1400


class VideoLibraryPage(QWidget):
    busy_changed = Signal(bool)

    def __init__(self, db: Database, config: AppConfig, parent=None) -> None:
        super().__init__(parent)
        self._db = db
        self._config = config
        self._rows = []
        self._thread = None
        self._worker = None
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 20, 28, 20)
        title = QLabel("Vidéos et audio DVD archivés")
        title.setObjectName("pageTitle")
        root.addWidget(title)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Fichier", "Durée", "Validation", "État"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAccessibleName("Vidéos et audio DVD archivés")
        self.table.itemSelectionChanged.connect(self._selection_changed)
        self.table.cellDoubleClicked.connect(lambda *_args: self._open_video())
        root.addWidget(self.table, 1)
        self.detail = QLabel("Sélectionnez un média.")
        self.detail.setWordWrap(True)
        self.detail.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        root.addWidget(self.detail)
        actions = QHBoxLayout()
        self.btn_refresh = QPushButton("Actualiser")
        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_cancel = QPushButton("Annuler la vérification")
        self.btn_cancel.clicked.connect(self._cancel_reconcile)
        self.btn_cancel.hide()
        self.btn_reconcile = QPushButton("Vérifier la publication en attente")
        self.btn_reconcile.clicked.connect(self._reconcile)
        self.btn_remove_pending = QPushButton("Retirer l'entrée manquante")
        self.btn_remove_pending.clicked.connect(self._remove_pending)
        self.btn_open = QPushButton("Ouvrir le média")
        self.btn_open.setProperty("primary", True)
        self.btn_open.clicked.connect(self._open_video)
        actions.addWidget(self.btn_refresh)
        actions.addWidget(self.btn_cancel)
        actions.addStretch(1)
        actions.addWidget(self.btn_open)
        root.addLayout(actions)
        recovery_actions = QHBoxLayout()
        recovery_actions.addWidget(self.btn_reconcile)
        recovery_actions.addWidget(self.btn_remove_pending)
        recovery_actions.addStretch(1)
        root.addLayout(recovery_actions)
        self.refresh()

    def is_busy(self) -> bool:
        return self._thread is not None

    def set_config(self, config: AppConfig) -> None:
        self._config = config

    def shutdown_background_work(self, *, timeout_ms: int = 12_000) -> bool:
        from audio_video_manager.ui.thread_lifecycle import shutdown_worker_thread
        return shutdown_worker_thread(self._thread, self._worker, timeout_ms=timeout_ms)

    def refresh(self) -> None:
        self._rows = list_videos(self._db)
        self.table.setRowCount(len(self._rows))
        for index, row in enumerate(self._rows):
            seconds = int(row.duration_seconds)
            duration = f"{seconds // 3600:02d}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"
            validation = {"decodable": "Décodable, source non vérifiée", "source_verified": "Vérifiée avec la source", "incomplete": "Validation incomplète"}.get(row.validation_status, "Validation inconnue")
            if row.publication_state == "pending" or not row.path_matches:
                validation = "Validation incomplète"
            state = "Publication en attente" if row.publication_state == "pending" else (
                "Fichier manquant" if not row.path_exists else "Disponible" if row.path_matches else "Fichier modifié"
            )
            for column, value in enumerate((Path(row.path).name, duration, validation, state)):
                self.table.setItem(index, column, QTableWidgetItem(value))
        self._selection_changed()

    def _selected_video(self):
        row = self.table.currentRow()
        return self._rows[row] if 0 <= row < len(self._rows) else None

    def _selection_changed(self) -> None:
        import json

        row = self._selected_video()
        self.btn_reconcile.setVisible(bool(row and row.path_exists and (row.publication_state == "pending" or not row.path_matches)))
        self.btn_reconcile.setText("Vérifier la publication en attente" if row and row.publication_state == "pending" else "Vérifier le fichier modifié")
        self.btn_remove_pending.setVisible(bool(row and row.publication_state == "pending" and not row.path_exists))
        self.btn_open.setEnabled(bool(row and row.publication_state == "published" and row.path_matches and not self.is_busy()))
        self.btn_reconcile.setEnabled(bool(row and row.path_exists and (row.publication_state == "pending" or not row.path_matches) and not self.is_busy()))
        self.btn_remove_pending.setEnabled(bool(row and row.publication_state == "pending" and not row.path_exists and not self.is_busy()))
        if row is None:
            self.detail.setText("Sélectionnez un média.")
            return
        try:
            streams = json.loads(row.streams_json)
            chapters = json.loads(row.chapters_json)
            stream_text = ", ".join(f"{stream.get('codec_type', '?')} : {stream.get('codec_name', '?')}" for stream in streams)
            validation = self.table.item(self.table.currentRow(), 2).text()
            self.detail.setText(f"{row.path}\n{validation} · {row.format} · {stream_text} · {len(chapters)} chapitre(s)")
        except (ValueError, TypeError, AttributeError):
            self.detail.setText(f"{row.path}\nMétadonnées illisibles dans le catalogue.")

    def _open_video(self) -> None:
        row = self._selected_video()
        if not row or row.publication_state != "published":
            return
        if not row.path_exists:
            self.refresh()
            QMessageBox.warning(self, "Vidéo manquante", "Le fichier n'est plus présent à son emplacement enregistré.")
            return
        if not row.path_matches:
            self.refresh()
            QMessageBox.warning(self, "Vidéo modifiée", "Le fichier a changé depuis sa validation; son ouverture est suspendue.")
            return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(row.path)):
            QMessageBox.warning(self, "Lecture", "Le lecteur système n'a pas pu ouvrir ce fichier.")

    def _reconcile(self) -> None:
        row = self._selected_video()
        if row is None or self.is_busy():
            return
        from audio_video_manager.ui.thread_lifecycle import attach_worker_thread
        from audio_video_manager.ui.video_worker import VideoReconcileWorker

        if row.sha256.startswith("intent:"):
            if QMessageBox.question(
                self, "Vérifier le média",
                "Une opération a été interrompue. Vérifier le fichier présent et l'ajouter au catalogue ?\n\n"
                "Sa provenance et sa fidélité au disque ne seront pas établies.",
            ) != QMessageBox.StandardButton.Yes:
                return
            from audio_video_manager.ui.dvd_worker import DvdTaskWorker

            self._worker = DvdTaskWorker(
                config=self._config, task="index", source=row.path, db_path=self._db.path,
            )
            self.btn_cancel.show()
        else:
            self._worker = VideoReconcileWorker(self._db.path, row.id)
        self._thread = attach_worker_thread(
            self._worker, on_finished=self._reconcile_finished,
            on_failed=self._reconcile_failed, on_cleared=self._reconcile_cleared,
            progress_slot=self._on_reconcile_progress,
        )
        self._selection_changed()
        self.detail.setText("Vérification de l'empreinte du fichier en cours…")
        self.busy_changed.emit(True)
        self._thread.start()

    def _cancel_reconcile(self) -> None:
        if self._worker is not None and hasattr(self._worker, "cancel"):
            self._worker.cancel()
            self.btn_cancel.setEnabled(False)
            self.detail.setText("Annulation demandée; le fichier reste intact.")

    def _on_reconcile_progress(self, message: str, _fraction: object) -> None:
        self.detail.setText(message)

    def _remove_pending(self) -> None:
        row = self._selected_video()
        if row is None or self.is_busy():
            return
        if QMessageBox.question(self, "Retirer l'entrée", "Retirer cette entrée en attente sans fichier du catalogue ?") != QMessageBox.StandardButton.Yes:
            return
        from audio_video_manager.library.video_archive import remove_missing_pending_video
        try:
            remove_missing_pending_video(self._db, row.id)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Entrée en attente", str(exc))
        self.refresh()

    def _reconcile_finished(self, _result: object) -> None:
        self.detail.setText("Publication vérifiée et indexée.")

    def _reconcile_failed(self, message: str) -> None:
        QMessageBox.warning(self, "Publication en attente", message)

    def _reconcile_cleared(self) -> None:
        self._thread = None
        self._worker = None
        self.btn_cancel.hide()
        self.btn_cancel.setEnabled(True)
        self.refresh()
        self.busy_changed.emit(False)


def _album_cover_path(album_dir: str | None) -> Path | None:
    if not album_dir:
        return None
    root = Path(album_dir)
    if not root.is_dir():
        return None
    for name in _COVER_NAMES:
        p = root / name
        if p.is_file() and p.stat().st_size > 0:
            return p
    return None


def _load_cover_pixmap(album_dir: str | None, size: int = 48) -> QPixmap | None:
    path = _album_cover_path(album_dir)
    if path is None:
        return None
    pix = QPixmap(str(path))
    if pix.isNull():
        return None
    return pix.scaled(
        size,
        size,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )


def _placeholder_cover(size: int, letter: str) -> QPixmap:
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    from PySide6.QtGui import QColor, QPainter, QFont

    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    from audio_video_manager.ui.fonts import display_font_family
    from audio_video_manager.ui.theme import TOKEN

    p.setBrush(QColor(TOKEN["accent"]))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(0, 0, size, size, 14, 14)
    p.setPen(QColor(TOKEN["ink"]))
    font = QFont(display_font_family())
    font.setBold(True)
    font.setPixelSize(max(18, size // 4))
    p.setFont(font)
    p.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, (letter or "?")[:1].upper())
    p.end()
    return pix


class LibraryPage(QWidget):
    def __init__(self, config: AppConfig, db: Database, parent=None) -> None:
        super().__init__(parent)
        self._config = config
        self._db = db
        self._rows: list[ReleaseRow] = []
        self._selected: ReleaseRow | None = None
        self._cover_size = 120
        self._narrow = False

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 20, 28, 20)
        root.setSpacing(12)

        title = QLabel("Ma bibliothèque")
        title.setObjectName("pageTitle")
        title.setAccessibleName("Ma bibliothèque")
        root.addWidget(title)

        self.lbl_root = QLabel()
        self.lbl_root.setObjectName("heroSub")
        self.lbl_root.setWordWrap(True)
        self.lbl_root.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        root.addWidget(self.lbl_root)

        tools = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setObjectName("search")
        self.search.setPlaceholderText("Rechercher un artiste ou un album…")
        self.search.setClearButtonEnabled(True)
        self.search.setAccessibleName("Recherche bibliothèque")
        self.search.textChanged.connect(self._apply_filter)
        self.btn_refresh = QPushButton("Actualiser")
        self.btn_refresh.setProperty("ghost", True)
        self.btn_refresh.setAccessibleName("Actualiser la bibliothèque")
        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_open_lib = QPushButton("Ouvrir le dossier bibliothèque")
        self.btn_open_lib.setProperty("ghost", True)
        self.btn_open_lib.clicked.connect(self._open_library_root)
        tools.addWidget(self.search, 1)
        tools.addWidget(self.btn_refresh)
        tools.addWidget(self.btn_open_lib)
        root.addLayout(tools)

        self.list = QListWidget()
        self.list.setObjectName("albumGrid")
        self.list.setAccessibleName("Liste des albums")
        self.list.setViewMode(QListWidget.ViewMode.IconMode)
        self.list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.list.setMovement(QListWidget.Movement.Static)
        self.list.setUniformItemSizes(True)
        self.list.setWordWrap(True)
        self.list.setSpacing(8)
        self.list.setIconSize(QSize(self._cover_size, self._cover_size))
        self.list.setGridSize(QSize(self._cover_size + 36, self._cover_size + 72))
        self.list.currentItemChanged.connect(self._on_select)
        # Priorité pochettes : stretch élevé (détail compact en étroit)
        root.addWidget(self.list, 5)

        self._detail_card = make_card()
        dv = QVBoxLayout(self._detail_card)
        dv.setContentsMargins(16, 14, 16, 14)
        dv.setSpacing(10)
        head = QHBoxLayout()
        self.cover_label = QLabel()
        self.cover_label.setObjectName("coverPlaceholder")
        self.cover_label.setFixedSize(96, 96)
        self.cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_label.setAccessibleName("Pochette de l’album")
        self.cover_label.setText("—")
        head.addWidget(self.cover_label)
        meta_col = QVBoxLayout()
        self.lbl_detail = QLabel("Sélectionnez un album.")
        self.lbl_detail.setWordWrap(True)
        self.lbl_detail.setAccessibleName("Détail album")
        meta_col.addWidget(self.lbl_detail)
        self.chip_status = make_chip("—", "ok")
        self.chip_status.hide()
        meta_col.addWidget(self.chip_status, 0, Qt.AlignmentFlag.AlignLeft)
        head.addLayout(meta_col, 1)
        actions = QHBoxLayout()
        self.btn_cover = QPushButton("Ajouter/remplacer la pochette")
        self.btn_cover.setAccessibleName("Ajouter ou remplacer la pochette de l’album")
        self.btn_cover.setToolTip(
            "Choisir une image locale et la conserver dans le dossier de cet album."
        )
        self.btn_cover.setEnabled(False)
        self.btn_cover.clicked.connect(self._choose_cover)
        actions.addWidget(self.btn_cover)
        actions.addStretch(1)
        self.btn_open_album = QPushButton("Ouvrir le dossier album")
        self.btn_open_album.setEnabled(False)
        self.btn_open_album.setProperty("primary", True)
        self.btn_open_album.clicked.connect(self._open_album)
        actions.addWidget(self.btn_open_album)
        dv.addLayout(head)
        dv.addLayout(actions)

        self.tbl_tracks = QTableWidget(0, 3)
        self.tbl_tracks.setHorizontalHeaderLabels(["#", "Titre", "Durée"])
        self.tbl_tracks.horizontalHeader().setStretchLastSection(True)
        self.tbl_tracks.setAccessibleName("Pistes de l’album")
        self.tbl_tracks.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tbl_tracks.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tbl_tracks.setMaximumHeight(160)
        self.tbl_tracks.setAlternatingRowColors(True)
        dv.addWidget(self.tbl_tracks)
        root.addWidget(self._detail_card, 2)

        self.empty_card = empty_state_card(
            "Aucun album pour l’instant",
            "Insérez un CD et utilisez « Archiver un disque ».",
        )
        self.empty_card.hide()
        root.addWidget(self.empty_card)

        # Compat 06H : lbl_empty toujours présent
        self.lbl_empty = QLabel(
            "Aucun album importé pour l’instant. Utilisez « Archiver un disque »."
        )
        self.lbl_empty.setProperty("role", "muted")
        self.lbl_empty.setWordWrap(True)
        self.lbl_empty.hide()
        root.addWidget(self.lbl_empty)

        self._update_root_label()

    def set_config(self, config: AppConfig) -> None:
        self._config = config
        self._update_root_label()

    def refresh(self) -> None:
        self._rows = list_releases(self._db, limit=500)
        self._apply_filter()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.refresh()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        w = self.width()
        narrow = w < _NARROW
        if narrow:
            size = 100
            track_h = 100
        elif w >= _WIDE:
            size = 148
            track_h = 200
        else:
            size = 120
            track_h = 160
        self.tbl_tracks.setMaximumHeight(track_h)
        lay = self.layout()
        if lay is not None:
            # Étroit : prioriser la grille ; large/max : laisser plus de place au détail
            li = lay.indexOf(self.list)
            di = lay.indexOf(self._detail_card)
            if li >= 0 and di >= 0:
                if narrow:
                    lay.setStretch(li, 6)
                    lay.setStretch(di, 1)
                elif w >= _WIDE:
                    lay.setStretch(li, 4)
                    lay.setStretch(di, 3)
                else:
                    lay.setStretch(li, 5)
                    lay.setStretch(di, 2)
        if size != self._cover_size or narrow != self._narrow:
            self._cover_size = size
            self._narrow = narrow
            self.list.setIconSize(QSize(size, size))
            self.list.setGridSize(QSize(size + 40, size + 78))
            if self.list.count():
                self._apply_filter()

    def _update_root_label(self) -> None:
        root = self._config.library_root or ""
        label = friendly_path_label(root, empty="—")
        self.lbl_root.setText(f"Albums FLAC locaux — {label}")
        self.lbl_root.setToolTip(path_tooltip(root) or "Dossier bibliothèque")

    def _apply_filter(self) -> None:
        q = (self.search.text() or "").strip().casefold()
        self.list.clear()
        shown = 0
        for row in self._rows:
            artist = row.album_artist or "Artiste inconnu"
            album = row.album or "Album sans titre"
            # Texte plat pour recherche / tests (item.text contient Queen)
            search_blob = f"{artist} — {album}"
            if row.year:
                search_blob += f" ({row.year})"
            if not row.path_exists:
                search_blob += "  · fichiers manquants"
            blob = f"{row.album_artist} {row.album} {row.year or ''}".casefold()
            if q and q not in blob:
                continue
            item = QListWidgetItem(search_blob)
            item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
            item.setData(Qt.ItemDataRole.UserRole, row.id)
            item.setToolTip(search_blob.replace("\n", " "))
            pix = _load_cover_pixmap(row.path, self._cover_size)
            if pix is None:
                pix = _placeholder_cover(self._cover_size, artist[:1])
            item.setIcon(QIcon(pix))
            if not row.path_exists:
                item.setForeground(Qt.GlobalColor.darkYellow)
            self.list.addItem(item)
            shown += 1
        empty = shown == 0
        self.lbl_empty.setVisible(False)
        self.empty_card.setVisible(empty and not q)
        self.list.setVisible(not empty)
        if empty and q:
            self.lbl_empty.setText("Aucun résultat pour cette recherche.")
            self.lbl_empty.setVisible(True)
        if empty:
            self.lbl_detail.setText("Aucun album à afficher.")
            self.tbl_tracks.setRowCount(0)
            self.btn_open_album.setEnabled(False)
            self.btn_cover.setEnabled(False)
            self.cover_label.clear()
            self.cover_label.setText("—")
            self.chip_status.hide()

    def _row_by_id(self, rid: int) -> ReleaseRow | None:
        for r in self._rows:
            if r.id == rid:
                return r
        return None

    def _on_select(self, current: QListWidgetItem | None, _prev) -> None:
        if current is None:
            return
        rid = int(current.data(Qt.ItemDataRole.UserRole))
        row = self._row_by_id(rid)
        if row is None:
            return
        self._selected = row
        status = "Prêt" if row.path_exists else "Fichiers manquants"
        n_tracks = len(list_tracks_for_release(self._db, rid))
        loc = friendly_path_label(row.path, empty="Emplacement inconnu")
        self.lbl_detail.setText(
            f"<b>{row.album_artist or '—'} — {row.album or '—'}</b><br/>"
            f"Année : {row.year or '—'} · {n_tracks} piste(s)<br/>"
            f"<span style='color:#5C6478'>Dossier : {loc}</span>"
        )
        self.lbl_detail.setToolTip(path_tooltip(row.path))
        self.chip_status.setText(status)
        self.chip_status.setObjectName("chip" if row.path_exists else "chipWarn")
        self.chip_status.setProperty("chip", "ok" if row.path_exists else "warn")
        self.chip_status.style().unpolish(self.chip_status)
        self.chip_status.style().polish(self.chip_status)
        self.chip_status.show()
        pix = _load_cover_pixmap(row.path, 96)
        if pix is not None:
            self.cover_label.setPixmap(pix)
            self.cover_label.setText("")
        else:
            self.cover_label.clear()
            self.cover_label.setText((row.album_artist or "?")[:1])
        tracks = list_tracks_for_release(self._db, rid)
        self.tbl_tracks.setRowCount(len(tracks))
        for i, t in enumerate(tracks):
            dur = ""
            if t.duration_ms:
                sec = int(t.duration_ms) // 1000
                dur = f"{sec // 60}:{sec % 60:02d}"
            missing = t.path and not Path(t.path).is_file()
            title = t.title or "Sans titre"
            if missing:
                title += " (fichier manquant)"
            self.tbl_tracks.setItem(i, 0, QTableWidgetItem(f"{t.number:02d}"))
            self.tbl_tracks.setItem(i, 1, QTableWidgetItem(title))
            self.tbl_tracks.setItem(i, 2, QTableWidgetItem(dur))
        self.btn_open_album.setEnabled(row.path_exists)
        self.btn_cover.setEnabled(row.path_exists)

    def _choose_cover(self) -> None:
        row = self._selected
        if row is None or not row.path:
            return
        album_dir = Path(row.path)
        if not album_dir.is_dir():
            QMessageBox.warning(self, "Pochette", "Le dossier de cet album est introuvable.")
            return
        selected, _filter = QFileDialog.getOpenFileName(
            self,
            "Choisir la pochette de l’album",
            "",
            "Images (*.jpg *.jpeg *.png)",
        )
        if not selected:
            return
        source = Path(selected)
        try:
            image_data = source.read_bytes()
        except OSError as exc:
            QMessageBox.warning(self, "Pochette", f"Lecture de l’image impossible : {exc}")
            return
        if not image_data or QImage.fromData(image_data).isNull():
            QMessageBox.warning(
                self,
                "Pochette",
                "Le fichier choisi n’est pas une image décodable par AVM.",
            )
            return

        existing = _album_cover_path(str(album_dir))
        if existing is not None:
            answer = QMessageBox.question(
                self,
                "Remplacer la pochette",
                "Une pochette existe déjà. La remplacer par l’image choisie ?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        destination = album_dir / "cover.jpg"
        temporary = album_dir / f".cover-{uuid.uuid4().hex}.tmp"
        try:
            temporary.write_bytes(image_data)
            temporary.replace(destination)
        except OSError as exc:
            QMessageBox.warning(self, "Pochette", f"Écriture dans la bibliothèque impossible : {exc}")
            return
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

        self.refresh()
        for index in range(self.list.count()):
            item = self.list.item(index)
            if int(item.data(Qt.ItemDataRole.UserRole)) == row.id:
                self.list.setCurrentItem(item)
                break

    def _open_album(self) -> None:
        row = self._selected
        if not row or not row.path:
            return
        path = Path(row.path)
        if path.is_dir():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        else:
            QMessageBox.warning(
                self,
                "Dossier manquant",
                "Le dossier album n’existe plus à cet emplacement.",
            )

    def _open_library_root(self) -> None:
        path = Path(self._config.library_root or "")
        if path.is_dir():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        else:
            QMessageBox.warning(
                self,
                "Bibliothèque",
                "Le dossier bibliothèque configuré est introuvable. Vérifiez Paramètres.",
            )
