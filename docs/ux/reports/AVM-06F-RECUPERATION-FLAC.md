# Rapport AVM-06F — Préparation récupération FLAC (sans exécution)

**Date :** 2026-11-03  
**Version :** 0.5.0  
**Job source (échec conservé) :** `bd40b604b7a147b985916f9f97f70223`  
**Phase :** **préparatoire uniquement** — aucune copie de récupération, tag, ni publication exécutée

---

## Verdict préparatoire

| Critère | Résultat |
|---------|----------|
| 17 FLAC originaux intacts | **GO** |
| Décodage intégral (ffmpeg null) | **GO** — 17/17 rc=0 |
| Fiche Approved + MBID CA 1992 | **GO** |
| Biblio test vide (hors marqueur) | **GO** |
| Mécanisme `staged_flac_files` | **GO** — pas de rip |
| Politique returncode stricte | **Conservée** (échec initial reste Failed) |
| Exécution récupération | **BLOQUÉE** — attendre autorisation explicite |

**Recommandation :** **GO technique** pour lancer la récupération staging dès autorisation mandant.

---

## 1. Inspection lecture seule

### Job SQLite

| Champ | Valeur |
|-------|--------|
| `state` / `step` | **Failed** / Failed |
| `error_summary` | `freaccmd returncode=4294967293` |
| `workdir` | `…\jobs\bd40b604b7a147b985916f9f97f70223` |
| `metadata_id` | `df038df1a34444b8a8ec4b5bd6e0b7cc` |
| `selected_release_mbid` | `4662a6ff-34e5-462f-bac0-584ac29cfd4d` |
| `collision_policy` | `rename` |
| `publish_allowed` | 1 |
| `library_path` | NULL |
| Checkpoint | `Ripping` `{drive: 0}` uniquement (pas de Staging/Tagging) |

**Invariant 06F :** cet enregistrement **ne doit pas** être réécrit en `Completed`. La récupération crée un **nouveau** `job_id`.

### Zone A

- 17 × `N.flac` + 17 × `N.flac.temp` (0 o, bruit fre:ac)  
- Aucun autre fichier  
- mtime : 14:33:48 → 14:39:05 (session rip d’origine)

### Bibliothèque isolée

`C:\Users\ComeToM3\Music\AVM-06C-Test-Library` : uniquement `.avm-06c-isolated`.

### Fiche approuvée

| Champ | Valeur |
|-------|--------|
| `approval` | **Approved** (`approved_at` 19:33:03Z) |
| Disc ID | `DsXlPG1OQWhceSELb2Eiq5rx1wU-` |
| Édition | Queen — Greatest Hits · **1992** · **CA** · Hollywood · **CD 61265** |
| MBID | `4662a6ff-34e5-462f-bac0-584ac29cfd4d` |
| Cover | `confirmed` · URL CAA |
| `is_compilation` | `false` (confirmé à l’approbation UI) |
| Pistes | 17 titres MB (piste 13 : glyphes `↑⬱` conservés) |
| Piste 17 | Titre *I Want to Break Free* · durée fiche/TOC **262000 ms** · FLAC **262,133 s** |
| Avertissement TOC vs MB (258733 ms) | Historique identify ; **durée fichier = TOC**, pas MB |

---

## 2. Vérification FLAC (preuves)

**Méthode CRC / décodage :**  
`C:\Program Files\freac\codecs\cmdline\ffmpeg.exe -v error -i <file>.flac -f null -`  
(décodeur FLAC libavcodec — vérification des trames / CRC à la lecture ; **aucune écriture** sur les originaux).

Complément : mutagen (rate/channels/bits/durée) + F-08a structurelle déjà OK (06E).

| # | Taille | Format | Δ TOC | Decode |
|---|--------|--------|-------|--------|
| 01–17 | 13–33 Mo | 44100 Hz · 2 ch · 16 bit | ≤ ±467 ms | **rc=0** tous |

- **ALL_DECODE_OK** = true  
- **MAX_ABS_TOC_DELTA_MS** = 467 (&lt; tolérance métier habituelle 600 ms)  
- SHA-256 préfixes enregistrés en session de diagnostic (ex. piste 1 `633c8e1e55487d0a…`) pour contrôle post-copie

Les fichiers **n’ont pas été altérés** (mtime inchangés après vérifs).

---

## 3. Mécanisme `staged_flac_files` (garanti sans rip)

Dans `run_archive_job` :

