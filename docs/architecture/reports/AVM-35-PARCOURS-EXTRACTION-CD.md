# AVM-35 — Parcours réel d’extraction CD

**Verdict : PARTIEL.** Le défaut de réinitialisation et d’isolation du suivi est corrigé et couvert par des tests UI ciblés. Les journaux communiqués par l’utilisateur rapportent les extractions et publications réussies de Janis Joplin et de Frank Sinatra, Disc 1; pour Sinatra Disc 2, ils établissent le démarrage de l’extraction mais pas son résultat final. Le correctif présent n’a lancé aucun rip physique.

## Objectif et parcours examiné

Rendre le parcours d’extraction CD lisible à partir d’événements réellement observés, sans fabriquer un pourcentage, et arrêter avant toute extraction si l’édition reste ambiguë. Le chemin examiné est le wizard Qt Widgets effectivement lancé par `run_app()`, jusqu’à l’identification et à l’approbation de la fiche. Le pipeline d’archivage et ses contrôles ont été vérifiés par tests; aucune écriture de média n’a été autorisée.

## Diagnostic et corrections

La progression pouvait donner une mesure trompeuse : `track N/M` était interprété comme un pourcentage global, les jalons du pipeline émettaient des fractions fixes, et l’attente de sortie bloquante empêchait de réagir proprement à l’absence d’événement. Les messages réels de fre:ac ne donnaient pas nécessairement une mesure globale.

Le parseur ne traite maintenant comme fraction que les pourcentages explicitement globaux. Les événements de piste alimentent le compteur, mais ne sont pas convertis en pourcentage. stdout et stderr sont consommés sans bloquer la surveillance; après une période sans nouvel événement, l’interface indique que fre:ac est actif sans inventer d’avancement. Les jalons du pipeline restent non mesurés. La barre devient indéterminée en l’absence de fraction; les états de sous-étapes, les erreurs, le résultat final et le statut global restent visibles pendant la navigation.

Le contrôle de doublon ne traite un album comme complet que si son dossier et le nombre attendu de pistes, toutes présentes, sont établis. Une fiche MusicBrainz non équivalente à plusieurs candidates ne peut pas être approuvée sur la seule base d’une présélection : l’utilisateur doit activer explicitement une édition, même si elle est déjà affichée comme candidate principale. L’approbation reste refusée tant que ce choix n’a pas eu lieu. La publication privilégie un nouveau dossier sans écrasement implicite.

La cause du mélange entre deux extractions était dans le suivi UI : `_reset_session()` effaçait les données d’identification et le résultat, mais conservait les widgets W4, le compteur de pistes et l’état du status bar principal. Le chemin de remplacement de Disc ID effaçait la fiche sans réinitialiser ce suivi. En outre, les callbacks progress/résultat/échec étaient reliés directement aux mêmes slots sans identité; un événement tardif pouvait donc repeindre le suivi courant, et la fin d’un ancien thread pouvait effacer les références du nouveau.

Chaque `ArchiveWorker` possède maintenant l’ID transmis à `run_archive_job` et au rapport. Le wizard n’applique progression, fin ou échec que pour son ID actif; le nettoyage d’un thread vérifie aussi son propriétaire. Le changement de session ou de disque remet à zéro sous-étapes, compteurs, barre et statut permanent, sans supprimer l’historique SQLite. Un nouveau CD détecté depuis l’écran de résultat affiche l’étape Disque. Au lancement, la vérification du disque est affichée comme étape active; les événements du pipeline déplacent ensuite l’état vers l’extraction et les étapes suivantes.

## Fichiers concernés

- Moteur et orchestration : `audio_video_manager/extraction/cd_ripper.py`, `audio_video_manager/orchestration/archive_job.py`, `audio_video_manager/ui/archive_worker.py`.
- Interface et progression : `audio_video_manager/ui/progress_labels.py`, `audio_video_manager/ui/wizard/archive_wizard.py`, `audio_video_manager/ui/main_window.py`.
- Identification et doublons : `audio_video_manager/metadata/apply_lookup.py`, `audio_video_manager/library/duplicates.py`.
- Régressions ciblées : `tests/test_cd_ripper.py`, `tests/test_progress_labels.py`, `tests/test_archive_pipeline.py`, `tests/test_duplicates_06k.py`, `tests/test_edition_ranker.py`, `tests/test_ui_library_history_06h.py`.

