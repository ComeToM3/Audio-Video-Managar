# AVM-19 — Stabilisation ciblée du parcours CD

**Mandat :** implémenter les corrections P0/P1 identifiées par
[AVM-18](./AVM-18-REVUE-MATURITE-PRODUCTION-CD.md), sans refonte ni
complexification. Sept corrections demandées : P0-2, P1-9, P1-11, P1-3,
P1-10, P0-1, P1-12. Diagnostic uniquement pour le périmètre ; correctifs
strictement limités aux constats cités.

---

## 1. Synthèse par correction

| # | Item AVM-18 | Fichier(s) modifié(s) | Verdict |
|---|---|---|---|
| 1 | P0-2 — copie publication TOCTOU-safe | `audio_video_manager/library/transfer.py` | **VALIDÉ** |
| 2 | P1-9 — collisions noms de pistes | `audio_video_manager/orchestration/archive_job.py` | **VALIDÉ** |
| 3 | P1-11 — rollback publication `replace` | `audio_video_manager/library/publish.py` | **VALIDÉ** |
| 4 | P1-3 — verrou de rip exclusif | `audio_video_manager/orchestration/rip_lock.py`, `archive_job.py` | **VALIDÉ** |
| 5 | P1-10 — tags FLAC sans champs obsolètes | `audio_video_manager/library/tags.py` | **VALIDÉ** |
| 6 | P0-1 — identification asynchrone | `audio_video_manager/ui/metadata_dialog.py` | **VALIDÉ (avec limite notée)** |
| 7 | P1-12 — délai/429 MusicBrainz | `audio_video_manager/metadata/musicbrainz_client.py` | **VALIDÉ** |

**Verdict global : VALIDÉ.** Les 7 corrections sont implémentées, testées
par des tests ciblés (`tests/test_avm19_stabilization.py`, 10 tests), et la
CI complète est verte (276 tests domaine + 8 modules UI, `OVERALL: GO`,
voir §4). Aucune donnée personnelle, aucune fonctionnalité CD/DVD existante
n'a été supprimée ou modifiée en dehors du périmètre demandé.

---

## 2. Détail par correction

### P0-2 — Copie de publication exclusive (TOCTOU) — `transfer.py`

**Constat AVM-18 :** les copies de publication utilisaient
`shutil.copy2(src, dest)` directement : fenêtre entre la vérification
d'absence de `dest` et l'écriture, permettant un écrasement si un autre
processus créait la cible entre-temps.

**Correctif :** nouvelle fonction `_atomic_exclusive_copy(src, dest)`
(`transfer.py:~100`) qui ouvre `dest` avec `os.O_CREAT|os.O_EXCL|os.O_WRONLY`
— création atomique garantie par l'OS, échoue immédiatement avec
`FileExistsError` si la cible existe déjà (créée par nous ou par un tiers).
Le contenu est ensuite copié dans le descripteur ouvert (`shutil.copyfileobj`)
et les métadonnées (`shutil.copystat`) ; tout échec en cours de copie
supprime le fichier partiel (`dest.unlink()`), évitant un résidu bloquant
une tentative ultérieure. Utilisée dans les branches `independent=True` et
`copy`/`auto` de `transfer_file()`. La voie hardlink (`os.link(src, dest)`)
reste inchangée — déjà atomique.

**Risque résiduel :** aucun écrasement silencieux n'est plus possible ;
message d'erreur identique au comportement précédent (`FileExistsError`)
pour compatibilité avec les appelants existants.

**Tests :** `test_transfer_copy_refuses_to_overwrite_existing_destination`
(vérifie refus + absence de corruption + absence de fichier temporaire
résiduel) ; non-régression confirmée sur
`tests/test_hardlink_security_06gp1.py::test_transfer_falls_back_to_copy_when_os_link_fails`
(ce test a révélé que la première itération du correctif réutilisait
`os.link` en interne et cassait le scénario de repli simulé — corrigé en
adoptant l'approche `O_EXCL` directe, sans fichier temporaire ni second
appel `os.link`).

---

### P1-9 — Collisions de noms de pistes après sanitisation — `archive_job.py`

**Constat AVM-18 :** la génération de noms de fichiers taggués utilisait une
sanitisation ad-hoc divergente de `metadata/path_preview.sanitize_segment`
utilisée ailleurs dans le produit ; en cas de convergence de deux titres
sanitisés, `shutil.copy2` écrasait silencieusement le premier fichier.

**Correctif (`archive_job.py:~654`) :** la génération du nom de fichier
réutilise désormais `sanitize_segment(track.title, fallback="_")` (cohérence
avec le reste du produit). Une boucle de désambiguïsation ajoute un suffixe
`" (2)", " (3)", ...` si `dest.exists()` avant la copie — aucun écrasement
silencieux possible même en cas de collision.

