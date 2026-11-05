# Rapport AVM-06O — Finition UX/UI et cohérence visuelle

**Date :** 2026-11-03  
**Version :** 0.5.0  
**Suite :** **182 passed** (175 préservés + 7 `test_ux_06o`) — 0 failed / 0 error (exécution fichier par fichier ; segfault GC Qt/fre:ac environnemental hors résultats)  
**Preuve Windows :** `platform=windows`, style appliqué Fusion puis enveloppe `QStyleSheetStyle` (QSS 06L)  
**Arrêt :** validation explicite GO/NO-GO avant tout autre mandat

---

## Verdict

| Anomalie 06M | Statut |
|--------------|--------|
| A-05 Disc ID hors parcours normal | **Corrigé** (plié sous « Détails techniques… ») |
| A-06 Chemins absolus dominants | **Corrigé** (libellés 1–2 segments + tooltip) |
| A-07 Fusion / QSS Windows | **Vérifié** (`QStyleFactory.create("Fusion")` + QSS ; méta capture `QStyleSheetStyle`) |
| A-09 Bibliothèque étroite / pochettes | **Amélioré** (stretch grille↑, icônes 100 px) |
| A-10 Bibliothèque maximisée | **Amélioré** (icônes 148 px ≥1400 px ; espace mort résiduel si peu d’albums) |
| A-11 Statut « CD N pistes » hors Archivage | **Corrigé** |
| A-13 Proportions W1 / Relire | **Amélioré** (`maxWidth` 280, aligné à gauche) |
| Paramètres scroll / troncature | **Corrigé** (`QScrollArea` + champs Expanding) |
| A-12 Table historique masquée | **Hors périmètre** (confirmé) |
| A-14 Actions sur carte Historique | **Hors périmètre** |
| 175 tests préservés | **GO** (182 total) |

**Recommandation : GO technique AVM-06O.**

---

## 1. Périmètre et méthode

### 1.1 Inclus

- Archivage W1 : Disc ID, proportions Relire, statut header.
- Bibliothèque : responsive 820 / 980 / 1120 / maximisé, chemins lisibles.
- Historique : libellés de chemins dans le détail (pas de refonte cartes).
- Paramètres : défilement vertical + champs chemin.
- Design system 06L : Fusion + QSS, a11y noms / focus préservés.

### 1.2 Exclus (contraintes respectées)

- Aucune extraction physique, fre:ac, SQLite v4, 06K, FLAC Queen, jobs historiques.
- Pas de QML, pas DVD, pas de nouvelle fonctionnalité métier.
- Suppression table historique masquée : hors périmètre.

### 1.3 Preuves vs simulations

| Type | Réel ? | Détail |
|------|--------|--------|
| Captures Qt `platform=windows` | **Oui** | `scripts/capture_avm06o_windows.py` → `docs/ux/reports/assets/avm06o-*.png` |
| Méta | **Oui** | `docs/ux/reports/avm06o-capture-meta.txt` |
| Suite pytest | **Oui** (logique) | 182 passed ; exit process parfois 0xC0000005 en GC (connu 06N) |
| Offscreen comme preuve visuelle | **Non** | Captures sans `QT_QPA_PLATFORM=offscreen` |
| Session CD optique live 06O | **Non rejouée** | W1 Disc ID simulé en UI pour capture ; comportement header validé en code + test |

---

## 2. Corrections

| Fichier | Changement |
|---------|------------|
| `ui/path_labels.py` | **Nouveau** — `friendly_path_label` / `path_tooltip` |
| `ui/wizard/archive_wizard.py` | Disc ID sous bouton « Détails techniques… » ; Relire `maxWidth=280` ; reset session |
| `ui/main_window.py` | Clear statut lecteur hors `NAV_ARCHIVE` ; `_on_status` filtré |
| `ui/theme.py` | `QStyleFactory.create("Fusion")` avant QSS |
| `ui/sections/library_page.py` | Chemins amicaux ; stretch grille/détail selon largeur ; tailles icônes 100/120/148 |
| `ui/sections/history_page.py` | Chemins amicaux + tooltip absolu dans le détail |
| `ui/sections/settings_page.py` | Contenu dans `QScrollArea` ; path rows Expanding |
| `tests/test_ux_06o.py` | 7 tests ciblés |
| `scripts/capture_avm06o_windows.py` | Captures Windows 820/980/1120/max |

---

## 3. Matrice d’acceptation

