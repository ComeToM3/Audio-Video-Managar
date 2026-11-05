# Rapport AVM-10B — Réconciliation des jobs et récupération contrôlée

**Date :** 2026-11-03  
**Version :** 0.5.0  
**Précédent :** AVM-10A (NO-GO V1 — diagnostic validé)  
**Suite autorisée :** AVM-10B uniquement  
**Arrêt :** ne pas engager AVM-10C sans validation explicite  

**Feuille de route approuvée :**  
AVM-10B → AVM-10C (tests/CI) → AVM-10D (intégrité/sécurité) → AVM-10E (validation CD) → AVM-10F (finitions/perf) → AVM-09 (distribution). FFmpeg/HTTP hors V1.

---

## Verdict

| Critère | Résultat |
|---------|----------|
| Détection démarrage jobs orphelins / interrompus | **GO** |
| Distinction actif / interrompu confirmé / incertain | **GO** |
| Jamais d’abandon automatique (ni sur l’âge) | **GO** |
| Aucune suppression / purge / déplacement destructif auto | **GO** |
| Reprise = staging fichiers (pas rip à la piste) | **GO** |
| Abandon = état SQLite seulement | **GO** |
| 06K / zone C / 07B préservés | **GO** |
| Job réel `a31763…` non récupéré automatiquement | **GO** (toujours `Ripping` en lecture seule post-mandat) |
| FLAC Queen non modifiés | **GO** (fixtures isolées uniquement) |
| Tests déterministes + **EXIT=0** | **GO** (13/13 `test_reconciliation_10b` + régressions) |
| **Verdict technique AVM-10B** | **GO** |

---

## 1. Audit (constat avant)

| Zone | Constat |
|------|---------|
| États actifs | `ACTIVE_JOB_STATES` (06K) : Ripping…AwaitingPublish… |
| Job `a31763…` | `Ripping`, `finished_at=NULL`, mode `technical_test` (crash 07B) |
| Reprendre UI | Bouton masqué (06N A-08) — F-13 non tenu |
| Abandon | `mark_job_abandoned` existait — fichiers non touchés |
| 06F staging | `staged_flac_files` + nouveau `job_id` — OK mais hors Historique |
| Verrou process | Aucun — impossible de distinguer fre:ac vivant vs orphelin |

---

## 2. Modifications

### 2.1 Domaine

| Fichier | Rôle |
|---------|------|
| `orchestration/rip_lock.py` | **Nouveau** — `.avm-rip.lock` (pid, job_id), lecture/écriture/clear |
| `orchestration/reconciliation.py` | **Nouveau** — classification liveness, reconcile, abandon, assess/run recovery |
| `orchestration/archive_job.py` | Pose/retire le verrou autour de `freaccmd` |
| `orchestration/rip_job.py` | Idem (test technique) |
| `storage/catalog.py` | `JobRow.metadata_id` / `disc_id` / `unfinished_active` ; abandon délègue à 10B |

### 2.2 Classification liveness (sans âge)

| Kind | Condition | Mutation auto |
|------|-----------|---------------|
| `PROCESS_ACTIVE` | Lock PID vivant | **Aucune** |
| `INTERRUPTED_CONFIRMED` | Lock PID mort **ou** freaccmd absent (probe False) | → `Interrupted` |
| `UNCERTAIN` | freaccmd tourne (PID non lié) **ou** probe None | **Aucune** |

**Interdit :** `Abandoned` automatique ; décision sur ancienneté seule.

### 2.3 Récupération contrôlée

1. Éligibilité : états récupérables + fiche **Approved** + FLAC F-08a + mapping pistes + 06K.  
2. Disque : match TOC si lisible ; sinon confirmation **hors ligne** explicite.  
3. Action UI : « Reprendre depuis les fichiers » → **nouveau** `run_archive_job(staged_flac_files=…)`.  
4. Source : octets/mtime préservés ; annotation `RecoverySpawned` ; état source inchangé (Failed/Interrupted/…).  
5. Garde concurrence : `try_acquire_recovery` (un seul run) + verrou nav 07B-style.