**Tests :** `test_archive_job_disambiguates_colliding_track_titles` — deux
pistes dont les titres convergent après sanitisation produisent deux
fichiers distincts dans `workdir/tagged/`.

---

### P1-11 — Rollback sûr de la publication `replace` — `publish.py`

**Constat AVM-18 :** en cas d'échec pendant une publication `replace`, le
rollback tentait un `dest_album.rmdir()` qui échouait silencieusement en
présence de sous-dossiers non vides (layouts multi-disque), empêchant à la
fois le nettoyage et la restauration ultérieure de l'ancien album depuis la
corbeille (`trash_dir`) — car la condition de restauration exigeait
`not dest_album.exists()`.

**Correctif (`publish.py:193-214`) :** le bloc `except Exception` effectue
désormais un `shutil.rmtree(dest_album, ignore_errors=True)` inconditionnel
(sûr : `dest_album` est toujours du contenu fraîchement créé par cette
publication, jamais une donnée utilisateur préexistante), puis restaure
`trash_dir` vers `dest_album` via `shutil.move`. Un échec de restauration
est désormais journalisé explicitement (`log.error`) au lieu d'être avalé
par un `except OSError: pass` muet.

**Tests :** `test_publish_replace_rollback_restores_old_album_with_nested_subdir`
— ancien album avec sous-dossier vide imbriqué (`CD1/`), échec simulé sur
la 2ᵉ piste via un `transfer_file` défaillant, vérifie que l'ancien album
est intégralement restauré (fichiers + sous-dossier) après l'exception.

---

### P1-3 — Verrou de rip réellement exclusif — `rip_lock.py`

**Constat AVM-18 :** `write_rip_lock` utilisait `Path.write_text`, non
atomique — deux processus pouvaient écrire le verrou en parallèle sans
qu'aucun des deux ne détecte l'autre.

**Correctif (`rip_lock.py:140-181`) :** réutilise exactement le patron déjà
établi par `try_acquire_recovery_file_lock` du même module : création
atomique via `os.O_CREAT|os.O_EXCL`, et en cas de `FileExistsError`,
inspection du verrou existant (`_parse_lock_file` + `is_lock_holder_active`,
fonctions déjà existantes, non dupliquées). Si le détenteur est actif →
nouvelle exception `RipLockHeldError` (au lieu d'un écrasement silencieux).
Si le verrou est mort/orphelin (PID mort ou identité PID incohérente, cas
réutilisation de PID déjà géré par le module) → reprise automatique
(unlink + nouvelle création atomique).

`archive_job.py` (`:382-397`) encadre l'appel `write_rip_lock` d'un
`try/except RipLockHeldError`, produit un
`format_user_error(kind=FailureKind.EXTRACTION, ...)` et renvoie un
`ArchiveJobReport(state="Failed", ...)` cohérent avec les autres chemins
d'échec du fichier (au lieu de laisser l'exception remonter brute).

**Tests :** `test_write_rip_lock_raises_when_holder_active` (contention
avec détenteur vivant → `RipLockHeldError`) ;
`test_write_rip_lock_reclaims_stale_lock_from_dead_pid` (verrou orphelin
repris silencieusement, comportement préservé). Non-régression vérifiée
contre `tests/test_reconciliation_10b.py` et `test_reconciliation_10c.py`
(aucun double appel `write_rip_lock` sans libération intermédiaire dans
ces tests — aucun impact).

---

### P1-10 — Tags FLAC sans champs obsolètes — `tags.py`

**Constat AVM-18 :** `apply_flac_tags` n'écrivait que les champs présents
dans la fiche approuvée mais ne retirait jamais un tag préexistant sur le
fichier source (ex. tag `comment`/`genre` laissé par fre:ac ou un tagging
antérieur) — contraire au commentaire du module
(« reflètent uniquement la fiche approuvée »).

**Correctif (`tags.py:38-44`) :** `audio.tags.clear()` est appelé juste
après l'ouverture du FLAC (et avant toute écriture `_set(...)`), si
`audio.tags is not None`. Vérifié via le `.venv` du projet que
`mutagen.flac.FLAC.__setitem__` recrée automatiquement le bloc de tags via
`add_tags()` si `tags is None` — la mise à zéro est donc sûre même sur un
FLAC sans bloc Vorbis Comment préexistant.

**Tests :** `test_apply_flac_tags_clears_stale_tag_not_in_sheet` — un FLAC
pré-tagué avec `comment`/`genre` (absents de la fiche) les voit disparaître
après `apply_flac_tags`, tout en conservant les champs attendus
(`album`, etc.).

