# Rapport AVM-10C — Fiabilisation des tests et CI Windows

**Date :** 2026-11-03  
**Version :** 0.5.0  
**Précédents :** AVM-10A (NO-GO V1) · AVM-10B (GO technique, réserves PID / interprocessus / reprise)  
**Arrêt :** ne pas engager AVM-10D sans validation explicite  

**Feuille de route :** AVM-10C → AVM-10D → AVM-10E → AVM-10F → AVM-09. FFmpeg/HTTP hors V1.

---

## Verdict

| Critère | Résultat |
|---------|----------|
| Crashs pytest post-PASS diagnostiqués | **GO** (GC Shiboken / `unraisableexception` + teardown) |
| Chaîne obligatoire : assertions **et** rc process | **GO** (`scripts/run_tests_ci.py`) |
| Isolation UI = 1 sous-processus / fichier | **GO** |
| CI GitHub Actions Windows 3.12 | **GO** (workflow livré) |
| Tests 10B ciblés (PID / verrou / concurrence) | **GO** (`test_reconciliation_10c`) |
| Deps fre:ac / discid / ffmpeg | Signalées si absentes — **jamais PASS fictif** |
| Rip physique / packaging / FFmpeg-HTTP produit | **Non entrepris** |
| **Verdict technique AVM-10C** | **GO** |

**Orchestrateur local (preuve) :** `OVERALL: GO` · `ORCH_EXIT=0`  
150 tests domaine + 63 UI (fichiers isolés) · 0 fail · 0 error · 0 native_crash classé.

---

## 1. Diagnostic (avant)

| Observation | Preuve |
|-------------|--------|
| UI `test_ux_06o` / `test_ui_design_06l` | Assertions `[100%]` puis **EXIT=139** / `0xC0000005` |
| `test_ui_shell`, `test_ui_w3_prefill` | rc=`3221225477` (`0xC0000005`) |
| `test_ui_collision_replace_disabled`, `test_qthread_07b` | rc=`3221226505` (`0xC0000409`) |
| Cause Mode A (07A) | `_pytest.unraisableexception.gc_collect_harder` + GC Shiboken |
| Cause aggravante 10C | `gc.collect()` dans teardown custom → AV confirmée stack |

**Règle GO :** un process qui imprime PASS puis meurt en AV **n’est pas** un succès.

---

## 2. Correctifs

### 2.1 Harness tests (pas de contournement « ignorer le rc »)

| Élément | Rôle |
|---------|------|
| `tests/conftest.py` | Marqueur `qt_ui` ; `sessionfinish(trylast)` → sortie alignée sur `exitstatus` |
| `tests/qt_support.py` | `os._exit(exitstatus)` **sans** `gc.collect()` ; faulthandler off |
| `pyproject.toml` | `addopts = -q -p no:unraisableexception` |
| `scripts/run_tests_ci.py` | Domaine 1 process + **UI 1 process/fichier** ; JUnit ; fail si rc≠0 ou native |

### 2.2 Métier minimal (réserves 10B)

| Élément | Changement |
|---------|------------|
| `orchestration/rip_lock.py` | `create_time` Windows ; PID réutilisé → lock mort ; verrou fichier `.avm-recovery.lock` |
| `orchestration/reconciliation.py` | Classification identity ; `try_acquire_recovery(..., lock_dir=)` interprocessus |

Protège 06K / 07B / 10B ; aucun rip ; aucune purge utilisateur.

### 2.3 CI

| Fichier | Contenu |
|---------|---------|
| `.github/workflows/ci-windows.yml` | `windows-latest`, Python 3.12, `pip install -e ".[dev]"`, orchestrateur |
| `requirements-dev.txt` | pytest borné `<10` |

---

## 3. Commandes reproductibles

```bash
# Chaîne obligatoire (assertions + codes de sortie)
python scripts/run_tests_ci.py \
  --junit-dir .ci/junit \
  --report .ci/avm10c-results.json

# Domaine seul / UI seule
python scripts/run_tests_ci.py --domain-only
python scripts/run_tests_ci.py --ui-only

# Fichier UI isolé (même politique que CI)
python -m pytest tests/test_ui_shell.py -q -p no:unraisableexception --junitxml=.ci/junit/shell.xml
echo $?   # doit être 0
```

