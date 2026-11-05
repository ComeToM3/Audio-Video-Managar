# 05 — Système visuel et accessibilité

## 1. Intention

Interface **calme, lisible, utilitaire** — outil d’archivage, pas marketing.  
Éviter le look « dashboard SaaS » (pas de violet néon, pas de cards empilées inutiles).

## 2. Typographie

| Rôle | Proposition | Taille approx. |
|------|-------------|----------------|
| Titre app / section | Segoe UI Semibold (Windows natif) | 18–20 pt |
| Titre d’étape | Segoe UI Semibold | 16 pt |
| Corps | Segoe UI Regular | 13–14 pt |
| Secondaire / aide | Segoe UI Regular | 12 pt, contraste réduit |
| Chemins / Disc ID | Consolas / Cascadia Mono | 11–12 pt |

Pas de police web exotique (app desktop locale).

## 3. Couleurs (thème clair recommandé)

| Token | Hex | Usage |
|-------|-----|--------|
| `--bg` | `#F7F6F3` | Fond app (légère chaleur, pas crème terracotta cliché) |
| `--surface` | `#FFFFFF` | Panneaux contenu |
| `--text` | `#1A1A1A` | Texte principal |
| `--text-muted` | `#5C5C5C` | Aide, secondaire |
| `--accent` | `#0B6E4F` | CTA primaire (vert forêt — archivage / OK) |
| `--accent-hover` | `#095C42` | Hover CTA |
| `--warn` | `#9A6700` | Avertissements |
| `--danger` | `#A40000` | Erreurs / destructive |
| `--border` | `#D8D5CE` | Séparateurs |
| `--focus` | `#0B6E4F` ring 2px | Focus clavier |

Thème sombre : **hors MVP** (éviter biais dark-by-default).

## 4. Espacements

- Grille 8 px.
- Marge contenu 24 px ; gap blocs 16 px ; gap champs formulaire 12 px.
- Stepper : 16 px entre étapes.
- Densité dialog actuelle → réduire ; une colonne principale max ~720 px pour le wizard.

## 5. Composants

| Composant | Règles |
|-----------|--------|
| Bouton primaire | Fond accent, texte blanc, radius 4 px, hauteur 36 px |
| Bouton secondaire | Bordure, fond surface |
| Bouton danger | Contour danger, usage Annuler/Abandonner |
| Nav latérale | Item actif = barre accent 3 px + fond léger |
| Stepper | Numéro + label ; complété = check ; futur = muted |
| Badge | Pill radius 4 (pas pill full « marketing ») |
| Cover | Ratio 1:1, fond `#E8E6E0` si manquant, pas d’overlay badges |
| Progress | Barre native + labels d’étape au-dessus |

**Cards :** uniquement pour album dans « Ma bibliothèque » (interaction sélection). Pas de cards dans le hero/wizard.

## 6. Accessibilité

- Contraste texte/fond ≥ WCAG AA.
- Focus clavier visible sur tous les CTA.
- Ordre tab = flux stepper.
- `QMessageBox` : titres explicites ; éviter erreurs SQLite brutes en premier plan.
- Pas d’information uniquement par la couleur (badge + texte).
- Taille fenêtre min. recommandée 1024×680 ; nav bascule onglets si largeur &lt; 900.

## 7. Redimensionnement

| Largeur | Comportement |
|---------|--------------|
| ≥ 1100 | Nav gauche 200 px + contenu |
| 900–1099 | Nav gauche 160 px |
| &lt; 900 | Nav en `QTabWidget` haut |
| Wizard | Scroll vertical si formulaire long ; stepper sticky en haut |

## 8. Motion (discret)

1. Transition d’étape : fondu court contenu (150–200 ms).
2. Progression : mise à jour labels d’étape (pas d’animation décorative).
3. Succès final : apparition check + chemin (pas de confettis).
