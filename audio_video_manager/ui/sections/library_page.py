"""Ma bibliothèque — grille de pochettes responsive (pas de lecteur audio)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QIcon, QPixmap
from PySide6.QtWidgets import (
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
from audio_video_manager.storage.catalog import ReleaseRow, list_releases, list_tracks_for_release
from audio_video_manager.storage.database import Database
from audio_video_manager.ui.path_labels import friendly_path_label, path_tooltip
from audio_video_manager.ui.widgets import empty_state_card, make_card, make_chip

_COVER_NAMES = ("cover.jpg", "cover.png", "folder.jpg", "Folder.jpg")
_NARROW = 900
_WIDE = 1400


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
        self.btn_open_album = QPushButton("Ouvrir le dossier album")
        self.btn_open_album.setEnabled(False)
        self.btn_open_album.setProperty("primary", True)
        self.btn_open_album.clicked.connect(self._open_album)
        head.addWidget(self.btn_open_album, 0, Qt.AlignmentFlag.AlignTop)
        dv.addLayout(head)

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