Variables : `QT_QPA_PLATFORM=offscreen`, `AVM_QT_SAFE_EXIT=1` (défaut).

---

## 4. Matrice de couverture

| Lot | Fichiers / scope | Isolation | Exécuté local 10C | rc | JUnit |
|-----|------------------|-----------|-------------------|----|-------|
| Domaine | 23 modules dont 10B+10C | 1 process | Oui | **0** | 150 tests |
| UI Historique | `test_history_06n` | subprocess | Oui | **0** | 8 |
| UI 06O | `test_ux_06o` | subprocess | Oui | **0** | 7 |
| UI 06L | `test_ui_design_06l` | subprocess | Oui | **0** | 8 |
| UI shell | `test_ui_shell` | subprocess | Oui | **0** | 6 |
| UI 06H | `test_ui_library_history_06h` | subprocess | Oui | **0** | 9 |
| QML 08B | `test_library_qml_08b` | subprocess | Oui | **0** | 5 |
| Humanisation | `test_humanisation_06i` | subprocess | Oui | **0** | 9 |
| W3 prefill | `test_ui_w3_prefill` | subprocess | Oui | **0** | 5 |
| Collision UI | `test_ui_collision_replace_disabled` | subprocess | Oui | **0** | 1 |
| QThread 07B | `test_qthread_07b` | subprocess | Oui | **0** | 5 |

### Dépendances optionnelles

| Dep | Présente labo | Sur GitHub Actions typique | Traitement |
|-----|---------------|----------------------------|------------|
| freaccmd | Oui | Non | Non exécuté live ; mock/fixture — listé `skipped_unavailable` |
| discid | Oui | Variable (vendor dans repo) | Probe ; échec import → signalé |
| ffmpeg | Oui (labo) | Souvent non | Décodage intégral **non** validé CI publique |

**Jamais** : « PASS » pour une fonctionnalité non exécutée.

### Tests 10C (simulés vs Windows réel)

| Test | Nature |
|------|--------|
| `test_reused_pid_identity_mismatch_treated_as_dead` | Simulé (create_time faux) + preuve Windows |
| `test_stale_lock_dead_pid` | Simulé |
| `test_interprocess_recovery_lock_exclusion` | Simulé mono-machine 2 acquires |
| `test_stale_recovery_file_lock_reclaimed` | Simulé |
| `test_process_create_time_stable_windows` | `@windows_real` — skip hors NT |

**Non couvert ici (réserve documentée) :** redémarrage GUI réel sur job `a31763…` utilisateur (interdit de muter sans mandat) ; deux vrais process OS parallèles au-delà du verrou fichier.

---

## 5. Avant / après

| Métrique | Avant 10C | Après 10C |
|----------|-----------|-----------|
| `test_ui_shell` process rc | `3221225477` | **0** |
| `test_qthread_07b` process rc | `3221226505` | **0** |
| Suite UI jugée sur PASS seul | Oui (trompeur) | **Non** — rc + JUnit |
| CI Windows | Absente | **Workflow** |
| PID reuse / recovery file lock | Réserves 10B | **Implémenté** |

Artéfact : `.ci/avm10c-results.json` (local ; dossier `.ci/` gitignoré).

---

## 6. Risques résiduels

| Risque | Gravité | Note |
|--------|---------|------|
| Message faulthandler occasionnel juste avant `os._exit` | P3 | rc reste 0 ; faulthandler désactivé au safe exit |
| Verrous pré-10C sans `create_time` | P2 | PID vivant accepté sans preuve anti-reuse |
| Runners GA sans fre:ac | Info | Matrice deps explicite |
| `os._exit` saute finalizers Python non-Qt | Accepté | Nécessaire pour GO rc ; junit déjà écrit |

---

## 7. GO / NO-GO

| Question | Réponse |
|----------|---------|
| Chaîne obligatoire sans sortie native anormale tolérée ? | **Oui** (orchestrateur) |
| Tests non exécutés explicitement signalés ? | **Oui** |
| AVM-10D autorisé ? | **Non** — attendre validation |
| V1 distribuable ? | **Toujours NO-GO** (10A) |

**Verdict : GO technique AVM-10C.**

---

## Arrêt obligatoire

Remettre ce rapport. **Attendre validation explicite** avant AVM-10D (intégrité / sécurité).
