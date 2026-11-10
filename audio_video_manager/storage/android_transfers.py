"""Historique des transferts Android associés aux pistes du catalogue AVM."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from audio_video_manager.storage.database import Database


@dataclass(frozen=True)
class AndroidTransferRow:
    id: int
    device_serial: str
    track_id: int
    source_path: str
    source_sha256: str
    source_size_bytes: int
    source_mtime_ns: int
    destination_path: str
    staging_path: str | None
    status: str
    attempted_at: str
    verified_at: str | None
    error_summary: str | None


def list_android_transfers(
    db: Database, device_serial: str
) -> list[AndroidTransferRow]:
    rows = db.connect().execute(
        """
        SELECT transfer.*
        FROM android_transfers AS transfer
        WHERE transfer.device_serial = ?
                ORDER BY transfer.attempted_at DESC, transfer.id DESC
        """,
        (device_serial,),
    ).fetchall()
    return [
        AndroidTransferRow(
            id=int(row["id"]),
            device_serial=str(row["device_serial"]),
            track_id=int(row["track_id"]),
            source_path=str(row["source_path"]),
            source_sha256=str(row["source_sha256"]),
            source_size_bytes=int(row["source_size_bytes"]),
            source_mtime_ns=int(row["source_mtime_ns"]),
            destination_path=str(row["destination_path"]),
            staging_path=row["staging_path"],
            status=str(row["status"]),
            attempted_at=str(row["attempted_at"]),
            verified_at=row["verified_at"],
            error_summary=row["error_summary"],
        )
        for row in rows
    ]


def begin_android_transfer(
    db: Database,
    *,
    device_serial: str,
    track_id: int,
    source_path: str,
    source_sha256: str,
    source_size_bytes: int,
    source_mtime_ns: int,
    destination_path: str,
    staging_path: str,
) -> None:
    attempted_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    db.connect().execute(
        """
        INSERT INTO android_transfers (
            device_serial, track_id, source_path, source_sha256,
            source_size_bytes, source_mtime_ns, destination_path,
            staging_path, status, attempted_at, verified_at, error_summary
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, NULL, NULL)
        ON CONFLICT(device_serial, track_id, source_sha256) DO UPDATE SET
            source_path = excluded.source_path,
            source_size_bytes = excluded.source_size_bytes,
            source_mtime_ns = excluded.source_mtime_ns,
            destination_path = excluded.destination_path,
            staging_path = excluded.staging_path,
            status = 'pending',
            attempted_at = excluded.attempted_at,
            verified_at = NULL,
            error_summary = NULL
        """,
        (
            device_serial,
            track_id,
            source_path,
            source_sha256,
            source_size_bytes,
            source_mtime_ns,
            destination_path,
            staging_path,
            attempted_at,
        ),
    )
    db.connect().commit()


def finish_android_transfer(
    db: Database,
    *,
    device_serial: str,
    track_id: int,
    source_sha256: str,
    succeeded: bool,
    staging_path: str | None,
    error_summary: str | None = None,
) -> None:
    verified_at = (
        datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        if succeeded
        else None
    )
    cursor = db.connect().execute(
        """
        UPDATE android_transfers
        SET status = ?, staging_path = ?, verified_at = ?, error_summary = ?
        WHERE device_serial = ? AND track_id = ? AND source_sha256 = ?
        """,
        (
            "succeeded" if succeeded else "failed",
            staging_path,
            verified_at,
            error_summary,
            device_serial,
            track_id,
            source_sha256,
        ),
    )
    if cursor.rowcount != 1:
        raise RuntimeError("L’enregistrement du transfert Android est introuvable.")
    db.connect().commit()


def mark_android_transfer_verified(
    db: Database,
    *,
    device_serial: str,
    transfer_id: int,
) -> None:
    verified_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    db.connect().execute(
        """
        UPDATE android_transfers
        SET status = 'succeeded', staging_path = NULL,
            verified_at = ?, error_summary = NULL
        WHERE device_serial = ? AND id = ?
        """,
        (verified_at, device_serial, transfer_id),
    )
    db.connect().commit()
