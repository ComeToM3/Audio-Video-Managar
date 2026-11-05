"""Construit un FLAC minimal valide (en-tête uniquement) pour les tests."""

from __future__ import annotations

from pathlib import Path


def write_minimal_flac(
    path: Path,
    *,
    sample_rate: int = 44100,
    channels: int = 2,
    bits: int = 16,
    total_samples: int = 44100,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    # STREAMINFO 34 bytes
    streaminfo = bytearray(34)
    streaminfo[0:2] = (4096).to_bytes(2, "big")
    streaminfo[2:4] = (4096).to_bytes(2, "big")
    # frame sizes 0 = unknown
    packed = (
        (sample_rate << 44)
        | ((channels - 1) << 41)
        | ((bits - 1) << 36)
        | (total_samples & 0xFFFFFFFFF)
    )
    streaminfo[10:18] = packed.to_bytes(8, "big")
    # MD5 left zero

    # last-metadata-block flag + type 0
    header0 = 0x80 | 0x00
    length = (34).to_bytes(3, "big")
    data = b"fLaC" + bytes([header0]) + length + bytes(streaminfo)
    # pad so file is not tiny-only edge
    data += b"\x00" * 8
    path.write_bytes(data)
    return path
