# Rapport AVM-06 — UI-0 + UI-1

**Date :** 2026-11-03  
**Version app :** 0.5.0  
**Périmètre :** coquille 4 sections (UI-0) + wizard archivage 5 étapes (UI-1)  
**Hors scope (respecté) :** rip réel, UI-2…UI-4, AVM-06C

## 1. Verdict

**UI-0 et UI-1 livrés** : navigation PySide6, wizard branché sur les services AVM-05, protections A3 / D-011…D-015, R1–R3 appliqués. Suites de tests automatisées **PASS** (89). **Aucun rip réel** exécuté dans ce mandat.

**Attente :** validation explicite du mandant avant AVM-06C.

## 2. Livrables code

| Zone | Fichiers |
|------|----------|
| Shell UI-0 | `ui/main_window.py`, `ui/theme.py`, `ui/sections/*` |
| Wizard UI-1 | `ui/wizard/archive_wizard.py` |
| Workers | `ui/identify_worker.py`, `ui/archive_worker.py` (+ `rip_worker` pour test technique) |
| A3 / R3 | `metadata/approval_fingerprint.py` |
| R1 | `ui/cover_cache.py`, `paths.default_cover_cache_dir` |
| FR progress | `ui/progress_labels.py` |
| Tests | `tests/test_approval_fingerprint.py`, `test_progress_labels.py`, `test_cover_cache.py`, `test_ui_shell.py` |

## 3. Conformité arbitrages / règles

| ID | Statut | Notes |
|----|--------|-------|
| A3 | OK | Nav section conserve `Approved` ; edit / identité / nouvelle ID → `Pending` via `sync_approval_with_fingerprint` / `revoke_approval` (métier, pas seulement UI) |
| A4 / D-013 | OK | Test technique uniquement Paramètres → Avancé |
| D-011 | OK | `assert_can_start_archive_rip` avant ArchiveWorker |
| D-012 | OK | Validation existante + formulaire W3 |
| D-014 | OK | Stepper : W3 avant W4 |
| D-015 | OK | Auto-approve désactivé / grisé ; pays préféré libellé « départage » |
| R1 | OK | Cache `%LOCALAPPDATA%/AudioVideoManager/cache/covers` (hors `jobs/`) |
| R2 | OK | UI-1 exige publication cochée ; pas de reprise publish séparée |
| R3 | OK | SHA-256 JSON `sort_keys` UTF-8 `ensure_ascii=False` |
| DVD | OK | Masqué dans Archiver ; mention « non disponible » en Avancé |

## 4. Critères d’acceptation

### UI-0

| ID | Résultat |
|----|----------|
| AC-U0-1 | OK — démarrage sur Archiver, pas de probes forcés |
| AC-U0-2 | OK — 4 sections ; &lt;900 px → `QTabBar`, sinon barre latérale |
| AC-U0-3 | OK — test technique sous Avancé |
| AC-U0-4 | OK — pas de DVD dans le wizard Archiver |

### UI-1

| ID | Résultat |
|----|----------|
| AC-U1-1 | OK — 5 étapes ; avance contrôlée |
| AC-U1-2 | OK — `approve_sheet` ; rip bloqué sinon |
| AC-U1-3 | OK — test nav Bibliothèque puis retour conserve Approved |
| AC-U1-4 | OK — edit post-approve → Pending + message |
| AC-U1-5 | OK — changement Disc ID à la relecture → révocation |
| AC-U1-6 | OK — mismatch géré par pipeline AVM-05 (inchangé) |
| AC-U1-7 | OK — case « Publier… » obligatoire en UI-1 |
| AC-U1-8 | OK — `map_progress_message` |
| AC-U1-9 | OK — bouton ouvrir dossier si publish OK |
| AC-U1-10 | OK — cache + affichage pochette si URL |
| AC-U1-11 | OK — non-régression pipeline / meta / ranker / identify |
| AC-U1-12 | OK — aucun auto-approve |

## 5. Tests exécutés

```text
python -m pytest
# 89 passed
```

Nouveaux tests ciblés : empreinte A3, progression FR, cache pochettes, shell/nav/settings/wizard dirty.

## 6. Limites et écarts

1. **Pas de rip réel** — W4/W5 validés structurellement + pipeline staging AVM-05 ; premier CD physique = **AVM-06C**.
2. **Bibliothèque / Historique** — stubs informatifs (UI-3 / UI-2), aucune fausse fonctionnalité.
3. **Identify offline** — en échec réseau, fiche TOC minimale pour saisie manuelle W3.
4. **Confirm Replace** — radio + libellé corbeille ; boîte de dialogue supplémentaire de confirmation Replace non ajoutée (écart mineur vs wireframe maximal).
5. **API `revoke_approval`** — ajoutée en métier (résolvait l’écart signalé en 06B §2.2).

## 7. Arrêt

**Aucun** AVM-06C, **aucun** UI-2…4, **aucun** rip réel dans ce livrable.  
Prochaine étape après **GO écrit** du mandant : checklist rip réel [specs/08-acceptation-tests-plan.md](../specs/08-acceptation-tests-plan.md) §6.
