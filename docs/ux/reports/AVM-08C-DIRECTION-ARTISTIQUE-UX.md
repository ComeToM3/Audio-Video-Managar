# Rapport AVM-08C — Direction artistique et expérience utilisateur

**Date :** 2026-11-03  
**Version :** 0.5.0  
**Suite technique :** inchangée (192 PASS AVM-08B) — **aucun code production modifié**  
**Prérequis :** AVM-08B **GO technique**  
**Choix DA (utilisateur) :** **A · Atelier nocturne** — validé 2026-11-03  
**Arrêt :** attendre mandat explicite **AVM-08D** (pas de migration auto)

---

## Verdict

| Question | Réponse |
|----------|---------|
| AVM-08B validé techniquement ? | **Oui** (hybride QML + repli Widgets) |
| Direction artistique choisie ? | **A · Atelier nocturne** (choix utilisateur) |
| Cause du look « vieillot » | Composition formulaire, Segoe/Fusion, densité carte-document, nav latérale utilitaire |
| Livrable maquettes | **3 directions** HTML HF · `prototypes/avm_08c/` |
| Recommandation DA initiale | C · Étagère vinyle (écartée par le choix) |
| Direction officielle | **A · Atelier nocturne** |
| AVM-08D | **Prêt à démarrer** sur mandat explicite — nav pilules, thème sombre/ambre |
| AVM-09 | Icône cible : `avm08c-icon-atelier.jpg` — **pas d’empaquetage** |

---

## 1. Audit visuel de l’existant (production)

Périmètre audité via code + captures 06L / 08B : shell, Archivage W1–W5, Bibliothèque (Widgets + QML 08B), Historique, Paramètres, dialogues doublons / états secondaires.

### 1.1 État actuel

| Zone | Constat |
|------|---------|
| **Shell** | Nav latérale `QListWidget` + stack ; marque en en-tête texte ; chrome « outil bureau » |
| **Thème 06L** | Fusion + QSS, fond crème `#F3F0E8`, accent forêt `#1B7A5C`, **Segoe UI** |
| **Bibliothèque Widgets** | Grille IconMode 120 px, détail bas, recherche — mieux qu’une liste, mais « dossier Windows » |
| **Bibliothèque QML 08B** | Grille + chips dans un **cadre Widgets** : rupture de surface, double langage |
| **Archivage** | Stepper pastilles + champs/cartes — lecture claire, ton **formulaire administratif** |
| **Historique** | Cartes statut + panneau détail — utile, aspect **tableau de tickets** |
| **Paramètres / dialogues** | Widgets natifs, densité irrégulière, peu de hiérarchie émotionnelle |
| **Responsive** | Breakpoint ~900 px fonctionnel ; pas de re-composition narrative |

### 1.2 Causes précises du look daté

1. **Composition rigide** — colonnes nav | contenu fixes ; peu de respiration asymétrique ou de plans de profondeur.  
2. **Aspect formulaire / document** — labels, cadres 1 px, cartes blanches sur crème : métaphore « dossier papier » plus que « collection audio ».  
3. **Typographie système** — Segoe UI partout ; titres 22 px sans display distinct ; hiérarchie faible.  
4. **Densité** — chips + bordures + ombres légères partout → bruit sans présence.  
5. **Alignements** — grilles Widget/QML et panneaux détail non synchronisés (08B : îlot QML dans chrome 06L).  
6. **Bordures** — `border` crème partout (radius 10–14) = langage 2018 « soft card UI ».  
7. **Navigation** — liste latérale type settings Windows, pas une identité produit.  
8. **Hiérarchie** — pochette secondaire face au chrome ; la collection n’est pas le héros.  
9. **Iconographie** — peu d’icônes métier ; statut texte + chips uniquement.  
10. **Motion** — quasi nulle (sauf QML limité) ; transitions stack abruptes.

**Synthèse :** 06L a modernisé les *composants* ; le *système* reste un outil de bureau chaleureux, pas une expérience collection premium.

---

## 2. Trois directions artistiques

Maquettes isolées : [`prototypes/avm_08c/index.html`](../../../prototypes/avm_08c/index.html)  
Chaque app : Bibliothèque · Archivage · Historique · toggle **820 px**.

