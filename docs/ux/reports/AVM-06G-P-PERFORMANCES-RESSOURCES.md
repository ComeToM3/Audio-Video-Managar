# Rapport AVM-06G-P — Performances et gestion des ressources

**Date :** 2026-11-03  
**Version :** 0.5.0  
**Suite :** **115 passed**  
**Banc JSON :** `docs/ux/reports/AVM-06G-P-bench.json`  
**Arrêt :** attendre validation avant AVM-06H

---

## Verdict

| Critère | Résultat |
|---------|----------|
| Baseline mesurée avant optimisation (copy forcé) | **GO** |
| Gains quantifiés (hardlink auto vs copy) | **GO** — voir §5 |
| Intégrité / returncode strict / publish safe | **Conservés** |
| UI non bloquante (QThread) | **Confirmé** (audit) |
| Sollicitation optique superflue | **Corrigée** (réutilisation `disc_read`) |
| Queen / jobs historiques | **Intact** (lecture seule bd40) |
| Optimisations risquées | **Documentées, non appliquées** |

**Recommandation :** **GO technique** 06G-P. **NO-GO 06H** jusqu’à validation mandant.

---

## 1. Environnement de mesure

| Élément | Valeur |
|---------|--------|
| OS | Windows 11 10.0.26300 |
| Python | 3.12.10 |
| CPU | 12 logical |
| ffmpeg | `C:\Tools\ffmpeg\bin\ffmpeg.EXE` |
| Corpus | 17 FLAC job `bd40…/rip` — **380 987 348 o** (~381 Mo) — **lecture seule** |
| Banc | `%TEMP%\avm-06gp-bench` + biblio temporaire |
| Script | `python scripts/avm_06gp_bench.py` |
| Rip optique | **Aucun** |

---

## 2. Cartographie des coûts

```text
[Optique] TOC discid (W1) → identify (réutilise disc_read)
        → archive match (DOIT réutiliser disc_read — corrigé)
        → fre:ac rip (hors banc 06G-P)
[CPU/IO]  F-08a header → decode ffmpeg null (dominante post-rip)
[IO]      rip → tagged (copie obligatoire, mutagen)
          tagged → inbox (hardlink auto)
          tagged → C (hardlink auto)
[Réseau]  MB rate-limit 1,1 s ; CAA meta ; cover bytes (cache disque)
```

| Opération | Nature | Notes |
|-----------|--------|-------|
| fre:ac rip | Optique + encode | Borné matériel ; non mesuré ici |
| `read_disc_toc` | Optique | Coûteux si répété inutilement |
| `list-drives` | freaccmd | Au refresh UI ; ne spin pas le média audio |
| Staging / inbox / publish | Disque | Dominé par copies avant 06G-P |
| Tagging | Copie + mutagen | Hardlink **interdit** (réécriture fichier) |
| F-08a | Lecture tête | ~2 ms / album |
| Decode intégral | CPU + lecture complète | ~1,8–2,0 s / album (mesuré) |
| Cover HTTP | Réseau | Évité si cache UI présent |

---

## 3. Instrumentation

Module `diagnostics/perf.py` → spans dans `run_archive_job` :

`disc_match`, `staging_to_zone_a`, `freac_rip`, `flac_integrity_f08a`, `flac_decode_full`, `cover_resolve`, `tagging_copy_and_write`, `inbox_transfer`, `publish_c`

Exposé dans `ArchiveJobReport.perf` (dict JSON-serializable).

---

## 4. Audit par domaine

### 4.1 Lecteur optique

| Constat | Action 06G-P |
|---------|----------------|
| W1 lit TOC ; identify réutilise `disc_read` | OK déjà |
| **ArchiveWorker ne passait pas `disc_read`** → 2ᵉ `read_disc_toc` avant rip | **Corrigé** : `disc_read=self._disc_read` |
| `refresh_drives` / `--list-drives` | Conservé (nécessaire UI) ; pas de throttle arbitraire de vitesse fre:ac |
| Annulation fre:ac | `terminate`/`kill` inchangé |
| Compression FLAC config | Inchangée (qualité > micro-gain CPU) |