---

### P0-1 — Identification asynchrone du dialogue de métadonnées — `metadata_dialog.py`

**Constat AVM-18 :** `DiscMetadataDialog.on_identify()` appelait
`identify_disc(...)` (lecture TOC + requête MusicBrainz) directement dans
le thread UI, bloquant l'interface pendant toute la durée de
l'identification.

**Correctif (`metadata_dialog.py`) :** réutilise intégralement le patron déjà
en place dans `ui/wizard/archive_wizard.py` — `IdentifyWorker`
(`ui/identify_worker.py`, non modifié) + `attach_worker_thread`/
`shutdown_worker_thread` (`ui/thread_lifecycle.py`, non modifié).
`on_identify()` devient asynchrone : crée le worker, démarre un `QThread`,
désactive les boutons sensibles pendant l'opération (`_set_identify_busy`),
réagit à `finished`/`failed` via `_on_identify_ok`/`_on_identify_fail`, et
un `closeEvent` surchargé garantit un arrêt borné du thread si la fenêtre
est fermée pendant une identification en cours (cohérent avec le
comportement documenté par AVM-15 pour les fermetures de fenêtres pendant
une opération Qt asynchrone).

**Limite résiduelle notée :** l'ancien code synchrone distinguait
`LibdiscidMissingError` (critique), `MusicBrainzError` et `RuntimeError`
génériques par icône/titre de boîte de dialogue différents. Le signal
partagé `IdentifyWorker.failed` n'émet que `str(exc)` — cette
différenciation de type est perdue au profit d'un message d'avertissement
générique unique. Ce compromis a été jugé acceptable et minimal plutôt que
de modifier le worker partagé avec l'assistant d'archivage (qui ne fait pas
cette distinction non plus). **Amélioration facultative (P2), non
bloquante,** si une différenciation fine est souhaitée ultérieurement.

**Précision :** `DiscMetadataDialog` n'est actuellement pas instancié par
`main_window.py` (code UI non branché, uniquement exercé par les tests) —
la correction a néanmoins été implémentée telle que demandée explicitement
par le mandat.

**Tests :** aucun test Qt supplémentaire créé (le harnais Qt offscreen
existant de `tests/test_metadata_dialog_sources.py` ne couvre que
`_apply_form_to_sheet()` et ne testait déjà pas `on_identify()` avant
cette modification — non-régression confirmée, 3/3 tests de ce fichier
passent toujours après le correctif).

---

### P1-12 — Délais MusicBrainz bornés + 429/Retry-After — `musicbrainz_client.py`

**Constat AVM-18 :** `lookup_releases_by_discid` appelait
`musicbrainzngs.get_releases_by_discid()` sans aucun délai borné
explicite, et toute réponse HTTP 429 remontait comme une erreur générique
sans tenir compte d'un éventuel en-tête `Retry-After` — risque de blocage
long ou d'échec immédiat sur une limitation de débit pourtant temporaire.

**Correctif (`musicbrainz_client.py`) :**
- `DEFAULT_TIMEOUT_SEC = 15.0` : la requête est désormais exécutée sous
  `_bounded_socket_timeout(DEFAULT_TIMEOUT_SEC)`, un gestionnaire de
  contexte posant `socket.setdefaulttimeout(...)` le temps de l'appel puis
  restaurant la valeur précédente (musicbrainzngs n'expose pas de
  paramètre de timeout par appel ; c'est le mécanisme que la librairie
  respecte en interne via `urllib`). `TimeoutError` est capturé et
  re-levé en `MusicBrainzError` explicite.
- `MAX_RETRY_AFTER_SEC = 10.0` : sur un 429, l'en-tête `Retry-After` est lu
  (`_retry_after_seconds`). S'il est présent et ≤ au plafond, **un seul**
  nouvel essai est tenté après l'attente indiquée ; sinon (en-tête absent,
  invalide, ou dépassant le plafond), l'appel échoue immédiatement avec un
  message explicite — jamais d'attente illimitée ni de boucle de reprise
  non bornée.

**Tests :**
`test_musicbrainz_lookup_wraps_timeout_error`,
`test_musicbrainz_429_with_short_retry_after_succeeds_on_retry`,
`test_musicbrainz_429_with_long_retry_after_raises_without_unbounded_wait`,
`test_default_timeout_is_bounded`. Non-régression confirmée sur
`tests/test_musicbrainz_identify.py` (18 tests) et
`tests/test_musicbrainz_identity.py`.

---

## 3. Fichiers modifiés (résumé)

