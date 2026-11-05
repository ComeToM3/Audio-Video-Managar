# Rapport AVM-07B — Stabilité QThread et frontières Python/UI

**Date :** 2026-11-03  
**Version :** 0.5.0  
**Suite :** **187 passed** (182 + 5 `test_qthread_07b`) — 0 failed / 0 error (JUnit par fichier)  
**Crash réel analysé :** session 2026-11-03 ~17:39 — `0xC0000409` + `QThread: Destroyed while thread '' is still running`  
**Arrêt :** validation explicite avant conception Qt Quick/QML

---

## Verdict

| Question | Réponse |
|----------|---------|
| Cause du crash réel `technical_test` ? | **Confirmée** — `QThread` parenté à la fenêtre, détruite pendant le rip |
| Correctifs cycle de vie appliqués ? | **Oui** (minimal) |
| Repro Windows old→`0xC0000409` / new→`rc=0` ? | **5/5** chaque |
| Suite métier préservée ? | **187 PASS** |
| Crash pytest `0xC0000005` (07A) corrigé ? | **Non** (hors scope lifecycle worker — documenté séparément) |
| Prototype QML ? | **Non** (inventaire frontières seulement) |
| **Verdict** | **GO** |

---

## 1. Chronologie job `a31763eed2ae423eb78ded45b125667a`

