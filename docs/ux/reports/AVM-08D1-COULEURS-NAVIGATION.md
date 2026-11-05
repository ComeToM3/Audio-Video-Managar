# Rapport AVM-08D.1 — Couleurs, profondeur et navigation

**Date :** 2026-11-03  
**Version :** 0.5.0  
**Prérequis :** AVM-08D GO technique ; rendu **non** validé → itération visuelle  
**Arrêt :** validation visuelle explicite avant AVM-09 / migration

---

## Verdict

| Critère | Statut |
|---------|--------|
| Palette officielle `#17191F` / ambre / iris / rose / jade | **OK** |
| Fond « peinture renversée » (ressource JPG optimisée) | **OK** |
| Barre latérale gauche (4 destinations) | **OK** — remplace les pilules |
| Harmonisation shell / QML / Widgets | **OK** |
| Bridge Python / repli Widgets / 06K | **Inchangés** |
| Captures Windows 820–1120 / max | **OK** |
| Tests UI ciblés | **26 PASS** observés ; teardown AV 07A possible |
| **Verdict technique** | **GO technique AVM-08D.1** |
| **Validation visuelle** | **EN ATTENTE** |

---

## 1. Palette

| Rôle | Hex |
|------|-----|
| Base | `#17191F` |
| Ambre (accent primaire) | `#F1B65C` |
| Iris (focus / secondaire) | `#7D8FE8` |
| Rose (alerte douce) | `#D782A6` |
| Jade (OK / succès) | `#58B9AA` |
| Encre / muted | `#F4F1EC` / `#A7AEBB` |

Typographie inchangée : **Fraunces** + **Outfit** (OFL).

---

## 2. Fond artistique

| Élément | Chemin |
|---------|--------|
| Source concept | `ui/assets/atelier_paint_canvas_src.jpg` + `docs/.../avm08d1-paint-canvas-source.jpg` |
| Version UI | `ui/assets/atelier_paint_canvas.jpg` (1920×1080, voile sombre lisibilité) |
| Shell | `AtelierRoot.paintEvent` — scale KeepAspectRatioByExpanding |
| QML Bibliothèque | `Image` + voile `#CC17191F` via `atelierBg` |

Pas d’animation ; une texture statique.

---

## 3. Navigation

Ordre affiché : **Bibliothèque → Archiver → Historique → Paramètres**.  
Indices stack / API tests **préservés** (0=Archiver, 1=Bibliothèque, …).

| Largeur | Comportement |
|---------|--------------|
| ≥ 900 px | Rail 196 px, libellés complets |
| < 900 px | Rail 76 px, libellés courts + tooltips, marque « AVM » |

Shims `nav` / `tab_bar` masqués (compat tests).

---

## 4. Captures (avant / après)

**Avant (08D pilules) :** `assets/avm08d-library-1120.png`  
**Après (08D.1) :**

| Fichier | Vue |
|---------|-----|
| `avm08d1-library-{820,980,1120,maximized}.png` | Bibliothèque |
| `avm08d1-archive-*.png` | Archivage |
| `avm08d1-history-*.png` | Historique |
| `avm08d1-settings-*.png` | Paramètres |
| `avm08d1-library-widgets-fallback-1120.png` | Repli Widgets |
| `avm08d1-capture-meta.txt` | `platform=windows` |

---

## 5. Tests

| Module | Résultat |
|--------|----------|
| `test_ui_shell` + `test_ui_design_06l` + `test_library_qml_08b` + `test_ux_06o` | **26 PASS** (dots) ; rc process parfois segfault teardown 07A |
| Échecs métier | **Aucun observé** |

---

## 6. Écarts résiduels

| Écart | Gravité |
|-------|---------|
| Wizard stepper toujours horizontal | P2 |
| Intensité du fond : peut encore être renforcée / adoucie selon goût | P2 |
| Rail étroit : abréviations (Bibl./Arch.) | P3 — volontaire |
| Historique Widgets ≠ maquette pixel | P2 |

---

## 7. GO / NO-GO

| Décision | Verdict |
|----------|---------|
| 08D.1 technique | **GO** |
| Validation visuelle | **EN ATTENTE** |
| AVM-09 | **NO-GO** |
| Migration QML wizard/Historique | **NO-GO** |

---

## Arrêt

Attendre validation visuelle explicite avant toute suite.
