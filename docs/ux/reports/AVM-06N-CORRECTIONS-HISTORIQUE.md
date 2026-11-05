# Rapport AVM-06N — Correction de l’Historique et fiabilisation UX

**Date :** 2026-11-03  
**Version :** 0.5.0  
**Suite :** **175 passed** (167 préservés + 8 `test_history_06n`)  
**Preuve Windows :** `platform=windows`, `hbar_max=0` aux largeurs 820 / 980 / 1120  
**Arrêt :** validation explicite avant ajustements visuels secondaires

---

## Verdict

| Anomalie 06M | Statut |
|--------------|--------|
| A-01 Sélection carte | **Corrigé** |
| A-02 Overflow horizontal | **Corrigé** (`hbar_max=0`) |
| A-03 Badges tronqués | **Corrigé** (état court + « Récupérable » séparé) |
| A-04 Codes fre:ac | **Corrigé** (résumé FR ; code en détail technique) |
| A-08 Reprendre trompeur | **Corrigé** (hors layout, jamais activé) |
| 167 tests préservés | **GO** (175 total) |

**Recommandation : GO technique AVM-06N.**

---

## 1. Diagnostic

| Cause | Effet |
|-------|--------|
| `QListWidget.setItemWidget` sans remontée de clic | Panneau bloqué sur « Sélectionnez une opération » |
| `sizeHint` / chips longs (`Échec · récupérable`) | Scrollbar horizontale + troncature |
| `humanize_error` laissait `code d’extraction = 4294967293` | Messages techniques en carte |
| Bouton « Reprendre » toujours enabled | Affordance fausse |

---

## 2. Corrections

| Fichier | Changement |
|---------|------------|
| `ui/sections/history_page.py` | `SelectableJobCard` (clic plein rectangle + enfants `WA_TransparentForMouseEvents`) ; `select_row()` ; scroll H off ; badges courts ; actions en colonne ; `btn_resume` hors layout |
| `ui/progress_labels.py` | Humanisation A-04 : codes returncode → « L’extraction audio n’a pas abouti. » + tech préservé |
| `tests/test_history_06n.py` | 8 tests (clic, clavier, largeurs, badges, humanize, table API) |

---

## 3. Captures Windows (après)

| Fichier | Largeur | Note |
|---------|---------|------|
| `assets/avm06n-history-1120.png` | 1120 | Sélection Échec + détail sync |
| `assets/avm06n-history-980.png` | 980 | Idem |
| `assets/avm06n-history-820.png` | 820 | Onglets étroits, `hbar_max=0` |
| `assets/avm06n-history-selected-completed.png` | 1120 | Terminé + « Ouvrir l’album » |
| `avm06n-capture-meta.txt` | — | `platform=windows`, `resume_visible=False` |

Comparaison conceptuelle avant : captures 06M `avm06m-history-*.png` (sélection défaillante, chips tronqués).

Régénération : `python scripts/capture_avm06n_history.py`

---

## 4. Tests

| Test | Couvre |
|------|--------|
| `test_card_click_selects_and_updates_detail` | A-01 + A-04 |
| `test_keyboard_row_change_updates_detail` | Clavier / currentRow |
| `test_no_horizontal_overflow_at_widths` | A-02 (820/980/1120) |
| `test_badges_short_and_recoverable_separate` | A-03 |
| `test_humanize_*` | A-04 |
| `test_table_api_still_works` | Compat 06H |
| Suite complète | **175 collected / passed** |

---

## 5. Risques résiduels

| Risque | Niveau | Note |
|--------|--------|------|
| Chemins absolus longs dans le panneau détail | Faible | Hors P1 ; elision = polish secondaire |
| Teardown Qt / probe fre:ac parfois bruyant sous pytest | Faible | Intermittent hors Historique ; pas reproduit en session `platform=windows` interactive capture |
| Actions toujours en bas du panneau (pas inline 06J) | Faible | Accepté (périmètre limité) |

---

## 6. Non-objectifs respectés

Aucun rip, QML, DVD, changement SQLite v4 / 06K / fre:ac pipeline, ni mutation FLAC Queen / jobs historiques.

---

## 7. Arrêt

**AVM-06N terminé — GO.**  
Attendre validation avant les polish secondaires (elision chemins, densités, etc.).