### 4.2 Copies A / B / C

Avant : jusqu’à **4× `copy2`** (staging → A, A→tagged, tagged→inbox, tagged→C).

Après (faible risque) :

| Étape | Stratégie | Justification |
|-------|-----------|---------------|
| Staging → A | `transfer` auto (hardlink) | Source externe intacte ; rollback N/A |
| A → tagged | **`copy2` obligatoire** | Mutagen réécrit le fichier |
| tagged → inbox | hardlink → repli copy | Traçabilité B sans double écriture |
| tagged → C | hardlink → repli copy | Source tagged/inbox restent ; rollback = unlink dest |

`AVM_TRANSFER=copy|link|auto` pour forcer le mode (banc / diagnostic).

### 4.3 Workers PySide6

`IdentifyWorker` / `ArchiveWorker` / `RipWorker` : `QObject` + `QThread`, signaux progress/finished. Aucun fre:ac / MB / decode sur le thread UI constaté. Annulation via `threading.Event`. **Pas de refonte UI.**

### 4.4 Cache MB / CAA

| Ressource | Avant | Après |
|-----------|-------|-------|
| Cover UI `cover_cache` | Hit disque | Inchangé |
| `resolve_cover_for_sheet` (archive) | Toujours HTTP si URL | **Lit d’abord le cache** (même clé SHA) |
| Lookup MB | Pas de cache local | **Option P1** (§7) — non appliqué |
| CAA JSON | Pas de cache | **Option P1** |

Mesure hit cache (seed local) : resolve **0,0004 s** vs téléchargement réseau typiquement secondes + rate-limit.

### 4.5 Décodage intégral

| Métrique | Valeur mesurée |
|----------|----------------|
| F-08a 17 pistes | **0,0021 s** |
| Decode ffmpeg 17 pistes (~381 Mo) | **1,8361 s** |
| Ratio | Decode ≈ **99,9 %** du coût verify |

**Conservé** (contrôle non redondant avec F-08a : CRC trames vs magic/STREAMINFO). Parallelisme = option P1 non appliquée.

---

## 5. Mesures avant / après (preuves)

Source : `AVM-06G-P-bench.json`.

### 5.1 Micro-transfert 17 FLAC (381 Mo)

| Mode | Durée | Mo/s | Méthode |
|------|-------|------|---------|
| `copy` (`AVM_TRANSFER=copy`) | **0,1816 s** | ~2098 | 17 copy |
| `auto` | **0,0063 s** | — | 17 hardlink |

Gain transfert unitaire : **≈ 29×** plus rapide (hardlink vs copie pleine).

### 5.2 Pipeline staging complet (même corpus, publish C temp)

| Mode | Wall | Spans utiles |
|------|------|----------------|
| **copy** (baseline) | **2,6778 s** | staging 0,185 + inbox 0,188 + publish 0,196 + tag 0,213 + decode 1,846 |
| **auto** (après) | **2,2502 s** | staging 0,008 + inbox 0,009 + publish 0,013 + tag 0,213 + decode 1,952 |

| Gain | Quantité |
|------|----------|
| Wall pipeline | **−0,43 s (−16 %)** |
| Somme staging+inbox+publish | **0,57 s → 0,03 s (−95 %)** |
| Decode (conservé) | ~1,85–1,95 s (variance run) — **non réduit** |

Le plafond post-rip hors fre:ac est le **décodage** ; les I/O de publication ne le sont plus.

---

## 6. Correctifs appliqués (faible risque)

| ID | Changement | Preuve |
|----|------------|--------|
| P-A1 | `transfer_file` hardlink + repli copy | Banc + tests |
| P-A2 | Inbox + publish via `transfer_file` | `pipeline_auto` hardlink 17 |
| P-A3 | Cache pochette dans `resolve_cover_for_sheet` | Test + 0,0004 s hit |
| P-A4 | `disc_read` passé à `ArchiveWorker` | Code wizard |
| P-A5 | Spans `PerfSession` dans archive_job | `report.perf` |
| P-A6 | Tests `tests/test_perf_06gp.py` | Inclus suite 115 |