| | **A · Atelier nocturne** | **B · Clair de presse** | **C · Étagère vinyle** |
|--|--------------------------|-------------------------|------------------------|
| **Métaphore** | Studio d’écoute privé | Presse / outil nordique | Étagère de disques chez soi |
| **Climat** | Sombre, ambre, monumental | Clair, teal, aéré | Sauge, crème, cuivre |
| **Nav** | Pilules flottantes haut | Barre supérieure pleine largeur | **Dock bas** centré |
| **Type** | Fraunces + Outfit | Source Serif / DM Sans géométrique | Literata + Sora |
| **Bibliothèque** | Pochettes larges, hero typo | Grille aérée, chrome jour | Rangée LP + tiroir détail |
| **Archivage** | Rail d’étapes + panneau sombre | Carte claire centrée | **Carte unique** (pochette) |
| **Historique** | Liste + panneau | Colonnes jour | Timeline « ce qui s’est passé » |
| **Ton émotionnel** | Premium nocturne | Précision diurne | Chaleur tangible |
| **Risque DA** | Fatigue dark / contraste | Trop « SaaS clair » | Dock bas peu Windows-natif |
| **Fichier** | `directions/a-atelier-nocturne/` | `directions/b-clair-de-presse/` | `directions/c-etagere-vinyle/` |

Les trois sont **premium, minimalistes, chaleureuses, contemporaines et fonctionnelles** — différenciées par métaphore, chrome et hiérarchie, pas seulement par palette.

---

## 3. Design system (cible post-choix)

À figer **après** sélection de direction. Structure commune proposée :

### 3.1 Identité

| Élément | Règle |
|---------|--------|
| Nom produit | « AudioVideo Manager » — signal héros (pas seulement nav) |
| Promesse | Collection locale, sans cloud, archivage CD → FLAC |
| Voix UI | Courte, affirmative (« Ouvrir l’album » > jargon technique) |

### 3.2 Typographie

| Rôle | A | B | C |
|------|---|---|---|
| Display | Fraunces | Source Serif 4 | Literata |
| UI | Outfit | DM Sans / Outfit | Sora |
| Corps | 14–15 / 1.45 | 14–15 / 1.5 | 14 / 1.45 |
| Titres page | clamp 1.8–2.4 rem | 1.75 rem | 2 rem serif |

**Prod actuelle :** Segoe uniquement → à remplacer (embarquement polices AVM-09 ou liens QFontDatabase).

### 3.3 Espacements & surfaces

| Token | Proposition |
|-------|-------------|
| Échelle | 4 / 8 / 12 / 16 / 24 / 32 / 48 |
| Surface principale | Une « scène » dominante par écran (pas empilement de mini-cartes) |
| Radius | Direction-dépendant : A 18 · B 12 · C 20–24 |
| Ombre | 1 niveau d’élévation max ; pas de multi-layer glow |

### 3.4 Iconographie

- Style outline 1.5–2 px, grille 24.  
- Priorité : lecteur, album, dossier, statut (ok / manquant / échec).  
- Pas d’emoji ; icône app = symbole AVM (voir §5).

### 3.5 Navigation & interactions

| Pattern | Intention |
|---------|-----------|
| 4 destinations max | Bibliothèque, Archiver, Historique, Paramètres |
| Focus visible | Anneau 2 px accent, contraste WCAG AA |
| Hover | TranslateY −2–4 px sur pochettes uniquement |
| Clic primaire | Une action dominante par état (06K préservé) |

### 3.6 Animations discrètes

- Entrée scène 200–280 ms opacity + 6–8 px Y.  
- Changement d’étape wizard : cross-fade contenu, stepper inchangé.  
- **Pas** de parallax ni glow pulse.

### 3.7 Accessibilité

- Contraste texte/fond ≥ 4.5:1 (A dark : vérifier muted `#A8A29E` sur `#1C1917`).  
- Cibles ≥ 40×40 px (dock C).  
- QML : `Accessible.name` (déjà smoke 08B) + parcours clavier shell.  
- Réduire les motions si `prefers-reduced-motion`.

---

## 4. Identité Windows (préparation AVM-09, sans empaquetage)

### 4.1 Concept d’icône AVM

| Direction | Fichier concept | Idée visuelle |
|-----------|-----------------|---------------|
| A | `assets/avm08c/avm08c-icon-atelier.jpg` | Glyphe ambre / disque sur fond pierre sombre |
| B | `assets/avm08c/avm08c-icon-presse.jpg` | Marque claire, teal, lisible petite taille |
| C | `assets/avm08c/avm08c-icon-vinyle.jpg` | Pochette / vinyle + sauge — **recommandé** |

Exigences Windows : lisibilité 16/24/32/48/256 ; fond simple ; pas de texte « AVM » illisible en 16 px.

### 4.2 Fenêtre & barre des tâches

| Élément | Stratégie |
|---------|-----------|
| Icône fenêtre | `QApplication.setWindowIcon` / `.ico` multi-résolution |
| Titre | `AudioVideo Manager` (pas `python.exe`) |
| Taskbar | Même icône ; groupement AppUserModelID dédié (AVM-09) |

### 4.3 Lancement / distribution (stratégie seule)

1. **Court terme (08D)** : design + shell ; Python encore visible OK.  
2. **AVM-09** : icône AVM, AppUserModelID, ressources embarquées, lanceur / exécutable sans console, tests install.  
3. **Hors 08C** : pas de PyInstaller / Inno / MSIX dans ce mandat.

