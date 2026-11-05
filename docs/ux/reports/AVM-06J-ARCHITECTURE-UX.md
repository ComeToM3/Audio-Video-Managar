# Rapport AVM-06J — Architecture UX/UI et prototypes modernes

**Date :** 2026-11-03  
**Version :** 0.5.0  
**Suite métier :** **146 passed** (inchangée — prototypes hors `audio_video_manager/`)  
**Arrêt :** validation explicite requise avant implémentation générale

---

## Verdict

| Question | Réponse |
|----------|---------|
| Stack recommandé | **Qt Widgets + design system QSS (Fusion)** — évolution progressive |
| QML / Qt Quick | **Non** comme migration globale ; option **ciblée** plus tard pour grille Bibliothèque |
| Prototypes | **3 écrans** exécutables + références HTML responsive |
| Impact métier / FLAC / tests | **Aucun** |

**Recommandation unique :** moderniser l’existant Widgets par un **design system** (tokens, cartes, stepper, états) sans réécrire le pipeline ni basculer tout le shell en QML.

---

## Phase 1 — Évaluation technique

### 1.1 Architecture actuelle (inventaire)

| Zone | Fichiers clés | Style |
|------|---------------|-------|
| Shell | `ui/main_window.py` | `QListWidget` + `QStackedWidget`, breakpoint 900 px |
| Wizard | `ui/wizard/archive_wizard.py` | 5 étapes, workers QThread |
| Bibliothèque / Historique | `ui/sections/library_page.py`, `history_page.py` | Listes / tables SQLite |
| Thème | `ui/theme.py` | QSS global, accent forêt `#0B6E4F` |
| Hors UI | `archive_worker`, `identify_worker`, `progress_labels` | Métier découplable |

**Réutilisable tel quel :** workers, repositories, catalog SQLite, fingerprint A3, progress mapping 06I, navigation 4 sections.

**Limitations réelles :**
- Look « utilitaire Windows » (widgets natifs, peu de cartes, densités irrégulières).
- QSS partiel sous style native Windows (progress, listes).
- Bibliothèque : liste + icônes, pas encore une grille « pochette d’abord ».
- Peu de micro-interactions (survol, élévation) sans peindre custom.

### 1.2 Comparaison Widgets / QML / hybride

| Critère | Widgets + QSS | Qt Quick / QML | Hybride (Widgets shell + QML views) |
|---------|---------------|----------------|-------------------------------------|
| Modernité visuelle | Bonne avec design system + Fusion | Excellente (animations, grilles) | Excellente sur zones QML |
| Responsive | Layouts Qt classiques (déjà 900 px) | Naturel (anchors/layouts QML) | Possible, 2 modèles à coordonner |
| Accessibilité Win | Mature (`AccessibleName`, focus) | Possible mais plus de pièges | Double surface à tester |
| Perf listes/covers | OK jusqu’à milliers avec virtualisation limitée | Meilleure pour grilles images | QML pour grille seule |
| Maintenance équipe | **Déjà maîtrisé** | Courbe QML + tooling | Complexité max |
| Coût migration | **Faible–moyen** | **Élevé** (réécriture UI) | Moyen–élevé |
| Risque régression métier | Faible si QSS/layout only | Élevé (réécriture liaisons) | Moyen (ponts Widgets↔QML) |

### 1.3 Risques

| ID | Risque | Mitigation |
|----|--------|------------|
| R1 | Migration QML totale casse wizard/A3 | Ne pas migrer le wizard en premier |
| R2 | QSS ignoré par style native | **Fusion** + tokens documentés |
| R3 | Animations décoratives | Interdites hors feedback utile (focus, état) |
| R4 | Double stack hybride | Réserver QML à Bibliothèque v2 seulement |

### 1.4 Recommandation argumentée

**Choisir Widgets + design system QSS (style Fusion).**

Pourquoi :
1. Le parcours 5 étapes, l’approbation et les workers sont **déjà stables** (146 tests).
2. Le gap perçu est surtout **visuel / hiérarchique**, pas un plafond technique Widgets.
3. Une migration QML globale offrirait peu de valeur métier pour un coût élevé et un risque de régression UX (D-011…D-015, busy lock, fingerprint).
4. Si la grille pochettes devient insuffisante en Widgets, introduire **une** vue QML Bibliothèque (phase ultérieure) sans toucher au wizard.

---

## Phase 2 — Langage visuel & prototypes

### 2.1 Direction « hybride musical »

| Token | Valeur | Rôle |
|-------|--------|------|
| Fond | `#F3F0E8` | Papier chaud |
| Surface | `#FFFFFF` | Cartes |
| Encre | `#0A3D32` / `#1A1F1C` | Titres / corps |
| Accent | `#1B7A5C` | CTA, progression |
| Muted | `#5A635C` | Secondaire |
| Radius | 10–14 px | Cartes / boutons |
| Type | Segoe UI | Desktop Windows |

