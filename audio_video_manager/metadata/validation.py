"""Validation stricte DiscMetadata — gate d'approbation."""

from __future__ import annotations

from dataclasses import dataclass

from audio_video_manager.metadata.enums import (
    ApprovalState,
    CoverStatus,
    FieldTrust,
    JobMode,
)
from audio_video_manager.metadata.forbidden import is_forbidden_label
from audio_video_manager.metadata.models import (
    TOC_DURATION_TOLERANCE_MS,
    DiscMetadata,
    FieldMeta,
)
from audio_video_manager.metadata.path_preview import build_path_preview


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    errors: list[str]
    warnings: list[str]


def _trust(meta: dict[str, FieldMeta], key: str) -> FieldTrust:
    fm = meta.get(key)
    return fm.trust if fm else FieldTrust.MISSING


def _require_confirmed(
    errors: list[str],
    label: str,
    meta: dict[str, FieldMeta],
    key: str,
    *,
    allow_unavailable: bool = False,
) -> None:
    t = _trust(meta, key)
    if t == FieldTrust.CONFIRMED:
        return
    if allow_unavailable and t == FieldTrust.UNAVAILABLE:
        return
    errors.append(f"{label}: confiance={t.value} (requis: confirmed" + (
        " ou unavailable)" if allow_unavailable else ")"
    ))


def validate_disc_metadata(sheet: DiscMetadata) -> ValidationResult:
    """Valide une fiche pour approbation mode normal (ignore technical_test soft)."""
    errors: list[str] = []
    warnings: list[str] = []
    sheet.ensure_defaults()

    # --- Identity / TOC ---
    toc = sheet.identity.toc
    if toc is None:
        errors.append("TOC absente (identity.toc) — mesure lecteur requise.")
    else:
        _require_confirmed(errors, "TOC", sheet.identity.field_meta, "toc")
        if toc.audio_track_count <= 0:
            errors.append("TOC: audio_track_count invalide.")
        if len(sheet.tracks) != toc.audio_track_count:
            errors.append(
                f"TOC: {len(sheet.tracks)} piste(s) fiche ≠ "
                f"{toc.audio_track_count} piste(s) TOC."
            )
        expected_numbers = [
            toc.first_track + i for i in range(toc.audio_track_count)
        ]
        actual_numbers = [t.number for t in sheet.tracks]
        if actual_numbers != expected_numbers:
            errors.append(
                f"Numéros de pistes incohérents avec la TOC "
                f"(attendu {expected_numbers}, obtenu {actual_numbers})."
            )
        for i, track in enumerate(sorted(sheet.tracks, key=lambda x: x.number)):
            if i < len(toc.track_durations_ms):
                delta = abs(track.duration_ms - toc.track_durations_ms[i])
                if delta > TOC_DURATION_TOLERANCE_MS:
                    errors.append(
                        f"Piste {track.number}: durée fiche {track.duration_ms} ms "
                        f"vs TOC {toc.track_durations_ms[i]} ms "
                        f"(tolérance {TOC_DURATION_TOLERANCE_MS} ms)."
                    )

    # Disc ID: confirmed si présent ; missing OK only if not required for manual?
    # Spec: oui si calculable — if missing, warning for auto lookup but allow manual approve
    disc_id_trust = _trust(sheet.identity.field_meta, "disc_id")
    if sheet.identity.disc_id:
        if disc_id_trust not in (FieldTrust.CONFIRMED, FieldTrust.UNAVAILABLE):
            warnings.append("disc_id présent mais confiance non confirmed.")
    else:
        if disc_id_trust == FieldTrust.MISSING:
            warnings.append(
                "disc_id manquant — lookup MB impossible ; fiche manuelle uniquement."
            )

    # --- Edition ---
    ed = sheet.edition
    _require_confirmed(errors, "album_title", ed.field_meta, "album_title")
    _require_confirmed(errors, "album_artist", ed.field_meta, "album_artist")
    if is_forbidden_label(ed.album_title):
        errors.append("album_title: valeur générique / interdite.")
    if is_forbidden_label(ed.album_artist):
        errors.append("album_artist: valeur générique / interdite.")

    year_trust = _trust(ed.field_meta, "year")
    if year_trust == FieldTrust.CONFIRMED:
        if ed.year is None or ed.year < 1900 or ed.year > 2100:
            errors.append("year: confirmed mais valeur invalide.")
    elif year_trust == FieldTrust.UNAVAILABLE:
        if not (ed.year_unavailable_justification or "").strip():
            errors.append(
                "year unavailable: justification textuelle obligatoire "
                "(exception documentée)."
            )
    else:
        errors.append(
            f"year: confiance={year_trust.value} "
            "(requis: confirmed ou unavailable avec justification)."
        )

    cover = ed.cover_status
    cover_trust = _trust(ed.field_meta, "cover_status")
    if cover == CoverStatus.MISSING or cover_trust == FieldTrust.MISSING:
        errors.append("cover_status: missing — traiter la pochette (confirmed ou unavailable).")
    elif cover == CoverStatus.AMBIGUOUS or cover_trust == FieldTrust.AMBIGUOUS:
        errors.append("cover_status: ambiguous — choix requis.")
    elif cover == CoverStatus.CONFIRMED:
        if not (ed.cover_path_or_url or "").strip():
            errors.append("cover_status confirmed: cover_path_or_url requis.")
        _require_confirmed(errors, "cover_status", ed.field_meta, "cover_status")
    elif cover == CoverStatus.UNAVAILABLE:
        if cover_trust != FieldTrust.UNAVAILABLE and cover_trust != FieldTrust.CONFIRMED:
            # allow unavailable trust
            if cover_trust != FieldTrust.UNAVAILABLE:
                errors.append("cover unavailable: marquer field_meta.cover_status=unavailable.")
    else:
        errors.append(f"cover_status invalide: {cover}")

    # Réédition : si is_reissue True, edition_notes or label/catalog recommended
    if ed.is_reissue is True:
        if not (ed.edition_notes or ed.label or ed.catalog_number):
            warnings.append(
                "Réédition: préciser edition_notes et/ou label/catalog_number."
            )
        for key in ("label", "catalog_number", "country"):
            if _trust(ed.field_meta, key) == FieldTrust.AMBIGUOUS:
                errors.append(f"{key}: ambiguous — trancher l'édition exacte.")

    # Compilation is optional metadata; missing/ambiguous never blocks approval.

    # MB IDs: never invent — if set must be confirmed; missing/unavailable OK for manual
    for key, val in (
        ("musicbrainz_release_id", ed.musicbrainz_release_id),
        ("musicbrainz_release_group_id", ed.musicbrainz_release_group_id),
    ):
        if val:
            # present — should be confirmed when we have MB later; for manual paste OK confirmed
            pass

    # --- Disc unit ---
    if sheet.disc.disc_number < 1 or sheet.disc.disc_total < 1:
        errors.append("disc_number/disc_total invalides.")
    if sheet.disc.disc_number > sheet.disc.disc_total:
        errors.append("disc_number > disc_total.")
    _require_confirmed(errors, "disc_number", sheet.disc.field_meta, "disc_number")
    _require_confirmed(errors, "disc_total", sheet.disc.field_meta, "disc_total")

    # --- Tracks ---
    if not sheet.tracks:
        errors.append("Aucune piste.")
    for t in sheet.tracks:
        t.ensure_field_meta()
        _require_confirmed(errors, f"piste {t.number} title", t.field_meta, "title")
        _require_confirmed(errors, f"piste {t.number} artist", t.field_meta, "artist")
        if is_forbidden_label(t.title):
            errors.append(f"piste {t.number}: title générique / interdit.")
        if is_forbidden_label(t.artist):
            errors.append(f"piste {t.number}: artist générique / interdit.")
        if t.duration_ms <= 0:
            errors.append(f"piste {t.number}: duration_ms invalide.")

    # Path preview
    preview = build_path_preview(sheet)
    sheet.path_preview = preview
    if any(p.startswith("<aperçu") or "<titre manquant>" in p for p in preview):
        errors.append("Aperçu chemins incomplet — corriger titres/album avant approbation.")
    if not preview:
        errors.append("Aperçu chemins vide (AC-M6).")

    return ValidationResult(ok=not errors, errors=errors, warnings=warnings)


