# Rapport AVM-10C.1 — Vérification indépendante de la stabilité Qt (Windows)

**Date :** 2026-11-03  
**Version produit :** 0.5.0  
**Précédent :** AVM-10C (GO infrastructure CI / harness — crashs natifs *non* prouvés corrigés)  
**Arrêt obligatoire :** ne **pas** engager AVM-10D avant validation explicite de ce rapport.

---

## Verdict

| Critère GO 10C.1 | Résultat |
|------------------|----------|
| Fermeture **normale** des processus de validation pytest UI | **NO-GO** |
| Sans `os._exit` / `AVM_QT_SAFE_EXIT` | **NO-GO** (plusieurs fichiers UI) |
| Sans désactivation systématique des diagnostics (`-p no:unraisableexception`) | **NO-GO** |
| Absence de crash natif `0xC0000005` / `0xC0000409` / Abort Shiboken | **NO-GO** (résiduel démontré) |
| App Windows réelle (Widgets/QML, `close()`, `app.exec`) | **GO** (cycles reproductibles) |
| Verrous AVM-10B/10C — 2 processus Windows + PID réutilisé / périmé | **GO** |
| Harness 10C conservé, classifications explicites | **GO** |

**Verdict argumenté : NO-GO** pour déclarer les crashs Qt « corrigés ».  
AVM-10C **confine** et **masque** les anomalies de fin de process pytest (`os._exit` + `-p no:unraisableexception`). Une correction partielle de teardown QML (10C.1) réduit les survivants et améliore un fichier (`test_ui_shell`) en fermeture naturelle, mais **ne satisfait pas** le critère GO.

---

## 1. Classification des résultats (contrat 10C.1)

| Label | Signification |
|-------|----------------|
| **PASS réel** | `rc=0`, `AVM_QT_SAFE_EXIT=0`, plugin `unraisableexception` **actif** |
| **PASS diagnostics off** | `rc=0`, sortie naturelle, mais `-p no:unraisableexception` |
| **PASS avec contournement** | `rc=0` grâce à `os._exit` (`AVM_QT_SAFE_EXIT=1`) |
| **Crash natif** | `0xC0000005` (3221225477), `0xC0000409`, segfault / Abort Shiboken |
| **Non testé** | Hors matrice / hors machine |

---

## 2. Audit harness (état figé)

| Artefact | Rôle | Nature |
|----------|------|--------|
| `tests/conftest.py` | `qt_ui` + `pytest_sessionfinish(trylast)` → `pytest_safe_exit` si `AVM_QT_SAFE_EXIT=1` (défaut) | **Contournement** documenté |
| `tests/qt_support.py` | Teardown soft + `os._exit` ; **interdit** `gc.collect()` | Contournement + cleanup |
| `pyproject.toml` | `addopts = -q -p no:unraisableexception` | **Atténuation** Mode A (GC forcé) |
| `scripts/run_tests_ci.py` | 1 process / fichier UI ; refuse rc natif | Correct pour CI — ne prouve pas la correction |
| `audio_video_manager/ui/thread_lifecycle.py` | QThread sans parent widget (07B) | Correctif métier conservé |
| QObject / QQuickWidget | Survivants après `close()` seul | Cause racine **partiellement** traitée en 10C.1 |

**Conclusion audit :** l’infrastructure 10C est saine pour la CI, mais `os._exit` et la coupure `unraisableexception` **ne sont pas** une preuve de stabilité Qt.

---

## 3. Matrice comparative (avant correctif teardown 10C.1)

**Commande :**

```bash
source .venv/Scripts/activate
python scripts/diag10c1/matrix_qt_stability.py
# → .ci/avm10c1-matrix-before.json  (+ JUnit .ci/avm10c1-junit/)
```

**Légende cellules :** `safe_exit` = `AVM_QT_SAFE_EXIT` ; `nou` = `-p no:unraisableexception`.

