# AVM-16 — Harmonisation des parcours CD/DVD

Date : 2026-11-07 · Windows local · Python 3.12 · branche `main` · commit de départ `b4c00071cab4a151bcf524b96a7c654064c15a1f`.

## Verdict : PARTIEL

Le parcours DVD publie et indexe automatiquement les MKV et MKA validés, sans seconde finalisation manuelle. Les deux parcours ont été exercés avec les vrais workers Qt, FFmpeg et SQLite sur une structure DVD synthétique. La CI complète passe. La validation sur DVD physique et la fidélité intégrale à la source ne sont pas démontrées dans ce mandat; les limites ci-dessous restent ouvertes.

## Écarts et harmonisation

- Le CD utilise l'assistant Archiver et sa progression jusqu'à la bibliothèque; le DVD utilisait déjà ce même assistant mais exigeait une inspection séparée, la lecture manuelle des pistes, la saisie de destination et une finalisation manuelle AVM-15 après extraction.
- Sur la première étape DVD, **Inspecter le disque** lance l'inspection depuis le bouton de navigation. Le titre le plus long reste une suggestion, jamais une identification certaine; en passant à l'étape titres, ses pistes sont inspectées automatiquement. Les changements de titre ou d'angle invalident toujours les résultats et le bouton Continuer relance leur lecture si nécessaire.
- Une piste audio unique exploitable est présélectionnée pour MKA; plusieurs pistes restent à choisir explicitement. Une destination libre sous la racine bibliothèque existante est proposée sans remplacer de fichier, mais demeure modifiable et doit être confirmée. L'attestation des droits et, le cas échéant, l'accord de conversion PCM restent obligatoires.
- L'extraction DVD conserve ses moteurs, confirmations, contrôles et publication atomique sans écrasement. Une réservation SQLite `pending` / `incomplete` est créée avant extraction; après publication, le worker vérifie le média local, ses flux, chapitres, son décodage et sa stabilité, puis l'indexe directement à son chemin publié. Aucune copie supplémentaire du média n'est imposée.
- Le résultat est enregistré **décodable**, jamais automatiquement **vérifié avec la source**. La progression existante couvre extraction puis validation locale et indexation. Après succès, **Voir dans la bibliothèque** ouvre l'onglet « Vidéos / audio DVD »; les albums CD et les présentations Widgets/QML restent en place.
- Une annulation ou erreur avant publication retire la réservation si aucun fichier n'existe. Si un fichier est présent, il est conservé et l'entrée reste en attente; le résultat explique l'échec et propose de réessayer l'indexation. Après redémarrage, la bibliothèque peut vérifier une intention en attente après confirmation explicite, sans présumer la provenance du fichier. Les doublons sont refusés sans effacer les fichiers.
- L'action existante de finalisation manuelle d'un MKV est conservée. Le moteur CD, les protections CSS et les fichiers AVM-14 ne sont pas modifiés.

## Preuves

- Sur `%LOCALAPPDATA%\Temp\AVM-11C\reference-dvd`, dossier DVD synthétique déjà autorisé, le parcours Qt hors écran a inspecté deux titres et sélectionné le titre 2. Les sorties ont été créées dans `%LOCALAPPDATA%\Temp\AVM-16-reprise-71fllr4i` : MKV de 4 055 998 octets et MKA de 240 886 octets. Les deux exécutions retournent 0; la base temporaire contient deux lignes `published` / `decodable`. Les confirmations ont été acceptées automatiquement pour ce contenu synthétique.
- Une reprise synthétique distincte a créé une intention en attente puis indexé le fichier existant avec le vrai worker et FFmpeg : entrée passée à `published` / `decodable`, fichier détecté et empreinte cohérente. Les captures des étapes titre et résultat sont conservées dans le dossier synthétique ci-dessus.
- Les SHA-256 des fichiers AVM-14 vérifiés en lecture seule correspondent aux valeurs précédemment relevées : MKV `b21519462e3391b5582686050f5ea589078540e9dd4b3d2aae35f66a52744c1a`, MKA `fe29a9efd718330e56fd28fbb76c2ff14aaf72b647a6162b291e9148456429fc`.
- Un premier test Qt en cours d'adaptation a pu déclencher une inspection sur le lecteur détecté; une lecture effective n'a pas été établie. Il a été corrigé pour simuler cette action avant les suites suivantes. Aucune extraction physique longue n'a été lancée et aucun résultat physique nouveau n'est revendiqué.

## Tests

- Tests ciblés CD/DVD et catalogue : extraction, inspection, annulation avant publication ou pendant indexation, conservation des fichiers, collisions, doublons, réservation durable, reprise confirmée et navigation vers la bibliothèque.
- CI complète : **359 tests**, 14 groupes, 0 échec, 0 erreur, 0 skip et aucun crash natif. Rapport `.ci/avm16-final-ci-results.json`; JUnit `.ci/junit/avm16-final/`.

  ```powershell
  .\.venv\Scripts\python.exe scripts/run_tests_ci.py --report .ci/avm16-final-ci-results.json --junit-dir .ci/junit/avm16-final
  ```

## Limites

- Le test de bout en bout utilise un dossier DVD synthétique, pas un disque optique physique. Aucune écoute ou validation humaine de synchronisation n'a été réalisée. Les limitations AVM-14 concernant le PCM physique et la fidélité intégrale restent applicables.
- L'inspection DVD et l'appel ffprobe local ne sont pas annulables immédiatement : ils restent bornés par leurs délais existants. L'indexation peut être annulée pendant le hachage ou le décodage; si la publication a déjà eu lieu, le fichier et l'entrée en attente sont conservés.
- Une intention en attente identifie une destination, pas la provenance du fichier qui y apparaît après interruption; la reprise demande donc confirmation et n'attribue que le statut « décodable ». Le catalogue ne calcule pas l'empreinte à chaque ouverture et conserve la limite AVM-15 de détection par taille et date.
- La suppression d'une réservation manquante depuis une seconde instance simultanée n'est pas coordonnée avec une extraction DVD en cours dans la première. Le fichier ne sera pas écrasé, mais une interruption dans cette situation peut exiger une récupération manuelle de l'indexation.
- La configuration personnelle, la bibliothèque personnelle, les fichiers AVM-14 et les changements Git préexistants ont été préservés; aucun commit ni synchronisation distante n'a été effectué.