# AVM-28E — Diagnostic de l’instance réelle

**Verdict : BLOQUÉ — la cause du défaut persistant n’est pas encore démontrée. Une seule observation de l’utilisateur avec le CD est nécessaire pour localiser la perte.**

## Faits vérifiés

- `Lancer-AudioVideoManager.bat` fixe son répertoire au dépôt, lance `.venv\Scripts\python.exe -m audio_video_manager`, et le point d’entrée appelle `ui.main_window.run_app`.
- Import vérifié avec ce Python : `audio_video_manager`, `ui.main_window` et `ui.wizard.archive_wizard` proviennent tous du dépôt courant. La fenêtre active utilise `ArchiveWizardPage` Widgets.
- AVM-28D a reproduit et corrigé les échecs CAA/Discogs qui pouvaient faire perdre un candidat valide. Ces essais étaient synthétiques; ils ne démontrent pas le résultat de l’instance de l’utilisateur.
- Des traces temporaires `AVM28E_TRACE` jalonnent le démarrage, la réception des candidats, l’application au modèle, l’édition retenue et les valeurs des champs visibles.
- Tests ciblés d’instrumentation : 26 réussis; diagnostics éditeur sans erreur; `git diff --check` réussi. Aucun lecteur n’a été accédé par l’assistant.

## Observation requise

1. Laisser le CD audio présent, fermer toutes les fenêtres AVM déjà ouvertes, puis lancer une fois `Lancer-AudioVideoManager.bat` depuis ce dépôt.
2. Attendre la fin de l’identification. Si plusieurs éditions sont proposées, en sélectionner une fois. **Ne pas cliquer sur « Continuer » ni sur « Extraire ».**
3. Renvoyer les lignes `AVM28E_TRACE` de la console, dans leur ordre d’apparition. Elles diront si le candidat manque, si son application au modèle échoue, ou si les valeurs diffèrent seulement dans les widgets.

La configuration de journalisation écrit aussi `avm.log` dans le dossier de logs AVM si les lignes console ne sont plus disponibles. Ne transmettre que les lignes `AVM28E_TRACE`.

**Aucun rip, commit ou push. Ne rien modifier ou déplacer dans la bibliothèque. Arrêt jusqu’à réception de cette observation; aucune correction spéculative n’est appliquée.**