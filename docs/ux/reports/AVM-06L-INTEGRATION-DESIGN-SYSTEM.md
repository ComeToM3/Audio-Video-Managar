# Rapport AVM-06L — Intégration du design system moderne

**Date :** 2026-11-03  
**Version :** 0.5.0  
**Suite :** **167 passed** (159 préservés + 8 `test_ui_design_06l`)  
**Arrêt :** validation explicite requise avant tout mandat suivant

---

## Verdict

| Critère | Résultat |
|---------|----------|
| M0 Design system Fusion/QSS centralisé | **GO** |
| M1 Historique en cartes + actions contextuelles | **GO** |
| M2 Bibliothèque grille pochettes + recherche + vides | **GO** |
| M3 Wizard modernisé (pastilles, W4 2 colonnes, progression) | **GO** |
| Garde-fous 06K intégrés au parcours (ouvrir album > réarchiver) | **GO** |
| Responsive < 900 px + focus / contrastes | **GO** |
| 159 tests métier préservés | **GO** (167 total) |
| Aucun rip / QML / DVD / mutation FLAC Queen | **GO** |

**Recommandation : GO technique AVM-06L.**

---

## 1. M0 — Design system

| Élément | Détail |
|---------|--------|
| Fichier | `audio_video_manager/ui/theme.py` |
| Tokens | Fond `#F3F0E8`, surface blanc, accent `#1B7A5C`, encre `#0A3D32`, chips ok/warn/err |
| Application | `apply_app_style(app)` → **Fusion** + QSS global |
| Widgets | `ui/widgets.py` — `make_card`, `make_chip`, `empty_state_card` |
| Shell | Marque « AudioVideo Manager » dans l’en-tête |

Direction : premium minimaliste, chaleureux, fonctionnel — alignée prototypes 06J.

---

## 2. M1 — Historique

- Cartes statut (`historyCards`) avec chips Terminé / récupérable / Échec
- Panneau détail + actions hiérarchisées (« Ouvrir l’album » primaire si publié)
- `QTableWidget` **conservé masqué** pour compat API tests 06H (`table.rowCount` / `selectRow`)
- Aucune suppression automatique de fichiers

---

## 3. M2 — Bibliothèque

- Grille `IconMode` (`albumGrid`), pochettes 120 px (96 px étroit)
- Recherche `#search`, détail album + chip Prêt / Fichiers manquants
- État vide en carte (CTA implicite vers archivage)
- Limite catalogue 500 albums (virtualisation native QListWidget)

---

## 4. M3 — Archivage

- Stepper pastilles (actif / fait / à venir)
- W4 : carte progression (piste/sous-étapes, barre réelle) + carte pochette / options collision
- Progression : titres via mapping 06I inchangé ; pas de % inventé

---

## 5. Garde-fous 06K dans le parcours

| Gate | UX |
|------|-----|
| Lecture disque | Bandeau inline (pas de modal) — démarrage app non bloqué |
| Approbation | Message court + rappel « ouvrir l’album » prioritaire |
| Pré-extraction | Dialog : **Ouvrir l’album existant** (défaut) → **Réarchiver volontairement…** (secondaire, 2ᵉ confirm) → Annuler |
| Domaine | Inchangé (`duplicates.py` + `run_archive_job`) |

---

## 6. Captures (écrans réels app)

| Fichier | Vue |
|---------|-----|
| `docs/ux/reports/assets/avm06l-archive.png` | Archivage (wizard) |
| `docs/ux/reports/assets/avm06l-library.png` | Bibliothèque grille |
| `docs/ux/reports/assets/avm06l-history.png` | Historique cartes |
| `docs/ux/reports/assets/avm06l-shell-narrow.png` | Mode étroit (< 900 px) |

Régénération : `python scripts/capture_avm06l.py`

Références prototypes 06J (avant conceptuel) : `docs/ux/reports/assets/avm06j-*.png`

---

## 7. Tests

| Fichier | Couverture |
|---------|------------|
| `tests/test_ui_design_06l.py` | Tokens QSS, grille IconMode, empty, missing, cartes historique, W4 cover/bandeau, path doublon, narrow |
| Suite complète | **167 passed** |

Parcours validés : redimensionnement, navigation, bibliothèque/historique, doublons domaine, états vides. Approbation / W3 : suites 06H/shell/prefill inchangées.

---

## 8. Risques résiduels

| Risque | Niveau | Note |
|--------|--------|------|
| Fusion sous `offscreen` / certains drivers | Faible | QSS appliqué ; rendu desktop réel = référence |
| Grille QListWidget vs milliers d’albums | Moyen | OK ~centaines ; QML grille réservée mandat ultérieur (06J M4) |
| Table historique masquée (dette API tests) | Faible | Peut être retirée quand les tests cibleront `list` |
| Modales doublon encore présentes en gate 3 | Acceptable | Une seule, centrée « ouvrir » ; gate 1 sans modal |
| Captures offscreen (glyphes) | Faible | Même limitation que 06J ; HTML 06J reste intention visuelle |

---

## 9. Non-objectifs respectés

- Pas de migration QML, pas de lecteur audio, pas de DVD  
- Pas de rip physique, pas de modification FLAC Queen / jobs historiques  
- D-011…D-015, SQLite v4, fre:ac, protections 06K **préservés**

---

## 10. Arrêt

**AVM-06L terminé.**  
Présenter ce rapport, les captures et le verdict **GO**.  
**Attendre validation explicite avant tout mandat suivant.**
