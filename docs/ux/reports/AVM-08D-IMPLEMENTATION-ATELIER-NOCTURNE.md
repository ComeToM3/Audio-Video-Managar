# Rapport AVM-08D — Implémentation Atelier nocturne

**Date :** 2026-11-03  
**Version :** 0.5.0  
**Direction :** A · Atelier nocturne (AVM-08C validé)  
**Référence :** `prototypes/avm_08c/directions/a-atelier-nocturne/app.html`  
**Preuve Windows :** captures `docs/ux/reports/assets/avm08d-*.png` · `platform=windows`  
**Arrêt :** validation visuelle explicite avant toute migration suivante

---

## Verdict

| Critère | Statut |
|---------|--------|
| Shell pilules flottantes (plus de sidebar 06L) | **OK** |
| Tokens Atelier nocturne centralisés Widgets + QML | **OK** |
| Polices Fraunces / Outfit embarquées (OFL) | **OK** |
| Bibliothèque QML restylée (hero, grille, bandeau) | **OK** — bridge Python inchangé |
| Archivage / Historique / Paramètres harmonisés (Widgets) | **OK** (peau sombre ; structure métier intacte) |
| `library_ui_mode` + repli Widgets | **OK** |
| Garde-fous 06K / SQLite / rip / FLAC / QThread | **Inchangés** |
| Captures 820 / 980 / 1120 / max | **OK** |
| Tests régression (fichier-par-fichier) | **0 failed** — teardown AV 07A possible |
| Qualité composition vs maquette | **Proche** — écarts listés §5 |
| **Verdict technique** | **GO technique AVM-08D** |
| **Validation visuelle utilisateur** | **EN ATTENTE** |

---

## 1. Ce qui a changé

| Zone | Fichiers | Nature |
|------|----------|--------|
| Tokens / QSS | `ui/theme.py` | Palette pierre / ambre, Fusion + palette sombre |
| Polices | `ui/fonts.py`, `ui/fonts/*.ttf` + OFL | Outfit + Fraunces via `QFontDatabase` |
| Shell | `ui/main_window.py` | Nav **pilules** ; shims `nav`/`tab_bar` masqués (API tests) |
| QML Theme | `ui/qml/AvmLibrary/Theme.qml` | Aligné tokens A |
| Bibliothèque QML | `LibraryPage.qml`, `AlbumCard`, `DetailPane`, `SearchBar` | Hero display, pochettes larges, détail bas |
| Host QML | `library_host.py` | Plus de préchargement QML en mode Widgets (lazy) |
| Widgets bibliothèque | `library_page.py` | Couleurs placeholder / détail → tokens |
| Wizard | `archive_wizard.py` | Couleur progression ambre |
| Tests | `test_ui_design_06l`, `test_ui_shell`, `test_ux_06o` | Accents / breakpoint pilules |
| Captures | `scripts/capture_avm08d_atelier.py` | 4 sections × 4 tailles + repli |

**Non modifié :** `library_bridge.py`, schéma SQLite, workers, 06K, fre:ac, packaging.

---

## 2. Design system appliqué

| Token | Valeur |
|-------|--------|
| Fond | `#141210` (+ glow `#2A2118` en QML) |
| Surface / elev | `#1C1917` / `#292524` |
| Encre / muted | `#FAFAF9` / `#A8A29E` |
| Accent | `#E8A54B` |
| OK / danger | `#6EE7B7` / `#FCA5A5` |
| Radius | 18 / 12–14 |
| Display / UI | Fraunces / Outfit (fallback Segoe) |

---

## 3. Captures Windows réelles

| Fichier | Vue |
|---------|-----|
| `assets/avm08d-library-{820,980,1120,maximized}.png` | Bibliothèque QML |
| `assets/avm08d-archive-*.png` | Archivage W1 |
| `assets/avm08d-history-*.png` | Historique |
| `assets/avm08d-settings-*.png` | Paramètres |
| `assets/avm08d-library-widgets-fallback-1120.png` | Repli Widgets |
| `avm08d-capture-meta.txt` | `platform=windows`, direction A |

Comparer à la maquette HTML et aux captures 06L/08B (crème / hybride non peinte).

---

## 4. Tests

| Parcours | Résultat |
|----------|----------|
| Suite fichier-par-fichier (JUnit) | **175 OK**, 0 fail, 0 error (hors 2 fichiers UI crashant au flush XML) |
| `test_ui_design_06l` / `test_ui_shell` / `test_ux_06o` / `test_library_qml_08b` / `test_history_06n` | Assertions **PASS** observées ; exit process parfois **0xC0000005** au teardown (AVM-07A) |
| QML bridge 08B | **5 PASS**, rc=0 |
| Échecs métier | **Aucun observé** |

---

## 5. Écarts restants vs maquette

| Écart | Gravité | Note |
|-------|---------|------|
| Wizard : stepper horizontal (pastilles) vs rail vertical maquette | P2 | Structure Widgets conservée volontairement |
| Barre « Interface classique… » au-dessus du QML | P3 | Repli obligatoire 08B — ton muted |
| Liste pistes absente du bandeau détail QML compact | P3 | Compacité maquette ; table complète en repli Widgets |
| Historique : layout 2 colonnes Widgets ≠ panneau maquette pixel-perfect | P2 | Peau + cartes OK ; pas de migration QML |
| Fatigue dark / contraste muted en journée | P2 | À valider utilisateur (réserve 08C) |
| Teardown pytest + Qt | P2 CI | Documenté 07A — hors critère runtime |

---

## 6. Implications AVM-09

- Icône cible : concept `avm08c-icon-atelier.jpg` → `.ico` multi-résolution.  
- Polices déjà embarquées (réduire la dette packaging).  
- **Pas d’empaquetage dans 08D.**

---

## 7. GO / NO-GO

| Décision | Verdict |
|----------|---------|
| Implémentation technique Atelier nocturne | **GO** |
| Validation visuelle utilisateur | **EN ATTENTE** |
| Migration QML wizard / Historique | **NO-GO** |
| AVM-09 packaging | **NO-GO** (mandat distinct) |

---

## Arrêt obligatoire

Attendre **validation visuelle explicite** avant toute nouvelle migration UI.  
Les tests techniques ne valident pas le design.
