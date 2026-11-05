# Rapport AVM-10C.2 — Assainissement des fixtures et stabilité native Qt

**Date :** 2026-11-03  
**Version produit :** 0.5.0  
**Précédent :** AVM-10C.1 (**NO-GO** — crashs confinés / contournés, non éliminés)  
**Autorisation :** 10C.2 ouvert pour corriger les causes résiduelles ; **AVM-10D suspendu** jusqu’à validation explicite.

---

## Verdict

| Critère GO 10C.2 | Résultat |
|------------------|----------|
| Tous les fichiers UI obligatoires, fermeture **naturelle** | **GO** (12/12) |
| `AVM_QT_SAFE_EXIT=0` (pas de `os._exit`) | **GO** |
| Diagnostics `unraisableexception` **actifs** | **GO** |
| Codes de sortie natifs `EXIT=0` (pas `0xC0000005` / Abort) | **GO** |
| Cycles app Windows (navigation Widgets/QML + close) | **GO** |
| QThread actifs / orphelins après teardown | **aucun** |
| Orchestrateur CI compatible (UI-only, politique naturelle) | **GO** (`OVERALL: GO`) |
| Métier SQLite / fre:ac / FLAC / 06K·07B·10B | **non modifié** |

**Verdict : GO** — les crashs pytest UI résiduels de 10C.1 sont imputables à des **fixtures / teardown incomplets** (widgets orphelins + GC Shiboken), pas à un défaut métier ni à un bogue PySide6 non contournable une fois le cleanup centralisé.

---

## 1. Causes démontrées

| ID | Cause | Preuve | Correctif |
|----|-------|--------|-----------|
| F1 | Widgets top-level créés dans les tests **sans** `close`/`deleteLater` systématique | `test_ux_06o`, `test_ui_collision_*`, pages orphelines ; 10C.1 survivors 206 QObject | Autouse + `shutdown_all_widgets()` |
| F2 | `QQuickWidget` / bridge survivant après `close()` | Audit 10C.1 ; Mode A `gc_collect_harder` | `LibraryHost.shutdown_ui()` (10C.1) + appel via dispose |
| F3 | `gc_collect_harder` (plugin unraisable) sur wrappers encore vivants | Stack faulthandler 10C.1 sur `ux_06o`/`ui_design` | Cleanup **avant** `pytest_unconfigure` → GC inoffensif |
| F4 | `os._exit` / `-p no:unraisableexception` | Matrice 10C.1 PASS contournement | **Retirés du défaut** CI / pyproject (secours `AVM_QT_SAFE_EXIT=1` conservé) |

**Repros minimales** (`scripts/diag10c2/minimal_repro_teardown.py` → `.ci/avm10c2-minimal-repro.json`) :

| Mode | Scénario | Résultat local |
|------|----------|----------------|
| A | MainWindow + dispose ordonné | PASS |
| B | Wizard sans teardown explicite (process court) | PASS (crash surtout sous pytest multi-tests + GC) |
| C | B + `qt_session_cleanup()` | PASS |
| D | close soft + `gc.collect()` après shutdown_ui | PASS (déclencheur historique atténué) |

Conclusion : défaut **fixture / cycle de vie test**, pas application Windows nominale (déjà GO en 10C.1).

---

## 2. Correctifs (sans refonte métier)

| Fichier | Changement |
|---------|------------|
| `tests/qt_support.py` | `dispose_widget`, `drain_deferred_deletes`, `shutdown_all_widgets`, `qt_session_cleanup` ; pas de `gc.collect` ; pas de double `setParent` destructeur |
| `tests/conftest.py` | Autouse teardown `qt_ui` ; `sessionfinish` cleanup **toujours** ; `os._exit` seulement si `AVM_QT_SAFE_EXIT=1` ; **défaut = 0** |
| `tests/test_qt_teardown_10c2.py` | Non-régression orphan wizard + MainWindow/QML |
| `pyproject.toml` | `addopts = -q` — **diagnostics ON** |
| `scripts/run_tests_ci.py` | Défaut `AVM_QT_SAFE_EXIT=0` ; plus de `-p no:unraisableexception` ; + fichiers teardown |
| `.github/workflows/ci-windows.yml` | `AVM_QT_SAFE_EXIT=0` |
| `ui/main_window.py` / `library_host.py` | Conservés (shutdown_ui 10C.1) |

**Interdits respectés :** aucune mutation SQLite/fre:ac/FLAC/données utilisateur ; protections 06K/07B/10B intactes ; `os._exit` n’est **pas** utilisé comme preuve GO.

---

## 3. Matrice exhaustive UI (fermeture naturelle)

**Politique :** `AVM_QT_SAFE_EXIT=0`, `unraisableexception` actif (`-o addopts=-q`), faulthandler ON.

```bash
python scripts/diag10c2/matrix_ui_natural.py
# → .ci/avm10c2-matrix-natural.json
```