Source : lecture seule `%LOCALAPPDATA%\AudioVideoManager\` (SQLite, `avm.log`, dossier jobs). **Aucun fichier modifié.**

| Heure locale (UTC−5) | UTC | Événement |
|----------------------|-----|-----------|
| 17:36:57 | | Lecteur fre:ac détecté |
| 17:37:03 | | TOC `D:` — Disc ID Queen GH, 17 pistes |
| 17:37:34–17:37:46 | | Navigation / Paramètres (probes freaccmd répétés) |
| **17:37:47** | **22:37:47Z** | **Job créé** `mode=technical_test`, `state=Ripping`, freaccmd `--track=all` démarré |
| 17:38:10 | | Probe freaccmd encore (UI vivante) |
| **17:39:03** | | **Dernière ligne log** (`freaccmd trouvé`) — puis silence process UI |
| 17:38–17:43 | | Fichiers `01.flac`…`17.flac` **continuent** d’être écrits (process fre:ac orphelin) |

### État SQLite (inchangé, constat)

| Champ | Valeur |
|-------|--------|
| `state` / `step` | `Ripping` |
| `finished_at` | `NULL` |
| `error_summary` | `NULL` |
| `mode` | `technical_test` |
| `workdir` | `...\jobs\a31763...\rip` |
| `publish_allowed` | `0` |

### Fichiers temporaires

17 pistes `.flac` + `.flac.temp` vides — rip quasiment complet **après** mort de l’UI. Cohérent avec destruction du `QThread` UI sans arrêt coopératif de fre:ac (le sous-processus a poursuivi).

---

## 2. Diagnostic causal

### Confirmé

1. `MainWindow._start_technical_test` créait `QThread(self)` → le thread est **enfant** de la fenêtre.  
2. Fermeture / destruction de `MainWindow` (ou de l’arbre Qt) **détruit le QThread C++ alors qu’il tourne** → message Qt + abort Windows **`0xC0000409`**.  
3. Même anti-pattern sur Identify / Archive : `QThread(self)` dans `archive_wizard.py`.  
4. Pas de `closeEvent` attendant les workers ; le test technique **ne verrouillait pas** la navigation/fermeture comme l’archivage.  
5. Repro synthétique Windows (`scripts/diag07b` / `.capture_avm07a/repro_qthread_windows_07b.json`) :
   - **Ancien** parent+destroy pendant run : **5/5** `0xC0000409`
   - **Nouveau** `attach` + `shutdown_worker_thread` : **5/5** `rc=0`

### Hypothèses secondaires (non nécessaires au correctif)

- La `QMessageBox` « Extraction démarrée » a pu précéder une fermeture rapide de la fenêtre.  
- Les probes freaccmd à 17:38–17:39 montrent une UI encore active peu avant le crash.

### Non lié (07A)

Les `0xC0000005` pytest / `gc_collect_harder` restent un problème de **harness de test** (GC Shiboken), distinct du crash runtime `0xC0000409` worker.

---

## 3. Corrections minimales

| Fichier | Changement |
|---------|------------|
| `ui/thread_lifecycle.py` | **Nouveau** — `attach_worker_thread` (QThread **sans** parent widget), `shutdown_worker_thread` (cancel + `wait` borné 12 s), `deleteLater` thread+worker **après** `finished` |
| `ui/main_window.py` | Tech test via helper ; verrou nav ; `closeEvent` annule+attend ; plus de `QThread(self)` |
| `ui/wizard/archive_wizard.py` | Identify/Archive via helper ; `shutdown_background_work()` |
| `tests/test_qthread_07b.py` | 5 tests (parent, shutdown, close simulé, subprocess rc, wizard idle) |

**Non fait (contraintes) :** pas de rip physique, pas de mutation du job `a31763…`, pas de changement pipeline/06K/SQLite, pas de `os._exit(0)`, pas de QML.

---

## 4. Tests Windows

| Preuve | Résultat |
|--------|----------|
| `pytest tests/test_qthread_07b.py` | **5 passed**, process **rc=0** |
| Repro old vs new (plateforme `windows`) | **5× STACK** / **5× OK** |
| Régression fichier-par-fichier | **187 passed**, 0 fail, 0 error |
| Exit process UI fichiers (07A) | Toujours AV/STACK **après** PASS — **non résolu ici** (attendu) |

---

## 5. Inventaire frontières Python / UI (préparation Qt Quick)

Objectif : cartographier ce qui peut rester en Python pur vs ce qui est collé aux Widgets — **sans migration**.

| Couche | Emplacement | Dépendance Qt | Future QML |
|--------|-------------|---------------|------------|
| Domaine / validation | `metadata/`, `library/duplicates.py` | Non | Réutiliser tel quel |
| Orchestration | `orchestration/rip_job.py`, `archive_job.py` | Non | Réutiliser ; progress via callbacks |
| Extraction | `extraction/` | Non | Réutiliser |
| Stockage | `storage/` | Non | Réutiliser |
| Workers | `ui/*_worker.py` | `QObject`/`Signal` mince | Remplaçables par `QThread`+QML ou bridge |
| Cycle thread | `ui/thread_lifecycle.py` | Qt Core | Conservable côté backend UI |
| Shell / nav | `ui/main_window.py` | Widgets | À remplacer (StackView) |
| Wizard | `ui/wizard/archive_wizard.py` | Widgets lourd | Candidat QML par étapes |
| Bibliothèque / Historique / Paramètres | `ui/sections/` | Widgets | Candidats QML |
| Design tokens / QSS | `ui/theme.py` | QSS Widgets | Tokens → Qt Quick Controls theming |
| Prototypes 06J | `prototypes/avm_06j/` | Widgets | Référence visuelle seulement |

**Frontière saine déjà présente :** workers n’embarquent pas de widgets ; le métier d’archivage est appelable sans UI. **Couplage restant :** construction wizard monolithique, dialogs `QMessageBox`, `QListWidget`+`setItemWidget` Historique.

---

## 6. Risques résiduels

| Risque | Gravité | Note |
|--------|---------|------|
| Job `a31763…` reste `Ripping` en base | P2 données | Lecture seule 07B ; recovery/abandon Historique possible ultérieurement |
| fre:ac orphelin si kill OS brutal | P2 | Cancel coopératif couvre fermeture UI ; pas SIGKILL |
| Timeout 12 s insuffisant si fre:ac bloque | P3 | `closeEvent` refuse de quitter (pas de masquage) |
| pytest `0xC0000005` / parfois `0xC0000409` teardown | P2 CI | Mandat 07A / futur harness — **pas** confondre avec runtime |
| IdentifyWorker sans `cancel` | P3 | Shutdown attend fin identify ; court en pratique |

---

## 7. GO / NO-GO

| Critère | Statut |
|---------|--------|
| Crash réel expliqué + corrigé | **Oui** |
| Preuve Windows avant/après | **Oui** |
| Tests concurrence ajoutés | **Oui** |
| Régression 187 PASS | **Oui** |
| Pas de prototype QML anticipé | **Oui** |
| **Verdict** | **GO technique AVM-07B** |

**Arrêt obligatoire :** attendre validation avant le mandat de conception Qt Quick/QML.