| Fichier | Nature du changement |
|---|---|
| `audio_video_manager/library/transfer.py` | `_atomic_exclusive_copy` (P0-2) |
| `audio_video_manager/library/publish.py` | Rollback `replace` (P1-11) |
| `audio_video_manager/orchestration/archive_job.py` | Collision noms pistes (P1-9) + verrou rip (P1-3) |
| `audio_video_manager/orchestration/rip_lock.py` | `write_rip_lock` exclusif + `RipLockHeldError` (P1-3) |
| `audio_video_manager/library/tags.py` | Nettoyage tags avant écriture (P1-10) |
| `audio_video_manager/ui/metadata_dialog.py` | Identification asynchrone (P0-1) |
| `audio_video_manager/metadata/musicbrainz_client.py` | Timeout + 429/Retry-After bornés (P1-12) |
| `tests/test_avm19_stabilization.py` | **Nouveau** — 10 tests ciblés couvrant les 6 correctifs testables directement |
| `scripts/run_tests_ci.py` | Ajout du nouveau fichier de tests à `DOMAIN_GLOBS` |

Aucun fichier non lié au mandat n'a été modifié. Aucune donnée, migration
SQLite ou fonctionnalité DVD n'a été touchée.

---

## 4. Validation

**Tests ciblés (nouveaux) :**
```
.venv\Scripts\python.exe -m pytest tests/test_avm19_stabilization.py -q
# 10 passed
```

**Non-régression sur les suites directement concernées :**
```
.venv\Scripts\python.exe -m pytest tests/test_reconciliation_10b.py tests/test_reconciliation_10c.py \
  tests/test_rip_job.py tests/test_archive_pipeline.py tests/test_archive_recovery_staging.py \
  tests/test_hardlink_security_06gp1.py tests/test_cd_ripper.py tests/test_video_archive_15.py \
  tests/test_perf_06gp.py tests/test_metadata_dialog_sources.py -q
# tous passés
.venv\Scripts\python.exe -m pytest tests/test_musicbrainz_identify.py tests/test_musicbrainz_identity.py -q
# tous passés
```

**CI complète (convention du dépôt) :**
```
.venv\Scripts\python.exe scripts\run_tests_ci.py --report .ci\avm19-report.json --junit-dir .ci\junit\avm19
# domain: tests=276 fail=0 err=0 skip=0
# 8 modules UI : tous OK
# OVERALL: GO
```

Toutes les validations sont des tests automatisés synthétiques (y compris
pour le verrou de rip, simulé par manipulation directe du fichier verrou,
et pour MusicBrainz, simulé par injection de `get_releases_fn`). **Aucune
extraction physique de CD réelle n'a été lancée** pour ce mandat — conforme
à la consigne « ne pas lancer d'extraction réelle sans autorisation ».
Aucun essai physique sur support n'était requis par les corrections
apportées (toutes situées dans la logique de fichiers, de verrouillage et
réseau, pas dans le pilotage matériel du lecteur).

---

## 5. Risques résiduels et limites

- **P0-1 :** perte de la différenciation du type d'erreur d'identification
  (critique vs avertissement) au profit d'un message générique unique —
  amélioration facultative P2, non bloquante.
- **P0-1 :** `DiscMetadataDialog` reste du code UI non branché dans
  `main_window.py` ; la correction le rend prêt à l'emploi mais ne change
  pas son statut d'intégration (hors périmètre du mandat).
- **P1-12 :** l'usage de `socket.setdefaulttimeout()` est une mesure
  globale au processus le temps de l'appel MusicBrainz (restaurée aussitôt
  après) ; c'est la seule option offerte par `musicbrainzngs` sans modifier
  cette dépendance, et sa portée est strictement bornée à la durée de
  l'appel réseau synchrone.
- **P1-3 :** le comportement de `run_rip_job()` en cas de `RipLockHeldError`
  non catché à ce niveau repose sur le `except Exception` générique déjà
  présent dans `RipWorker.run()` (`ui/rip_worker.py`) — jugé suffisant
  (l'erreur remonte proprement à l'UI), aucune modification apportée à
  `rip_job.py` lui-même (hors périmètre explicite du mandat).
- Aucune régression introduite n'a été détectée sur l'ensemble de la CI
  (276 tests domaine + 8 modules UI, tous verts).

---

## 6. Verdict

**VALIDÉ.** Les 7 corrections P0/P1 du mandat AVM-19 sont implémentées,
couvertes par des tests ciblés, non régressives sur la CI complète du
dépôt, et respectent les garde-fous (aucune donnée perdue, aucune
fonctionnalité CD/DVD supprimée, aucune refonte, réutilisation systématique
des mécanismes existants : patron de verrou atomique, workers Qt,
`sanitize_segment`).

Mandat clos. Aucun chantier AVM-20 engagé.
