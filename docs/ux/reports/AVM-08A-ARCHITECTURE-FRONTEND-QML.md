# Rapport AVM-08A — Architecture frontend Qt Quick/QML

**Date :** 2026-11-03  
**Version :** 0.5.0  
**Contexte :** AVM-07B validé ; Widgets restent l’UI de production  
**Prototype :** `prototypes/avm_08a/` (isolé)  
**Preuve visuelle :** `platform=windows`, catalogue local lecture seule (1 album Queen GH)  
**Arrêt :** validation avant toute migration / intégration QML dans l’app principale

---

## Verdict

| Question | Réponse |
|----------|---------|
| QML apporte-t-il un gain perceptible vs Widgets/QSS ? | **Oui** sur Bibliothèque (grille, survol, composition) |
| Remplacer toute l’UI maintenant ? | **Non** |
| Prochaine étape recommandée | **Migration progressive** : Bibliothèque QML en vue embarquée (hybride), wizard Widgets |
| Prototype exécutable ? | **Oui** — `python prototypes/avm_08a/run.py` |
| Production Widgets intacte ? | **Oui** |
| **Recommandation** | **GO architecture** pour une phase 08B d’intégration hybride Bibliothèque — **NO-GO** remplacement global |

---

## 1. Audit transversal (Widgets actuel)

### 1.1 Inventaire par écran

| Écran | Composants clés | Interactions | États | Forces | Incohérences / omissions |
|-------|-----------------|--------------|-------|--------|---------------------------|
| **Shell** | Nav liste / onglets &lt;900 px, header statut | 4 sections, verrou busy 07B | Lecteur OK/manquant, busy | Stable, a11y noms | Statut outil vs CD parfois confus |
| **W1 Disque** | Combo lecteur, Relire, détails tech, bandeau 06K | Relire TOC, Continuer | Vide / CD détecté / doublon | Disc ID replié (06O) | Vide vertical résiduel |
| **W2 Identification** | Cover, métas, alts, worker | Identifier, choisir édition | Loading réseau, échec soft | Découplé worker | Peu de skeleton loading |
| **W3 Approbation** | Formulaire dense, empreinte A3 | Éditer, Approuver, doublon gate | Brouillon / approuvé / révoqué | Règles métier claires | Densité visuelle élevée |
| **W4 Extraction** | Progress, steps, collision, cancel | Start, cancel, % réel | Busy, erreurs humanisées | Honest progress | Layout utilitaire |
| **W5 Terminé** | Résumé, ouvrir dossier, historique | CTA post-job | Succès / échec | Clair | Peu de célébration discrète |
| **Bibliothèque** | `QListWidget` IconMode, détail, pistes | Recherche, sélection, ouvrir | Vide, manquant, prêt | Données réelles, chemins amicaux | Moins fluide qu’une grille native ; peu d’animation |
| **Historique** | Cartes `setItemWidget`, panneau | Sélection 06N, actions | Terminé/Échec/… | Humanisé | Écart vs prototype 06J (actions sur carte) ; table masquée |
| **Paramètres** | Form + `QScrollArea` | Save, browse, tech test | Scroll 06O | Complet | Chemins absolus dans champs (nécessaire) |

### 1.2 Patterns transverses

| Pattern | Constat |
|---------|---------|
| Design tokens 06L | Cohérents (crème / forêt) mais rendu Widgets limité (élévation, hover riche) |
| Feedback | `QMessageBox` modal fréquent — casse le flux |
| Responsive | Breakpoint 900 OK ; SplitView QML plus naturel |
| Accessibilité | Bons `AccessibleName` ; focus QSS partiel |
| Async | Workers + `thread_lifecycle` 07B — **réutilisables** sous QML |

---

## 2. Architecture QML proposée

```
qml/
  app/
    MainShell.qml          # StackView 4 sections
    NavigationRail.qml
  pages/
    ArchiveWizard/*.qml    # plus tard — rester Widgets en P1
    LibraryPage.qml        # premier candidat
    HistoryPage.qml
    SettingsPage.qml
  components/              # design system
    AvButton.qml, AvChip.qml, AvCard.qml, AvSearchField.qml
    CoverArt.qml, EmptyState.qml, Stepper.qml
  theme/
    Theme.qml (singleton)  # tokens partagés avec Python
python/
  bridge/
    LibraryBridge.py       # QAbstractListModel + slots
    JobBridge.py           # plus tard
  # Métier inchangé : catalog, orchestration, extraction
```

### 2.1 Navigation & états

- `StackView` + `NavigationRail` (large) / `TabBar` (étroit &lt; 900).  
- État global `AppState` (busy, section, snackbar) exposé en `contextProperty` ou `QObject`.  
- Verrous busy 07B : même règles, côté bridge.

### 2.2 Pont Python ↔ QML

| Direction | Mécanisme |
|-----------|-----------|
| Données listes | `QAbstractListModel` + `roleNames` |
| Actions | `@Slot` sur bridge (`search`, `selectRow`, `openAlbum`) |
| Progress workers | Signaux existants → propriétés / modèles |
| Interdit | Logique métier dans QML ; écriture SQLite depuis QML |

### 2.3 Responsive

| Largeur | Bibliothèque |
|---------|--------------|
| &lt; 980 | `SplitView` vertical — grille au-dessus, détail dessous |
| ≥ 980 | Grille + panneau détail latéral |
| ≥ 1400 | Covers plus grandes (`coverLg`) |

---

## 3. Design system (Qt Quick)

### 3.1 Principes

