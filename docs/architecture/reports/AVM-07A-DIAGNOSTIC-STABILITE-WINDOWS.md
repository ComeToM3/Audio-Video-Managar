# Rapport AVM-07A — Diagnostic de stabilité native Windows

**Date :** 2026-11-03  
**Version :** 0.5.0  
**Environnement :** Windows 10 (build 26300), Python 3.12.10, PySide6 6.12.0, pytest 9.0.1  
**fre:ac :** `C:\Program Files\freac\freaccmd.exe` présent  
**libdiscid :** `vendor/libdiscid/libdiscid-0.6.4-win/x64/discid.dll` chargeable  
**Contrainte :** diagnostic lecture seule — aucun correctif applicatif appliqué  
**Arrêt :** validation explicite avant toute correction

---

## Verdict

| Question | Réponse |
|----------|---------|
| Le `0xC0000005` est-il reproductible ? | **Oui** (pytest UI / suite) |
| Les tests échouent-ils avant le crash ? | **Non** — en Mode A les tests affichent `[100%]` / PASS puis le process meurt |
| L’application normale (`python -m audio_video_manager`) est-elle touchée ? | **Non démontré** — 0 crash sur cycles ouverture/navigation/fermeture |
| freaccmd / libdiscid plantent-ils seuls ? | **Non** |
| Cause probable ? | **Cycle de vie Qt/Shiboken × garbage collector pytest** (pas un bug métier d’archivage) |
| **Verdict** | **GO** — risque utilisateur final **isolé et maîtrisé** (harness de test) |

---

## 1. Synthèse exécutive

Le code `0xC0000005` (ACCESS_VIOLATION) observé après AVM-06O est un **crash natif pendant le garbage collection Python**, presque toujours après que les assertions aient réussi. Deux modes coexistent :

| Mode | Quand | Stack typique | Fréquence |
|------|-------|---------------|-----------|
| **A — Teardown pytest** | Fin de session, après `[100%]` | `Garbage-collecting` → `_pytest.unraisableexception.gc_collect_harder` → `_ensure_unconfigure` | **Très élevée** sur fichiers UI (ex. `test_ux_06o` 5/5, `test_ui_design_06l` 5/5) |
| **B — GC en cours de session** | Suite complète ~79 %, ou enchaînements multi-fichiers UI | `Garbage-collecting` pendant `ArchiveWizardPage.__init__` / `_build_w*` | **Élevée** sur `pytest tests/` ; variable selon ordre |

L’application desktop Windows réelle (plateforme `windows`, pas offscreen), avec navigation et fermeture propre, **n’a pas produit** ce crash dans les essais de ce mandat.

---

## 2. Matrice de reproduction

Scripts : `scripts/diag07a/` · Artéfacts : `.capture_avm07a/*.json` · `faulthandler` activé (`-X faulthandler`).

### 2.1 Orchestrateur (résumé)

| Scénario | Répétitions | Résultat process | Notes |
|----------|-------------|------------------|-------|
| `isolate_crash.py` (freaccmd, discid, MainWindow×8+GC, Wizard×8+GC, History teardown) | 1 | **OK rc=0** | Contrôle hors pytest |
| `app_lifecycle.py` (5 cycles show/nav/close, `platform=windows`) | 5/5 | **OK** | App normale |
| Harness `app.exec()` + `QTimer.quit` | 6/6 | **OK rc=0** | Entrée type runtime |
| `pytest tests/` (suite) | 3/3 | **AV 0xC0000005** | Souvent mid-suite ~79 % |
| `pytest tests/test_ux_06o.py` | 5/5 | **AV après 100 %** | Mode A |
| `pytest tests/test_ui_design_06l.py` | 5/5 | **AV après 100 %** | Mode A |
| `pytest … -p no:unraisableexception` (fichier UI seul) | variable | Parfois **rc=0** ; parfois **Fatal Python error: Aborted** (Shiboken, sans frame) après 100 % ; parfois encore AV | Atténue `gc_collect_harder`, **ne sécurise pas** la fin de process Qt |
| `pytest tests/test_freaccmd.py` | 5/5 | **OK rc=0** | Pas de Qt widgets |
| `pytest` batch non-UI (duplicates+pipeline+freaccmd) | 1 | **OK** | |
| `freaccmd --list-drives` | 5/5 | **OK** | Process enfant stable |
| `test_history_06n.py` / `test_ui_shell.py` seuls | souvent OK | **OK** | Teardown cartes plus soigné (06N) |

