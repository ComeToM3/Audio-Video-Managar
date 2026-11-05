# Développement — Phase 0…3 (AVM-01…04)

## Prérequis

- Windows 10/11
- Python **3.11+** (testé : 3.12)
- fre:ac CLI (`freaccmd.exe`) pour détection et rip
- `discid.dll` x64 sous `vendor/libdiscid/` (ou `AVM_LIBDISCID_DIR`)

## Installation

Dans le dépôt :

```bash
python -m venv .venv
# Git Bash / bash
source .venv/Scripts/activate
# ou PowerShell : .venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

## Exécution

```bash
python -m audio_video_manager
```

**Double-clic Windows :** à la racine du dépôt, `Lancer-AudioVideoManager.bat` (utilise `.venv\Scripts\python.exe` uniquement).  
Raccourci bureau : cibler ce `.bat` (chemins relatifs au script — pas de chemin absolu machine).  
Détail / tests : [../ux/reports/AVM-06D-LANCEUR-WINDOWS.md](../ux/reports/AVM-06D-LANCEUR-WINDOWS.md).

L’UI affiche la détection freaccmd, le chemin SQLite, et permet d’enregistrer la config dans `%LOCALAPPDATA%\AudioVideoManager\config.json` (surcharge possible via `AVM_DATA_DIR`).

## Tests

```bash
python -m pytest
```

Les tests isolent les données via `AVM_DATA_DIR` (fixture). Le cas **freaccmd absent** est couvert sans rip.

## Variables d’environnement utiles

| Variable | Effet |
|----------|--------|
| `AVM_DATA_DIR` | Racine data (config, logs, DB, jobs) |
| `AVM_LIBRARY_ROOT` | Défaut de la bibliothèque musicale |
| `AVM_LIBDISCID_DIR` | Dossier contenant `discid.dll` (override vendor) |

## Gate + identification (AVM-03 / AVM-04)

- Fiche : « Ouvrir / éditer la fiche… » → **Lire TOC + chercher MusicBrainz** → choisir édition → Approuver.
- Rip **archive** : verrouillé sans `Approved`.
- Rip **test technique** : confirmation explicite, zone A only.
- API : `identify_disc`, `apply_release_candidate`, `approve_sheet`, `assert_can_start_archive_rip`.
- Validation MB : [avm-04-validation.md](../validation/avm-04-musicbrainz.md).
- Test manuel technique : [manual-rip-test.md](manual-rip-test.md).

## Hors scope actuel

mutagen tags post-rip, DVD extract, AccurateRip, publish zone C, install silencieuse d’outils.
