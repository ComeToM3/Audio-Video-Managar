"""Pont Bibliothèque QML — lecture catalogue via Database partagée (AVM-08B)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import (
    Property,
    QAbstractListModel,
    QModelIndex,
    QObject,
    Qt,
    Signal,
    Slot,
)
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl

from audio_video_manager.storage.catalog import list_releases, list_tracks_for_release
from audio_video_manager.storage.database import Database
from audio_video_manager.ui.path_labels import friendly_path_label

_COVER_NAMES = ("cover.jpg", "cover.png", "folder.jpg", "Folder.jpg", "cover.jpeg")


def _find_cover_uri(album_dir: str | None) -> str:
    if not album_dir:
        return ""
    root = Path(album_dir)
    if not root.is_dir():
        return ""
    for name in _COVER_NAMES:
        p = root / name
        if p.is_file() and p.stat().st_size > 0:
            return p.as_uri()
    return ""


def _fmt_ms(ms: int | None) -> str:
    if not ms:
        return "—"
    s = int(ms) // 1000
    return f"{s // 60}:{s % 60:02d}"


def _rows_from_db(db: Database) -> list[dict]:
    rows: list[dict] = []
    for rel in list_releases(db, limit=500):
        tracks = list_tracks_for_release(db, rel.id)
        path_ok = rel.path_exists
        files_ok = path_ok and (
            all((t.path and Path(t.path).is_file()) for t in tracks) if tracks else True
        )
        rows.append(
            {
                "id": rel.id,
                "artist": rel.album_artist or "Artiste inconnu",
                "album": rel.album or "Album sans titre",
                "year": int(rel.year) if rel.year else 0,
                "path": rel.path or "",
                "pathLabel": friendly_path_label(rel.path, empty="—"),
                "cover": _find_cover_uri(rel.path),
                "ready": bool(files_ok),
                "missing": not path_ok,
                "trackCount": len(tracks),
                "tracks": [
                    {
                        "number": t.number,
                        "title": t.title or f"Piste {t.number}",
                        "duration": _fmt_ms(t.duration_ms),
                    }
                    for t in tracks[:60]
                ],
            }
        )
    return rows


class AlbumListModel(QAbstractListModel):
    ArtistRole = Qt.ItemDataRole.UserRole + 1
    AlbumRole = Qt.ItemDataRole.UserRole + 2
    YearRole = Qt.ItemDataRole.UserRole + 3
    CoverRole = Qt.ItemDataRole.UserRole + 4
    PathLabelRole = Qt.ItemDataRole.UserRole + 5
    ReadyRole = Qt.ItemDataRole.UserRole + 6
    MissingRole = Qt.ItemDataRole.UserRole + 7
    TrackCountRole = Qt.ItemDataRole.UserRole + 8
    IdRole = Qt.ItemDataRole.UserRole + 9
    LetterRole = Qt.ItemDataRole.UserRole + 10

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._all: list[dict] = []
        self._rows: list[dict] = []
        self._filter = ""

    def reload(self, rows: list[dict]) -> None:
        self.beginResetModel()
        self._all = list(rows)
        self._apply_filter_locked()
        self.endResetModel()

    def _apply_filter_locked(self) -> None:
        q = self._filter
        if not q:
            self._rows = list(self._all)
            return
        self._rows = [
            r
            for r in self._all
            if q in f"{r['artist']} {r['album']} {r['year']}".casefold()
        ]

    def rowCount(self, parent=QModelIndex()) -> int:  # noqa: N802
        if parent.isValid():
            return 0
        return len(self._rows)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):  # noqa: N802
        if not index.isValid() or not (0 <= index.row() < len(self._rows)):
            return None
        r = self._rows[index.row()]
        return {
            self.IdRole: r["id"],
            self.ArtistRole: r["artist"],
            self.AlbumRole: r["album"],
            self.YearRole: r["year"],
            self.CoverRole: r["cover"],
            self.PathLabelRole: r["pathLabel"],
            self.ReadyRole: r["ready"],
            self.MissingRole: r["missing"],
            self.TrackCountRole: r["trackCount"],
            self.LetterRole: (r["artist"] or "?")[:1].upper(),
            Qt.ItemDataRole.DisplayRole: f"{r['artist']} — {r['album']}",
        }.get(role)

    def roleNames(self):  # noqa: N802
        return {
            self.IdRole: b"albumId",
            self.ArtistRole: b"artist",
            self.AlbumRole: b"album",
            self.YearRole: b"year",
            self.CoverRole: b"cover",
            self.PathLabelRole: b"pathLabel",
            self.ReadyRole: b"ready",
            self.MissingRole: b"missing",
            self.TrackCountRole: b"trackCount",
            self.LetterRole: b"letter",
        }

    @Slot(str)
    def setFilter(self, text: str) -> None:
        self.beginResetModel()
        self._filter = (text or "").strip().casefold()
        self._apply_filter_locked()
        self.endResetModel()

    def album_at(self, row: int) -> dict | None:
        if 0 <= row < len(self._rows):
            return self._rows[row]
        return None


class LibraryBridge(QObject):
    selectionChanged = Signal()
    sourceChanged = Signal()
    countChanged = Signal()
    openFailed = Signal(str)

    def __init__(self, db: Database, parent=None) -> None:
        super().__init__(parent)
        self._db = db
        self._model = AlbumListModel(self)
        self._selected: dict | None = None
        self._source = "catalogue local"
        self.reload()

    def reload(self) -> None:
        """Recharge depuis la Database partagée (pas de nouvelle connexion métier)."""
        self._model.reload(_rows_from_db(self._db))
        self._selected = None
        self.selectionChanged.emit()
        self.countChanged.emit()
        self.sourceChanged.emit()

    @Property(QObject, constant=True)
    def albums(self):
        return self._model

    @Property(str, notify=sourceChanged)
    def sourceLabel(self) -> str:
        return self._source

    @Property(str, notify=selectionChanged)
    def selectedArtist(self) -> str:
        return (self._selected or {}).get("artist", "")

    @Property(str, notify=selectionChanged)
    def selectedAlbum(self) -> str:
        return (self._selected or {}).get("album", "")

    @Property(int, notify=selectionChanged)
    def selectedYear(self) -> int:
        return int((self._selected or {}).get("year") or 0)

    @Property(str, notify=selectionChanged)
    def selectedCover(self) -> str:
        return (self._selected or {}).get("cover", "")

    @Property(str, notify=selectionChanged)
    def selectedPathLabel(self) -> str:
        return (self._selected or {}).get("pathLabel", "")

    @Property(str, notify=selectionChanged)
    def selectedLetter(self) -> str:
        return (self._selected or {}).get("artist", "?")[:1].upper()

    @Property(bool, notify=selectionChanged)
    def selectedReady(self) -> bool:
        return bool((self._selected or {}).get("ready"))

    @Property(bool, notify=selectionChanged)
    def selectedMissing(self) -> bool:
        return bool((self._selected or {}).get("missing"))

    @Property(int, notify=selectionChanged)
    def selectedTrackCount(self) -> int:
        return int((self._selected or {}).get("trackCount") or 0)

    @Property("QVariantList", notify=selectionChanged)
    def selectedTracks(self):
        return list((self._selected or {}).get("tracks") or [])

    @Property(bool, notify=selectionChanged)
    def hasSelection(self) -> bool:
        return self._selected is not None

    @Slot(result=int)
    def albumCount(self) -> int:
        return self._model.rowCount()

    @Slot(int)
    def selectRow(self, row: int) -> None:
        self._selected = self._model.album_at(row)
        self.selectionChanged.emit()

    @Slot(str)
    def search(self, text: str) -> None:
        self._model.setFilter(text)
        self._selected = None
        self.selectionChanged.emit()
        self.countChanged.emit()

    @Slot()
    def openAlbumFolder(self) -> None:
        path = (self._selected or {}).get("path") or ""
        if not path or not Path(path).is_dir():
            self.openFailed.emit("Dossier album introuvable.")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    @Slot()
    def refresh(self) -> None:
        filt = self._model._filter  # noqa: SLF001
        self.reload()
        if filt:
            self._model.setFilter(filt)
