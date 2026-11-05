# Test manuel — extraction CD réelle (**mode test technique**)

Relevant de **D-013** : validation freaccmd / FLAC en zone A uniquement.  
**Ce n’est pas** le parcours archive (qui exige une fiche `DiscMetadata` approuvée — AVM-02B / D-011).

**Ne pas lancer sans confirmation explicite** (disque légitimement possédé, lecteur prêt).  
**Ne pas publier** le résultat en bibliothèque définitive.

Pré-contrôle typique (AVM-02 validation) :

| Contrôle | Exemple observé |
|----------|-----------------|
| Lecteur | `0: ATAPI iHAS324 C (1:0:0)` — lettre Windows `D:` |
| Média | `MediaLoaded=True`, `VolumeName=Audio CD` |
| freaccmd | `C:\Program Files\freac\freaccmd.exe` |
| FLAC | compression **5**, **sans** `--eject` |
| Destination | **uniquement** `%LOCALAPPDATA%\AudioVideoManager\jobs\{job_id}\rip\` |
| Bibliothèque | `...\Music\AudioVideoManager` — **non modifiée** |

## Prérequis

- freaccmd 1.1.7 détecté
- CD audio dans le lecteur
- `pip install -e ".[dev]"` et venv actif
- Confirmation utilisateur sur le chemin job exact

## Procédure (UI)

1. `python -m audio_video_manager`
2. Vérifier lecteur dans la liste (ex. ATAPI iHAS324).
3. Compression FLAC 5, **éjection décochée** sauf besoin.
4. Cliquer **Démarrer l'extraction** → confirmer la boîte de dialogue.
5. Attendre la fin ; noter le `job_id` et le workdir affichés.
6. Contrôler :
   - fichiers `*.flac` dans `{jobs_dir}/{job_id}/rip/`
   - section **F-08a** (intégrité) dans le résumé
   - section **F-08b** (faible) : ne doit **pas** affirmer un rip parfait / AccurateRip

## Procédure (CLI agent, après confirmation)

Créer un job via `run_rip_job` (même règles : workdir neuf, pas de bibliothèque C).

## Annulation

Relancer un rip et cliquer **Annuler** ; vérifier `cancelled=True` et absence de succès.

## Hors scope de ce test

- MusicBrainz / tags / organisation finale (zones B/C)
- AccurateRip
- DVD

Voir aussi [library-conventions.md](../domain/library-conventions.md).
