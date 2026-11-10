# AVM-28C — Ergonomie d’identification et d’approbation CD

**Verdict : PARTIEL.** Le parcours est remanié et validé par tests et captures Qt aux tailles 1100×720 et 820×640. Aucun visuel « avant » de l’utilisateur n’était joint; les captures « après » sont synthétiques et offscreen, pas une validation sur écran Windows/DPI physique.

## Changements

- Les cinq étapes CD deviennent quatre : disque, fiche, extraction, résultat. La sélection MusicBrainz et la fiche corrigible partagent une seule zone principale défilante. Pochette, album, artiste, année, compilation et édition sont réunis en tête; label, catalogue, pays, numéro de disque, pistes et destination suivent dans le même défilement. Le tableau s’agrandit selon le nombre de pistes et n’a plus de scrollbar imbriquée; les durées sont affichées en minutes/secondes.
- Le choix d’une autre édition met immédiatement la fiche visible à jour. Une correction manuelle confirmée n’est jamais remplacée sans question; « Non » conserve la correction et l’édition courante. L’approbation existante est révoquée si l’identité ou la fiche change.
- L’action « Continuer » enregistre et approuve explicitement la fiche; l’action séparée « Extraire » est le seul déclencheur du rip. Les états techniques et la popup de succès redondante disparaissent. Les champs compilation ambigus sont signalés et les noms accessibles du bouton suivent l’action affichée.
- L’aperçu de pochette ne déclenche plus de requête réseau dans le thread UI; il lit le cache local. Le téléchargement éventuel reste dans le chemin de publication existant.
- Le parcours DVD conserve ses cinq étapes et ses actions; aucun changement au mode `technical_test`, à fre:ac, au schéma SQLite ou au pipeline de publication.

## Captures

Captures « après », données synthétiques, thème et polices AVM chargés :

- 1100×720 : [haut](../../ux/reports/assets/avm28c-review-1100-top.png), [pistes](../../ux/reports/assets/avm28c-review-1100-tracks.png), [destination](../../ux/reports/assets/avm28c-review-1100-bottom.png)
- 820×640 : [haut](../../ux/reports/assets/avm28c-review-820-top.png), [pistes](../../ux/reports/assets/avm28c-review-820-tracks.png), [destination](../../ux/reports/assets/avm28c-review-820-bottom.png)

La scrollbar unique permet d’atteindre les pistes et chemins sur la fenêtre étroite. Aucune capture utilisateur initiale n’était disponible pour produire un avant/après fidèle.

## Vérification

- Tests ciblés UI/CD/DVD : **55 réussis**, incluant sélection d’édition, remplacement refusé/accepté d’une correction, état compilation ambigu, corrections manuelles, retrait/changement de CD, révocation d’approbation, navigation clavier et absence de démarrage du rip par « Continuer ».
- CI : `.venv/Scripts/python.exe scripts/run_tests_ci.py --report .ci/avm28c-final-ci-results.json --junit-dir .ci/junit/avm28c-final` — **383 tests, 13 groupes, 0 échec, 0 erreur, 0 skip, 0 crash natif**.
- Diagnostics éditeur : aucune erreur sur les fichiers Python touchés; `git diff --check` réussi.
- Aucun lancement de l’application native, accès à un lecteur optique, appel MusicBrainz réel ou rip n’a été effectué.

## Fichiers

- AVM-28C : `audio_video_manager/ui/wizard/archive_wizard.py`, `tests/test_ui_w3_prefill.py`, `tests/test_ui_shell.py`, `tests/test_ui_library_history_06h.py`, les six captures ci-dessus et ce rapport.
- Les modifications AVM-28 déjà présentes dans `identify_worker.py`, `main_window.py` et `test_drives.py` ont été préservées, sans extension par AVM-28C.

**Limite restante :** confirmer le rendu et la navigation au clavier sur une fenêtre Windows réelle, idéalement avec la capture initiale de référence. Aucun rip n’a été lancé; AVM-28C s’arrête ici, sans commit ni mandat suivant.