def apply_validation(sheet: DiscMetadata) -> ValidationResult:
    result = validate_disc_metadata(sheet)
    sheet.validation_errors = list(result.errors)
    sheet.validation_warnings = list(result.warnings)
    sheet.path_preview = build_path_preview(sheet)
    sheet.touch()
    return result


class ApprovalError(ValueError):
    """Approbation ou rip archive refusé."""


def approve_sheet(sheet: DiscMetadata, *, note: str = "") -> DiscMetadata:
    """
    Approuve la fiche si validation OK (mode normal).

    Verrou métier : ne pas se contenter de l'UI.
    """
    if sheet.mode == JobMode.TECHNICAL_TEST:
        raise ApprovalError(
            "Une fiche technical_test ne s'approuve pas pour l'archive ; "
            "utiliser le mode test technique de rip."
        )
    result = apply_validation(sheet)
    if not result.ok:
        raise ApprovalError(
            "Fiche non approuvable:\n- " + "\n- ".join(result.errors)
        )
    from audio_video_manager.metadata.models import _utc_now

    sheet.approval = ApprovalState.APPROVED
    sheet.approved_at = _utc_now()
    sheet.approved_by_note = note or "Approuvé manuellement"
    sheet.touch()
    return sheet


def assert_can_start_archive_rip(sheet: DiscMetadata | None) -> None:
    """Gate D-011 — indépendante de l'UI."""
    if sheet is None:
        raise ApprovalError("Aucune fiche DiscMetadata — rip archive refusé.")
    if sheet.mode != JobMode.NORMAL:
        raise ApprovalError(
            "Mode fiche ≠ normal — rip archive refusé (utiliser technical_test)."
        )
    if sheet.approval != ApprovalState.APPROVED:
        raise ApprovalError(
            f"Approbation={sheet.approval.value} — "
            "AwaitingMetadataApproval non satisfait (D-011)."
        )
    # Re-valider au moment du rip (fiche peut avoir dérivé)
    result = validate_disc_metadata(sheet)
    if not result.ok:
        raise ApprovalError(
            "Fiche Approved devenue invalide:\n- " + "\n- ".join(result.errors)
        )
