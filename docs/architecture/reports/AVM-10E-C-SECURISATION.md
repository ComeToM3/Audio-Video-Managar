# AVM-10E-C — Sécurisation et préparation de la validation physique

**Date :** 2026-11-04  
**Version AVM :** 0.5.0  
**Périmètre :** launcher isolé, garde de démarrage fail-closed, isolation des données, prérequis matériels, tests.  
**Limite impérative :** aucune extraction ni interruption réelle n'a été exécutée.

## Verdict

**VALIDÉ SOUS RÉSERVES** pour le mandat de sécurisation et de préparation. Le lanceur 10E passe son préflight réel dans le `.venv`, les chemins effectifs sont ceux de l'allowlist, le lecteur présente le Disc ID autorisé avec 22 pistes et les destinations sont vides. La CI complète passe et les empreintes des données de production et de Queen sont inchangées.

**Environnement prêt pour l'extraction physique autorisée : OUI, sous réserves.** Cette conclusion concerne uniquement l'état observé aujourd'hui. Avant le rip, relancer le préflight et la lecture TOC, confirmer une nouvelle fois le même Disc ID, puis obtenir/maintenir une autorisation explicite de rip. Le présent mandat s'arrête avant le rip. La compatibilité Python 3.11 n'a pas été vérifiée : seul Python 3.12.10 est disponible dans les environnements détectés.

## 1. Modifications

- `audio_video_manager/diag10e_isolation.py` ajoute un préflight opt-in (`AVM_10E_MODE=1`) qui ne crée ni ne modifie de fichier.
- Le préflight exige le dépôt, le venv, l'interpréteur, `LOCALAPPDATA`, `USERPROFILE`, `ProgramFiles`, le répertoire de données, la bibliothèque, la configuration, SQLite, les logs, les jobs et fre:ac. Les chemins doivent être absolus, canoniques, existants et correspondre à l'allowlist AVM-10E.
- Les valeurs effectives sont résolues et contrôlées avant le démarrage de l'UI. Les réglages `library_root`, `jobs_dir`, `log_dir` et `freaccmd_path` sont eux aussi validés contre leur destination autorisée.
- Les composants du chemin sont examinés avec `lstat`; les symlinks et points de réanalyse Windows (dont les jonctions) bloquent le lancement. Le parcours des arborescences échoue également en cas d'erreur d'accès.
- Les identités de fichiers (volume/index) de toute la racine de données de production et de l'archive Queen sont protégées. Un hardlink de ces fichiers depuis les zones 10E bloque le lancement.
- `audio_video_manager/__main__.py` appelle le garde avant l'import de l'UI, le logger et l'ouverture/migration de SQLite. Le lancement normal hors mode 10E conserve son comportement.
- `scripts/diag10e/run_app_10e_isolated.bat` calcule correctement la racine du dépôt, active `\.venv`, compare le `VIRTUAL_ENV` normalisé et l'interpréteur trouvé par `where python`, puis lance le préflight. `AVM_10E_PREFLIGHT_ONLY=1` s'arrête après celui-ci.
- `tests/test_10e_isolation.py` couvre le chemin valide, chemins absents/non canoniques, redirections de config, `freaccmd` non autorisé, hardlinks, symlinks/attributs de réanalyse, refus avant l'UI et démarrage normal. Le fichier est inclus dans la suite domaine de `scripts/run_tests_ci.py`.

Le lancement réel du batch a d'abord révélé une racine de dépôt calculée avec un niveau de trop ; cette erreur a été corrigée. Le batch a ensuite passé le préflight en mode préflight-seulement avec le venv et les chemins résolus ci-dessous.

## 2. Preuves d'isolation

Préflight du lanceur : **PASS**, code retour `0`, aucune UI démarrée.

| Élément | Chemin effectivement résolu |
|---|---|
| Racine du dépôt | `C:\Users\ComeToM3\Dev\AudioVideoManager` |
| Python actif | `C:\Users\ComeToM3\Dev\AudioVideoManager\.venv\Scripts\python.exe` |
| Version active | Python `3.12.10` x64 |
| Données 10E | `C:\Users\ComeToM3\AppData\Local\AudioVideoManager-10E` |
| SQLite 10E | `...\AudioVideoManager-10E\avm.sqlite3` |
| Logs 10E | `...\AudioVideoManager-10E\logs` |
| Jobs 10E | `...\AudioVideoManager-10E\jobs-10e` |
| Bibliothèque 10E | `C:\Users\ComeToM3\Music\AVM-10E-Test-Library` |
| fre:ac approuvé | `C:\Program Files\freac\freaccmd.exe` |

La configuration lue au démarrage pointe vers ces chemins. La bibliothèque est vide (0 fichier), `jobs-10e` est vide, et une lecture SQLite en mode `ro` donne `jobs=0`, `releases=0`, `tracks=0`. La base 10E existe (73 728 octets) ; le dossier de logs contient son fichier de log existant.

La validation fail-closed refuse notamment un chemin absent, un chemin différent de l'allowlist, une configuration orientée production, un interpréteur hors `.venv`, un point de réanalyse, un hardlink vers un fichier protégé ou une arborescence impossible à parcourir. Ces refus sont exercés sur des répertoires temporaires par les tests.

## 3. Lecteur, média et dépendances

Ces probes sont des lectures non destructives ; aucune commande de rip n'a été envoyée.

