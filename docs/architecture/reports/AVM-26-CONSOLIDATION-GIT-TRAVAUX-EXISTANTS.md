# AVM-26 — Consolidation Git des travaux existants

**État : groupe applicatif principal préparé dans l’index; aucun commit créé.** Branche `main` alignée sur `origin/main`, HEAD initial `b4c0007` (`Initial commit`). L’index était vide au début d’AVM-26. Le worktree reste volontairement modifié et contient d’autres groupes non indexés.

## Inventaire et décisions

- **Groupe applicatif CD/DVD/UI :** modifications CD de MusicBrainz, verrouillage et publication; modules DVD ajoutés; schéma/catalogue et shell partagés; suppression approuvée de `DiscMetadataDialog`; tests CD/DVD/UI et documentation produit. Ces changements sont interdépendants dans `config.py`, `main_window.py`, `archive_wizard.py`, `library_host.py`, `library_page.py`, les modules storage et `tests/test_ui_shell.py`. Les séparer par hunks créerait des états de travail incohérents; ils sont donc préparés ensemble.
- **Entretien :** suppression de `placeholder_page.py` (déjà démontrée sans appel) et rapports AVM-25/26. Ce groupe reste non indexé afin de préserver une frontière claire avec le changement fonctionnel.
- **Outils de diagnostic :** `scripts/diag11f/validate_windows.py`, `scripts/diag12/inspect_physical.py`, `scripts/diag14/validate_physical.py` restent non indexés. Ils sont des outils séparés de reproduction/inspection, référencés par les rapports; ils ne sont ni importés par l’application ni invoqués par la CI.
- **Rapports/preuves AVM-11 à AVM-24 :** laissés non indexés. Plusieurs rapports et JSON d’evidence contiennent des chemins absolus du profil utilisateur ou renvoient à des captures d’interface; l’ensemble doit être examiné/redigé en cohérence avec ses références avant versionnement. Les captures n’ont pas été ouvertes, déplacées ou ajoutées à l’index.
- **Instructions locales :** `.github/copilot-instructions.md` reste non indexé, car c’est un fichier d’instructions propre au dépôt dont la publication doit être confirmée séparément.
- **Données générées/personnelles :** aucun SQLite, média, job, configuration, `.ci/`, `.capture_avm*/`, `.tmp-avm-smoke/`, cache, `*.egg-info` ou secret n’est suivi ou indexé par AVM-26. Les preuves existantes sous `docs/` restent intactes.

## Groupe indexé

Un seul groupe est actuellement dans l’index : **42 fichiers, 5 972 insertions et 757 suppressions**, vérifiés via `git diff --cached`. Message proposé :

```text
feat: integrate CD archival and DVD-Video workflows
```

Fichiers inclus exactement :

```text
.gitignore
README.md
audio_video_manager/config.py
audio_video_manager/extraction/__init__.py
audio_video_manager/extraction/dvd.py
audio_video_manager/extraction/dvd_extractor.py
audio_video_manager/extraction/dvd_navigation.py
audio_video_manager/library/video_archive.py
audio_video_manager/metadata/musicbrainz_client.py
audio_video_manager/metadata/video.py
audio_video_manager/orchestration/archive_job.py
audio_video_manager/orchestration/rip_lock.py
audio_video_manager/storage/catalog.py
audio_video_manager/storage/database.py
audio_video_manager/storage/schema.py
audio_video_manager/ui/dvd_extraction_dialog.py
audio_video_manager/ui/dvd_worker.py
audio_video_manager/ui/main_window.py
audio_video_manager/ui/metadata_dialog.py        (suppression AVM-23 approuvée)
audio_video_manager/ui/sections/library_host.py
audio_video_manager/ui/sections/library_page.py
audio_video_manager/ui/sections/settings_page.py
audio_video_manager/ui/video_worker.py
audio_video_manager/ui/wizard/archive_wizard.py
docs/domain/disc-metadata.md
docs/product/architecture.md
docs/product/decisions.md
docs/product/requirements.md
docs/product/roadmap.md
scripts/run_tests_ci.py
tests/test_archive_pipeline.py
tests/test_avm19_stabilization.py
tests/test_config.py
tests/test_database.py
tests/test_dvd_extractor_11c.py
tests/test_dvd_inspector_11b.py
tests/test_library_qml_08b.py
tests/test_metadata_dialog_sources.py    (suppression AVM-23 approuvée)
tests/test_ui_shell.py
tests/test_ui_w3_prefill.py
tests/test_ux_06o.py
tests/test_video_archive_15.py
```

La suppression de `metadata_dialog.py` et de ses tests est incluse parce que l’abandon a été approuvé en AVM-23; `IdentifyWorker` et les services partagés sont conservés. Le choix QML explicite et les protections correspondantes restent présents. Le groupe ne contient aucun rapport historique ni fichier de preuve.

## Groupes proposés ensuite

1. **Commit applicatif** — le groupe de 42 fichiers actuellement indexé, message proposé ci-dessus. Il combine CD et DVD en raison des fichiers UI/configuration/catalogue partagés; CI complète déjà passée sur ce worktree.
2. **Commit d’entretien** — à indexer après le premier : `audio_video_manager/ui/sections/placeholder_page.py` (suppression), `docs/architecture/reports/AVM-25-ASSAINISSEMENT-GIT-NETTOYAGE-CIBLE.md` et `docs/architecture/reports/AVM-26-CONSOLIDATION-GIT-TRAVAUX-EXISTANTS.md`. Message proposé : `chore: remove unused placeholder UI page`.
3. **Commit de diagnostics facultatif** — `scripts/diag11f/validate_windows.py`, `scripts/diag12/inspect_physical.py`, `scripts/diag14/validate_physical.py`; à décider séparément avec leurs rapports référents.
4. **Documentation/evidence AVM-11 à AVM-24** — ne pas indexer avant revue des chemins personnels, des captures et de la complétude des liens. Les rapports AVM-20/21/22/23/24 sont non suivis; les preuves `.ci/` restent ignorées et exclues.
5. **`.github/copilot-instructions.md`** — décision distincte requise sur son caractère local ou partagé; laissé hors index.

Ces groupes 2 à 5 n’ont pas été ajoutés à l’index. L’index ne contient donc que le groupe applicatif et ne représente pas encore un ensemble complet de commits.

## Validation

- Historique : `git log -8 --oneline --decorate` montre uniquement `b4c0007` (`Initial commit`); aucun commit précédent n’a été modifié.
- Index initial vide; `git diff --cached --name-status` confirme désormais les 42 fichiers listés ci-dessus.
- `git diff --cached --check` : réussi. Scan des lignes ajoutées indexées pour `ComeToM3`, `C:\Users\` et `AVM-06C-Test-Library` : aucun résultat. La recherche dans l’index complet retrouve des références personnelles préexistantes dans des fichiers déjà versionnés, mais aucun de ces fichiers ni leur contenu n’est modifié/indexé par ce groupe.
- `git status --short --branch` : `main...origin/main`; aucun commit, push ou changement de branche.
- Suites ciblées préalables : widgets/QML, métadonnées, publication et DVD; résultat final de CI : **369 tests, 13 groupes, 0 échec/erreur/skip/crash natif** avec `.venv/Scripts/python.exe scripts/run_tests_ci.py --report .ci/avm25-ci-results.json --junit-dir .ci/junit/avm25`. Les contenus indexés correspondent aux fichiers testés; le stage n’a changé que l’index.

**Arrêt AVM-26 :** le groupe applicatif est prêt à être revu et validé. Aucun `git commit` n’a été exécuté; les autres groupes et leur versionnement attendent votre approbation.