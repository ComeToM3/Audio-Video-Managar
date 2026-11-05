"""AVM-06 — empreinte A3 / R3 (JSON UTF-8 canonique)."""

from __future__ import annotations

import json

from audio_video_manager.metadata.approval_fingerprint import (
    compute_approval_fingerprint,
    revoke_approval,
    sheet_fingerprint_payload,
    sync_approval_with_fingerprint,
)
from audio_video_manager.metadata.enums import ApprovalState, CoverStatus, FieldTrust
from audio_video_manager.metadata.factories import make_approvable_sheet
from audio_video_manager.metadata.models import FieldMeta
from audio_video_manager.metadata.validation import approve_sheet


def _approved():
    sheet = make_approvable_sheet()
    sheet.edition.label = "Island"
    sheet.edition.catalog_number = "CID"
    sheet.edition.country = "CA"
    sheet.edition.cover_status = CoverStatus.UNAVAILABLE
    sheet.edition.field_meta["cover_status"] = FieldMeta(trust=FieldTrust.UNAVAILABLE)
    approve_sheet(sheet, note="test")
    return sheet


def test_fingerprint_stable_and_utf8_canonical() -> None:
    sheet = _approved()
    sheet.edition.album_title = "Hélène — été"
    fp1 = compute_approval_fingerprint(sheet)
    fp2 = compute_approval_fingerprint(sheet)
    assert fp1 == fp2
    assert len(fp1) == 64
    payload = sheet_fingerprint_payload(sheet)
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    assert "Hélène" in raw
    assert "\\u" not in raw
    assert raw == json.dumps(
        json.loads(raw), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def test_edit_title_invalidates_via_sync() -> None:
    sheet = _approved()
    fp = compute_approval_fingerprint(sheet)
    assert sheet.approval == ApprovalState.APPROVED
    sheet.edition.album_title = "Autre titre"
    still, msg = sync_approval_with_fingerprint(sheet, fp)
    assert still is False
    assert sheet.approval == ApprovalState.PENDING
    assert msg and "modifiée" in msg.casefold()


def test_navigation_style_no_sync_keeps_approved() -> None:
    """A3 : sans changement de données, Approved reste (pas de sync forcée)."""
    sheet = _approved()
    fp = compute_approval_fingerprint(sheet)
    still, msg = sync_approval_with_fingerprint(sheet, fp)
    assert still is True
    assert msg is None
    assert sheet.approval == ApprovalState.APPROVED


def test_identity_change_detected() -> None:
    sheet = _approved()
    fp = compute_approval_fingerprint(sheet)
    sheet.identity.disc_id = "other.disc.id"
    still, _ = sync_approval_with_fingerprint(sheet, fp)
    assert still is False
    assert sheet.approval == ApprovalState.PENDING


def test_revoke_approval_clears_fields() -> None:
    sheet = _approved()
    revoke_approval(sheet, note="test revoke")
    assert sheet.approval == ApprovalState.PENDING
    assert sheet.approved_at is None
    assert any("test revoke" in w for w in sheet.validation_warnings)


def test_track_edit_invalidates() -> None:
    sheet = _approved()
    fp = compute_approval_fingerprint(sheet)
    sheet.tracks[0].title = "Titre modifié"
    still, _ = sync_approval_with_fingerprint(sheet, fp)
    assert still is False


def test_first_release_date_change_invalidates() -> None:
    sheet = _approved()
    fp = compute_approval_fingerprint(sheet)
    sheet.edition.first_release_date = "2002"
    still, _ = sync_approval_with_fingerprint(sheet, fp)
    assert still is False
    assert sheet.approval == ApprovalState.PENDING


def test_unknown_year_justification_change_invalidates() -> None:
    sheet = _approved()
    fp = compute_approval_fingerprint(sheet)
    sheet.edition.year = None
    sheet.edition.year_unavailable_justification = "Date d'édition absente des sources"
    still, _ = sync_approval_with_fingerprint(sheet, fp)
    assert still is False
    assert sheet.approval == ApprovalState.PENDING
