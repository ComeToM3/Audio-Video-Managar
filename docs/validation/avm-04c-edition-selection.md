# Rapport de validation — AVM-04C

**Date :** 2026-11-03  
**Version :** 0.4.1  
**Objectif :** sélection intelligente d’éditions MusicBrainz (préférence pays = départage).

---

## Verdict

**GO** — cas Queen *Greatest Hits* : auto-sélection **CA 1992** (`CD 61265`), avertissement TOC piste 17 conservé (`partial`, non forcé en `exact`), **aucune auto-approbation**.

---

## Décision produit (D-015)

| Élément | Règle |
|---------|--------|
| `preferred_release_country` | Défaut **`CA`** — critère de **départage** uniquement |
| Provenance | Le pays préféré **n’est pas** une preuve que le pressage est canadien |
| Auto-sélection édition | Si équivalence musicale + critères suffisants |
| Auto-approbation fiche | **Interdite** cette version ; `auto_approve_high_confidence=False` (UI grisée) |
| Divergences pistes / TOC bloquantes | **Jamais** ignorées → sélection manuelle |

---

## Classement des écarts

| Sévérité | Exemples |
|----------|----------|
| **minor** | Pays, année, catalogue, label, barcode ; durée TOC Δ ≤ 5 s |
| **significant** | Titre album/artiste différent ; une piste au titre différent ; durées Δ > 5–15 s |
| **blocking** | Nombre de pistes ; ≥2 titres de pistes différents ; TOC count mismatch / nombreux mismatches |

Équivalence musicale = aucun écart `blocking` ni `significant` sur le contenu (titres / artistes / count / durées inter-éditions significatives).

---

## Cas de référence (simulé = données AVM-04B)

| Candidat | Pays | Année | Catalogue | toc_match |
|----------|------|-------|-----------|-----------|
| Hollywood US | US | 1991 | HR 61265-2 | partial (piste 17) |
| Hollywood CA | CA | 1992 | CD 61265 | partial (piste 17) |

**Résultat attendu / obtenu :** sélection **CA** ; warnings incluent `Piste 17: TOC 262000 ms vs MB 258733 ms` ; `toc_match` reste `partial`.

---

## Livrables code

| Fichier | Rôle |
|---------|------|
| `metadata/edition_ranker.py` | Diffs, équivalence, `rank_and_select_releases` |
| `metadata/apply_lookup.py` | `identify_disc` → 4-tuple + smart apply |
| `config.py` | `preferred_release_country`, `auto_approve_high_confidence` |
| UI | Préférence pays ; résumé sélection ; case auto-approve désactivée |

---

## Tests

| Suite | Contenu |
|-------|---------|
| `tests/test_edition_ranker.py` | Queen CA/US, préférence US, titres différents, TOC bloquant, identify Pending |
| Régression identify | 4-tuple, multi non-équivalent → manuel |

**pytest :** **62 passed** (2026-11-03).

---

## Limitations

- Préférence pays n’identifie pas le pressage réel ; l’utilisateur peut encore changer d’édition dans la combo.
- `high_confidence_for_future_auto_approve` est calculé mais **jamais** appliqué à `approval`.
- Équivalence basée sur titres/durées/métadonnées MB disponibles — pas sur l’audio rippé.