| Critère | Résultat | Preuve |
|---------|----------|--------|
| Aucun débordement horizontal majeur | **OK** observé | Captures archive / library / settings |
| Info essentielle non tronquée (Disc ID accessible, chemins via tooltip) | **OK** | W1 tech details ; history/library tooltips |
| Interface cohérente 06L | **OK** | Crème / accent forêt / cartes |
| Parcours métier inchangés | **OK** | Wizard 5 étapes ; 06K non touché |
| ≥175 tests | **182 PASS** | JUnit par fichier |
| Navigation clavier / AccessibleName | **Préservé** | Noms W1 tech, Relire, settings scroll ; pas d’audit NVDA |

---

## 4. Captures Windows

### 4.1 Avant (référence AVM-06M)

| Sujet | Asset 06M |
|-------|-----------|
| W1 Disc ID visible | `assets/avm06m-archive-1120.png` |
| Bibliothèque chemins longs | `assets/avm06m-library-1120.png` / `…-maximized.png` |
| Paramètres sans scroll dédié | `assets/avm06m-settings-1120.png` |

### 4.2 Après (AVM-06O)

| Fichier | Largeur | Note |
|---------|---------|------|
| `avm06o-archive-w1-1120.png` | 1120 | Disc ID **masqué** ; Relire compact |
| `avm06o-archive-w1-980.png` | 980 | Idem |
| `avm06o-archive-w1-820.png` | 820 | Mode onglets |
| `avm06o-archive-w1-tech-details.png` | 1120 | Disc ID visible après toggle |
| `avm06o-library-1120.png` | 1120 | `Dossier : Queen / 1992 - Greatest Hits` |
| `avm06o-library-980.png` | 980 | |
| `avm06o-library-820.png` | 820 | Grille prioritaire (stretch) |
| `avm06o-library-maximized.png` | ~1707 | Icônes plus grandes ; vide si 1 album |
| `avm06o-history-1120.png` | 1120 | `Album publié : Queen / 1992 - Greatest Hits` |
| `avm06o-settings-1120.png` | 1120 | Champs lisibles |
| `avm06o-settings-820.png` | 820 | |
| `avm06o-settings-scrolled.png` | 820 | Scroll vertical Avancé |

**Méta :** `platform=windows`, `style=QStyleSheetStyle`, `status_after_leave_archive=Outil d’extraction détecté`, `w1_tech_default_checked=False`.

---

## 5. Tests automatisés

| Module | Résultat |
|--------|----------|
| `tests/test_ux_06o.py` (7) | PASS — chemins, Disc ID, statut header, scroll Settings, Fusion/QSS tokens, biblio |
| Suite complète (29 fichiers) | **182 passed**, 0 failed, 0 error |
| Exit process UI | Parfois `0xC0000005` en GC après PASS (fre:ac / Qt) — **non régressif métier**, déjà documenté 06N |

---

## 6. Accessibilité

| Point | Statut |
|-------|--------|
| `AccessibleName` « Afficher les détails techniques du disque » | Ajouté |
| `AccessibleName` Relire / Paramètres scroll | Préservés / ajoutés |
| Focus ring QSS 06L | Inchangé |
| Tab order Paramètres (scroll) | Ordre logique contenu ; smoke seulement |

---

## 7. Risques résiduels

| Risque | Gravité | Note |
|--------|---------|------|
| Espace mort grille bibliothèque avec peu d’albums | P3 | Normal en IconMode ; densification limitée sans refonte |
| Titre pochette tronqué (`Greatest Hits…`) | P3 | `wordWrap` + gridSize ; acceptable |
| Chemins Paramètres encore absolus dans les champs éditables | P3 | Nécessaire pour édition ; tooltip + scroll |
| `objectName` style vide sous QSS | Info | Qt enveloppe Fusion → `QStyleSheetStyle` ; Fusion bien demandé |
| Segfault GC pytest UI | Env | Hors périmètre 06O |
| A-12 / A-14 | P3 | Toujours hors périmètre |

---

## 8. GO / NO-GO

| Question | Réponse |
|----------|---------|
| Anomalies secondaires 06M ciblées traitées ? | **Oui** (A-05, A-06, A-07, A-09–A-11, A-13 + Paramètres) |
| Architecture / design system 06L conservés ? | **Oui** |
| 175+ tests ? | **Oui (182)** |
| Preuves Windows réelles ? | **Oui** (pas offscreen seul) |
| **Verdict** | **GO technique AVM-06O** |

**Arrêt obligatoire :** attendre validation utilisateur avant tout autre mandat.
