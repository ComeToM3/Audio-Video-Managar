"""Pont lecture seule Bibliothèque → QML (AVM-08A). Ne modifie pas les données."""

from __future__ import annotations

import os
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


_COVER_NAMES = ("cover.jpg", "cover.png", "folder.jpg", "Folder.jpg", "cover.jpeg")


def _find_cover(album_dir: str | None) -> str:
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


def _friendly(path: str | None) -> str:
    if not path:
        return "—"
    parts = [x for x in Path(path).parts if x not in ("\\", "/", "")]
    if len(parts) >= 2:
        return " / ".join(parts[-2:])
    return parts[0] if parts else "—"


def load_albums_readonly() -> list[dict]:
    """Charge le catalogue réel si disponible, sinon jeu de démonstration."""
    rows: list[dict] = []
    try:
        from audio_video_manager.storage.catalog import list_releases, list_tracks_for_release
        from audio_video_manager.storage.database import Database

        local = Path(os.environ.get("LOCALAPPDATA", "")) / "AudioVideoManager" / "avm.sqlite3"
        if local.is_file():
            db = Database(local)
            db.initialize()
            for rel in list_releases(db, limit=200):
                tracks = list_tracks_for_release(db, rel.id)
                ready = rel.path_exists and all(
                    (t.path and Path(t.path).is_file()) for t in tracks
                ) if tracks else rel.path_exists
                rows.append(
                    {
                        "id": rel.id,
                        "artist": rel.album_artist or "Artiste inconnu",
                        "album": rel.album or "Album sans titre",
                        "year": int(rel.year) if rel.year else 0,
                        "path": rel.path or "",
                        "pathLabel": _friendly(rel.path),
                        "cover": _find_cover(rel.path),
                        "ready": bool(ready),
                        "missing": not rel.path_exists,
                        "trackCount": len(tracks),
                        "tracks": [
                            {
                                "number": t.number,
                                "title": t.title or f"Piste {t.number}",
                                "duration": _fmt_ms(t.duration_ms),
                            }
                            for t in tracks[:40]
                        ],
                    }
                )
            db.close()
    except Exception:  # noqa: BLE001 — prototype : fallback démo
        rows = []

    if rows:
        return rows

    # Démo isolée (aucune écriture)
    return [
        {
            "id": 1,
            "artist": "Queen",
            "album": "Greatest Hits",
            "year": 1992,
            "path": "",
            "pathLabel": "Queen / Greatest Hits",
            "cover": "",
            "ready": True,
            "missing": False,
            "trackCount": 3,
            "tracks": [
                {"number": 1, "title": "We Will Rock You", "duration": "2:02"},
                {"number": 2, "title": "We Are the Champions", "duration": "2:59"},
                {"number": 3, "title": "Another One Bites the Dust", "duration": "3:35"},
            ],
        },
        {
            "id": 2,
            "artist": "Demo Artist",
            "album": "Album manquant",
            "year": 2001,
            "path": "",
            "pathLabel": "gone / x",
            "cover": "",
            "ready": False,
            "missing": True,
            "trackCount": 0,
            "tracks": [],
        },
    ]


def _fmt_ms(ms: int | None) -> str:
    if not ms:
        return "—"
    s = int(ms) // 1000
    return f"{s // 60}:{s % 60:02d}"


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
        self._all = load_albums_readonly()
        self._rows = list(self._all)

    def rowCount(self, parent=QModelIndex()) -> int:  # noqa: N802
        if parent.isValid():
            return 0
        return len(self._rows)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):  # noqa: N802
        if not index.isValid() or not (0 <= index.row() < len(self._rows)):
            return None
        r = self._rows[index.row()]
        mapping = {
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
        }
        return mapping.get(role)

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
        q = (text or "").strip().casefold()
        self.beginResetModel()
        if not q:
            self._rows = list(self._all)
        else:
            self._rows = [
                r
                for r in self._all
                if q in f"{r['artist']} {r['album']} {r['year']}".casefold()
            ]
        self.endResetModel()

    def album_at(self, row: int) -> dict | None:
        if 0 <= row < len(self._rows):
            return self._rows[row]
        return None


class LibraryBridge(QObject):
    """API exposée à QML."""

    selectionChanged = Signal()
    sourceChanged = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._model = AlbumListModel(self)
        self._selected: dict | None = None
        local = Path(os.environ.get("LOCALAPPDATA", "")) / "AudioVideoManager" / "avm.sqlite3"
        self._source = "catalogue local (lecture seule)" if local.is_file() else "données de démonstration"

    @Property(QObject, constant=True)
    def albums(self):
        return self._model

    @Slot(result=int)
    def albumCount(self) -> int:
        return self._model.rowCount()

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

    @Slot(int)
    def selectRow(self, row: int) -> None:
        self._selected = self._model.album_at(row)
        self.selectionChanged.emit()

    @Slot(str)
    def search(self, text: str) -> None:
        self._model.setFilter(text)
        self._selected = None
        self.selectionChanged.emit()
