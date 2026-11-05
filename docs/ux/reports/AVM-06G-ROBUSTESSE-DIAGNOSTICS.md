# Rapport AVM-06G — Robustesse et diagnostics

**Date :** 2026-11-03  
**Version :** 0.5.0  
**Suite :** **109 passed** (100 pré-06G + 9 tests diagnostics)  
**Arrêt :** résultats présentés — **attendre validation avant AVM-06H**

---

## Verdict

| Critère | Résultat |
|---------|----------|
| Returncode fre:ac strict (`== 0`) | **Conservé** |
| Job historique `bd40…` Failed + 17 FLAC zone A | **Intact** |
| 17 FLAC publiés Queen (biblio test) | **Intact** (aucune suppression / retag) |
| D-011…D-015 | **Préservés** |
| Journaux fre:ac persistants | **GO** |
| Taxonomie d’échecs + messages FR | **GO** |
| Décodage intégral optionnel (ffmpeg) | **GO** (explicite si absent) |
| Mapping piste/fichier + durées | **GO** (durées = warning) |
| Diagnostic pochette (sans recadrage) | **GO** — cause lecteur / vignette 500×500 |
| Publication partielle / collisions | **Mitigé** (catch RuntimeError → `PUBLISH`) |
| Rip réel / DVD / refonte UX | **Non entrepris** |

**Recommandation : GO technique** pour clôturer 06G. **NO-GO AVM-06H** jusqu’à validation mandant.

---

## 1. Captures fre:ac (stdout / stderr)

| Élément | Détail |
|---------|--------|
| Module | `diagnostics/freac_logs.py` |
| Fichiers | `freac_stdout.txt`, `freac_stderr.txt`, `freac_meta.json` |
| Emplacement | Dossier **job** (parent de `…/rip`) |
| Contenu meta | `argv`, `returncode`, tailles flux, `flac_count`, `cancelled` |
| Politique | Écriture **après** lecture des flux ; échec d’écriture → warning log, **jamais** masquage du `returncode` |

Le ripper (`FreacCdRipper`) compose un message FR via `freac_user_message` tout en gardant `returncode` et la queue stderr dans le détail technique.

---

## 2. Taxonomie des échecs

`FailureKind` (`diagnostics/failure_kinds.py`) + champ `ArchiveJobReport.failure_kind` :

| Kind | Cas |
|------|-----|
| `extraction` | fre:ac `rc ≠ 0`, annulé côté outil, 0 FLAC |
| `integrity` | F-08a, mapping piste, décodage ffmpeg échoué |
| `metadata` | pochette en erreur (warning FR, non bloquant publish) |
| `publish` | `PublishResult` négatif **ou** `RuntimeError` mid-copy (rollback) |
| `cancelled` / `interrupted` | utilisateur / cancel pendant tags |
| `unknown` | réservé |

Message type : résumé FR → `Action possible` → `Détail technique` (code, chemins). Les FLAC déjà présents sont signalés comme **récupérables, non publiés automatiquement**.

---

## 3. Contrôles FLAC

1. **F-08a** (structure) — inchangé, bloquant.  
2. **`decode_many` / ffmpeg null** — si outil trouvé (`AVM_FFMPEG` → PATH → fre:ac `codecs/cmdline/ffmpeg.exe`) : décodage intégral bloquant.  
3. **Sans outil** : `attempted=False`, `ok=True`, message *« ffmpeg introuvable … Contrôle structurel F-08a seul »* (non silencieux).  
4. **Mapping** : count ≠ N, doublons de numéro, trous 1…N si tous numérotés → `INTEGRITY`.  
5. **Durées vs TOC** : écart > 1,5 s → **warning** (non bloquant).

---

## 4. Cohérence SQLite / checkpoints / interruption

Lecture seule `avm.sqlite3` (post-06C/E/F) :

| Job | État | Checkpoints | Notes |
|-----|------|-------------|-------|
| `bd40b604…` | **Failed** | `Ripping` seul | error `freaccmd returncode=4294967293` ; 17 FLAC + `.temp` en zone A |
| `c43af993…` | Cancelled | `Ripping` | Annulation utilisateur |
| `8e23e82d…` | **Completed** | Ripping → FlacIntegrity → Tagging → Organizing | `library_path` = album Queen test |

Comportements renforcés :

- Cancel pendant tagging → état `Interrupted` + `FailureKind.INTERRUPTED`.  
- Checkpoint `FlacIntegrity` inclut désormais `"decode": "ok"|"skipped"` (jobs futurs).  
- Publication C : exception mid-copy capturée → Failed/`PUBLISH` (plus de remontée brute non typée).

---

## 5. Publication partielle, collisions, Windows

| Risque | Mitigation constatée |
|--------|----------------------|
| Album incomplet | Refus publish si `len(staged) ≠ layout` |
| Collision | Skip / Rename / Replace→trash (Replace UI toujours désactivé) |
| Copie interrompue | Rollback unlink des fichiers écrits + tentative restore trash ; message FR `PUBLISH` |
| Restauration Windows | Best-effort ; action utilisateur sur `.avm-trash` documentée dans le message |
| Inbox B | Toujours remplie avant C (traçabilité) — doublon inbox + C attendu |

