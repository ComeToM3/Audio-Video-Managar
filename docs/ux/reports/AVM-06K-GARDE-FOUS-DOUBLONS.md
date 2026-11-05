# Rapport AVM-06K — Détection des doublons et garde-fous d’archivage

**Date :** 2026-11-03  
**Version :** 0.5.0  
**Suite :** **159 passed** (146 préservés + 13 nouveaux `test_duplicates_06k`)  
**Arrêt :** validation explicite requise avant AVM-06L

---

## Verdict

| Critère | Résultat |
|---------|----------|
| Aucun doublon accidentel publié silencieusement | **GO** |
| Pas de fausse équivalence sur le seul titre | **GO** |
| Réarchivage volontaire possible et traçable | **GO** (`confirmed_rearchive` + `warnings_json`) |
| Contrôles domaine (indépendants de l’UI) | **GO** (`library/duplicates.py` + `run_archive_job`) |
| Messages FR contextualisés | **GO** |
| Démarrage app non bloqué par disque déjà archivé | **GO** (gate W1 advisory) |
| Schéma SQLite v4 compatible | **GO** |
| D-011…D-015 / TOC / fingerprint / Queen / jobs historiques | **Préservés** (aucune mutation FLAC / aucun rip) |
| Tests | **159 passed** |

**Recommandation : GO technique AVM-06K — attendre validation avant AVM-06L.**

---

## 1. Audit (constat avant / après)

| Zone | Avant 06K | Après 06K |
|------|-----------|-----------|
| Identifiants persistés | `releases.disc_id`, `releases.mbid` ; jobs sans `disc_id` | + `jobs.disc_id` (v4) |
| Collision | `CollisionPolicy` chemin album **à la publication** seulement | + détection catalogue **avant rip** et **avant publish** |
| Disc ID / MBID | Pas de gate pré-extraction | `assess_duplicates` / `assert_archive_allowed` |
| Similarité titre | — | `SIMILAR_META` → **WARN** uniquement |
| Concurrence | Busy UI seulement | DENY si job actif même disc/MBID |
| Réarchivage | Possible via Rename sans garde métier | Bloqué par défaut ; confirm explicite |

---

## 2. Matrice de décisions

| Signal | Fiabilité | Gate | Action |
|--------|-----------|------|--------|
| Disc ID **et** MBID identiques, dossier présent | Haute | `REQUIRE_CONFIRM` | Bloque sans `confirmed_rearchive=True` |
| Même MBID, dossier présent | Haute | `REQUIRE_CONFIRM` | Idem (même édition MB) |
| Même Disc ID, MBID différent / absent, dossier présent | Moyenne | `REQUIRE_CONFIRM` | Avertit « autre édition » — **pas d’assimilation auto** |
| Disc/MBID match, dossier **absent** | Moyenne | `WARN` | Autorise ; message « dossier introuvable » |
| Artiste+album similaires, MBID distincts | Faible | `WARN` | Jamais `REQUIRE` / jamais équivalence |
| Titre seul (sans IDs forts) | Faible | `WARN` | Idem |
| Job actif (Ripping…AwaitingPublish…) même disc/MBID | — | `DENY` | Même avec confirm réarchivage |
| Job Failed/Cancelled/… avec `workdir` présent | — | `WARN` | Pointe vers l’historique |
| Aucun hit / pas de DB | — | `ALLOW` | Passage normal |

**Règle d’or :** deux pressages / éditions MusicBrainz distincts ne sont **jamais** fusionnés automatiquement sur le titre.

---

## 3. Points de contrôle (3 gates)

| # | Moment | Couche | Comportement |
|---|--------|--------|--------------|
| 1 | Lecture TOC (W1) | UI + domaine | Advisory FR ; **n’empêche pas** de continuer ni le démarrage app |
| 2 | Approbation fiche (W3) | UI + domaine | Warning contextualisé après approve réussie |
| 3a | Avant extraction (W4) | UI | Dialog confirm « Confirmer le réarchivage » si `REQUIRE_CONFIRM` |
| 3b | Entrée `run_archive_job` | **Domaine** | `assert_archive_allowed` — filet anti-contournement UI |
| 3c | Avant `publish_album` | **Domaine** | Revalidation (exclut le `job_id` courant) |

---

## 4. Implémentation

| Fichier | Rôle |
|---------|------|
| `library/duplicates.py` | Service domaine : kinds, gates, messages FR, `assert_archive_allowed` |
| `storage/schema.py` | `SCHEMA_VERSION = 4` |
| `storage/database.py` | Migration v3→v4 : `jobs.disc_id`, indexes `idx_releases_mbid`, `idx_jobs_disc_id` |
| `orchestration/archive_job.py` | Gate début + pré-publish ; persist `disc_id` + `rearchive_confirmed=true` |
| `ui/archive_worker.py` | Propage `confirmed_rearchive` |
| `ui/wizard/archive_wizard.py` | Gates 1–3 + dialogs FR |
| `tests/test_duplicates_06k.py` | 13 scénarios |

**Non touché :** FLAC Queen, job `bd40…`, pipeline fre:ac, D-011 validation, TOC match, hardlink P1, prototypes 06J.

---

## 5. Migration SQLite

```
v3 → v4
  ALTER TABLE jobs ADD COLUMN disc_id TEXT
  CREATE INDEX IF NOT EXISTS idx_releases_mbid ON releases(mbid)
  CREATE INDEX IF NOT EXISTS idx_jobs_disc_id ON jobs(disc_id)
```

- Rétrocompatible : colonnes nullable ; jobs historiques sans `disc_id` restent lisibles.
- Détection jobs pré-v4 : si colonne absente, le service ignore le filtre disc côté jobs (MBID seul).

---

## 6. Tests couverts

| Scénario | Test |
|----------|------|
| Exact Disc+édition + confirm | `test_exact_disc_and_edition_requires_confirm` |
| Même MBID | `test_same_mbid_present_requires_confirm` |
| Éditions différentes (titre) | `test_different_editions_not_auto_equated` |
| Même Disc ID / autre MBID | `test_same_disc_different_mbid_not_merged` |
| Dossier disparu | `test_missing_folder_warns_not_blocks` |
| Titre seul | `test_title_only_never_require_confirm` |
| Job concurrent | `test_active_job_denies` |
| Exclude self job | `test_exclude_own_job_id` |
| Récupérable | `test_recoverable_job_warns` |
| Pipeline bloqué puis réarchivage | `test_pipeline_blocks_silent_duplicate` |
| Migration | `test_schema_v4_has_jobs_disc_id`, `test_migration_v3_to_v4` |

---

## 7. Risques résiduels

| Risque | Niveau | Mitigation / suite |
|--------|--------|---------------------|
| Course entre deux lancements quasi simultanés | Faible (usage mono-utilisateur) | Gate DENY après 1er INSERT ; pas de verrou SQLite dédié |
| Jobs anciens sans `disc_id` | Faible | Match via `selected_release_mbid` |
| Historique incomplet (release sans path/mbid) | Faible | WARN similarité ou ALLOW |
| Confirm UI oubliée mais API appelée avec flag | N/A | Flag volontaire côté worker ; domaine exige le flag |
| Replace silencieux | N/A | Replace UI toujours désactivé (06C) ; Rename pour réarchivage |

---

## 8. Arrêt

**AVM-06K terminé.** Présenter ce rapport et **attendre validation explicite** avant tout mandat AVM-06L.
