# AVM-28 — Parcours complet d’importation CD

**Verdict : PARTIEL — le parcours Windows est implémenté et testé synthétiquement; aucun CD physique ni rip fre:ac réel n’a été exécuté.** La validation matérielle finale reste à faire avec un véritable CD audio.

## Corrections apportées

- **Détection et retrait (Windows).** `MainWindow.nativeEvent` filtre `WM_DEVICECHANGE` pour les arrivées/retraits de volumes et programme un scan debouncé. Le scan fre:ac + TOC s’exécute dans un `QThread` via `OpticalMediaScanWorker`, jamais dans le thread UI. Il démarre à l’ouverture de l’assistant, à son retour depuis une autre section, lors d’un événement Windows et via **Actualiser les lecteurs**. Le retrait/non-lecture invalide la TOC et révoque toute approbation existante; un nouveau Disc ID écarte l’ancienne fiche et relance l’identification.
- **Lecteurs distincts.** W1 distingue le lecteur/index fre:ac utilisé pour le rip du périphérique Windows utilisé par libdiscid pour la TOC. Avec plusieurs candidats, le wizard demande de sélectionner les deux et d’en confirmer la correspondance avant le rip. Aucune correspondance par heuristique de nom de modèle n’est inventée. Le choix manuel et le rafraîchissement restent disponibles si fre:ac ou Windows ne détecte pas automatiquement le lecteur.
- **Identification et assistant.** Une seule TOC lisible déclenche l’identification asynchrone existante (MusicBrainz et pochette CAA). Les éditions multiples restent à choisir dans W2. En cas d’absence de résultat ou d’erreur réseau, le chemin existant propose la fiche manuelle W3. L’approbation explicite reste obligatoire.
- **Protection des autres états.** Le scan est annulé au passage au parcours DVD, n’auto-identifie pas en dehors de W1 et participe à l’état occupé/à l’arrêt borné du shell. Le rip normal, son annulation, le contrôle du TOC avant rip, l’intégrité FLAC, les doublons, la publication non destructive, l’indexation et le rafraîchissement Widgets restent dans leurs composants existants. `technical_test` conserve son chemin zone jobs sans publication.

## Fichiers modifiés

| Fichier | Modification |
|---|---|
| `audio_video_manager/ui/identify_worker.py` | Ajout du résultat structuré et du worker de scan des lecteurs/TOC. Le worker est réutilisable par le wizard et ne lance pas de rip. |
| `audio_video_manager/ui/wizard/archive_wizard.py` | Détection asynchrone, choix des périphériques, relecture manuelle, réaction au média retiré/changé, confirmation multi-lecteur et garde de l’approbation. |
| `audio_video_manager/ui/main_window.py` | Filtrage des événements Windows de volume et planification du scan lorsque l’assistant CD est actif. |
| `tests/test_drives.py` | Cas synthétiques : lecteur sans CD et lecteur Windows contenant un CD lisible. |
| `tests/test_ui_shell.py` | Cas synthétiques : résultat de détection déclenchant W2, retrait révoquant l’approbation, panne d’identification laissant la saisie manuelle, filtrage d’événements de volume; les scénarios DVD existants restent dans le fichier. |

Aucun changement aux services de publication, au schéma SQLite, aux paramètres, au mode `technical_test`, au code DVD ou à la bibliothèque Widgets n’a été nécessaire.

## Validation

- Tests ciblés, exécutés par fichier pour isoler Qt : `test_ui_shell.py` **30**, `test_drives.py` **4**, `test_ui_w3_prefill.py` **8**, `test_ux_06o.py` **10**, `test_library_qml_08b.py` **5**, `test_musicbrainz_identify.py` **19**, `test_edition_ranker.py` **8**, `test_cd_ripper.py` **7**, `test_rip_job.py` **1**, `test_archive_pipeline.py` **10**; tous réussis.
- CI Windows complète : `.venv/Scripts/python.exe scripts/run_tests_ci.py --report .ci/avm28-ci-results.json --junit-dir .ci/junit/avm28` — **375 tests, 13 groupes, 0 échec, 0 erreur, 0 skip, 0 crash natif; GO**.
- Diagnostics éditeur : aucune erreur sur les cinq fichiers modifiés. `git diff --check` : réussi.
- Tous les essais de détection utilisent des objets TOC synthétiques et des fonctions patchées; aucune notification de périphérique physique n’a été provoquée ou observée, aucun `discid.read` réel, aucune identification réseau réelle et aucun rip n’ont été exécutés.

## Validation physique à effectuer

1. Dans Paramètres, vérifier que le chemin permanent `library_root` voulu est sélectionné et enregistré; aucune bibliothèque existante n’est migrée automatiquement.
2. Avec un CD dont la reproduction est autorisée, laisser AVM ouvert dans Archiver et insérer le disque. Vérifier la détection Windows, l’identité du lecteur dans les deux listes et l’identification. Si l’association des lecteurs n’est pas certaine, ne pas confirmer la paire.
3. Vérifier l’édition, les pistes et les métadonnées, corriger si besoin, puis approuver explicitement. À W4, confirmer le mode normal, la destination et l’option de publication.
4. Attendre W5; vérifier publication/indexation réussie, chemin, nombre de FLAC, présence de l’album dans Ma bibliothèque Widgets et ouverture de son dossier. Contrôler ensuite les tags et l’écoute dans un lecteur externe.
5. Si un test technique est lancé séparément, vérifier qu’il annonce clairement l’absence de publication et laisser ses fichiers dans le dossier temporaire.

La preuve utilisateur doit consigner le résultat effectivement observé; les tests automatisés ne constituent pas une preuve de lecture, d’extraction physique ni de fidélité au disque. **Arrêt AVM-28 après ce rapport.**