Aucune modification des 17 FLAC publiés ni du dossier Queen.

---

## 6. Diagnostic pochette (lecteur externe « mal centrée »)

**Preuves** — `Queen/Greatest Hits (1992)/cover.jpg` + FLAC `01` (lecture seule) :

| Mesure | Valeur |
|--------|--------|
| `cover.jpg` | 28 980 o, **500×500**, ratio **1:1**, RGB |
| EXIF / orientation | **Absent** (pas de rotation metadata) |
| Coins vs centre | Coins sombre rougeâtres, pas de bandes blanches type letterbox dans le fichier |
| Embarquée | Même blob que `cover.jpg` ; dims **réelles** JPEG 500×500 |
| METADATA Picture width/height | **0×0** sur fichiers publiés (écrits avant renseignement dims) |
| Cache CAA local | `e534e30a….jpg` 500×500, 37 811 o (autre variante front, même format vignette) |

**Conclusion :** pas de recadrage AVM. L’affichage « décentré / bandes » côté lecteur externe s’explique par une **vignette carrée 500 px** placée dans une zone d’UI plus large (letterboxing lecteur), pas par un défaut de géométrie du fichier.  
**Correctif code (nouveaux jobs) :** `tags.py` renseigne `Picture.width/height` depuis le JPEG ; `cover_geometry.analyze_cover_bytes` ajoute des notes au rapport job. **Pas de retag** des 17 FLAC sans mandat explicite.

---

## 7. Messages d’erreur FR

Exemples couverts :

- Extraction `4294967293` / signé `-3` + hint « fichier attendu » + compte FLAC récupérables.  
- Intégrité mapping / F-08a / décodage.  
- Publish / rollback.  
- Interruption tagging.

Toujours : cause compréhensible + action réellement dispo (journaux job, ne pas re-rip aveugle, inbox/trash).

---

## 8. Tests de régression (sans CD)

Fichier `tests/test_diagnostics_06g.py` :

| Test | Cible |
|------|--------|
| `test_freac_signed_code_and_user_message_keeps_technical` | −3 / 17 FLAC / tech visible |
| `test_persist_freac_logs` | fichiers job |
| `test_ripper_persists_logs_and_french_error_on_nonzero` | Popen simulé rc≠0 |
| `test_match_rejects_duplicate_track_numbers` | mapping |
| `test_cover_geometry_square_thumbnail` | notes vignette |
| `test_embedded_cover_sets_dimensions` | Picture w/h |
| `test_decode_skips_explicitly_without_tool` | skip explicite |
| `test_decode_ok_when_ffmpeg_present` | soft-skip si pas d’outil |
| `test_publish_runtime_error_classified_as_publish` | erreur simulée publish |

**Suite complète : 109 passed.**

---

## 9. Fichiers touchés (06G)

| Chemin | Rôle |
|--------|------|
| `diagnostics/failure_kinds.py` | taxonomie + messages fre:ac |
| `diagnostics/freac_logs.py` | persistance I/O |
| `extraction/cd_ripper.py` | logs + FR + returncode strict |
| `verification/flac_decode.py` | décodage intégral optionnel |
| `library/cover_geometry.py` | analyse dims / notes |
| `library/tags.py` | width/height Picture |
| `orchestration/archive_job.py` | kinds, decode, durées, cover notes, publish catch |
| `tests/test_diagnostics_06g.py` | régressions |
| `docs/ux/reports/AVM-06G-ROBUSTESSE-DIAGNOSTICS.md` | ce rapport |

---

## 10. Risques résiduels

| ID | Gravité | Description | Suite proposée |
|----|---------|-------------|----------------|
| R-G1 | P2 | AccurateRip / offset non couverts | Hors 06G |
| R-G2 | P2 | Picture 0×0 sur album Queen déjà publié | Retag optionnel sur mandat |
| R-G3 | P2 | Restore trash Windows non garantie à 100 % | Doc utilisateur / UI-2 |
| R-G4 | Info | Job Failed `bd40` vs FLAC OK | Conservé volontairement |
| R-G5 | Info | fre:ac peut encore renvoyer rc≠0 avec FLAC OK | Strict conservé ; recovery staging inchangé |

---

## 11. Critères GO / NO-GO

### Clôture AVM-06G

| # | Critère | Statut |
|---|---------|--------|
| G1 | Logs fre:ac persistés + erreurs non masquées | **GO** |
| G2 | FailureKind + messages FR | **GO** |
| G3 | Decode optionnel explicite | **GO** |
| G4 | Mapping / durées | **GO** |
| G5 | SQLite / interrupt / publish catch audités | **GO** |
| G6 | Pochette diagnostiquée sans recadrage | **GO** |
| G7 | Tests + 109 PASS | **GO** |
| G8 | Pas de rip / pas de mutation biblio / strict rc | **GO** |

### Entrée AVM-06H

| # | Critère | Statut |
|---|---------|--------|
| H0 | Validation mandant de ce rapport | **EN ATTENTE** |

---

**Fin AVM-06G — arrêt obligatoire. Attendre GO explicite avant AVM-06H.**