Principes : **pochette valorisée**, peu de chrome, stepper lisible, états vides/erreur explicites, focus 2 px, pas de dark mode imposé, pas de violet « AI default ».

### 2.2 Prototypes livrés

| Prototype | Contenu | Responsive |
|-----------|---------|------------|
| **Archivage** | Stepper 5, carte progression + titres de pistes, sous-étapes, pochette, Annuler | Colonne unique < 900 px |
| **Bibliothèque** | Recherche, grille 3 cartes, badges Prêt / manquants, bandeau détail | 1 colonne étroit |
| **Historique** | Cartes statuts (Terminé / récupérables / Échec), actions disponibles seulement | Empilement naturel |

**Exécutable isolé (PySide6) :**

```bash
python prototypes/avm_06j/run.py
```

**Références HTML inspectables (texte réel + media queries) :**

`prototypes/avm_06j/html/index.html`

**Captures de layout (Fusion / offscreen) :**

| Fichier | Vue |
|---------|-----|
| `docs/ux/reports/assets/avm06j-archive.png` | Archivage large |
| `docs/ux/reports/assets/avm06j-library.png` | Bibliothèque grille |
| `docs/ux/reports/assets/avm06j-history.png` | Historique cartes |
| `docs/ux/reports/assets/avm06j-shell-narrow.png` | Mode étroit |

> Note capture : sous `offscreen`, le glyphe Segoe peut apparaître dégradé ; le **HTML** et `run.py` restent les preuves textuelles / interactives de référence.

### 2.3 Inventaire composants prototype → cible app

| Composant prototype | Cible progressive dans l’app |
|---------------------|------------------------------|
| `navRail` + `navBtn` | Remplacer / styler `QListWidget#navList` |
| `card` (`QFrame#card`) | Envelopper wizard W4, items biblio/historique |
| Stepper pills | Enrichir `_step_buttons` wizard |
| `coverPlaceholder` / cartes album | `LibraryPage` grille |
| Chips ok/warn/err | Historique + badges manquants |
| `search` | Déjà présent — appliquer tokens |
| Progress Fusion | `QProgressBar` W4 |
| Empty state card | Bibliothèque vide |

---

## Plan de migration progressif

| Phase | Périmètre | Complexité | Risque | Tests |
|-------|-----------|------------|--------|-------|
| **M0** | Adopter Fusion + tokens QSS (sans changer layouts) | S | Faible | Suite UI existante |
| **M1** | Cartes Historique + chips récupérables (déjà partiel 06I) | S | Faible | `test_ui_library_history*` |
| **M2** | Bibliothèque en grille pochettes (Widgets) | M | Faible–moyen | Nouveaux tests layout |
| **M3** | Wizard : stepper pills, W4 en 2 colonnes (pochette + progression) | M | Moyen (régression wizard) | `test_ui_shell`, W3 prefill |
| **M4** *(option)* | Vue QML grille Bibliothèque si perf/visuel insuffisant | L | Moyen | Pont QWidget::createWindowContainer |
| **M5** | Interdit sans nouveau mandat : rewrite QML du wizard | XL | Élevé | — |

Estimation relative : **M0–M3 ≈ 3–6 jours-dev** selon polish ; **M4 ≈ +4–8 jours** ; **M5 à éviter**.

---

## Compromis

| Compromis | Choix |
|-----------|-------|
| Look « app store » immédiat vs stabilité | Stabilité d’abord ; look via QSS/cartes |
| Animations fluides QML | Uniquement feedback utile plus tard |
| Parité pixel HTML ↔ Qt | HTML = intention ; Qt = produit |
| Lecteur audio / DVD | Hors scope (contraintes) |

---

## Conformité contraintes

| Contrainte | Statut |
|------------|--------|
| Pas de rip / DVD / lecteur audio | **OK** |
| Pas de modif FLAC Queen / jobs historiques | **OK** |
| Pas de refonte pipeline | **OK** |
| 146 tests préservés | **OK** (vérifié) |
| Prototypes isolés du métier | **OK** (`prototypes/avm_06j/`) |

---

## Livrables

| Livrable | Chemin |
|----------|--------|
| Rapport | `docs/ux/reports/AVM-06J-ARCHITECTURE-UX.md` |
| Prototype PySide | `prototypes/avm_06j/run.py` |
| HTML | `prototypes/avm_06j/html/index.html` |
| Captures | `docs/ux/reports/assets/avm06j-*.png` |

---

**Fin AVM-06J — arrêt obligatoire.**  
Présenter : recommandation Widgets+QSS, prototypes Archivage/Bibliothèque/Historique, plan M0–M3.  
**Attendre validation explicite avant toute implémentation générale dans l’app.**
