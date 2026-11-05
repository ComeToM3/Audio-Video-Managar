from pathlib import Path

from audio_video_manager.verification.flac_integrity import check_flac_integrity
from audio_video_manager.verification.rip_check import evaluate_rip_check
from tests.flac_fixtures import write_minimal_flac


def test_rip_check_weak_ok_does_not_claim_perfect(tmp_path: Path) -> None:
    path = write_minimal_flac(tmp_path / "t.flac")
    integrity = [check_flac_integrity(path)]
    result = evaluate_rip_check(integrity, rip_success=True, cancelled=False)
    assert result.status == "weak_ok"
    assert "AccurateRip" in result.summary or "pas d'AccurateRip" in result.summary.lower() or "non disponible" in result.summary
    assert "parfait" in result.summary.lower() or "≠" in result.summary or "pas" in result.summary.lower()


def test_rip_check_failed_on_cancel() -> None:
    result = evaluate_rip_check([], rip_success=False, cancelled=True)
    assert result.status == "failed"