### 2.2 Distinction pytest vs application

| Critère | pytest UI | Application normale |
|---------|-----------|---------------------|
| `QApplication` | Fixture module, pas de `exec()`, processEvents partiel | `run_app()` → `app.exec()` puis `db.close()` |
| Destruction widgets | Implicite / GC pytest agressif (`gc_collect` ×5) | `close()` utilisateur / fin de process ordonnée |
| Plateforme | `QT_QPA_PLATFORM=offscreen` | `windows` |
| Crash observé ici | **Oui** | **Non** (0/5+6 cycles) |

### 2.3 Trace Mode A (confirmée)

```
....... [100%]
Windows fatal exception: access violation
Current thread … (most recent call first):
  Garbage-collecting
  File ".../_pytest/unraisableexception.py", line 33, in gc_collect_harder
  File ".../_pytest/unraisableexception.py", line 94, in cleanup
  …
  File ".../_pytest/config/__init__.py", …, in _ensure_unconfigure
```

Les points de tests sont **PASS** ; le code de sortie process devient `3221225477` (`0xC0000005`) **après** le reporting.

### 2.4 Trace Mode B (confirmée sur suite)

```
[ 79%] …
Windows fatal exception: access violation
  Garbage-collecting
  File ".../ui/wizard/archive_wizard.py", line … in _build_w4  (ou _build_w2 / _build_w5)
  File ".../archive_wizard.py", … in __init__
  File ".../tests/test_ui_design_06l.py", … in test_wizard_w4_has_cover_and_dup_banner
```

Interprétation : le GC Python s’exécute **pendant** l’allocation de widgets wizard ; un objet C++/Shiboken déjà invalide est finalisé → AV. Le numéro de ligne dans `_build_w*` varie (site d’allocation, pas la cause racine).

---

## 3. Analyse cycle de vie (lecture code)

### 3.1 Confirmé

1. **Crash = GC natif**, pas une assertion Python échouée.  
2. **Plugin pytest `unraisableexception`** appelle `gc_collect_harder(5)` en fin de session — déclencheur fiable du Mode A.  
3. **Hors pytest**, créer/détruire `MainWindow` / `ArchiveWizardPage` avec `deleteLater` + `processEvents` + `gc.collect()` **ne crash pas** (8 cycles).  
4. **freaccmd** et **discid.dll** (via loader AVM) sont stables en isolation.  
5. **Application Windows** : 5 cycles navigation Archivage↔Biblio↔Historique↔Paramètres + fermeture = OK ; 6 process `app.exec()`+quit = OK.

### 3.2 Hypothèses (fortes, non prouvées au niveau instruction CPU)

| ID | Hypothèse | Soutien |
|----|-----------|---------|
| H1 | Finalizer Shiboken / wrapper Qt détruit dans le mauvais ordre sous GC forcé | Stack toujours `Garbage-collecting` ; disparition partielle avec `-p no:unraisableexception` |
| H2 | Widgets UI de test sans teardown systématique (`MainWindow`, wizard, list widgets) laissent des proxies morts | Fichiers avec cleanup explicite (`history_06n`) plus souvent rc=0 |
| H3 | Accumulation multi-modules (plusieurs fixtures `qapp` module + freaccmd) fragilise la suite complète | Mode B surtout sur `pytest tests/` / enchaînements |
| H4 | Interaction secondaire fre:ac DLL injectée dans le process parent via subprocess répétés | **Faible** : freaccmd tests seuls OK ; isolate OK ; mais freac+design a parfois AV (corrélation ≠ cause) |

### 3.3 Non reproductible / hors scope

- Dump WinDbg / PDB Qt non réalisés (pas d’outil symbol installé dans ce mandat).  
- Crash utilisateur pendant rip réel : **non testé** (contrainte : pas d’extraction physique).  
- `0xC0000409` (stack buffer) : observé historiquement de façon intermittente ; **0 occurrence** dans la matrice 07A principale.