1. **Chaleureux & minimal** — papier crème, accent forêt (continuité marque 06L).  
2. **Pochettes d’abord** — la grille domine ; le détail sert la sélection.  
3. **Motion utile** — scale carte 1.03, focus bordure, pas de confettis.  
4. **États explicites** — vide / chargement / erreur / manquant / prêt.  
5. **A11y** — `Accessible.name`, focus clavier GridView, contrastes WCAG-ish.

### 3.2 Tokens (singleton `Theme.qml`)

| Token | Valeur | Usage |
|-------|--------|-------|
| `bg` / `bgDeep` | `#F3F0E8` / `#EAE6DB` | Fond dégradé discret |
| `surface` | `#FFFFFF` | Cartes, champs |
| `inkTitle` / `ink` / `muted` | `#0A3D32` / `#1A1F1C` / `#5A635C` | Hiérarchie texte |
| `accent` | `#1B7A5C` | CTA, sélection |
| `radius` | 14 / 10 | Cartes / contrôles |
| Espacements | 6–36 | Grille 4/8 |

### 3.3 Composants prototype

`AlbumCard`, `SearchBar`, `DetailPane`, `EmptyState` — déjà dans `prototypes/avm_08a/qml/Avm08a/`.

---

## 4. Prototype Bibliothèque (preuve)

| Élément | Détail |
|---------|--------|
| Lancement | `python prototypes/avm_08a/run.py` |
| Données | `%LOCALAPPDATA%\AudioVideoManager\avm.sqlite3` **lecture seule** (fallback démo) |
| Fonctions | Grille, recherche, sélection, panneau détail + pistes |
| Non-buts | Ouverture dossier no-op ; pas d’écriture ; pas dans `main_window` |

### Captures Windows réelles

| Fichier | Largeur | Note |
|---------|---------|------|
| `assets/avm08a-library-1120.png` | 1120 | Split horizontal, cover Queen réelle |
| `assets/avm08a-library-980.png` | 980 | |
| `assets/avm08a-library-820.png` | 820 | Split vertical |
| `assets/avm08a-library-maximized.png` | ~1707 | |
| `avm08a-capture-meta.txt` | | `platform=windows`, `albums=1`, source catalogue local |

**Réel** : captures Qt Quick `windows` (pas offscreen).  
**Simulation** : aucune extraction ; CTA « Ouvrir » volontairement inactif.

---

## 5. Matrice comparative QML vs Widgets/QSS

| Critère | Widgets + QSS (prod) | Qt Quick (prototype 08A) | Gagnant |
|---------|----------------------|---------------------------|---------|
| Qualité visuelle grille | Bonne | **Supérieure** (hover, radius, composition) | QML |
| Wizard / formulaires denses | **Mature** | Possible mais coût élevé | Widgets |
| Interactions fluides | Limitées | Naturelles | QML |
| Perf grilles images | OK petite biblio | Meilleure virtualisation | QML |
| Accessibilité Win | **Plus rodée** ici | À durcir | Widgets (aujourd’hui) |
| Maintenabilité équipe | Maîtrisée | Courbe QML | Widgets court terme |
| Complexité pont | N/A | Modérée (models/slots) | — |
| Coût migration globale | — | **Élevé** | — |
| Risque régression métier | Faible si inchangé | Élevé si wizard migré trop tôt | — |
| Stabilité threads 07B | OK | Réutilisable tel quel | Égalité |

**Synthèse :** QML justifie un investissement **ciblé Bibliothèque (puis Historique)** ; le wizard et Paramètres restent Widgets jusqu’à critères d’acceptation atteints.

---

## 6. Migration progressive

### Phase 08B (si GO) — Hybride Bibliothèque

1. Embarquer `QQuickWidget` / `QQuickView` dans la section Bibliothèque **ou** fenêtre prototype basculable par flag.  
2. Bridge production : mêmes `list_releases` / `list_tracks` ; ouvrir dossier via slot Python.  
3. Critères d’acceptation : recherche, sélection, a11y clavier, 820/1120/max, 187+ tests, aucun rip, flag off = Widgets.

### Phase 08C — Historique QML

Cartes + actions inline (rapprochement intention 06J).

### Phase 08D+ — Wizard (optionnel)

Uniquement si 08B/C stables ; migrer étape par étape (W1 d’abord).

### Points de décision

| Gate | Condition pour continuer |
|------|---------------------------|
| G1 | Prototype 08A validé (ce rapport) |
| G2 | Intégration hybride Bibliothèque sans régression busy/07B |
| G3 | Historique QML + a11y OK |
| G4 | Décision explicite avant tout QML wizard |

---

## 7. Risques

| ID | Risque | Mitigation |
|----|--------|------------|
| R1 | Double stack Widgets+QML | Feature flag ; une section à la fois |
| R2 | A11y QML sous-estimée | Checklist NVDA/focus dès 08B |
| R3 | Divergence tokens QSS/QML | Theme.qml aligné sur `theme.TOKEN` |
| R4 | Tentation rewrite wizard | Interdit avant G4 |
| R5 | Confusion prod / prototype | README + bandeau « Lecture seule » |

---

## 8. GO / NO-GO

| Décision | Verdict |
|----------|---------|
| Architecture & design system documentés | **GO** |
| Prototype Bibliothèque prouvé sous Windows | **GO** |
| Remplacer l’UI production maintenant | **NO-GO** |
| Autoriser mandat **08B intégration hybride Bibliothèque** | **GO conditionnel** (après validation utilisateur de 08A) |

**Arrêt obligatoire :** attendre validation avant migration ou intégration QML dans l’application principale.
