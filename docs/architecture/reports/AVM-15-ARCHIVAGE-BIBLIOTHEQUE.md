# AVM-15 — Archivage vidéo et bibliothèque

Date : 2026-11-07 · Windows local · Python 3.12 · branche `main` · commit de départ `b4c00071cab4a151bcf524b96a7c654064c15a1f`.

## Verdict : PARTIEL

La finalisation d'un MKV existant et sa consultation dans la bibliothèque sont implémentées et vérifiées sur un média synthétique. Le MKV physique AVM-14 n'a pas été modifié, copié ni publié pendant ce mandat : sa destination n'a pas été choisie et confirmée dans l'interface. La comparaison intégrale de ce fichier avec son DVD reste non établie; aucun statut « vérifié avec la source » ne lui est attribué.

## Parcours et changements

- Dans **Archiver → DVD-Video**, l'action **Finaliser un MKV existant** demande un fichier et une destination, puis une confirmation explicite indiquant que la source reste intacte et que la fidélité au DVD n'est pas vérifiée. L'opération s'exécute dans un worker Qt; la navigation principale est verrouillée durant l'opération.
- La source est copiée de manière indépendante dans un staging créé dans le dossier de destination. FFprobe recueille format, durée, flux et chapitres; FFmpeg décode les flux audio et vidéo sans créer de fichier média ni réencoder la sortie. Une empreinte SHA-256 est calculée et contrôlée à nouveau après validation. La source n'est ni déplacée ni supprimée.
- Une entrée SQLite `pending` est enregistrée avant la publication. Le fichier est publié par lien dur depuis le staging local, sans remplacement; si le système de fichiers ne permet pas cette opération, la publication échoue. Une transaction SQLite sérialise la publication et la suppression d'une réservation. Si la mise à jour finale SQLite échoue après création du fichier, l'entrée reste en attente et n'est pas présentée comme une réussite.
- La migration SQLite v5 ajoute la table `videos` sans modifier les albums ou les données existantes. Elle conserve chemin, SHA-256, taille, date de modification, format, durée, JSON des flux et chapitres, statut de validation, état de publication et date d'import. Chemin et empreinte uniques empêchent les doublons indexés; une destination déjà présente n'est jamais écrasée.
- La finalisation locale enregistre **décodable**, affiché « Décodable, source non vérifiée ». Les valeurs distinctes **source_verified** et **incomplete** sont prévues dans le catalogue; le parcours de finalisation locale ne peut pas attribuer une vérification à la source. Une entrée en attente ou un fichier manquant/modifié est présenté comme « Validation incomplète ».
- La bibliothèque conserve ses interfaces audio Widgets et QML et ajoute un onglet **Vidéos**. Il affiche les fichiers, la durée, la validation, l'état et les flux disponibles; l'ouverture utilise le lecteur associé par le système. La configuration existante ne propose pas de lecteur externe spécifique.
- Un fichier manquant ou dont la taille/date a changé n'est pas ouvert comme fichier validé. Une vérification explicite de l'empreinte permet de réconcilier une publication en attente ou un fichier inchangé dont la date a varié; une empreinte différente est refusée. Une réservation en attente sans fichier peut être retirée du catalogue après confirmation, sans effacer de fichier.
- La règle Git qui ignorait tout dossier `library/` conserve l'exclusion des médias et rend explicitement visible le nouveau module source vidéo.

## Preuves

- Média synthétique créé localement avec FFmpeg : vidéo MPEG-2 et audio PCM de deux secondes, 286 826 octets. La finalisation a produit une copie indépendante de même taille et une entrée SQLite `published` / `decodable` avec les métadonnées des flux.
- Un essai Qt hors écran avec vrai `VideoFinalizeWorker`, vrais FFmpeg/ffprobe et SQLite temporaire a confirmé le parcours Archiver → confirmation → publication → Bibliothèque → Vidéos; l'entrée est affichée « Décodable, source non vérifiée » et l'action d'ouverture est disponible. L'ouverture réelle d'un lecteur système n'a pas été automatisée; son appel est couvert par un test simulé.
- Captures hors écran à 720 × 560 et 1100 × 720 dans `%LOCALAPPDATA%\Temp\AVM-15-layout-x19tg5o1\`; base et médias synthétiques isolés sous Temp. Elles ne constituent pas une validation interactive native de toutes les configurations.
- Aucune lecture du DVD, extraction physique, modification des fichiers provisoires AVM-14, configuration personnelle ou bibliothèque personnelle n'a été effectuée. Aucun commit ni synchronisation Git n'a été effectué; les modifications préexistantes ont été conservées.

## Tests

- Tests ciblés : migration et conservation des albums; finalisation, métadonnées et copie indépendante; doublon, destination existante, échec de lien, échec de décodage, entrée en attente après échec SQLite, réconciliation par empreinte, fichier absent ou modifié; UI de confirmation et ouverture simulée.
- CI complète : **340 tests**, 14 groupes, 0 échec, 0 erreur, 0 skip et aucun crash natif. Résultat `.ci/avm15-final-ci-results.json`; JUnit `.ci/junit/avm15-final/`.

  ```powershell
  .\.venv\Scripts\python.exe scripts/run_tests_ci.py --report .ci/avm15-final-ci-results.json --junit-dir .ci/junit/avm15-final
  ```

## Limites

- L'import local valide la décodabilité audio/vidéo du fichier copié, pas l'identité de son contenu avec le DVD. L'état `source_verified` est réservé à une preuve future et aucun parcours de ce mandat ne le définit. Les sous-titres ne sont pas décodés par le contrôle intégral, même si leurs métadonnées disponibles sont indexées.
- Le fichier AVM-14 est toujours provisoire. Pour le finaliser, l'utilisateur doit le sélectionner puis choisir et confirmer une nouvelle destination. Un système de fichiers sans liens durs compatibles ne peut pas publier avec cette méthode.
- L'état « disponible » utilise taille et date de modification, pas un recalcul SHA-256 à chaque ouverture; une modification conservant ces attributs pourrait ne pas être détectée. La vérification explicite d'une entrée en attente ou modifiée recalcule l'empreinte complète.
- La finalisation et la vérification d'empreinte n'offrent pas actuellement d'annulation coopérative ni de pourcentage de progression. Si l'utilisateur tente de fermer la fenêtre pendant une opération longue, la fermeture peut être refusée après l'attente bornée; il faut attendre sa fin.
- Le catalogue vidéo ne reçoit pas automatiquement les extractions DVD existantes : un MKV doit être finalisé par l'action explicite. Le MKA natif depuis le DVD et la preuve d'identité intégrale avec la source restent hors de ce mandat.