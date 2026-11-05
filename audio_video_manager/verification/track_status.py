"""Statuts de vérification piste pour catalogue SQLite (AVM-10D) — aucun succès fictif."""

from __future__ import annotations

from dataclasses import dataclass

from audio_video_manager.verification.flac_decode import FlacDecodeResult
from audio_video_manager.verification.flac_integrity import FlacIntegrityResult
from audio_video_manager.verification.rip_check import RipCheckResult


@dataclass(frozen=True)
class TrackVerificationStatus:
    """
    Champs catalogue honnêtes.

    - ``flac_ok`` : 1 = structure F-08a OK ; 0 = échec ; None = non exécuté
    - ``rip_check_status`` : statut F-08b + suffixe decode (jamais « ok » si non tenté)
    """

    flac_ok: int | None
    rip_check_status: str


def decode_tag(decode: FlacDecodeResult | None) -> str:
    if decode is None:
        return "decode=not_run"
    if not decode.attempted:
        return "decode=not_run"
    return "decode=ok" if decode.ok else "decode=failed"


def compose_rip_check_status(
    rip: RipCheckResult | None,
    decode: FlacDecodeResult | None,
) -> str:
    base = rip.status if rip is not None else "not_run"
    return f"{base};{decode_tag(decode)}"


def track_verification_status(
    integrity: FlacIntegrityResult | None,
    decode: FlacDecodeResult | None,
    rip: RipCheckResult | None,
) -> TrackVerificationStatus:
    if integrity is None:
        flac_ok: int | None = None
    else:
        flac_ok = 1 if integrity.ok else 0
    return TrackVerificationStatus(
        flac_ok=flac_ok,
        rip_check_status=compose_rip_check_status(rip, decode),
    )
