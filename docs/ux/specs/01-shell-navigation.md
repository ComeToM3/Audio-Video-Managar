# 01 — Coquille et navigation (4 sections)

## 1. Responsabilités

| Section | ID | Responsabilité | Ne fait pas |
|---------|-----|----------------|-------------|
| **Archiver un disque** | `nav.archive` | Parcours guidé CD → bibliothèque | Config avancée, historique complet |
| **Ma bibliothèque** | `nav.library` | Consulter albums publiés (C) + inbox B | Édition tags batch, lecture audio |
| **Historique** | `nav.history` | Jobs SQLite, reprise/abandon, chemins | Lancer un nouvel archivage |
| **Paramètres** | `nav.settings` | Config utilisateur + Avancé (test technique) | Workflow d’import |

Section par défaut au lancement : **Archiver un disque**.

## 2. Chrome application

```text
┌─ TitleBar: AudioVideoManager {version} ─────────────────────────┐
│ Header: [pastille lecteur]  « CD détecté · 17 pistes »    [Aide] │
├─ Nav 160–200px ─┬─ Contenu (QStackedWidget) ────────────────────┤
│ Archiver        │                                               │
│ Bibliothèque    │                                               │
│ Historique      │                                               │
│ Paramètres      │                                               │
└─────────────────┴───────────────────────────────────────────────┘
```

| Zone | Contenu |
|------|---------|
| Pastille lecteur | Idle / CD détecté / Lecture… / Erreur lecteur — mise à jour sans bloquer |
| Aide | Dialogue court : « Archive locale FLAC · pas de cloud · approbation manuelle » |
| Nav active | Barre accent 3 px + fond léger |

## 3. Transitions entre sections

| Depuis → Vers | Comportement |
|---------------|--------------|
| Archiver → autre | **Autorisé** à tout moment ; état wizard **conservé en mémoire** (session) |
| Autre → Archiver | Reprend l’étape courante ; si `Approved`, **conservé** (A3) |
| Pendant extraction (étape 4 en cours) | Navigation **désactivée** ou confirm « Annuler l’archivage en cours ? » |
| Job terminé étape 5 | Navigation libre |

## 4. Breakpoints

| Largeur | Nav |
|---------|-----|
| ≥ 900 px | `QListWidget` / boutons verticaux à gauche |
| &lt; 900 px | `QTabWidget` en haut (mêmes 4 libellés FR) |

Fenêtre min. conseillée : 1024×680.

## 5. Widgets shell (PySide6)

- `QMainWindow` + `QWidget` central `QHBoxLayout` ou `QVBoxLayout` (tabs).
- Contenu : `QStackedWidget` (4 pages).
- Thème : propriétés dynamiques / QSS tokens ([../05-systeme-visuel.md](../05-systeme-visuel.md)).

## 6. Messages globaux

| Situation | Message FR |
|-----------|------------|
| freaccmd absent | « L’outil d’extraction (fre:ac) est introuvable. Ouvrez Paramètres pour indiquer son emplacement. » |
| Bibliothèque inaccessible | « Le dossier bibliothèque est inaccessible. Vérifiez le chemin dans Paramètres. » |
| Annulation job | « Archivage annulé. Les fichiers incomplets ne sont pas publiés. » |
