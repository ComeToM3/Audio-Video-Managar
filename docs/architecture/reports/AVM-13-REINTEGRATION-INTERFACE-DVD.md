# AVM-13 — Réintégration de l'interface DVD

Date : 2026-11-07 · AudioVideoManager 0.5.0 · Windows local · Python 3.12.10

## Verdict : PARTIEL

Les parcours CD et DVD sont réunis dans Archiver. Les deux sorties DVD sont produites et validées sur la structure synthétique autorisée, et la CI complète passe. La validation reste partielle : aucun DVD physique autorisé à la reproduction n'a été testé, l'annulation d'une inspection n'est pas immédiate et un test exploratoire de cycle de vie Qt simulé a présenté une instabilité native non expliquée.

## État initial et divergences

- Dépôt local `C:\Users\ComeToM3\Dev\AudioVideoManager`, branche `main`, commit `b4c00071cab4a151bcf524b96a7c654064c15a1f`. L'arbre contenait déjà des modifications suivies et de nombreux fichiers DVD non suivis, préservés pendant le mandat. Aucun commit ni synchronisation Git n'a été effectué.
- Les moteurs DVD, le worker, les tests d'inspection et d'extraction, et les rapports AVM-11B à AVM-12 étaient présents. Le rapport AVM-12 ne valide pas l'extraction physique et ne conclut pas à une protection CSS.
- L'interface d'origine comprend quatre sections et un assistant CD à cinq étapes. AVM-11D avait ajouté au rail un bouton DVD ouvrant un dialogue modal séparé, avec son propre formulaire, sa progression et sa fermeture; le parcours ne bénéficiait pas de la navigation de l'assistant.

## Modifications et parcours

- Dans Archiver, le choix initial distingue CD audio et DVD-Video. Le rail retrouve ses quatre sections; le dialogue DVD est remplacé par un panneau intégré, sans nouvelle fenêtre modale de parcours.
- CD : disque, identification, approbation des métadonnées musicales, extraction/publication, résultat. Les étapes, le moteur CD et leurs règles d'approbation restent inchangés.
- DVD : source et inspection, choix du titre et de l'angle et lecture des pistes, options et destination, extraction, résultat. Aucun formulaire de métadonnées musicales n'est imposé. La suggestion du titre le plus long reste modifiable; tout changement de source, titre ou angle invalide l'inspection pertinente.
- Les flux vidéo et sous-titres disponibles, chapitres et pistes audio sont présentés. MKV conserve le maître complet; MKA permet de cocher les pistes audio dans les options. Les formulaires DVD défilent si nécessaire.
- L'attestation des droits ou d'une autorisation et la confirmation explicite demeurent requises. Les erreurs, la progression, l'annulation et l'ouverture du dossier de résultat restent accessibles. La navigation principale est verrouillée durant une tâche DVD; la fermeture demande l'annulation et attend l'arrêt borné du worker.
- Les paramètres DVD sont propagés au panneau après enregistrement. L'indication dans Paramètres pointe désormais vers Archiver. Le script de diagnostic AVM-11F utilise le panneau à la place du dialogue.
- Les moteurs, leurs restrictions, les contrôles CSS, la validation des sorties et la publication sans écrasement n'ont pas été modifiés par AVM-13. Le style global n'a pas été modifié.

## Vérifications

- Shell Qt ciblé : 11 tests réussis, notamment navigation DVD, contrôles des étapes, invalidation de l'angle, choix MKA, droits, extension et confirmation, réinitialisation, verrouillage et demande d'annulation simulée.
- Tests CD et DVD ciblés : 48 réussis (`test_cd_ripper.py`, `test_archive_pipeline.py`, `test_dvd_inspector_11b.py`, `test_dvd_extractor_11c.py`).
- CI complète, en processus isolés Qt, sous Windows et `QT_QPA_PLATFORM=offscreen` : **14 groupes, 322 tests, 0 échec, 0 erreur, 0 skip, aucun crash natif**. Commande :

  ```powershell
  .\.venv\Scripts\python.exe scripts/run_tests_ci.py --report .ci/avm13-final-ci-results.json --junit-dir .ci/junit/avm13-final
  ```

- Test de bout en bout hors écran dans `MainWindow`, avec le vrai `DvdTaskWorker`, FFmpeg et la structure synthétique `%LOCALAPPDATA%\Temp\AVM-11C\reference-dvd` : deux titres détectés, titre 2 et une piste audio; MKV validé de 4 055 998 octets et MKA validé de 240 886 octets. Les confirmations ont été acceptées automatiquement pour ce contenu synthétique autorisé. Résultats dans `%LOCALAPPDATA%\Temp\AVM-13-gy2r8e_9`.
- Annulation réelle immédiatement après démarrage d'une extraction synthétique : message d'annulation avant préflight, aucun fichier final, code de sortie 0. L'annulation au milieu d'une extraction est couverte par les tests du moteur, pas par ce scénario UI réel.
- Contrôle visuel hors écran à 720 × 560 : étape Options visible, défilement disponible, texte de l'attestation mesuré dans la largeur du contrôle. Ce contrôle ne remplace pas une validation interactive native de toutes les tailles et langues.

## Limites restantes

- Aucun accès au lecteur physique ni extraction de DVD physique dans ce mandat. Les erreurs de lecture physique et l'état de protection décrits dans AVM-12 restent non résolus; aucun déchiffrement ou contournement CSS n'a été ajouté.
- L'inspection DVD ne reçoit pas actuellement le signal d'annulation du worker : la demande n'interrompt pas immédiatement une inspection déjà lancée. Les délais et la fermeture bornée existants restent applicables.
- Un test exploratoire avec worker Qt simulé et annulation rapide a provoqué une violation d'accès puis des blocages dans certains essais; sa cause n'a pas été établie. Le test d'intégration conservé simule le câblage, tandis que les deux extractions et l'annulation avant préflight ci-dessus utilisent le vrai worker. Cela ne démontre pas l'absence de problème dans toutes les courses de fermeture ou d'annulation.
- Le DVD synthétique ne démontre pas la conservation de sous-titres DVD réels ni de langues IFO réelles. Le DVD reste publié comme fichier choisi par l'utilisateur; aucune indexation DVD supplémentaire dans Bibliothèque ou Historique n'a été introduite.
- La compatibilité d'un exécutable empaqueté avec le sous-processus de navigation DVD demeure non vérifiée, comme signalé dans AVM-11F.