| Fichier | safe=0 nou=0 | safe=0 nou=1 | safe=1 nou=1 | safe=1 nou=0 |
|---------|--------------|--------------|--------------|--------------|
| `test_history_06n` | **PASS réel** rc=0 | PASS diag-off | PASS contournement | PASS contournement |
| `test_ux_06o` | **0xC0000005** | **0xC0000005** | PASS contournement | PASS contournement |
| `test_ui_shell` | Abort/rc=3 | Abort/rc=3 | PASS contournement | PASS contournement |
| `test_ui_design_06l` | **0xC0000005** | **0xC0000005** | PASS contournement | PASS contournement |
| `test_qthread_07b` | **PASS réel** rc=0 | PASS diag-off | PASS contournement | PASS contournement |
| `test_ui_collision_replace_disabled` | Abort/rc=3 | PASS diag-off | PASS contournement | PASS contournement |

**Synthèse avant :** `pass_real=2` · `pass_workaround=12` · `native_crash=4` · `other_fail=3` · `go_criterion_natural_close=false`

Preuve clé : pour `test_ux_06o` / `test_ui_design_06l`, **même sans** `unraisableexception`, la sortie naturelle reste en **AV**. Donc désactiver le plugin **ne suffit pas** ; `os._exit` **masque**.

---

## 4. Correctif racine partiel (démontré) + matrice après

### 4.1 Cause confirmée

Audit `scripts/diag10c1/qt_survivor_audit.py` **avant** :

- Après `close()` soft : **206** QObject vivants, dont `QQuickWidget` / `QQmlEngine` / `QQmlContext`
- **0** `QThread` encore `isRunning()`
- Les refs Python empêchent une destruction ordonnée → GC / finalizer Shiboken → `0xC0000005` (stack `Garbage-collecting` → `gc_collect_harder`)

### 4.2 Correctif appliqué (métier minimal)

| Fichier | Changement |
|---------|------------|
| `ui/sections/library_host.py` | `shutdown_ui()` : `setSource()`, clear cache, `deleteLater` bridge/quick |
| `ui/main_window.py` | `closeEvent` appelle toujours `_shutdown_ui_surfaces()` |
| `tests/qt_support.py` | Teardown : `shutdown_ui` + `deleteLater` + `DeferredDelete` (toujours **sans** `gc.collect`) |
| `tests/test_qt_teardown_10c1.py` | Non-régression refs QML + absence de QThread running |
| Harness `os._exit` / `no:unraisableexception` | **Conservés** pour la CI — explicitement classés *contournement* |

### 4.3 Survivants après correctif

```text
after_soft_teardown_count: 3
survivor_types_top: QCommonStyle×2, QApplication×1
qml_related: []
running_qthreads: []
```

### 4.4 Matrice après (même script)

Artefact : `.ci/avm10c1-matrix-after.json`

| Fichier | safe=0 nou=0 (critère GO) | Δ vs avant |
|---------|---------------------------|------------|
| `test_history_06n` | **PASS réel** | = |
| `test_ux_06o` | **0xC0000005** | inchangé (toujours Mode A sous GC) |
| `test_ui_shell` | **PASS réel** | **amélioré** (était Abort/rc=3) |
| `test_ui_design_06l` | **0xC0000005** | inchangé |
| `test_qthread_07b` | **PASS réel** | = |
| `test_ui_collision_replace_disabled` | Abort/rc=3 | inchangé sous diagnostics |

**Synthèse après :** `pass_real=3` · `go_criterion_natural_close=false`

`os._exit` reste nécessaire pour les fichiers lourds UI sous CI. Une cellule intermittente (`test_ui_design` + `safe=1` + diagnostics) a aussi produit une AV — rappel : le contournement n’est pas une immunité absolue si le crash survient *pendant* le test.

---

## 5. Application Windows réelle (hors pytest)

```bash
unset QT_QPA_PLATFORM
AVM_10C1_CYCLES=3 python scripts/diag10c1/app_lifecycle_windows.py
# → .ci/avm10c1-app-lifecycle.json
```

| Mesure | Résultat |
|--------|----------|
| Plateforme | Windows native (`QT_QPA_PLATFORM` non forcé) |
| Cycles | 3× `MainWindow` show → navigation Widgets/QML → `close()` |
| `app.exec()` | 0 |
| `os._exit` | **non utilisé** |
| Crash natif | **aucun** |

→ La **fermeture utilisateur** du shell est stable dans ce protocole. Le problème dominant est le **cycle de vie pytest / Shiboken / GC**, pas le chemin `closeEvent` nominal.

---

## 6. Verrous — deux processus Windows

