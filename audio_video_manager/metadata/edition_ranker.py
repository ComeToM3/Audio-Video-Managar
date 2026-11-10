"""Classement intelligent des éditions MusicBrainz — sans invention ni auto-approve."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Sequence

from audio_video_manager.metadata.musicbrainz_client import ReleaseCandidate

# Écart durée TOC vs MB considéré mineur (cas Queen piste 17 ≈ 3,3 s)
MINOR_DURATION_MS = 5000
# Au-delà : significatif ; si beaucoup de pistes → bloquant
SIGNIFICANT_DURATION_MS = 15000


class DiffSeverity(str, Enum):
    MINOR = "minor"
    SIGNIFICANT = "significant"
    BLOCKING = "blocking"


@dataclass(frozen=True)
class EditionDiff:
    code: str
    severity: DiffSeverity
    message: str


@dataclass
class RankedEdition:
    candidate: ReleaseCandidate
    toc_blocking: bool
    toc_diffs: list[EditionDiff] = field(default_factory=list)
    # score plus bas = meilleur (pénalités)
    score: int = 0
    reasons: list[str] = field(default_factory=list)


@dataclass
class SelectionDecision:
    """Décision de sélection — jamais une preuve de provenance physique."""

    selected: ReleaseCandidate | None
    auto_selected: bool
    require_manual_choice: bool
    preferred_country: str
    ranked: list[RankedEdition]
    pairwise_diffs: list[EditionDiff]
    summary: str
    warnings: list[str] = field(default_factory=list)
    # Préparé pour futur auto-approve haute confiance (toujours False ici)
    high_confidence_for_future_auto_approve: bool = False


def _norm(s: str | None) -> str:
    return " ".join((s or "").casefold().split())


def _country_norm(c: str | None) -> str:
    return (c or "").strip().upper()


def evaluate_candidate_vs_toc(candidate: ReleaseCandidate) -> RankedEdition:
    """Évalue un candidat seul contre sa comparaison TOC déjà calculée."""
    diffs: list[EditionDiff] = []
    blocking = False
    score = 0
    reasons: list[str] = []

    toc = candidate.toc_match or "unknown"
    if toc == "mismatch":
        # Compter notes de durée / count
        count_mismatch = any("Nombre de pistes" in n for n in candidate.score_notes)
        if count_mismatch:
            blocking = True
            diffs.append(
                EditionDiff(
                    "toc_track_count",
                    DiffSeverity.BLOCKING,
                    candidate.score_notes[0]
                    if candidate.score_notes
                    else "Nombre de pistes TOC ≠ medium",
                )
            )
            score += 1000
        else:
            # Toutes les pistes hors tolérance stricte MB
            n_notes = len(candidate.score_notes)
            if n_notes >= max(3, (len(candidate.track_titles) or 1) // 2):
                blocking = True
                diffs.append(
                    EditionDiff(
                        "toc_many_mismatches",
                        DiffSeverity.BLOCKING,
                        f"TOC mismatch sur {n_notes} piste(s)",
                    )
                )
                score += 800
            else:
                diffs.append(
                    EditionDiff(
                        "toc_mismatch",
                        DiffSeverity.SIGNIFICANT,
                        "; ".join(candidate.score_notes[:3]) or "TOC mismatch",
                    )
                )
                score += 200
                reasons.append("toc_match=mismatch")
    elif toc == "partial":
        for note in candidate.score_notes:
            # Extraire écart si possible
            sev = DiffSeverity.MINOR
            score_add = 5
            if "vs MB" in note:
                try:
                    # "Piste 17: TOC 262000 ms vs MB 258733 ms"
                    parts = note.replace("ms", "").split()
                    nums = [int(x) for x in parts if x.isdigit()]
                    if len(nums) >= 2:
                        delta = abs(nums[-2] - nums[-1])
                        if delta > SIGNIFICANT_DURATION_MS:
                            sev = DiffSeverity.SIGNIFICANT
                            score_add = 40
                        elif delta > MINOR_DURATION_MS:
                            sev = DiffSeverity.SIGNIFICANT
                            score_add = 25
                        else:
                            sev = DiffSeverity.MINOR
                            score_add = 5
                except ValueError:
                    pass
            diffs.append(EditionDiff("toc_partial", sev, note))
            score += score_add
            if sev == DiffSeverity.SIGNIFICANT:
                reasons.append(f"écart durée significatif: {note}")
            else:
                reasons.append(f"écart durée mineur: {note}")
    elif toc == "exact":
        reasons.append("toc_match=exact")
    else:
        diffs.append(
            EditionDiff(
                "toc_unknown",
                DiffSeverity.MINOR,
                "Correspondance TOC non évaluée",
            )
        )
        score += 15

    if not candidate.track_titles:
        diffs.append(
            EditionDiff(
                "no_tracks",
                DiffSeverity.SIGNIFICANT,
                "Pas de titres de pistes MusicBrainz",
            )
        )
        score += 50

    return RankedEdition(
        candidate=candidate,
        toc_blocking=blocking,
        toc_diffs=diffs,
        score=score,
        reasons=reasons,
    )


def compare_editions(
    a: ReleaseCandidate,
    b: ReleaseCandidate,
) -> list[EditionDiff]:
    """Différences entre deux éditions candidates (pas inventées)."""
    diffs: list[EditionDiff] = []

    if len(a.track_titles) != len(b.track_titles):
        diffs.append(
            EditionDiff(
                "track_count",
                DiffSeverity.BLOCKING,
                f"Nombre de pistes {len(a.track_titles)} vs {len(b.track_titles)}",
            )
        )
        return diffs

    title_mismatches = 0
    for i, (ta, tb) in enumerate(zip(a.track_titles, b.track_titles), start=1):
        if _norm(ta) != _norm(tb):
            title_mismatches += 1
            diffs.append(
                EditionDiff(
                    "track_title",
                    DiffSeverity.BLOCKING
                    if title_mismatches >= 2
                    else DiffSeverity.SIGNIFICANT,
                    f"Piste {i}: « {ta} » vs « {tb} »",
                )
            )

    if _norm(a.title) != _norm(b.title):
        diffs.append(
            EditionDiff(
                "album_title",
                DiffSeverity.SIGNIFICANT,
                f"Titre album: « {a.title} » vs « {b.title} »",
            )
        )

    if _norm(a.artist_credit) != _norm(b.artist_credit):
        diffs.append(
            EditionDiff(
                "album_artist",
                DiffSeverity.SIGNIFICANT,
                f"Artiste: « {a.artist_credit} » vs « {b.artist_credit} »",
            )
        )

    # Durées entre éditions
    for i, (da, db) in enumerate(
        zip(a.track_durations_ms, b.track_durations_ms), start=1
    ):
        if da is None or db is None:
            continue
        delta = abs(da - db)
        if delta > SIGNIFICANT_DURATION_MS:
            diffs.append(
                EditionDiff(
                    "duration_between",
                    DiffSeverity.SIGNIFICANT,
                    f"Piste {i}: durées éditions Δ={delta} ms",
                )
            )
        elif delta > MINOR_DURATION_MS:
            diffs.append(
                EditionDiff(
                    "duration_between",
                    DiffSeverity.MINOR,
                    f"Piste {i}: durées éditions Δ={delta} ms",
                )
            )

    if _country_norm(a.country) != _country_norm(b.country):
        diffs.append(
            EditionDiff(
                "country",
                DiffSeverity.MINOR,
                f"Pays: {a.country or '?'} vs {b.country or '?'}",
            )
        )
    if (a.year or 0) != (b.year or 0):
        diffs.append(
            EditionDiff(
                "year",
                DiffSeverity.MINOR,
                f"Année: {a.year} vs {b.year}",
            )
        )
    cats_a = sorted(_norm(x) for x in a.catalog_numbers)
    cats_b = sorted(_norm(x) for x in b.catalog_numbers)
    if cats_a != cats_b:
        diffs.append(
            EditionDiff(
                "catalog",
                DiffSeverity.MINOR,
                f"Catalogue: {a.catalog_numbers} vs {b.catalog_numbers}",
            )
        )
    labs_a = sorted(_norm(x) for x in a.labels)
    labs_b = sorted(_norm(x) for x in b.labels)
    if labs_a != labs_b:
        diffs.append(
            EditionDiff(
                "label",
                DiffSeverity.MINOR,
                f"Label: {a.labels} vs {b.labels}",
            )
        )
    if (a.barcode or "") != (b.barcode or "") and (a.barcode or b.barcode):
        # Même œuvre, barcode différent = souvent édition distincte mais pas bloquant seul
        diffs.append(
            EditionDiff(
                "barcode",
                DiffSeverity.MINOR,
                f"Code-barres: {a.barcode} vs {b.barcode}",
            )
        )
    if (a.disambiguation or "") != (b.disambiguation or "") and (
        a.disambiguation or b.disambiguation
    ):
        diffs.append(
            EditionDiff(
                "disambiguation",
                DiffSeverity.MINOR,
                f"Disambiguation: {a.disambiguation!r} vs {b.disambiguation!r}",
            )
        )

    # Upgrade: un seul titre de piste différent reste significant; ≥2 → déjà blocking
    if title_mismatches == 1:
        # ensure at least significant present
        pass
    elif title_mismatches >= 2:
        # mark overall — already per-track blocking
        pass

    return diffs


def editions_musically_equivalent(diffs: Sequence[EditionDiff]) -> bool:
    """Équivalence musicale = aucun écart bloquant ni significatif sur le contenu."""
    for d in diffs:
        if d.severity == DiffSeverity.BLOCKING:
            return False
        if d.severity == DiffSeverity.SIGNIFICANT and d.code in (
            "track_title",
            "album_title",
            "album_artist",
            "track_count",
            "duration_between",
            "toc_mismatch",
            "toc_many_mismatches",
            "toc_track_count",
        ):
            return False
    return True


def rank_and_select_releases(
    candidates: Sequence[ReleaseCandidate],
    *,
    preferred_country: str = "CA",
) -> SelectionDecision:
    """
    Classe et éventuellement sélectionne une édition.

    ``preferred_country`` est un **départage**, jamais une preuve que le disque
    physique a été pressé dans ce pays.
    """
    pref = _country_norm(preferred_country) or "CA"
    ranked = [evaluate_candidate_vs_toc(c) for c in candidates]
    # Pénalité pays hors préférence (faible — départage seulement)
    for r in ranked:
        cc = _country_norm(r.candidate.country)
        if cc and cc != pref:
            r.score += 3
            r.reasons.append(f"pays {cc} ≠ préférence {pref} (départage)")
        elif cc == pref:
            r.reasons.append(f"pays {cc} = préférence (départage)")
        if not r.candidate.catalog_numbers:
            r.score += 2
        if not r.candidate.labels:
            r.score += 1

    ranked.sort(key=lambda r: (r.toc_blocking, r.score, r.candidate.release_id))

    pairwise: list[EditionDiff] = []
    warnings: list[str] = []

    if not ranked:
        return SelectionDecision(
            selected=None,
            auto_selected=False,
            require_manual_choice=False,
            preferred_country=pref,
            ranked=[],
            pairwise_diffs=[],
            summary="Aucun candidat à classer.",
            warnings=[],
            high_confidence_for_future_auto_approve=False,
        )

    if len(ranked) == 1:
        only = ranked[0]
        if only.toc_blocking:
            return SelectionDecision(
                selected=None,
                auto_selected=False,
                require_manual_choice=True,
                preferred_country=pref,
                ranked=ranked,
                pairwise_diffs=[],
                summary="Candidat unique mais écarts TOC bloquants — choix / correction manuelle.",
                warnings=[d.message for d in only.toc_diffs if d.severity == DiffSeverity.BLOCKING],
                high_confidence_for_future_auto_approve=False,
            )
        warns = [d.message for d in only.toc_diffs if d.severity != DiffSeverity.BLOCKING]
        return SelectionDecision(
            selected=only.candidate,
            auto_selected=True,
            require_manual_choice=False,
            preferred_country=pref,
            ranked=ranked,
            pairwise_diffs=[],
            summary="Édition unique sélectionnée automatiquement (vérifier puis Approuver).",
            warnings=warns,
            high_confidence_for_future_auto_approve=only.candidate.toc_match == "exact"
            and not warns,
        )

    # Multi : comparer tous les non-bloquants TOC
    viable = [r for r in ranked if not r.toc_blocking]
    if not viable:
        return SelectionDecision(
            selected=None,
            auto_selected=False,
            require_manual_choice=True,
            preferred_country=pref,
            ranked=ranked,
            pairwise_diffs=[],
            summary="Tous les candidats ont des écarts TOC bloquants — sélection manuelle.",
            warnings=["Écarts TOC bloquants sur tous les candidats."],
            high_confidence_for_future_auto_approve=False,
        )

    if len(viable) == 1:
        only = viable[0]
        warns = [d.message for d in only.toc_diffs]
        warns.append(
            f"{len(ranked) - 1} autre(s) candidat(s) écarté(s) (TOC bloquant)."
        )
        return SelectionDecision(
            selected=only.candidate,
            auto_selected=True,
            require_manual_choice=False,
            preferred_country=pref,
            ranked=ranked,
            pairwise_diffs=[],
            summary=(
                "Un seul candidat viable après filtrage TOC — sélection automatique. "
                "Vérifier puis Approuver."
            ),
            warnings=warns,
            high_confidence_for_future_auto_approve=only.candidate.toc_match == "exact",
        )

    # Pairwise among viable
    all_equiv = True
    for i in range(len(viable)):
        for j in range(i + 1, len(viable)):
            diffs = compare_editions(viable[i].candidate, viable[j].candidate)
            pairwise.extend(diffs)
            if not editions_musically_equivalent(diffs):
                all_equiv = False

    if all_equiv and len(viable) >= 2:
        # Preférer pays
        pref_hits = [r for r in viable if _country_norm(r.candidate.country) == pref]
        chosen_rank = pref_hits[0] if pref_hits else viable[0]
        # warnings: TOC + diffs mineurs entre éditions
        for d in chosen_rank.toc_diffs:
            warnings.append(d.message)
        for d in pairwise:
            if d.severity == DiffSeverity.MINOR:
                warnings.append(d.message)
        others = [
            f"{r.candidate.country or '?'}/{r.candidate.year or '?'} "
            f"({r.candidate.catalog_numbers[0] if r.candidate.catalog_numbers else r.candidate.release_id[:8]})"
            for r in viable
            if r.candidate.release_id != chosen_rank.candidate.release_id
        ]
        summary = (
            f"Éditions musicalement équivalentes — sélection auto "
            f"{chosen_rank.candidate.country or '?'} {chosen_rank.candidate.year or ''} "
            f"(préférence pays={pref} comme départage, pas comme provenance). "
            f"Alternatives: {', '.join(others) if others else 'aucune'}."
        )
        return SelectionDecision(
            selected=chosen_rank.candidate,
            auto_selected=True,
            require_manual_choice=False,
            preferred_country=pref,
            ranked=ranked,
            pairwise_diffs=pairwise,
            summary=summary,
            warnings=warnings,
            # TOC partial → pas haute confiance pour futur auto-approve
            high_confidence_for_future_auto_approve=(
                chosen_rank.candidate.toc_match == "exact"
                and not any(
                    d.severity != DiffSeverity.MINOR for d in chosen_rank.toc_diffs
                )
            ),
        )

    # Non équivalents: proposer le meilleur candidat viable, sans auto-approbation.
    # L'utilisateur garde le choix des alternatives et doit approuver la fiche.
    sig = [
        d.message
        for d in pairwise
        if d.severity in (DiffSeverity.SIGNIFICANT, DiffSeverity.BLOCKING)
    ]
    return SelectionDecision(
        selected=viable[0].candidate,
        auto_selected=False,
        require_manual_choice=True,
        preferred_country=pref,
        ranked=ranked,
        pairwise_diffs=pairwise,
        summary=(
            f"{len(viable)} éditions non équivalentes — proposition la mieux classée présélectionnée; "
            "vérifiez-la ou choisissez une autre édition avant d’approuver."
        ),
        warnings=sig or [d.message for d in pairwise[:6]],
        high_confidence_for_future_auto_approve=False,
    )
