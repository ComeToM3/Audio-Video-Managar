# AVM-24 — Passage à l’archivage CD réel

**Verdict : PARTIEL — le routage/configuration et le pipeline logiciel sont vérifiés; aucun CD physique n’a été lu dans ce mandat.** La validation matérielle finale reste à effectuer par l’utilisateur avec son prochain CD et son accord explicite.

## Fonctionnement établi

- **Configuration.** `AppConfig.library_root` est persisté dans `config.json`. Paramètres fournit un sélecteur de dossier, et Enregistrer sauvegarde la valeur puis la transmet au wizard et à `LibraryHost`. Une nouvelle configuration cible `~/Music/AudioVideoManager` (sous Windows, le dossier Music du profil). Les dossiers de jobs et SQLite restent séparés sous `%LOCALAPPDATA%\AudioVideoManager` par défaut. La publication crée la racine bibliothèque si elle n’existe pas; l’enregistrement du réglage ne déplace ni ne crée des albums.
- **Mode `technical_test`.** Paramètres → Avancé déclenche `RipWorker` → `run_rip_job(mode=TECHNICAL_TEST)`. Les FLAC et l’état du job restent dans la zone de travail sous `jobs_dir`; `run_rip_job` interdit la publication bibliothèque même si une fiche approuvée lui est fournie. Le message affiche maintenant explicitement `technical_test` et « Publication bibliothèque : aucune ».
- **Archivage normal.** Le wizard CD exige l’approbation, vérifie le CD/TOC, exige l’option « Publier dans ma bibliothèque après extraction », puis passe la valeur courante de `library_root` à `ArchiveWorker` et appelle le pipeline avec `confirm_publish=True`. Le pipeline vérifie les FLAC, les doublons et les collisions, place les fichiers de travail/inbox sous la racine configurée, publie sous cette même racine sans écrasement silencieux, puis enregistre le release et ses pistes dans la base SQLite utilisateur.
- **Affichage.** Widgets lit `releases` depuis cette même base; `list_releases()` ne filtre pas selon la racine, et le wizard rafraîchit la bibliothèque après publication. Le W4 affiche maintenant le mode normal et la destination avant le rip. W5 distingue une publication/indexation réussie d’une publication non effectuée ou ignorée; le test technique n’est jamais présenté comme un album archivé.
- **Récupération et doublons.** La reprise depuis fichiers exige une confirmation, crée un nouveau job à partir des FLAC existants sans déplacer/supprimer les sources, réutilise la racine configurée et repasse par les contrôles de doublons et publication. L’archivage normal fait aussi un contrôle initial et un second juste avant publication. Ces mécanismes n’ont pas été réécrits.

## Modifications AVM-24

| Fichier | Changement |
|---|---|
| `audio_video_manager/ui/sections/settings_page.py` | Le champ est libellé « Destination des albums » et précise que les jobs restent dans le dossier temporaire. Le sélecteur et la persistance existants sont conservés. |
| `audio_video_manager/ui/wizard/archive_wizard.py` | Mode et racine configurée visibles avant le rip; le résultat final distingue publication/indexation réussie, doublon ignoré et publication non effectuée. |
| `audio_video_manager/ui/main_window.py` | Résultat du test technique indique explicitement le mode et l’absence de publication bibliothèque. |
| `tests/test_ux_06o.py` | Trois cas ciblés dans un fichier existant : sauvegarde du dossier via Paramètres et propagation au wizard/bibliothèque; messages du résultat normal/non publié; test technique clairement non publié. Sauvegarde isolée via `AVM_DATA_DIR`; aucun réglage utilisateur n’a été écrit. |
| `tests/test_archive_pipeline.py` | Le test synthétique de publication vérifie que le chemin SQLite correspond au dossier créé sous la racine fournie. |
| `docs/architecture/reports/AVM-24-PASSAGE-ARCHIVAGE-CD-REEL.md` | Présent rapport et procédure manuelle. |

Aucun changement n’a été apporté aux services métier de rip/publication, au schéma SQLite, aux mécanismes de récupération/doublons, aux fonctions DVD, aux médias, aux bases utilisateur ou aux dossiers de jobs. Les changements préexistants, notamment DVD, ont été préservés.

## Vérifications

- Tests ciblés UI et publication : `tests/test_ux_06o.py` **10 réussis**; `tests/test_archive_pipeline.py` **10 réussis**.
- Configuration, récupération, doublons, réconciliation et affichage : `test_config.py` **2**, `test_archive_recovery_staging.py` **4**, `test_duplicates_06k.py` **13**, `test_reconciliation_10b.py` **13**, `test_reconciliation_10c.py` **8**, `test_ui_library_history_06h.py` **9**; tous réussis.
- CI Windows complète : `.venv/Scripts/python.exe scripts/run_tests_ci.py --report .ci/avm24-ci-results.json --junit-dir .ci/junit/avm24` — **369 tests, 13 groupes, 0 échec, 0 erreur, 0 skip, 0 crash natif; GO**.
- `git diff --check` sur les fichiers suivis ciblés : réussi. Les résultats CI restent dans `.ci/`, ignoré par Git.
- Ces validations sont synthétiques. Le test pipeline injecte des FLAC existants; aucune lecture TOC physique, commande fre:ac sur un CD réel, extraction matérielle ou écoute n’a été effectuée.

## Procédure avec le prochain CD

1. Dans **Paramètres → Bibliothèque**, utiliser « Parcourir » pour sélectionner le dossier permanent choisi (ou conserver le dossier Music par défaut), puis **Enregistrer**. Vérifier la destination affichée dans la bibliothèque. AVM ne migre pas automatiquement l’ancienne bibliothèque de test; ses fichiers et entrées restent en place. Ce réglage ne change que les archivages futurs.
2. Après votre décision de lancer le rip physique, choisir **CD audio** dans Archiver, sélectionner le lecteur, relire le disque et lancer l’identification. Vérifier l’édition, les pistes et les champs coffret, puis approuver la fiche.
3. À l’étape **Extraction / publication**, confirmer que W4 affiche **Mode : archivage CD normal**, la bonne destination permanente et que « Publier dans ma bibliothèque après extraction » est coché. Garder la politique de collision non destructive proposée.
4. Attendre W5. Le succès doit indiquer **Publication et indexation SQLite : réussies** ainsi que le dossier publié. Ouvrir ce dossier, puis **Ma bibliothèque** et vérifier la présence de l’album et de ses pistes FLAC. L’écoute et l’acceptation du résultat restent une validation humaine.
5. Si un **test technique** est lancé séparément, son dossier temporaire ne constitue pas un album archivé et ne sera pas publié dans la bibliothèque.

Aucune bibliothèque de test n’a été migrée; aucune ancienne donnée n’a été déplacée, remplacée ou supprimée. **Arrêt AVM-24 après ce rapport**, sans extraction physique ni mandat suivant.