## Vérifications

- Lot ciblé couvrant UI Bibliothèque/Historique, UI shell, pipeline, ripper CD et cycle de vie QThread : **77 passed**.
- Une invocation combinée a affiché les 77 tests réussis, puis l’hôte Python a terminé avec `0xC0000409`. Les mêmes groupes ont été relancés séparément : UI/Historique **17**, QThread **5**, UI shell/pipeline/ripper **55**, chacun avec sortie normale.
- Régressions UI : reset entre sessions, changement de CD depuis le résultat, démarrage du nouveau job à l’étape réelle, et rejet des signaux progress/fin/échec d’un ancien ID.
- Le pipeline staging confirme que l’ID fourni est celui du rapport final. Les tests de ripper et pipeline sont synthétiques; ils ne constituent pas une preuve d’extraction physique.
- Diagnostics Pylance sur les modules et tests concernés : **aucune erreur**.

## Lanceur et rendu UI

Le lanceur fourni, `Lancer-AudioVideoManager.bat`, fait `cd /d "%~dp0"`, choisit `%~dp0.venv\Scripts\python.exe`, puis lance `-m audio_video_manager`. Avec ce répertoire et cet interpréteur exacts, Python a résolu `audio_video_manager`, `archive_wizard.py` et `archive_worker.py` sous `C:\Users\ComeToM3\Dev\AudioVideoManager`. La métadonnée de distribution `0.5.0` se trouve à la racine du dépôt; elle ne correspond pas à un second chemin de code importé.

Le rendu natif Qt vérifié pour ce correctif utilisait une base/configuration temporaires et une fiche synthétique « Demo Artist — Demo Album », sans scan optique ni extraction. Il confirme l’apparence de la liste d’étapes et de la barre indéterminée, mais ne représente pas les données de la bibliothèque réelle ni une seconde installation. Une fenêtre AVM laissée ouverte avant le correctif conserverait naturellement son ancien code en mémoire; la relancer avec le lanceur ci-dessus charge les fichiers du dépôt contrôlés ici.
- Validation Windows réelle via le point d’entrée de l’application, avec base SQLite ouverte en lecture seule et initialisation/réconciliation neutralisées pour l’essai : lecteur `D:`, Disc ID `2xw0cBHPwrpxbp6sjw1TXuduyLw-`, 10 pistes, 5 éditions MusicBrainz non équivalentes. Cliquer sur Continuer affiche le refus de choix explicite; la fiche demeure `Pending`, les jobs restent à **12 → 12**, et aucun archivage ne démarre. Capture temporaire : `%TEMP%\avm35-physical-gate-final.png`.

## Limites et arrêt

Lors d’une validation Windows précédente, le CD D: de Janis Joplin présentait cinq éditions non équivalentes; Continuer était alors bloqué, la base restait à 12 jobs et aucun rip n’avait été lancé. Les journaux fournis ensuite par l’utilisateur rapportent Janis Joplin — Super Hits et Frank Sinatra — Disc 1 extraits et publiés avec succès, puis le démarrage du rip de Sinatra Disc 2 (`mKyMXyTLHA3OQ0V6abFXQXiuIO0-`, 20 pistes); son issue n’est pas établie par les informations fournies. Ces journaux sont des observations rapportées, non reproduites pendant le correctif.

Le correctif de suivi a été validé par tests Qt synthétiques; il n’a pas relancé les extractions ni modifié la bibliothèque ou les médias personnels. La validation physique présentée ci-dessus démontre l’identification et le gate d’approbation, pas l’état UX pendant ou après les extractions récemment rapportées.

**Prochaine vérification :** établir dans les journaux le résultat final de Sinatra Disc 2 et confirmer que son job est publié et retrouvable dans la Bibliothèque. Aucun rip supplémentaire n’est requis pour valider le correctif de suivi.
