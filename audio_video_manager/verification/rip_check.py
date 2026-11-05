"""Vérification du rip (F-08b) — contrôles faibles uniquement en phase 1."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from audio_video_manager.verification.flac_integrity import FlacIntegrityResult


@dataclass(frozen=True)
class RipCheckResult:
    """
    Ne constitue **pas** une preuve AccurateRip / rip parfait.

    Phase 1 : présence de fichiers, intégrité FLAC, cohérence basique CD Red Book
    si STREAMINFO lisible (44.1 kHz / 16-bit typiques).
    """

    status: str  # unavailable | weak_ok | weak_warn | failed
    summary: str
    expected_cd_pcm: bool | None = None


def evaluate_rip_check(
    integrity_results: list[FlacIntegrityResult],
    *,
    rip_success: bool,
    cancelled: bool,
) -> RipCheckResult:
    if cancelled:
        return RipCheckResult(
            status="failed",
            summary="Rip annulé — vérification rip non applicable.",
        )
    if not integrity_results:
        return RipCheckResult(
            status="failed",
            summary="Aucun fichier FLAC à évaluer (F-08b faible impossible).",
        )

    all_ok = all(r.ok for r in integrity_results)
    if not all_ok or not rip_success:
        return RipCheckResult(
            status="failed",
            summary=(
                "Contrôle rip faible : échec — fichiers manquants, intégrité FLAC "
                "en échec, ou freaccmd non réussi. "
                "Ce n'est pas un diagnostic AccurateRip."
            ),
        )

    cd_like = []
    for r in integrity_results:
        info = r.streaminfo
        if info is None:
            cd_like.append(None)
            continue
        cd_like.append(
            info.sample_rate_hz == 44100
            and info.bits_per_sample == 16
            and info.channels in (1, 2)
        )

    if any(x is False for x in cd_like):
        return RipCheckResult(
            status="weak_warn",
            summary=(
                f"{len(integrity_results)} piste(s) FLAC intègres, mais caractéristiques "
                "hors profil CD Red Book typique (44.1 kHz / 16-bit). "
                "AccurateRip non exécuté — ne pas conclure à un rip parfait."
            ),
            expected_cd_pcm=False,
        )

    if any(x is None for x in cd_like):
        return RipCheckResult(
            status="weak_ok",
            summary=(
                f"{len(integrity_results)} piste(s) avec intégrité FLAC OK. "
                "STREAMINFO incomplet sur certaines pistes. "
                "AccurateRip / preuve de rip sans erreur : non disponible (phase 1)."
            ),
            expected_cd_pcm=None,
        )

    return RipCheckResult(
        status="weak_ok",
        summary=(
            f"{len(integrity_results)} piste(s) FLAC intègres, profil PCM CD typique "
            "(44.1 kHz / 16-bit). "
            "Attention : intégrité fichier ≠ rip vérifié (pas d'AccurateRip en phase 1)."
        ),
        expected_cd_pcm=True,
    )
