# AudioVideoManager

Application Windows locale, gratuite et open source (**GPL-3.0-or-later**) pour l’importation automatisée de collections de **CD audio** (DVD musicaux reportés).

Flux cible : disque → identification → extraction **FLAC** → métadonnées / pochettes → organisation → contrôles → disque suivant.

> **État :** **AVM-06 UI-0 + UI-1** livrés (coquille + wizard archivage) — validation rip réel **AVM-06C** en cours ; lanceur Windows **AVM-06D**.  
> Version **0.5.0**.  
> Docs : [docs/README.md](docs/README.md) · Rapport UI : [docs/ux/reports/AVM-06-UI-0-UI-1.md](docs/ux/reports/AVM-06-UI-0-UI-1.md).

## Décisions retenues (extrait)

| ID | Décision |
|----|----------|
| D-001 | GPL-3.0-or-later |
| D-002 | fre:ac / `freaccmd` unique ripper CD MVP |
| D-003 | Python, PySide6, SQLite, mutagen, MusicBrainz, libdiscid |
| D-004 | MusicBrainz primaire ; offline possible |
| D-005 | `{AlbumArtist}/{Album} ({Year})/{NN} - {Title}.flac` |
| D-006 | Art embarqué + `cover.jpg` |
| D-007 | Sidecar JSON reporté |
| D-008 | Produit AudioVideoManager ; package `audio_video_manager` |
| D-009 | Jamais d’écrasement silencieux |
| D-010 | DVD extraction reportée |
| D-011…D-015 | Gate meta, anti-placeholders, mode test, sélection intelligente éditions |

Détail : [docs/product/decisions.md](docs/product/decisions.md).

## Documentation

Index complet : **[docs/README.md](docs/README.md)**

| Zone | Contenu |
|------|---------|
| [docs/product/](docs/product/) | Exigences, architecture, décisions, roadmap |
| [docs/domain/](docs/domain/) | Fiche disque, conventions bibliothèque |
| [docs/engineering/](docs/engineering/) | Dev, fre:ac, test rip manuel |
| [docs/validation/](docs/validation/) | Rapports AVM-04…05 |
| [docs/ux/](docs/ux/) | Conception UX + specs 06B + [rapport UI-0/UI-1](docs/ux/reports/AVM-06-UI-0-UI-1.md) |

## Prérequis

| Outil | Statut |
|-------|--------|
| fre:ac 1.1.7 + `freaccmd.exe` | Requis pour rip |
| `discid.dll` (x64) | Fourni sous `vendor/libdiscid/` |
| Python 3.11+ | OK |
| Réseau | Optionnel (MusicBrainz / CAA) ; fiche manuelle offline possible |

## Installation rapide

```bash
python -m venv .venv
source .venv/Scripts/activate   # PowerShell : .venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python -m audio_video_manager
python -m pytest
```

Sous Windows, après installation du `.venv` : double-cliquer **`Lancer-AudioVideoManager.bat`** (ou raccourci vers ce fichier).

Détail : [docs/engineering/development.md](docs/engineering/development.md).

## Prochaine action

Valider le livrable UI-0/UI-1 et le correctif F1 ; poursuivre **AVM-06C** (rip réel contrôlé) après autorisation. Lanceur : [docs/ux/reports/AVM-06D-LANCEUR-WINDOWS.md](docs/ux/reports/AVM-06D-LANCEUR-WINDOWS.md).

## Avertissement

Archivage de supports dont vous détenez les droits d’usage. Pas de contournement anticopie.