**Non modifié :** Queen library, jobs `bd40`/`8e23`, returncode fre:ac, F-08a, decode obligatoire si outil présent, D-011…D-015.

---

## 7. Options non appliquées (risque / ROI)

| ID | Priorité | Idée | Risque | Pourquoi pas maintenant |
|----|----------|------|--------|-------------------------|
| O1 | P1 | Decode parallèle (pool) | Contension disque/CPU ; flaky CI | Decode déjà ~2 s ; gain faible vs complexité |
| O2 | P1 | Cache disque réponses MB/CAA JSON | Fraîcheur / invalidation | Rate-limit 1,1 s suffisant MVP |
| O3 | P2 | `move` tagged → C (supprimer copie/lien) | Rollback / récupération A-B | Hardlink couvre l’essentiel sans consommer la source |
| O4 | P2 | Baisser `--flac_compression` | Taille/qualité | Décision produit, pas perf seule |
| O5 | P2 | Skip decode si AccurateRip OK | Outil absent ; politique intégrité | Contredit mandat « contrôles obligatoires » |
| O6 | P2 | mmap / buffers custom fre:ac | Hors contrôle AVM | Encodeur externe |

---

## 8. Compromis & limites

- Hardlink = **même volume NTFS** ; sinon repli `copy2` automatique.
- Hardlink inbox/C partagent les octets avec `tagged/` : une modification in-place d’un côté affecte les autres noms (peu probable sur archive figée).
- Banc **sans rip optique** : le coût fre:ac (dizaines de minutes possibles) reste le vrai mur utilisateur ; 06G-P optimise le **post-rip** et les **copies**.
- `CompletedWithWarnings` sur le banc : cover `unavailable` sur fiche factory (attendu).
- Variance decode ±0,1 s entre runs — ne pas sur-interpréter.

---

## 9. Recommandations P0 / P1 / P2

| Pri | Recommandation | Statut |
|-----|----------------|--------|
| **P0** | Conserver decode + F-08a + returncode strict | Fait |
| **P0** | Réutiliser `disc_read` à l’archive | **Fait** |
| **P0** | Hardlink A/B/C (hors tagging) | **Fait** |
| **P1** | Exposer spans perf dans UI avancée / log job | Futur |
| **P1** | Cache MB JSON TTL court | Option |
| **P1** | Mesurer rip réel fre:ac (durée/lecteur) sur prochain CD volontaire | 06H+ |
| **P2** | Decode parallèle opt-in | Option |
| **P2** | Retag Picture dims Queen (hors perf) | Mandat séparé |

---

## 10. Critères d’acceptation

| # | Critère | Statut |
|---|---------|--------|
| AC1 | Pas de régression tests | **115 passed** |
| AC2 | UI non bloquante | **Audit OK** |
| AC3 | Pas de TOC optique superflue à l’archive | **Démontré / corrigé** |
| AC4 | Ressources maîtrisées + gains mesurés | **§5** |
| AC5 | Pas d’optimisation théorique présentée comme gain | **Respecté** |
| AC6 | Queen / bd40 / strict fre:ac | **Préservés** |

---

## 11. Fichiers

| Chemin | Rôle |
|--------|------|
| `diagnostics/perf.py` | Spans |
| `library/transfer.py` | hardlink/copy |
| `library/publish.py` | transfer publish |
| `library/cover.py` | cache avant HTTP |
| `orchestration/archive_job.py` | spans + transfer inbox/staging |
| `ui/wizard/archive_wizard.py` | `disc_read` → worker |
| `scripts/avm_06gp_bench.py` | Banc reproductible |
| `tests/test_perf_06gp.py` | Régressions |
| `docs/ux/reports/AVM-06G-P-bench.json` | Preuves brutes |
| `docs/ux/reports/AVM-06G-P-PERFORMANCES-RESSOURCES.md` | Ce rapport |

---

**Fin AVM-06G-P — arrêt obligatoire. Attendre GO explicite avant AVM-06H.**
