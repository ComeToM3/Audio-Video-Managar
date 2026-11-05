# Rapport AVM-06C-F2 — Diagnostic fre:ac (lecture seule)

**Date :** 2026-11-03  
**Job :** `bd40b604b7a147b985916f9f97f70223`  
**Disque :** Queen — Greatest Hits · Disc ID `DsXlPG1OQWhceSELb2Eiq5rx1wU-` · 17 pistes  
**Contrainte respectée :** aucune extraction, suppression, déplacement ni publication

---

## Verdict

| | |
|--|--|
| **Cause** | **Confirmée** — construction argv ` --pattern ` + ` <track> ` (deux jetons) incompatible avec le parseur `freaccmd` |
| **Code -3** | Documenté dans le **code source** fre:ac 1.1.7 = erreur « fichier introuvable » (et couverture manquante) ; listé génériquement dans le Readme (« negative exit codes ») **sans** table publique détaillée |
| **Rip audio** | Les **17 FLAC sont présents et lisibles** en zone A malgré l’échec applicatif |
| **Recommandation** | **NO-GO** nouvel archivage CD réel tant que l’argv n’est pas corrigé ; **GO** correctif minimal argv + reprise sécurisée (voir §8) |

---

## 1. Chronologie job (preuves)

| Heure locale | Événement |
|--------------|-----------|
| 14:33:26 | Disc ID OK · démarrage rip |
| 14:33:26 | argv logué (voir §2) |
| 14:33:48 → 14:39:05 | Écriture successive `1.flac` … `17.flac` (~5,3 min) |
| 14:39:05 | SQLite `state=Failed` · `error_summary=freaccmd returncode=4294967293` |

**SQLite** (`jobs`) :

- `workdir` : `…\jobs\bd40b604b7a147b985916f9f97f70223`
- `mode=normal` · `publish_allowed=1` · `collision_policy=rename`
- `selected_release_mbid=4662a6ff-…` (CA 1992)
- `library_path=NULL` — **aucune publication**
- Bibliothèque test `Music\AVM-06C-Test-Library` : uniquement le marqueur `.avm-06c-isolated`

**Journal `avm.log` :** enregistre le démarrage et l’argv ; **ne capture pas** stdout/stderr fre:ac (les messages fre:ac n’y figurent donc pas).

---

## 2. Argv réellement utilisé

```text
C:\Program Files\freac\freaccmd.exe
  --encoder=flac
  --drive=0
  --track=all
  -d C:\Users\ComeToM3\AppData\Local\AudioVideoManager\jobs\bd40b604b7a147b985916f9f97f70223\rip
  --pattern
  <track>
  --
  -c
  5
```

Source : `build_freaccmd_rip_argv` dans `audio_video_manager/extraction/cd_ripper.py` :

- `--pattern` et `request.pattern` (`<track>`) en **deux arguments** ;
- `-c 5` correctement placé **après** `--` (options encodeur FLAC).

### Compatibilité aide freaccmd 1.1.7 (probes sans rip)

| Élément | Aide / source | Statut |
|---------|---------------|--------|
| `--encoder=flac` | documenté | OK |
| `--drive=0` | documenté | OK (lecteur 0 = ATAPI iHAS324) |
| `--track=all` | documenté | OK |
| `-d <dir>` | documenté | OK |
| `--pattern=<pat>` **ou** `-p <pat>` | documenté | **notre forme espace `--pattern` + valeur ≠ `--pattern=`** |
| `--` puis `-c 5` | `-h flac` : compression 0–8 | OK |

`ScanForProgramOption` (source) ne reconnaît que :

- `--pattern=%VALUE` (forme **avec `=`**) ;
- `-p %VALUE` (forme courte).

`ScanForFiles` traite tout jeton **sans** `-` comme fichier d’entrée. Or `ParamHasArguments("--pattern")` **ne** consomme **pas** le jeton suivant (`<track>` n’est pas dans la liste courte `-p`).

**Conséquence :** le littéral `<track>` est ajouté comme fichier fantôme → message fre:ac `File not found: <track>` → `errorCode = -3`.

### Preuve non destructive (reproduite sans rip CD)

```text
freaccmd --encoder=flac -d <tmpdir> --pattern "<track>" -- -c 5
→ File not found: <track>

freaccmd --encoder=flac -d <tmpdir> --pattern="<track>" -- -c 5
→ (pas de File not found: <track>)
```

---

## 3. Signification de `4294967293` / `-3`

| Représentation | Valeur |
|----------------|--------|
| Unsigned 32-bit (Windows / Python parfois) | `4294967293` |
| Signé | **-3** |