### 3.4 Points code pertinents (sans modification)

- `ui/main_window.py` — `run_app()` : cycle de vie sain (`exec` → `db.close()`).  
- `ui/wizard/archive_wizard.py` — `__init__` construit W1–W5 + `refresh_drives()` → `FreacCdRipper.list_drives()` (subprocess).  
- `tests/test_*` UI — `QApplication` en fixture `scope="module"` sans destruction ordonnée en fin de session.  
- `_pytest/unraisableexception.py` — `gc_collect_harder` en `cleanup`.

---

## 4. Risque utilisateur final

| Scénario utilisateur | Risque | Justification |
|----------------------|-------|---------------|
| Lancer l’app, naviguer, fermer | **Faible** | 0 crash / 11 process+cycles Windows |
| Archivage / rip | **Non évalué ici** (interdit) ; pas d’indice que le crash pytest soit le même chemin | Workers `QThread` non exercés dans ce diagnostic |
| CI / développeur `pytest` | **Élevé (confort)** | Faux signal « planté » alors que tests PASS ; codes sortie non fiables |
| Intégrité données / FLAC / SQLite | **Aucun lien observé** | Crash post-assert / hors I/O métier |

**Conclusion risque produit :** le défaut actuel **ne justifie pas un NO-GO produit**. Il justifie un correctif **côté tests / teardown Qt** (mandat suivant), pas une alerte stabilité runtime utilisateur sur la base des preuves 07A.

---

## 5. Plan de correction ciblé (proposition — non exécuté)

| Priorité | Action | Effet attendu |
|----------|--------|---------------|
| **P0** | Documenter que le rc process peut être `0xC0000005` après PASS ; juger la suite via JUnit / compteurs passed | CI honnête immédiatement |
| **P1** | Fixture session `qapp` unique + teardown ordonné : `close()` / `deleteLater` / `processEvents` / optionnellement `os._exit(0)` après écriture du rapport | Réduire Mode A |
| **P1** | Désactiver ou contourner `gc_collect_harder` pour les jobs UI (`-p no:unraisableexception` **ou** pytest-qt) | Mode A fortement atténué |
| **P1** | Isoler les tests UI dans des **sous-processus** (un fichier = un process) dans CI | Contient Mode B |
| **P2** | Généraliser le pattern 06N : couper callbacks/`Signal` avant `clear()` / destruction des `setItemWidget` | Moins de wrappers morts |
| **P2** | Éviter de laisser des `MainWindow`/`ArchiveWizardPage` orphelins en fin de test | Hygiène Shiboken |
| **P3** | Si besoin : WinDbg + symbol Qt sur un minidump Mode B | Preuve instruction-level |

**Hors scope recommandé :** refactor métier, migration SQLite, changement fre:ac, rip.

---

## 6. Preuves et artéfacts

| Fichier | Contenu |
|---------|---------|
| `.capture_avm07a/orchestrator.json` | Codes sortie isolate / app / matrix / shutdown×N |
| `.capture_avm07a/repro_matrix.json` | Suite×3, UI files, freaccmd×5, ordres |
| `.capture_avm07a/app_lifecycle.json` | 5 cycles Windows OK |
| `.capture_avm07a/isolate_crash.json` | freaccmd, discid, Qt×8 OK |
| `.capture_avm07a/teardown_focus.json` | Mode A vs `-p no:unraisableexception` ; app.exec×6 |
| `.capture_avm07a/full_no_unraisable.err` | Mode B stack suite |
| `scripts/diag07a/*.py` | Reproducteurs (conservés) |

---

## 7. GO / NO-GO

| Critère mandat | Évaluation |
|----------------|------------|
| Crash isolé ? | **Oui** — pytest/GC/Qt ; pas l’app normale dans les essais |
| Stabilité app normale démontrée ? | **Oui** (cycles + `app.exec`) dans les limites « sans rip » |
| Risque maîtrisé ? | **Oui** pour l’utilisateur final ; dette CI à traiter en 07B |
| **Verdict** | **GO** |

**Arrêt obligatoire :** attendre validation avant tout correctif ou reprise des travaux UX/UI.
