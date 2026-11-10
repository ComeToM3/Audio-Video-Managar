# AVM-28H — Verrou de rip et job orphelin

**Verdict : PARTIEL — cause logicielle démontrée et corrigée; aucune extraction physique complète n’a été effectuée.**

## Observations Windows

- Configuration effective de `%LOCALAPPDATA%\AudioVideoManager` : freaccmd `C:\Program Files\freac\freaccmd.exe`, bibliothèque conservée `C:\Users\ComeToM3\Music\AVM-06C-Test-Library`, jobs et SQLite dans les données locales. Aucun chemin n’a été modifié.
- Le journal réel confirme pour le Disc ID `NvdIQWqFgWqITaT0S.JVxYAv6Ls-` des lectures `D:` à **20 pistes**, y compris pendant la tentative. La lecture ultérieure annoncée à 2 pistes ne figure pas dans le journal disponible; la logique TOC n’a pas été modifiée.
- Le job `b6988620f57843a697380ef1df8db6bf` est en SQLite `Ripping/Ripping`, checkpoint unique `{"drive":0}`, sans `finished_at` ni erreur. Son dossier `rip` est vide, sans `.avm-rip.lock` ni FLAC. Au contrôle, aucun processus `freaccmd.exe`/`freac.exe` n’était actif; des processus Python de l’interface restaient ouverts.
- Le journal atteint « Extraction fre:ac → zone A… », mais ne contient pas `Démarrage rip argv`; freaccmd n’a donc pas été lancé pendant cette tentative.

## Cause et correction

`run_archive_job` écrit le verrou `.avm-rip.lock` dans `rip/`, puis appelle `FreacCdRipper.rip`. Ce dernier refusait tout contenu dans le dossier, y compris le verrou que le pipeline venait d’y écrire. Le refus `FileExistsError` survenait avant `Popen`. Il échappait aussi au pipeline après l’insertion SQLite du job `Ripping`, laissant l’état actif sans fin ni erreur.

Le ripper ignore maintenant uniquement `.avm-rip.lock` dans son garde de dossier; tout autre fichier préexistant continue de bloquer pour empêcher l’écrasement. Si `FileExistsError` survient avant le lancement, `run_archive_job` renvoie un rapport `Failed`, finalise le job SQLite avec `finished_at` et une action explicite, puis retire le verrou. Les autres échecs freaccmd déjà retournés en `RipResult` gardent leur chemin existant.

## Vérification

- `test_rip_success_with_mocked_process` avec le verrou réel présent et `test_archive_rip_launch_refusal_finishes_job_as_failed` : **2 réussis**; aucun freaccmd réel n’est invoqué.
- Diagnostics éditeur sans erreur; `git diff --check` réussi. Aucune CI complète n’a été relancée; seules les vérifications ciblées demandées ont été faites.
- Le job réel n’a pas été modifié/réconcilié par l’assistant. Aucun processus n’a été interrompu; aucun fichier temporaire, FLAC, bibliothèque ou SQLite n’a été modifié.

## Observation requise avant la suite

Dans la fenêtre AudioVideoManager actuellement ouverte, indiquez seulement si elle affiche encore « En cours » ou un résultat d’échec/terminé. Ne cliquez ni sur Annuler, ni sur Reprendre, ni sur Extraire et ne fermez pas encore les fenêtres. L’état SQLite réel reste `Ripping` malgré l’absence observée de freaccmd; une relance pourrait lancer la réconciliation existante et modifier cet état.

**Aucune nouvelle extraction, suppression, interruption forcée, commit ou push. L’autorisation pour une extraction physique complète n’est pas demandée avant clarification de l’instance active.**