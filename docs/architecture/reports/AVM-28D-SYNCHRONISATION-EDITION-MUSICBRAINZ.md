# AVM-28D — Synchronisation de l’édition MusicBrainz

**Verdict : PARTIEL.** La perte du résultat est reproduite et corrigée; les parcours de données et de widgets passent en synthétique. Le CD et l’application native sur le lecteur Windows de l’utilisateur n’ont pas été testés.

## Cause racine

Deux appels secondaires pouvaient empêcher la fiche MusicBrainz d’atteindre les widgets :

1. `identify_disc` interrogeait Cover Art Archive **avant** d’appliquer le candidat. Une exception de réseau (notamment un timeout non couvert par les exceptions CAA connues) interrompait donc l’application du titre, artiste, année et pistes.
2. `IdentifyWorker` attendait ensuite Discogs et son rapport avant d’émettre `finished`. Une exception inattendue faisait émettre `failed`; `_on_identify_fail` remplaçait la fiche par la TOC seule.

Reproduction sans réseau : candidat MusicBrainz valide + `TimeoutError` CAA produisait une exception; candidat valide + `RuntimeError` Discogs produisait zéro résultat `finished` et un `failed`. La connexion Qt elle-même et le slot de changement de sélection fonctionnaient avec des résultats valides; les anciens tests ne simulaient pas ces frontières de worker.

## Correction

- Appliquer le candidat à la fiche avant l’appel CAA. Une erreur CAA est journalisée et laisse intactes les métadonnées MusicBrainz; CAA ne peut plus invalider l’identification.
- Émettre la fiche principale sans attendre CAA, le téléchargement de l’image ou Discogs. Un worker d’enrichissement secondaire charge la pochette dans le cache et construit les propositions Discogs/MB.
- L’enrichissement est associé au `release_id` sélectionné. Un résultat tardif d’une autre édition est ignoré; les corrections manuelles sont conservées. La pochette ne modifie pas une fiche déjà approuvée.
- Le choix manuel d’édition met toujours à jour immédiatement les champs, pistes, aperçu de destination et validation; la fingerprint est calculée sur la fiche affichée lors de « Continuer ». Le rip garde son action séparée « Extraire ».

## Vérification

- Tests UI fiche : **18**; modèle MusicBrainz/enrichissement : **35**; UI/CD/DVD : **43**; pipeline CD/ripper/jobs : **18**; tous réussis.
- Intégration Qt : résultat worker transmis aux widgets visibles; édition unique présélectionnée, plusieurs éditions via `currentIndexChanged`, changement avec corrections refusé/accepté, résultats absents, pistes/durées, pochette depuis le worker, chemins et fingerprint d’approbation vérifiés.
- Régressions reproduites : timeout CAA et exception Discogs. Après correction, le candidat reste visible et approuvable; le fallback Discogs n’efface plus le résultat.
- CI : `.venv/Scripts/python.exe scripts/run_tests_ci.py --report .ci/avm28d-final-ci-results.json --junit-dir .ci/junit/avm28d-final` — **389 tests, 13 groupes, 0 échec, 0 erreur, 0 skip, 0 crash natif**.
- Diagnostics éditeur : aucune erreur sur les fichiers Python touchés; `git diff --check` réussi.
- Aucun appel réseau MusicBrainz/CAA/Discogs réel, accès lecteur optique ou rip physique n’a été effectué. Les tests utilisent des candidats synthétiques, des signaux Qt et des remplacements réseau.

## Fichiers AVM-28D

- `audio_video_manager/metadata/apply_lookup.py` — appliquer le candidat avant CAA et isoler ses erreurs.
- `audio_video_manager/ui/identify_worker.py` — séparer le résultat principal de l’enrichissement secondaire et charger la pochette hors thread UI.
- `audio_video_manager/ui/wizard/archive_wizard.py` — actualiser la pochette/fiche seulement pour l’édition toujours sélectionnée.
- `tests/test_ui_w3_prefill.py` — couverture intégrée du worker, des signaux, des widgets visibles et des échecs CAA/Discogs.

Le comportement Windows avec le CD réel reste à confirmer par l’utilisateur; aucun rip n’a été lancé. Aucun changement à fre:ac, SQLite, au pipeline FLAC, au parcours DVD ou à `technical_test`. **Aucun commit ni push. Arrêt AVM-28D.**