# Rapport AVM-06H — Modernisation UX/UI PySide6

**Date :** 2026-11-03  
**Version :** 0.5.0  
**Suite :** **136 passed**  
**Arrêt :** attendre validation avant tout mandat suivant

---

## Verdict

| Critère | Résultat |
|---------|----------|
| Parcours 5 étapes compréhensible | **GO** |
| Bibliothèque utilisable (SQLite) | **GO** |
| Historique utilisable (SQLite) | **GO** |
| Progression / annulation / succès = publish OK | **GO** (conservé + sous-étapes) |
| Accessibilité de base | **GO** (focus, noms, contraste) |
| Pas de régression métier / 127→136 tests | **GO** |
| Queen / jobs historiques intacts | **GO** |
| Pas de rip / DVD / lecteur audio | **Respecté** |

**Recommandation : GO technique AVM-06H.** Attendre validation mandant.

---

## 1. Audit initial (réutilisation)

| Composant | Décision |
|-----------|----------|
| `MainWindow` + nav 4 sections | Conservé ; pages réelles à la place des stubs |
| `ArchiveWizardPage` W1–W5 | Affiné (stepper, progression, a11y) — pas de rewrite |
| Workers QThread | Inchangés |
| `theme.py` QSS | Enrichi (focus, titres, tables) |
| Pipeline / D-011…D-015 | Non modifiés |

---

## 2. Harmonisation visuelle

| Élément | Changement |
|---------|------------|
| Typo | Segoe UI, titres 18px `#pageTitle` / `#wizardTitle` |
| Couleurs | Accent `#0B6E4F`, fond `#F7F6F3`, textes contrastés (`#4A4A4A` muted) |
| Focus | Bordure 2px accent sur boutons, champs, nav |
| Stepper | Propriétés `step` / `active` / `done` |
| Terminologie | Étape 4 : **Extraction / publication** ; libellés FR inchangés côté métier |

**Description vérifiable (offscreen) :** fenêtre 1100×720, sidebar 200 px, 4 entrées nav ; wizard avec 5 pastilles d’étapes ; Bibliothèque liste + détail ; Historique table 4 colonnes.

---

## 3. Wizard — parcours 5 étapes

1. **Disque** — lecteur, Relire, TOC  
2. **Identification** — MB, pochette cache, alternatives  
3. **Approbation** — formulaire + pistes + Approuver explicite (D-015)  
4. **Extraction / publication** — collision, publish obligatoire, sous-étapes + barre + Annuler  
5. **Terminé** — succès **uniquement** si `Completed*` + publish ; boutons dossier + **Voir l’historique**

Navigation : Retour sécurisé (A3 conserve Approved sans édition) ; session conservée entre sections.

Sous-étapes W4 : Vérification → Extraction → Contrôle → Tags/pochette → Organisation → Publication (mise en avant via `progress_step_index`).

---

## 4. Bibliothèque (UI-3)

Fichier : `ui/sections/library_page.py` + `storage/catalog.py`

| Capacité | Détail |
|----------|--------|
| Liste | `releases` tri `imported_at` |
| Recherche | Filtre artiste/album |
| Détail | Métadonnées + table pistes |
| Chemins | Badge « dossier manquant » si `Path` absent |
| Actions | Ouvrir album / ouvrir racine biblio / Actualiser |
| Non fait | Lecteur audio, grille fancy, édition tags |

---

## 5. Historique (UI-2)

Fichier : `ui/sections/history_page.py`

| Capacité | Détail |
|----------|--------|
| Table | Date, état FR, mode, id court |
| Détail | warnings, library_path, workdir, erreur |
| Ouvrir album / workdir | Si dossiers existent |
| Abandonner | `state=Abandoned` — **aucune suppression fichier** |
| Reprendre | Message honnête « non disponible pour cet état » (pas de faux backend) |

---

## 6. Accessibilité

- `setAccessibleName` sur nav, listes, progression, CTAs  
- Focus visible QSS  
- Textes sélectionnables sur chemins  
- Pas d’emoji ; contrastes renforcés sur muted/warning/error  
- Redimensionnement : breakpoint 900 px (sidebar ↔ onglets) conservé  

Limite : pas d’audit Narrator exhaustif automatisé ; fondamentaux seulement.

---

## 7. Performance UI

- Traitements longs restent hors thread UI (workers)  
- Refresh Bibliothèque/Historique à l’affichage / navigation (requêtes SQLite bornées `LIMIT 200`)  
- Pas de polling coûteux  

---

## 8. Tests

| Fichier | Couverture |
|---------|------------|
| `tests/test_ui_library_history_06h.py` | catalog, pages, shell, stepper, signal historique |
| Suites existantes | shell, W3 prefill, collision, progress — **vert** |

**136 passed** (pytest).

---

## 9. Limites & non-objectifs

| Limite | Note |
|--------|------|
| Pas de rip réel dans ce mandat | Contraint |
| Replace collision toujours désactivé | AVM-06C |
| Reprise job incomplete | Message UI seulement |
| Pas de miniatures pochette en Bibliothèque | Chemin fichier seulement |
| Pas de i18n / thèmes sombre | Hors scope |
| Queen / bd40 | Non modifiés |

---

## 10. Recommandations suivantes (hors 06H)

| Pri | Idée |
|-----|------|
| P1 | Dialogue confirmation Replace |
| P1 | Miniatures cover.jpg dans Bibliothèque |
| P2 | Filtres Historique par état |
| P2 | Audit Narrator manuel checklist |

---

## 11. Fichiers touchés

| Chemin | Rôle |
|--------|------|
| `ui/theme.py` | QSS 06H |
| `ui/main_window.py` | Library/History + nav refresh |
| `ui/wizard/archive_wizard.py` | Stepper, sous-étapes, historique |
| `ui/progress_labels.py` | `PIPELINE_STEPS` / index |
| `ui/sections/library_page.py` | **nouveau** |
| `ui/sections/history_page.py` | **nouveau** |
| `storage/catalog.py` | **nouveau** requêtes |
| `tests/test_ui_library_history_06h.py` | **nouveau** |
| `docs/ux/reports/AVM-06H-MODERNISATION-INTERFACE.md` | ce rapport |

---

**Fin AVM-06H — arrêt obligatoire. Attendre validation explicite avant mandat suivant.**
