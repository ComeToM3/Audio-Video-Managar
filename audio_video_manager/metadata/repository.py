"""Persistance DiscMetadata (SQLite)."""

from __future__ import annotations

import json
from typing import Any

from audio_video_manager.metadata.models import DiscMetadata
from audio_video_manager.storage.database import Database


class DiscMetadataRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def save(self, sheet: DiscMetadata) -> None:
        sheet.touch()
        payload = json.dumps(sheet.to_dict(), ensure_ascii=False)
        conn = self.db.connect()
        conn.execute(
            """
            INSERT INTO disc_metadata(id, mode, approval, payload_json, created_at, updated_at, approved_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                mode=excluded.mode,
                approval=excluded.approval,
                payload_json=excluded.payload_json,
                updated_at=excluded.updated_at,
                approved_at=excluded.approved_at
            """,
            (
                sheet.id,
                sheet.mode.value,
                sheet.approval.value,
                payload,
                sheet.created_at,
                sheet.updated_at,
                sheet.approved_at,
            ),
        )
        conn.execute(
            "DELETE FROM disc_metadata_corrections WHERE metadata_id=?",
            (sheet.id,),
        )
        for c in sheet.corrections:
            conn.execute(
                """
                INSERT INTO disc_metadata_corrections(
                    metadata_id, field, old_value, new_value, at, note, provenance
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sheet.id,
                    c.field,
                    c.old_value,
                    c.new_value,
                    c.at,
                    c.note,
                    c.provenance.value,
                ),
            )
        conn.commit()

    def get(self, metadata_id: str) -> DiscMetadata | None:
        conn = self.db.connect()
        row = conn.execute(
            "SELECT payload_json FROM disc_metadata WHERE id=?",
            (metadata_id,),
        ).fetchone()
        if row is None:
            return None
        data: dict[str, Any] = json.loads(row["payload_json"])
        return DiscMetadata.from_dict(data)

    def list_ids(self, *, limit: int = 50) -> list[str]:
        conn = self.db.connect()
        rows = conn.execute(
            "SELECT id FROM disc_metadata ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [str(r["id"]) for r in rows]
