# fre:ac CLI — constat local

Dernière vérification : **2026-11-03** (mandat AVM-01). Aucun rip lancé.

## 1. Faits observés

| Fait | Détail |
|------|--------|
| fre:ac GUI | `C:\Program Files\freac\freac.exe` |
| **freaccmd.exe** | **Présent** : `C:\Program Files\freac\freaccmd.exe` (119088 octets) |
| Version CLI (bannière) | `fre:ac - free audio converter v1.1.7 (x86-64) command line interface` |
| Licence | GPL-2.0 (`COPYING` dans le dossier d’install) |
| Aide (exécutable sans argument) | Affiche usage + encodeurs. Exit **0** depuis Git Bash ; via `subprocess` Python (CREATE_NO_WINDOW) returncode observé **4294967294** (−2 en int32 signé). Ne pas assimiler ce code à « binaire invalide ». |
| `--list-drives` | **OK**, exit code **0** (shell et Python) — 1 lecteur : `0  1:0:0  ATAPI iHAS324   C` |
| `--version` | **Pas d’option dédiée observée** : l’invocation imprime l’aide (stdout) avec **exit code 127** et stderr vide. La version utile est la bannière `v1.1.7` de l’aide sans argument (exit 0). |
| `-h flac` / `--help=flac` | Affiche les options spécifiques encodeur FLAC (observé) |

### Encodeurs listés par l’aide locale

`sndfile`, `coreaudio`, `fdkaac`, `flac`, `lame`, `meh`, `mac`, `mpc`, `vorbis`, `ofr`, `opus`, `speex`, `tak`, `wv`, `wma`, `sndfile-wave`

### Options CLI confirmées (extrait aide réelle)

- `--encoder` / `-e`, `--help` / `-h`, `-d`, `-o`, `--pattern` / `-p`
- `--list-drives`, `--drive` / `-cd`, `--track` / `-t`, `--timeout`, `--cddb`, `--eject`
- `--superfast`, `--threads`
- `--split-chapters`, `--add-cover`, `--add-cover-back`
- `--cuesheet`, `--playlist`, `--ignore-chapters`, `--ignore-coverart`
- `--list-configs`, `--config`, `--quiet`

## 2. Hypothèses restantes

| ID | Hypothèse |
|----|-----------|
| H-CLI-04 | AccurateRip sans option CLI dédiée ; activation éventuelle via `--config` / profil GUI |
| H-CLI-05 | Codes retour négatifs sur erreur de rip (notes de version 1.1.7) — non exercés ici (pas de rip) |

## 3. Blocages

| ID | Statut | Détail |
|----|--------|--------|
| B-01 (`freaccmd` absent) | **Levé** | Binaire présent et probes non destructifs OK |
| B-02 | Ouvert côté rip réel | Aide / list-drives OK ; **rip réel non exécuté dans AVM-02** (attente confirmation manuelle) |

## 4. Intégration AVM

La détection applicative (`audio_video_manager.extraction.cd.probe_freaccmd`) exécute les mêmes probes non destructifs et affiche stdout/stderr **tels quels** dans l’UI.