| Contrôle | Statut | Résultat observé |
|---|---|---|
| fre:ac `--list-drives` | **PASS** | Retour `0`; lecteur `0`, device path `1:0:0`, `ATAPI iHAS324 C` |
| TOC libdiscid fraîche | **PASS** | Device `D:`; Disc ID `HKAtvzd2gALbaC2d4HONIWPCE0Q-`; 22 pistes |
| Correspondance avec l'identité autorisée | **PASS** | Disc ID exact et nombre de pistes exacts |
| fre:ac sans argument (probe usage) | **RÉSERVE** | Usage affiché, code `4294967294` (valeur observée non nulle) |
| FFmpeg | **PASS** | `C:\Tools\ffmpeg\bin\ffmpeg.EXE`, code `0`, version `2025-12-04-git-d6458f6a8b-essentials_build-www.gyan.dev` |
| `discid` / libdiscid | **PASS** | Import et lecture TOC réussis |
| Espace `jobs-10e` | **PASS** | 337 695 535 104 octets, soit 322 051,6 MiB libres |
| Espace bibliothèque 10E | **PASS** | Même volume C:, même espace libre : 322 051,6 MiB |

La préparation précédente estimait un besoin de 2 783 MiB pour 22 pistes ; l'espace actuellement mesuré dépasse cette estimation. Le code `4294967294` du probe fre:ac sans argument reste à expliquer ; le probe explicite `--list-drives`, qui est celui utilisé pour identifier le lecteur, retourne `0`.

Durées TOC observées, pistes 01 à 22, en millisecondes : `214000, 215000, 192000, 246000, 187000, 144000, 191000, 143000, 144000, 186000, 188000, 171000, 153000, 356000, 227000, 230000, 222000, 225000, 158000, 205000, 186000, 111000`. Ce sont des mesures du disque, pas des durées FLAC, puisqu'aucun fichier n'a été extrait.

## 4. Tests et intégrité des données

| Validation | Résultat |
|---|---|
| Tests ciblés `tests/test_10e_isolation.py` | **PASS** — 17 tests, 0 échec, 0 erreur, 0 skip |
| CI domaine après intégration du nouveau fichier | **PASS** — 185 tests, 0 échec, 0 erreur, 0 skip |
| CI complète (13 groupes de processus) | **PASS** — 252 tests, 0 échec, 0 erreur, 0 skip ; retour global `0` ; `skipped_unavailable=[]` |
| Diagnostics Python des fichiers modifiés | **PASS** — aucune erreur signalée |
| Empreintes avant/après la CI complète | **PASS** — 144 fichiers de la racine de données de production et de Queen ont des SHA-256, tailles et dates de modification identiques |
| Extraction physique / retour rip / FLAC / métadonnées / publication | **SKIP** — expressément hors action de ce mandat |
| Annulation et interruption réelle | **SKIP** — expressément interdites sans autorisation distincte |
| Tests sous Python 3.11 | **SKIP** — Python 3.11 absent des interpréteurs détectés |

Le Python Install Manager est absent ; `py -0p` et les environnements Pylance ne montrent que Python 3.12 et le `.venv` Python 3.12.10. Ce résultat ne certifie pas Python 3.11 et ne le présente pas comme équivalent.

Résultats CI : `.ci/avm10e-c-final2-results.json` et JUnit sous `.ci/avm10e-c-final2-junit/`.

## 5. Données de production

Avant et après la dernière CI, les empreintes SHA-256, tailles et `mtime_ns` des 144 fichiers recensés sous `AudioVideoManager` de production et l'archive `Queen/Greatest Hits (1992)` sont identiques. Aucun fichier ajouté, supprimé ou modifié n'a été détecté dans ces périmètres. La bibliothèque 10E est restée vide et les tables `jobs`, `releases` et `tracks` de sa base sont restées à zéro.

Cette preuve couvre la CI finale exécutée pour ce mandat. Le rapport AVM-10E antérieur documente une tentative de lancement précédente ayant écrit dans le journal de production ; ce fait historique demeure distinct de la CI encadrée ici et n'est pas effacé par le constat présent.

## 6. Risques et conditions avant rip

1. Une course reste théoriquement possible si un chemin est remplacé entre le préflight et l'ouverture ultérieure par l'application (TOCTOU). Relancer le préflight immédiatement avant l'opération et ne pas changer les chemins ensuite.
2. Le code détecte le bit Windows `FILE_ATTRIBUTE_REPARSE_POINT` et les symlinks ; les tests vérifient un symlink réel et les attributs de jonction. La création d'une jonction Windows réelle n'a pas été nécessaire ni testée sur la machine.
3. Le probe fre:ac sans argument retourne `4294967294` malgré l'usage affiché. Confirmer que le retour de la commande de rip et du probe `--list-drives` reste acceptable lors de l'opération autorisée ; capturer les sorties brutes.
4. Python 3.11 n'est pas disponible ici. La suite actuelle est validée sous 3.12.10 uniquement.
5. L'identité du disque peut changer si le média est retiré/remplacé. Relire le Disc ID et le compte de pistes au moment du rip.
6. Le parcours fonctionnel n'a pas encore prouvé MusicBrainz, l'approbation humaine, l'extraction, le décodage FLAC, les tags, la pochette, la publication ou la cohérence release/tracks après écriture.

## 7. Conclusion opérationnelle

Le launcher et son garde fail-closed sont validés pour l'environnement observé, les destinations isolées sont vides et les prérequis matériels courants correspondent au CD candidat. L'environnement est **prêt sous réserves** pour le rip réel lorsqu'il sera explicitement autorisé. Aucun rip, aucune interruption et aucun mandat AVM-10F/AVM-09 n'ont été entrepris.