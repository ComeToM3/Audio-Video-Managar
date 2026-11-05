"""Intégrité FLAC (F-08a) — sans mutagen : magic + STREAMINFO minimal."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FlacStreamInfo:
    sample_rate_hz: int
    channels: int
    bits_per_sample: int
    total_samples: int

    @property
    def duration_sec(self) -> float | None:
        if self.sample_rate_hz <= 0 or self.total_samples <= 0:
            return None
        return self.total_samples / self.sample_rate_hz


@dataclass(frozen=True)
class FlacIntegrityResult:
    path: Path
    ok: bool
    size_bytes: int
    message: str
    streaminfo: FlacStreamInfo | None = None


def _read_streaminfo(data: bytes) -> FlacStreamInfo | None:
    """Parse le premier bloc STREAMINFO s'il est en tête (cas standard)."""
    if len(data) < 4 + 4 + 34:
        return None
    if data[0:4] != b"fLaC":
        return None
    header = data[4:8]
    block_type = header[0] & 0x7F
    length = int.from_bytes(header[1:4], "big")
    if block_type != 0 or length < 34:
        return None
    payload = data[8 : 8 + length]
    if len(payload) < 34:
        return None
    # STREAMINFO layout (RFC / FLAC):
    # min/max block (2+2), min/max frame (3+3), then 64-bit packed fields…
    packed = int.from_bytes(payload[10:18], "big")
    sample_rate = (packed >> 44) & 0xFFFFF
    channels = ((packed >> 41) & 0x7) + 1
    bits = ((packed >> 36) & 0x1F) + 1
    total_samples = packed & 0xFFFFFFFFF
    return FlacStreamInfo(
        sample_rate_hz=sample_rate,
        channels=channels,
        bits_per_sample=bits,
        total_samples=total_samples,
    )


def check_flac_integrity(path: Path) -> FlacIntegrityResult:
    """
    Vérifie qu'un fichier ressemble à un FLAC décodable au niveau structure.

    Ce n'est **pas** une vérification AccurateRip / qualité de rip (F-08b).
    """
    p = Path(path)
    if not p.is_file():
        return FlacIntegrityResult(p, False, 0, "fichier absent")
    size = p.stat().st_size
    if size < 42:
        return FlacIntegrityResult(p, False, size, "fichier trop petit pour un FLAC")

    try:
        with p.open("rb") as fh:
            head = fh.read(1024)
    except OSError as exc:
        return FlacIntegrityResult(p, False, size, f"lecture impossible : {exc}")

    if not head.startswith(b"fLaC"):
        return FlacIntegrityResult(p, False, size, "magic fLaC absent")

    info = _read_streaminfo(head)
    if info is None:
        return FlacIntegrityResult(
            p,
            True,
            size,
            "magic OK ; STREAMINFO non lu en tête (structure atypique) — intégrité partielle",
            None,
        )

    if info.sample_rate_hz <= 0 or info.channels <= 0 or info.bits_per_sample <= 0:
        return FlacIntegrityResult(p, False, size, "STREAMINFO incohérent", info)

    return FlacIntegrityResult(
        p,
        True,
        size,
        (
            f"FLAC OK — {info.sample_rate_hz} Hz, {info.channels} ch, "
            f"{info.bits_per_sample} bit"
            + (
                f", ~{info.duration_sec:.1f}s"
                if info.duration_sec is not None
                else ""
            )
        ),
        info,
    )


def check_many(paths: list[Path]) -> list[FlacIntegrityResult]:
    return [check_flac_integrity(p) for p in paths]