| Fichier | rc | Classification |
|---------|----|----------------|
| `test_history_06n.py` | 0 | **PASS réel** |
| `test_ux_06o.py` | 0 | **PASS réel** |
| `test_ui_design_06l.py` | 0 | **PASS réel** |
| `test_ui_shell.py` | 0 | **PASS réel** |
| `test_ui_library_history_06h.py` | 0 | **PASS réel** |
| `test_library_qml_08b.py` | 0 | **PASS réel** |
| `test_humanisation_06i.py` | 0 | **PASS réel** |
| `test_ui_w3_prefill.py` | 0 | **PASS réel** |
| `test_ui_collision_replace_disabled.py` | 0 | **PASS réel** |
| `test_qthread_07b.py` | 0 | **PASS réel** |
| `test_qt_teardown_10c1.py` | 0 | **PASS réel** |
| `test_qt_teardown_10c2.py` | 0 | **PASS réel** |

**Synthèse :** 12/12 PASS réel · `go=true`  
**Re-run immédiat :** 12/12 PASS réel (anti-flake).

### Avant (10C.1) vs après (10C.2) — cellules critiques

| Fichier | 10C.1 natural+diag | 10C.2 natural+diag |
|---------|--------------------|--------------------|
| `test_ux_06o` | `0xC0000005` | **0 PASS réel** |
| `test_ui_design_06l` | `0xC0000005` | **0 PASS réel** |
| `test_ui_collision_*` | Abort / rc=3 | **0 PASS réel** |
| `test_ui_shell` | Abort / puis PASS partiel | **0 PASS réel** |

---

## 4. Orchestrateur / CI

```bash
AVM_QT_SAFE_EXIT=0 python scripts/run_tests_ci.py --ui-only \
  --junit-dir .ci/avm10c2-orch-junit \
  --report .ci/avm10c2-orch-results.json
```

Résultat : **`OVERALL: GO`** · `ORCH_EXIT=0` · 12 fichiers UI · 0 native_crash · JUnit OK.

Secours documenté : `AVM_QT_SAFE_EXIT=1` réactive `os._exit` (contournement) — **ne compte pas** comme preuve de stabilité.

---

## 5. Cycles Windows réels

```bash
unset QT_QPA_PLATFORM
AVM_10C1_CYCLES=3 python scripts/diag10c1/app_lifecycle_windows.py
python scripts/diag10c1/qt_survivor_audit.py
```

| Mesure | Résultat |
|--------|----------|
| 3× open / nav Widgets+QML / close / `app.exec` | OK, code 0 |
| `os._exit` | non utilisé |
| Survivants post-teardown | 3 (`QApplication` + `QCommonStyle`×2) |
| `QQuickWidget` / engine | **0** |
| `QThread` running | **[]** |

---

## 6. Tests de non-régression

| Test | Rôle |
|------|------|
| `tests/test_qt_teardown_10c1.py` | Refs QML nulles après close ; pas de QThread running |
| `tests/test_qt_teardown_10c2.py` | Orphan `ArchiveWizardPage` + `shutdown_all` MainWindow |

Inclus dans `UI_TEST_FILES` et l’orchestrateur.

---

## 7. Risques résiduels

1. **Flakiness latente** possible sur d’autres machines / versions PySide — deux passes locales OK ne remplacent pas la CI GitHub.
2. **`AVM_QT_SAFE_EXIT=1`** encore disponible : ne pas le réactiver « pour faire passer » sans rouvrir un diagnostic.
3. Tests qui créeraient des QObject **hors** `QApplication.topLevelWidgets()` (timers globaux, singletons) restent un angle mort théorique.
4. `gc.collect()` explicite dans un futur test reste **interdit** côté harness.
5. Packaging / rip physique / AVM-10D : **hors scope** ; arrêt obligatoire avant 10D.

---

## 8. Artefacts

| Chemin | Rôle |
|--------|------|
| `.ci/avm10c2-matrix-natural.json` | Matrice exhaustive |
| `.ci/avm10c2-orch-results.json` | Orchestrateur UI GO |
| `.ci/avm10c2-junit/` · `.ci/avm10c2-orch-junit/` | JUnit |
| `.ci/avm10c2-minimal-repro.json` | Repros A–D |
| `.ci/avm10c2-survivors.json` | Survivants post-teardown |
| `scripts/diag10c2/*` | Outils de preuve |

---

## 9. Décision suite

| Lot | Statut |
|-----|--------|
| AVM-10C (CI harness) | Conservé, **aligné** sur fermeture naturelle |
| AVM-10C.1 | Diagnostic NO-GO **confirmé comme justifié** à date |
| **AVM-10C.2** | **GO** technique local |
| **AVM-10D** | **Suspendu** — attendre validation explicite humaine de ce rapport |

---

**Fin du rapport AVM-10C.2 — verdict GO (fermeture naturelle + diagnostics actifs).**
