"""Requêtes lecture seule pour Bibliothèque / Historique (UI)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from audio_video_manager.storage.database import Database


@dataclass(frozen=True)
class ReleaseRow:
    id: int
    disc_id: str | None
    mbid: str | None
    album_artist: str | None
    album: str | None
    year: int | None
    path: str | None
    status: str
    imported_at: str | None

    @property
    def path_exists(self) -> bool:
        return bool(self.path and Path(self.path).is_dir())


@dataclass(frozen=True)
class TrackRow:
    number: int
    title: str | None
    path: str | None
    duration_ms: int | None
    flac_ok: int | None


@dataclass(frozen=True)
class JobRow:
    id: str
    state: str
    step: str | None
    workdir: str | None
    started_at: str | None
    finished_at: str | None
    error_summary: str | None
    mode: str | None
    collision_policy: str | None
    warnings_json: str | None
    library_path: str | None
    metadata_id: str | None = None
    disc_id: str | None = None

    @property
    def warnings(self) -> list[str]:
        if not self.warnings_json:
            return []
        try:
            data = json.loads(self.warnings_json)
        except json.JSONDecodeError:
            return [self.warnings_json]
        if isinstance(data, list):
            return [str(x) for x in data]
        return [str(data)]

    @property
    def library_exists(self) -> bool:
        return bool(self.library_path and Path(self.library_path).is_dir())

    @property
    def workdir_exists(self) -> bool:
        return bool(self.workdir and Path(self.workdir).is_dir())

    @property
    def files_recoverable(self) -> bool:
        """Zone temporaire encore présente après échec / interruption (pas de suppression)."""
        return self.state in {
            "Failed",
            "Cancelled",
            "Interrupted",
            "Abandoned",
        } and self.workdir_exists

    @property
    def unfinished_active(self) -> bool:
        return self.finished_at is None and self.state in {
            "Ripping",
            "Tagging",
            "Staging",
            "FlacIntegrity",
            "Organizing",
            "ReadyToPublish",
            "AwaitingPublishConfirmation",
        }


def list_releases(db: Database, *, limit: int = 200) -> list[ReleaseRow]:
    conn = db.connect()
    rows = conn.execute(
        """
        SELECT id, disc_id, mbid, album_artist, album, year, path, status, imported_at
        FROM releases
        ORDER BY imported_at DESC, id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [
        ReleaseRow(
            id=int(r["id"]),
            disc_id=r["disc_id"],
            mbid=r["mbid"],
            album_artist=r["album_artist"],
            album=r["album"],
            year=r["year"],
            path=r["path"],
            status=r["status"] or "unknown",
            imported_at=r["imported_at"],
        )
        for r in rows
    ]


def list_tracks_for_release(db: Database, release_id: int) -> list[TrackRow]:
    conn = db.connect()
    rows = conn.execute(
        """
        SELECT number, title, path, duration_ms, flac_ok
        FROM tracks
        WHERE release_id = ?
        ORDER BY number ASC
        """,
        (release_id,),
    ).fetchall()
    return [
        TrackRow(
            number=int(r["number"]),
            title=r["title"],
            path=r["path"],
            duration_ms=r["duration_ms"],
            flac_ok=r["flac_ok"],
        )
        for r in rows
    ]


def list_jobs(db: Database, *, limit: int = 200) -> list[JobRow]:
    conn = db.connect()
    cols = {row[1] for row in conn.execute("PRAGMA table_info(jobs)").fetchall()}
    rows = conn.execute(
        """
        SELECT *
        FROM jobs
        ORDER BY COALESCE(started_at, updated_at, id) DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    out: list[JobRow] = []
    for r in rows:
        keys = set(r.keys())
        out.append(
            JobRow(
                id=str(r["id"]),
                state=str(r["state"]),
                step=r["step"],
                workdir=r["workdir"],
                started_at=r["started_at"],
                finished_at=r["finished_at"],
                error_summary=r["error_summary"],
                mode=r["mode"] if "mode" in keys else None,
                collision_policy=r["collision_policy"] if "collision_policy" in keys else None,
                warnings_json=r["warnings_json"] if "warnings_json" in keys else None,
                library_path=r["library_path"] if "library_path" in keys else None,
                metadata_id=(
                    str(r["metadata_id"])
                    if "metadata_id" in cols and r["metadata_id"]
                    else None
                ),
                disc_id=(
                    str(r["disc_id"]) if "disc_id" in cols and r["disc_id"] else None
                ),
            )
        )
    return out


def mark_job_abandoned(db: Database, job_id: str) -> bool:
    """Marque un job abandonné — ne supprime aucun fichier (AVM-10B)."""
    from audio_video_manager.orchestration.reconciliation import (
        mark_job_abandoned as _abandon,
    )

    return _abandon(db, job_id)


def state_label_fr(state: str) -> str:
    mapping = {
        "Completed": "Terminé",
        "CompletedWithWarnings": "Terminé (avertissements)",
        "Failed": "Échec",
        "Cancelled": "Annulé",
        "Interrupted": "Interrompu",
        "Abandoned": "Abandonné",
        "Ripping": "Extraction…",
        "Tagging": "Tags…",
        "Staging": "Préparation…",
        "AwaitingPublishConfirmation": "En attente de publication",
        "SkippedDuplicate": "Doublon ignoré",
        "ReadyToPublish": "Prêt à publier",
    }
    return mapping.get(state, state)
