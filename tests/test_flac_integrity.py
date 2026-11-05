from pathlib import Path

from audio_video_manager.verification.flac_integrity import check_flac_integrity
from tests.flac_fixtures import write_minimal_flac


def test_integrity_ok_cd_profile(tmp_path: Path) -> None:
    path = write_minimal_flac(tmp_path / "a.flac")
    result = check_flac_integrity(path)
    assert result.ok is True
    assert result.streaminfo is not None
    assert result.streaminfo.sample_rate_hz == 44100
    assert result.streaminfo.bits_per_sample == 16
    assert result.streaminfo.channels == 2


def test_integrity_rejects_non_flac(tmp_path: Path) -> None:
    path = tmp_path / "x.flac"
    path.write_bytes(b"NOTFLAC" + b"\x00" * 64)
    result = check_flac_integrity(path)
    assert result.ok is False
    assert "magic" in result.message.lower() or "fLaC" in result.message