1. Si `staged_flac_files is not None` → `shutil.copy2` vers **nouveau** `jobs/<new_id>/rip/`  
2. `RipResult(argv=("staged",), returncode=0)` — **aucune** instanciation utile de `FreacCdRipper.rip`  
3. Suite : F-08a → tags → inbox → publish si `confirm_publish=True`  
4. Disc match : avec staging et sans `disc_read`, warning « Disc ID non vérifiée » si `skip_disc_match=False` et pas de TOC ; pour 06F prévoir `skip_disc_match=True` **ou** relecture TOC optionnelle si CD encore présent (recommandé si disque dispo)

**Politique returncode :** `FreacCdRipper` reste strict (`returncode == 0` requis). L’échec `bd40…` **n’est pas** requalifié en succès.

---

## 4. Plan de récupération (à exécuter seulement après GO)

### Préconditions

- [x] Pattern fre:ac corrigé (06E)  
- [x] 17 FLAC décodables  
- [x] Fiche Approved en base  
- [x] Biblio = `AVM-06C-Test-Library`  
- [ ] **Autorisation écrite mandant**

### Étapes prévues (futur mandat d’exécution)

1. Charger `DiscMetadata` id `df038df1…` via repository (Approved).  
2. `assert_can_start_archive_rip(sheet)`.  
3. Lister `…/bd40…/rip/{1..17}.flac` ordonnés.  
4. Appeler `run_archive_job` avec :  
   - `staged_flac_files=<ces chemins>`  
   - `jobs_root` = jobs AVM standard (crée **nouveau** UUID)  
   - `library_root` = `…\Music\AVM-06C-Test-Library`  
   - `collision_policy=CollisionPolicy.RENAME`  
   - `confirm_publish=True`  
   - `skip_disc_match=True` *ou* TOC live si CD dans D:  
   - `cover` via URL fiche / CAA (comme pipeline normal)  
5. **Ne pas** passer `freaccmd` pour un rip ; chemin freaccmd ignoré si staging.  
6. Vérifier post-exécution :  
   - job `bd40…` toujours `Failed` + mêmes SHA originaux  
   - nouveau job `Completed*`  
   - 17 FLAC + `cover.jpg` sous biblio test  
   - tags MB / titres  
7. Mettre à jour `AVM-06C-VALIDATION-CD-REEL.md`.

### Interdits pendant / après (rappel)

- Pas de `REPLACE`  
- Pas de move/delete sur `bd40…/rip/*.flac`  
- Pas de réécriture `state=Completed` sur `bd40…`  
- Pas d’extraction physique

---

## 5. Risques résiduels

| Risque | Mitigation |
|--------|------------|
| CD absent → pas de re-check Disc ID | Documenter warning staging ; optionnel TOC si CD présent |
| Glyphes titre piste 13 | Conservés tels quels (pas de normalisation 06F) |
| Réseau CAA pour cover | Pipeline retélécharge ; sinon cover déjà confirmée URL |
| Double album si rejeu | Rename → `import-2` |

---

## 6. Tests ajoutés

`tests/test_archive_recovery_staging.py` :

- staging **n’appelle pas** `FreacCdRipper.rip`  
- originaux octets/mtime préservés  
- job Failed préexistant **reste** Failed  
- nouveau job Completed + publish Rename  
- approbation toujours exigée  
- collision → second dossier (Rename)

```text
python -m pytest  →  100 passed  (96 + 4 recovery)
```

(`test_pattern_equals…` dans le même fichier ; total suite à confirmer à l’exécution locale : **100** si 96+4.)

---

## 7. Checklist GO / NO-GO exécution

| ID | Critère | Statut prépa |
|----|---------|--------------|
| G1 | 17 FLAC décodage intégral OK | **GO** |
| G2 | Fiche Approved + MBID CA | **GO** |
| G3 | Biblio test isolée vide | **GO** |
| G4 | Staging sans rip (tests) | **GO** |
| G5 | Failed `bd40` non réécrit (tests) | **GO** |
| G6 | Autorisation mandant | **NO-GO jusqu’à GO écrit** |
| N1 | Assouplir returncode fre:ac | **NO** (hors mandat) |
| N2 | Re-rip physique | **NO** |
| N3 | Modifier/supprimer originaux | **NO** |

---

## 8. Arrêt obligatoire

Aucune copie de récupération, intégration de métadonnées ni publication n’a été lancée.

**Attente :** autorisation explicite pour exécuter le §4 (staging → tags → publish Rename dans `AVM-06C-Test-Library`).
