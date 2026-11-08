# AVM-25 — Assainissement Git et nettoyage ciblé

**Verdict : VALIDÉ pour le nettoyage ciblé; dépôt non propre, car les travaux fonctionnels préexistants restent volontairement non commités et non indexés.** Aucun commit, stage, reset, purge locale ou déplacement n’a été effectué.

## Inventaire Git

L’état observé comprend des modifications suivies et de nombreux nouveaux fichiers non suivis, entre autres :

| Groupe constaté | Exemples présents dans l’arbre de travail | Traitement AVM-25 |
|---|---|---|
| CD / pipeline | `metadata/musicbrainz_client.py`, `orchestration/archive_job.py`, `orchestration/rip_lock.py`, `tests/test_avm19_stabilization.py`, `tests/test_archive_pipeline.py`, changements `config.py` | Conservé; aucune remise à zéro ni réorganisation. |
| DVD | `extraction/dvd.py`, `dvd_extractor.py`, `dvd_navigation.py`, `metadata/video.py`, `library/video_archive.py`, workers/dialogue DVD, `catalog.py`, `database.py`, `schema.py`, tests DVD et rapports/preuves AVM-11 à AVM-16 | Conservé intégralement; plusieurs fichiers sont non suivis et relèvent du travail utilisateur. |
| UI partagée CD/DVD | `ui/main_window.py`, `settings_page.py`, `wizard/archive_wizard.py`, `library_host.py`, `library_page.py`, `tests/test_ui_shell.py` | Conservé. Ces fichiers mélangent des deltas UI/CD/DVD; ne pas les committer en bloc sans séparation hunk par hunk. |
| Documentation et preuves | README, docs produit/domaine, rapports AVM-11 à AVM-24 et répertoires evidence | Conservés; aucune preuve historique n’a été supprimée ou éditée par AVM-25. |
| Tests / scripts locaux | `scripts/run_tests_ci.py`, diagnostics `scripts/diag11f`, `diag12`, `diag14`, tests CD/DVD/UI | Conservés. La liste CI existante demeure inchangée pour AVM-25. |
| Instructions locales | `.github/copilot-instructions.md` non suivi | Conservé comme fichier de travail utilisateur. |

Le changement préexistant de `.gitignore` qui autorise `audio_video_manager/library/video_archive.py` au milieu de l’ignore générique `library/` est cohérent avec le nouveau module DVD versionné/non suivi; il n’a pas été modifié. La recherche Git des motifs `__pycache__`, bytecode Python, SQLite, `.ci/`, `.capture_*` et `*.egg-info` n’a trouvé aucun de ces artefacts déjà suivis. Les captures et images suivies sous `docs/` restent des preuves documentaires, pas des sorties générées accidentellement à la racine.

## Nettoyage exécuté

- Retiré `audio_video_manager/ui/sections/placeholder_page.py`. Le fichier ne contenait que la classe `PlaceholderPage`; aucune référence d’import, instanciation, chargement dynamique, QML, test ou documentation active n’a été trouvée. AVM-22 avait déjà identifié ce stub comme retirable. Le retrait n’affecte ni API publique ni parcours.
- Aucun autre code historique n’a été retiré : les prototypes `prototypes/avm_*` sont référencés comme sources visuelles et commandes par les rapports UX; `scripts/diag*` et `scripts/capture_avm*.py` sont cités dans les procédures et rapports historiques. QML est conservé par décision AVM-22/23.
- Aucun artefact ignoré n’a été purgé. Les anciens `.ci/avm10c1*`, `avm10c2*`, `avm10d*` sont référencés comme résultats dans les rapports AVM-10C/10D. Les `.capture_avm*` sont des preuves locales de validations UX; AVM-21 demandait une autorisation de purge qui n’est pas donnée nommément ici. `.ci/`, captures, `.tmp-avm-smoke/`, caches, `*.egg-info`, dossiers de jobs, médias, SQLite et configurations restent intacts. Les nouveaux résultats AVM-25 demeurent sous `.ci/avm25-ci-results.json` et `.ci/junit/avm25/`, ignorés par Git.
- Le dialogue `DiscMetadataDialog` et son test étaient déjà supprimés avant AVM-25 par AVM-23; ce ne sont pas des suppressions AVM-25.

## Groupes proposés pour de futurs commits

Rien n’a été indexé. La séparation suivante est proposée pour préserver l’autonomie des changements et faciliter la revue :

1. **Stabilisation CD** : changements de MusicBrainz, verrou rip, pipeline/archive et tests CD correspondants; relire AVM-19 et les rapports CD associés.
2. **Destination et UX CD** : défaut Widgets, réglage/persistance bibliothèque, wizard, retours de publication et tests UI/config. Les fichiers `config.py`, `main_window.py`, `settings_page.py`, `archive_wizard.py`, `library_host.py` et `library_page.py` contiennent aussi des changements DVD : les séparer par hunks, pas par ajout complet du fichier.
3. **Fonctionnalité DVD** : extraction/inspection, modèle/catalogue et schéma, workers/UI, tests et rapports DVD. Les fichiers partagés tels que `main_window.py`, `archive_wizard.py`, `library_page.py`, `catalog.py`, `database.py`, `schema.py`, `README.md` et `pyproject.toml` exigent une revue hunk par hunk.
4. **Assainissement AVM-25** : suppression isolée de `audio_video_manager/ui/sections/placeholder_page.py` et présent rapport uniquement.
5. **Rapports/preuves AVM-11 à AVM-24** : groupe de documentation distinct; vérifier avant indexation que les captures et rapports non suivis sont bien destinés à être versionnés. Ne pas inclure `.ci/` ou d’autres artefacts ignorés.

Ce sont des propositions de groupement; l’arbre reste entièrement non indexé par AVM-25. Aucun `git add` n’a été exécuté afin de ne pas capturer des modifications utilisateur en vrac.

## Validation

- Recherche des références `PlaceholderPage` après retrait : aucune référence active; les seules occurrences restantes sont les mentions d’analyse dans AVM-22.
- Suites Widgets/Historique ciblées : `tests/test_ui_design_06l.py` **8 réussis**; `tests/test_ui_library_history_06h.py` **9 réussis**.
- CI Windows complète : `.venv/Scripts/python.exe scripts/run_tests_ci.py --report .ci/avm25-ci-results.json --junit-dir .ci/junit/avm25` — **369 tests, 13 groupes, 0 échec, 0 erreur, 0 skip, 0 crash natif; GO**.
- `git diff --check` : réussi.

Les suites sont synthétiques; aucune extraction CD/DVD physique n’a été lancée. Les rapports, médias personnels, bases SQLite, configurations, jobs, QML et travaux DVD préexistants sont à laisser intacts.

**Arrêt AVM-25 :** le seul nettoyage de code est la suppression du stub sans référence. Aucun commit, nettoyage destructif, stage ou mandat suivant n’est engagé.