---

## 5. Comparaison & recommandation

| Critère | A | B | C |
|---------|---|---|---|
| Distinguabilité vs 06L crème | ★★★★★ | ★★★☆☆ | ★★★★☆ |
| Cohérence « collection audio » | ★★★★☆ | ★★☆☆☆ | ★★★★★ |
| Lisibilité jour / bureau | ★★☆☆☆ | ★★★★★ | ★★★★☆ |
| Faisabilité QML 08D | ★★★★☆ | ★★★★☆ | ★★★★☆ |
| Continuité garde-fous 06K | ★★★★★ | ★★★★★ | ★★★★★ |
| Identité Windows mémorable | ★★★★☆ | ★★★☆☆ | ★★★★★ |
| Risque rejet « trop sombre / trop SaaS » | Moyen-haut | Moyen | **Bas–moyen** |

### Recommandation initiale (rapport) : C · Étagère vinyle

Argumentaire historique conservé pour traçabilité ; **non retenue**.

### Choix validé : **Direction A · Atelier nocturne**

**Décision utilisateur (2026-11-03).** Positionnement studio premium sombre / ambre.

**Implications design figées pour 08D :**
- Chrome : fond pierre `#141210` / surfaces `#1C1917`–`#292524`, accent ambre `#E8A54B`.  
- Type : Fraunces (display) + Outfit (UI).  
- Nav : **pilules flottantes** (pas dock bas, pas barre top plein largeur).  
- Bibliothèque : pochettes monumentales, hero typo, détail en bandeau.  
- Archivage : rail d’étapes + panneau sombre.  
- Historique : liste + panneau détail.  
- Icône Windows (09) : concept `avm08c-icon-atelier.jpg`.

**Réserves à traiter en 08D :** contraste muted/fond (AA) ; fatigue dark en journée ; Paramètres en 4ᵉ pilule ou feuille.

---

## 6. Implications AVM-08D & AVM-09

### AVM-08D (cible : Direction A)

| Ordre | Travaux | Contrainte |
|-------|---------|------------|
| 1 | Tokens QML + Widgets = Atelier nocturne | Pas de changement métier |
| 2 | Shell : navigation **pilules** flottantes | Repli Widgets **conservé** |
| 3 | Bibliothèque QML : restyler (ambre/sombre), pas réécrire le bridge | `library_ui_mode` inchangé |
| 4 | Historique / wizard : skin Widgets A d’abord ; QML seulement si GO partiel | Stop migratoire si look rejeté |
| 5 | Référence visuelle : `prototypes/avm_08c/directions/a-atelier-nocturne/app.html` | Isolation prototypes |

**Interdit en 08D sans nouveau mandat :** SQLite, rip, FLAC, QThread, 06K, packaging.

### AVM-09

- Figer icône `.ico` à partir de **Atelier nocturne** (`avm08c-icon-atelier.jpg`).  
- AppUserModelID, manifeste ressources, lanceur sans console Python.  
- Tests : icône taskbar, démarrage, install/uninstall smoke.  
- **Pas commencé** tant que mandat AVM-09.

---

## 7. Inventaire livrables

| Livrable | Chemin |
|----------|--------|
| Hub maquettes | `prototypes/avm_08c/index.html` |
| Direction A | `prototypes/avm_08c/directions/a-atelier-nocturne/app.html` |
| Direction B | `prototypes/avm_08c/directions/b-clair-de-presse/app.html` |
| Direction C | `prototypes/avm_08c/directions/c-etagere-vinyle/app.html` |
| Icônes concept | `docs/ux/reports/assets/avm08c/avm08c-icon-*.jpg` |
| Captures comparatives | `docs/ux/reports/assets/avm08c/avm08c-compare-{a,b,c}-*.png` |
| README assets | `docs/ux/reports/assets/avm08c/README.md` |
| Ce rapport | `docs/ux/reports/AVM-08C-DIRECTION-ARTISTIQUE-UX.md` |

**Production (`audio_video_manager/`) :** **aucune modification** AVM-08C.

---

## 8. GO / NO-GO

| Décision | Verdict |
|----------|---------|
| Audit + 3 directions + maquettes HF | **GO livré** |
| Choix DA utilisateur | **A · Atelier nocturne** |
| AVM-08C clôturé (direction figée) | **GO** |
| Démarrer AVM-08D | **EN ATTENTE** mandat explicite |
| Empaquetage AVM-09 | **NO-GO** |

---

## Arrêt

Direction **A · Atelier nocturne** enregistrée.  
**Ne pas démarrer AVM-08D** tant que le mandat d’implémentation n’est pas donné explicitement.

Référence maquette : `prototypes/avm_08c/directions/a-atelier-nocturne/app.html`