### 2.4 UI

| Surface | Changement |
|---------|------------|
| Démarrage `MainWindow` | `reconcile_unfinished_jobs` + bandeau Historique + dialogue info |
| Historique | Détails FLAC / interruption ; Reprendre ; Abandon confirmé |
| Fermeture | `closeEvent` attend aussi le worker de récupération |

### 2.5 Non fait (volontaire)

- Auto-reprise / auto-publish de `a31763…`  
- Suppression workdir / `.flac.temp`  
- Rip fre:ac piste-à-piste  
- AVM-10C CI / packaging  

---

## 3. Preuves

### 3.1 Tests automatisés

```text
pytest tests/test_reconciliation_10b.py  → 13 passed, EXIT=0
pytest + archive_recovery + history_06n + duplicates_06k + qthread_07b
         + database + hardlink_06gp1 + archive_pipeline
         → 67 passed, EXIT=0
```

Couverture `test_reconciliation_10b` :

| Test | Garantie |
|------|----------|
| `test_crash_simulated_marks_interrupted_not_abandoned` | Orphelin type a31763 → Interrupted, fichiers OK |
| `test_reconcile_idempotent_repeated_restarts` | Relances ×3 |
| `test_freaccmd_running_leaves_uncertain` | Pas de mutation si fre:ac vivant |
| `test_alive_lock_pid_is_process_active` | Lock PID courant |
| `test_dead_lock_pid_confirms_interrupted` | Lock PID mort |
| `test_abandon_does_not_delete_files` | Abandon idempotent |
| `test_incomplete_flac_denies_recovery` | Mapping incomplet |
| `test_missing_metadata_denies_recovery` | Tech test sans fiche |
| `test_successful_recovery_preserves_source` | Nouveau job + source intacte |
| `test_recovery_cancel_midway` | Annulation |
| `test_double_recovery_guard` | Anti double clic / concurrence |
| `test_list_job_flac_ignores_temp_and_tagged` | Inventaire sûr |
| `test_mark_interrupted_never_uses_age_alone` | Probe None → UNCERTAIN |

### 3.2 Données utilisateur (lecture seule post-implémentation)

| Job | État observé |
|-----|--------------|
| `a31763eed2ae423eb78ded45b125667a` | **Toujours** `Ripping` / `finished_at=NULL` — **non** auto-récupéré dans ce mandat |

Au **prochain démarrage GUI**, si `freaccmd` est inactif, la réconciliation le passera en `Interrupted` (fichiers inchangés). Ce n’est pas une récupération staging.

### 3.3 Invariants préservés

- Bibliothèque zone C / hardlinks P1  
- Gates 06K (`ACTIVE_JOB` / `REQUIRE_CONFIRM`)  
- Cycle `attach_worker_thread` / `shutdown_worker_thread` (07B)  
- Politique fre:ac `returncode == 0`  

---

## 4. Limites

| Limite | Gravité | Note |
|--------|---------|------|
| freaccmd global sans PID enfant | P2 | Si fre:ac tourne pour un autre job → UNCERTAIN sur tous les orphelins |
| Reprise tech test sans `metadata_id` | Attendu | DENY honnête (cas a31763) |
| Decode ffmpeg non exigé ici | P2 | Reporté AVM-10D |
| Probe `tasklist` Windows | P3 | Hors Windows → UNCERTAIN |
| Historique UI tests offscreen | Info | `isHidden()` vs `isVisible()` |

---

## 5. GO / NO-GO

| Question | Réponse |
|----------|---------|
| AVM-10B objectifs atteints ? | **Oui** |
| Prêt pour AVM-10C ? | **Oui**, sous validation mandant |
| V1 distribuable ? | **Toujours NO-GO** (10A) |
| AVM-10C / 09 / FFmpeg-HTTP ? | **NO-GO** jusqu’à décision |

**Verdict : GO technique AVM-10B.**

---

## Arrêt obligatoire

Attendre validation explicite avant **AVM-10C** (fiabilité tests/CI) et tout mandat suivant.
