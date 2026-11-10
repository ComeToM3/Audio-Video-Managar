# AVM-28G — Fiche CD et paramètres

**Verdict : PARTIEL.** Le blocage artificiel de compilation et l’organisation des paramètres sont corrigés et testés. L’approbation sur le CD Windows réel reste à confirmer.

## Cause et correction

`validate_disc_metadata` exigeait `field_meta.is_compilation == CONFIRMED` deux fois, y compris pour `MISSING` ou `AMBIGUOUS`. Une fiche dont l’information n’existait pas était donc refusée avec `is_compilation: required`, bien que ce champ ne soit pas nécessaire à l’intégrité du rip.

La compilation demeure un état à trois valeurs : `True` ou `False` confirmé est conservé; `MISSING`/`AMBIGUOUS` reste inconnu. L’inconnu n’est plus un échec d’approbation. Les validations de TOC, Disc ID quand disponible, titres, année, pochette, pistes, durées et chemins restent actives. Les tags FLAC `COMPILATION=1` ne sont toujours écrits que lorsque la valeur est vraie; aucune fausse valeur négative n’est ajoutée.

## Paramètres

- Niveau principal : dossier de bibliothèque musicale modifiable et éjection du CD après extraction.
- « Afficher les paramètres avancés » : pays de départage, freaccmd, outils DVD, compression FLAC, mode d’affichage de bibliothèque, dossiers temporaires/logs, test technique et diagnostic fre:ac.
- Les contrôles d’auto-approbation indisponible et le texte DVD redondant ont été retirés. Les valeurs techniques persistées restent chargées/sauvegardées.
- Pour une nouvelle installation, Windows `SHGetKnownFolderPath(FOLDERID_Music)` détermine Musique, puis `AudioVideoManager` est ajouté. Sur cette machine, la résolution réelle retourne `C:\Users\ComeToM3\Music` et le défaut serait `C:\Users\ComeToM3\Music\AudioVideoManager`.
- `AVM_LIBRARY_ROOT` reste prioritaire. `AppConfig.from_dict` conserve exactement le `library_root` d’une configuration existante, y compris `AVM-06C-Test-Library`; aucun dossier n’est créé, déplacé ou migré par ce changement.

## Validation

- Compilation `True`, `False`, `MISSING` et `AMBIGUOUS` : approbation possible si les autres champs requis sont valides.
- Tests ciblés : `test_disc_metadata.py` **19**, paramètres/UX **3**, configuration **3**, fiche et `test_ux_06o.py` **28**; tous réussis. Toggle avancé et persistance de destination vérifiés.
- CI : `.venv/Scripts/python.exe scripts/run_tests_ci.py --report .ci/avm28g-ci-results.json --junit-dir .ci/junit/avm28g` — **394 tests, 13 groupes, 0 échec, 0 erreur, 0 skip, 0 crash natif**.
- Résolution Known Folder exécutée sur Windows; diagnostics éditeur sans erreur; `git diff --check` réussi.
- Le CD réel n’a pas été lu ou approuvé pendant cette session. Aucun rip n’a été lancé.

## Confirmation Windows requise

Avec le CD qui affichait l’erreur, ouvrir l’application, vérifier que les métadonnées sont présentes, puis cliquer une fois sur « Continuer ». Cela approuve et enregistre la fiche dans SQLite; **ne pas cliquer sur « Extraire »**. Confirmer si l’écran d’extraction apparaît sans erreur `is_compilation`.

**Aucun commit ni push. Arrêt AVM-28G en attente de cette observation.**