```bash
python scripts/diag10c1/two_process_locks.py
# → .ci/avm10c1-two-process-locks.json
```

| Cas | Résultat |
|-----|----------|
| Enfant acquiert `.avm-recovery.lock` | OK |
| Parent bloqué pendant la détention | OK (`parent_blocked_while_child_holds=true`) |
| Verrou rip périmé (PID mort) | `stale_lock_active=false` |
| PID vivant + `create_time` falsifié (réutilisation) | `reused_pid_lock_active=false` |
| `ok` global | **true** |

Protège AVM-10B/10C ; aucun rip physique ; aucune mutation données utilisateur.

---

## 7. Causes confirmées vs contournements

| ID | Cause / mécanisme | Preuve | Statut |
|----|-------------------|--------|--------|
| C1 | `gc_collect_harder` (`unraisableexception`) sur wrappers Qt vivants | Stack faulthandler Mode A (`test_ux_06o` natural+diag) | **Confirmé** — atténué par `-p no:…` (contournement) |
| C2 | Survivants `QQuickWidget`/engine après `close()` Python | Audit 206 → 3 après `shutdown_ui` | **Corrigé partiellement** |
| C3 | Finalizer / Abort Shiboken en fin de process pytest | `Fatal Python error: Aborted` + `<no Python frame>` | **Confirmé** — non éliminé |
| C4 | `os._exit` après assertions | Matrice : crash → PASS contournement | **Contournement** (CI) — à ne pas confondre avec PASS réel |
| C5 | QThread détruit trop tôt | 07B + audit `running_qthreads=[]` | **Non reproduit** ici |

---

## 8. Limites

- Matrice échantillon (6 fichiers UI historiques) — pas 100 % des modules UI en une passe.
- Flakiness possible (AV pendant paint / Abort post-`[100%]`).
- `offscreen` ≠ GPU utilisateur ; l’app lifecycle native couvre mieux le cas boutique.
- Pas de rip CD ; fre:ac/discid hors scope stabilité Qt.
- Correctif QML n’adresse pas tous les arbres Widgets créés dans les tests sans `deleteLater`.

---

## 9. Corrections nécessaires pour un futur GO 10C.1

1. Teardown systématique des fixtures UI (autouse) : `close` + `shutdown_ui` + `deleteLater` + drain `DeferredDelete`, **sans** `gc.collect`.
2. Remplacer ou isoler `gc_collect_harder` sans masquer les *vrais* unraisables (hook custom / pytest-qt documenté).
3. Atteindre **PASS réel** sur toute la liste `UI_TEST_FILES` sous matrice `safe=0 nou=0`.
4. Alors seulement : retirer `AVM_QT_SAFE_EXIT` par défaut et `-p no:unraisableexception` du `addopts`, en gardant l’orchestrateur qui refuse les rc natifs.

---

## 10. Artefacts reproductibles

| Chemin | Contenu |
|--------|---------|
| `scripts/diag10c1/matrix_qt_stability.py` | Matrice 2×2 |
| `scripts/diag10c1/app_lifecycle_windows.py` | Cycles app native |
| `scripts/diag10c1/two_process_locks.py` | 2 process + stale/reuse |
| `scripts/diag10c1/qt_survivor_audit.py` | Survivants QObject |
| `.ci/avm10c1-matrix-before.json` / `-after.json` | Preuves chiffrées |
| `.ci/avm10c1-junit/` | JUnit par cellule |
| `.ci/avm10c1-app-lifecycle.json` | App GO |
| `.ci/avm10c1-two-process-locks.json` | Verrous GO |
| `.ci/avm10c1-survivors.json` (+ after) | Survivants |

---

## 11. Lien avec AVM-10C / suite

| Lot | Lecture 10C.1 |
|-----|----------------|
| AVM-10C harness + CI | **Toujours GO** pour *fiabiliser la CI* — inchangé |
| AVM-10C « crashs corrigés » | **Réinterprété : confinés / contournés**, pas éliminés |
| AVM-06K / 07B / 10B | Préservés (verrous revalidés) |
| **AVM-10D** | **Interdit** jusqu’à validation explicite de ce NO-GO / d’un re-run GO |

---

**Fin du rapport AVM-10C.1 — verdict NO-GO stabilité Qt pytest ; GO app lifecycle + verrous interprocessus.**