**Documentation officielle Readme fre:ac 1.1.7 :** « added negative exit codes to indicate errors when running freaccmd » — **sans** dictionnaire -1/-2/-3/-4.

**Code source local** `startconsole.cpp` (freac 1.1.7) :

| Code | Usage observé dans le source |
|------|------------------------------|
| **-1** | erreur générique / conversion aborted (`OnFinishEncoding(!success)`) |
| **-2** | option / track / config invalide |
| **-3** | **fichier introuvable** (`File not found: …`) ou **pochette absente** (`Cover art file not found`) |
| **-4** | CD ripping disabled |

Le rip des pistes CD a réussi (`OnFinishEncoding(true)` n’aurait pas forcé -1). Le **-3** vient du fichier fantôme `<track>`, **en parallèle** du rip réussi.

---

## 4. Inventaire zone A (lecture seule)

Dossier : `…\jobs\bd40b604b7a147b985916f9f97f70223\rip\`

| Fichier | Taille | `.flac.temp` | Mutagen FLAC | Durée vs TOC |
|---------|--------|--------------|--------------|--------------|
| `1.flac` … `17.flac` | ~13–33 Mo chacun | présent, **0 octet** chacun | **OK** (magic `fLaC`) | écart &lt; 0,5 s |
| **Total** | **~381 Mo** | 17 × 0 o | **17/17 OK** | cohérent |

Dernière piste : `17.flac` · 28 776 711 o · mtime 14:39:05.

Espace disque au diagnostic : **~342 Go** libres — pas un facteur limitant.

Permissions : fichiers lisibles ; pas d’indice de blocage d’écriture (tailles finales non nulles).

Annulation UI : non — `error_summary` = returncode, pas « Annulé » ; durée ~5 min jusqu’à la piste 17.

---

## 5. Chaîne d’échec AVM (pas fre:ac audio)

1. `FreacCdRipper.rip` exige `returncode == 0` **et** présence de FLAC.  
2. Ici : FLAC OK **mais** returncode ≠ 0 → `success=False`.  
3. `run_archive_job` s’arrête **avant** F-08a / tags / inbox / publish.  
4. Job marqué `Failed` — bibliothèque intacte.

Hypothèses **écartées** (ou très faibles) :

| Hypothèse | Verdict |
|-----------|---------|
| Disque / lecteur défaillant mid-rip | Faible — 17/17 FLAC valides |
| `--drive=0` incorrect | Écarté — rip réel des 17 pistes |
| `-c 5` mal placé | Écarté — pas de `File not found: 5` ; forme après `--` conforme |
| Timeout AVM | Écarté — `timeout_sec=None` |
| Espace disque / permissions | Écarté |
| Annulation utilisateur | Écarté |

---

## 6. Correctif minimal proposé (non appliqué)

Dans `build_freaccmd_rip_argv` :

1. Remplacer les deux jetons `--pattern`, `<track>` par **un** jeton `--pattern=<track>`  
   **ou** utiliser `-p` + valeur (reconnu par `ParamHasArguments`).  
2. Conserver `--` + `-c` + niveau.  
3. Tests unitaires : argv exact ; idéalement assertion « aucun jeton égal à `<track>` hors forme `=`. »  
4. Optionnel (suivi) : journaliser stdout/stderr fre:ac dans le job ; traiter « returncode ≠ 0 mais N FLAC intègres » comme avertissement + revue, pas silence.

**Ne pas** supprimer les FLAC du job `bd40…` sans décision.

---

## 7. Protocole de reprise sécurisé (après GO correctif)

1. Valider et merger le correctif argv + tests.  
2. **Ne pas** relancer un rip dans le même `rip/` (refuse non vide).  
3. Options :  
   - **A (recommandée si conservation des FLAC)** : reprise pipeline avec `staged_flac_files` pointant vers les 17 FLAC déjà validés (pas de 2ᵉ extraction) — fiche toujours Approved, Disc ID inchangé, biblio test isolée, collision Rename.  
   - **B** : nouveau job + rip complet après correctif (plus long, usure CD).  
4. Vérifier W5 : tags, `cover.jpg`, arborescence sous `AVM-06C-Test-Library`, lecture externe.  
5. Compléter `AVM-06C-VALIDATION-CD-REEL.md`.

---

## 8. GO / NO-GO

| Décision | Portée |
|----------|--------|
| **NO-GO** | Nouvel archivage / rip réel avec l’argv actuel |
| **GO (après validation mandant)** | Correctif argv minimal + tests |
| **GO reprise** | Après correctif : voie A (staging) ou B (re-rip) selon choix mandant |

**Arrêt :** aucun correctif appliqué dans ce mandat F2 — en attente de décision.
