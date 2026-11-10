# AVM-23 — Consolidation UI et simplification ciblée

**Verdict : VALIDÉ pour le périmètre AVM-23.** Widgets est le défaut effectif, QML reste sélectionnable explicitement, et le dialogue indépendant a été retiré sans perdre les contrôles de métadonnées nécessaires au parcours CD.

## Modifications

| Fichier(s) | Changement |
|---|---|
| `audio_video_manager/config.py`, `ui/sections/library_host.py`, `ui/sections/settings_page.py` | Widgets devient le défaut pour une nouvelle configuration, une valeur absente/invalide et les replis des paramètres. Les valeurs explicites `qml` restent valides; `AVM_LIBRARY_UI` garde priorité et le repli automatique QML→Widgets reste intact. Aucun fichier de configuration utilisateur n’a été modifié. |
| `audio_video_manager/ui/wizard/archive_wizard.py` | W3 expose le numéro et le nombre total de disques du coffret. Les valeurs sont préremplies, les corrections sont enregistrées avec provenance utilisateur, la validation existante contrôle leur cohérence et l’empreinte d’approbation est recalculée/révoquée après modification. |
| `audio_video_manager/ui/metadata_dialog.py`, `tests/test_metadata_dialog_sources.py` | Dialogue indépendant et ses trois tests dédiés retirés conformément à la décision produit. `IdentifyWorker`, les services de métadonnées, la validation et le dépôt de fiches restent en place et utilisés par le wizard. |
| `scripts/run_tests_ci.py`, `tests/test_avm19_stabilization.py` | Retrait du test supprimé de la liste CI et actualisation du docstring AVM-19 qui le citait. Les entrées CI préexistantes, notamment les tests DVD, sont conservées. |
| `tests/test_config.py`, `tests/test_library_qml_08b.py`, `tests/test_ui_w3_prefill.py` | Les tests existants vérifient le défaut Widgets, la persistance du choix QML explicite, l’override QML/Widgets, le préremplissage et la correction des champs disque, ainsi que la révocation de l’approbation. Aucun nouveau fichier de test. |
| `docs/domain/disc-metadata.md` | La description d’interface est actualisée pour documenter le wizard actif et ses champs. Les rapports d’audit/validation historiques restent inchangés. |

**Capacités conservées dans le wizard :** identification asynchrone, choix d’édition, correction des métadonnées d’album et des pistes, compilation à trois états, justification d’année indisponible, affichage des propositions/sources, validation, aperçu des chemins, brouillon et approbation explicite. Le numéro/total de disque, requis pour les coffrets par le modèle et la validation, était le champ de correction utile manquant et a été ajouté à W3.

La saisie manuelle d’un chemin de pochette n’a pas été transférée : le parcours courant prévisualise la pochette CAA et autorise explicitement une pochette indisponible. L’édition manuelle du Disc ID n’a pas été transférée, car l’identité doit provenir de la lecture TOC. Aucun bouton de rejet autonome n’a été ajouté; le wizard permet le retour à l’étape précédente ou l’abandon du parcours.

## Préservation

Le choix QML explicite, le sélecteur temporaire, `LibraryHost`, les ressources QML, le repli et les protections de cycle de vie sont préservés. Aucun changement n’a été apporté aux fonctions DVD, au schéma SQLite, aux médias, aux bases ou aux dossiers de jobs. Les changements DVD non commités restent intacts.

`metadata_dialog.py` portait une modification Git préexistante AVM-19 pour rendre son identification asynchrone. Le fichier a été retiré sous l’approbation explicite d’abandon du dialogue; le worker partagé et le chemin asynchrone actif du wizard sont conservés. Les références qui subsistent dans les anciens rapports, résultats `.ci/` et métadonnées générées restent des traces historiques, non des appels actifs.

## Validation

- Configuration, résolution du mode et W3 : **11 tests réussis** (`test_config.py`, `test_resolve_mode_env_and_config`, `test_ui_w3_prefill.py`).
- Widgets/QML et cycle de vie Qt, chaque fichier exécuté isolément : `test_library_qml_08b.py` **5**, `test_ui_design_06l.py` **8**, `test_ui_library_history_06h.py` **9**, `test_ui_w3_prefill.py` **8**, `test_qt_teardown_10c1.py` **2**, `test_qt_teardown_10c2.py` **2**; tous réussis.
- Métadonnées, approbation et pipeline CD : **60 tests réussis** (`test_disc_metadata.py`, `test_approval_fingerprint.py`, `test_archive_pipeline.py`, `test_metadata_enrichment.py`, `test_musicbrainz_identify.py`).
- CI Windows complète : `.venv/Scripts/python.exe scripts/run_tests_ci.py --report .ci/avm23-ci-results.json --junit-dir .ci/junit/avm23` — **366 tests, 13 groupes, 0 échec, 0 erreur, 0 skip, 0 crash natif; GO**. Le total baisse de trois tests dédiés au dialogue supprimé.
- Python **3.12.10**; vérification des erreurs éditeur : aucune; `git diff --check` sur les fichiers suivis ciblés : réussi.

Aucune extraction CD/DVD physique n’a été lancée. La validation automatisée confirme l’intégration logicielle, pas une lecture matérielle ou une écoute humaine. AVM-23 s’arrête ici; aucun mandat suivant ni commit n’a été engagé.