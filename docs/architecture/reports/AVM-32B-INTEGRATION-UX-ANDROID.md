# AVM-32B — Intégration native de l’export Android

**Date :** 2026-11-09
**Verdict : VALIDÉ**

## Architecture UI active

Le lancement réel passe par [`__main__.py`](../../../audio_video_manager/__main__.py) vers `run_app()` dans [`main_window.py`](../../../audio_video_manager/ui/main_window.py). La fenêtre unique `MainWindow` possède une navigation latérale et un `QStackedWidget` principal. L’entrée Bibliothèque est un [`LibraryHost`](../../../audio_video_manager/ui/sections/library_host.py), qui héberge un stack Widgets/QML ainsi qu’un onglet de contenu vidéo/DVD.

La page Widgets [`LibraryPage`](../../../audio_video_manager/ui/sections/library_page.py) et [`SettingsPage`](../../../audio_video_manager/ui/sections/settings_page.py) emploient des marges de contenu de 28×20 px, des titres `pageTitle`, les contrôles stylés globalement par le thème AVM et une `QScrollArea` lorsque le contenu peut dépasser la hauteur disponible.

## Cause de la régression

Le bouton Android de `LibraryHost` créait `AndroidExportDialog` puis appelait `dialog.exec()`. Le contenu s’ouvrait donc en fenêtre modale séparée, avec une taille propre de 900×650, au lieu de participer à la navigation et au redimensionnement de `MainWindow`.

## Intégration réalisée

- Le contenu d’export est maintenant un `QWidget` enfant du stack interne de Bibliothèque. Il n’a pas de fenêtre native propre.
- Le bouton Bibliothèque affiche cette vue dans le même contenu principal, masque temporairement le basculement Widgets/QML et l’onglet DVD, puis un bouton **Retour à la bibliothèque** restaure exactement la vue précédente.
- Aucun item permanent n’a été ajouté à la barre latérale et `main_window.py` n’a pas été modifié.
- La page reprend `pageTitle`, les marges 28×20, les boutons `primary`/`ghost` et une zone défilante sans barre horizontale. Les colonnes de pistes réservent l’espace résiduel aux titres; les états visibles sont courts et leur détail reste disponible en infobulle.
- La recherche ADB, la sélection appareil, le scan, l’historique, la confirmation et le worker Qt sont conservés. Le service `android_export.py`, l’historique SQLite v6 et les règles de copie n’ont pas été modifiés dans AVM-32B.

## Fichiers modifiés

- [`library_host.py`](../../../audio_video_manager/ui/sections/library_host.py) : navigation interne, mémorisation/restauration de la vue et raccord à la racine bibliothèque mise à jour.
- [`android_export_dialog.py`](../../../audio_video_manager/ui/sections/android_export_dialog.py) : le contenu devient `AndroidExportPage`; mise en page AVM, scroll et colonnes adaptées.
- [`test_ui_library_history_06h.py`](../../../tests/test_ui_library_history_06h.py) et [`test_library_qml_08b.py`](../../../tests/test_library_qml_08b.py) : aller-retour via le bouton, absence de fenêtre secondaire, conservation du mode actif et contrôles de sélection.

Les changements préexistants présents dans ces tests, notamment les modifications antérieures de `test_ui_library_history_06h.py`, ont été préservés.

## Vérifications

- Tests ciblés finaux : `tests/test_ui_library_history_06h.py` et `tests/test_library_qml_08b.py` — **15 passed**.
- Diagnostics Python Pylance : aucune erreur dans les composants et tests modifiés. `git diff --check` : aucune erreur d’espacement.
- Le point d’entrée réel `run_app()` a été démarré sous Windows avec `AVM_DATA_DIR` et `AVM_LIBRARY_ROOT` isolés dans `%TEMP%`, une base et une piste synthétiques. Dans les lancements de capture contrôlés, le déclencheur du scan optique a été neutralisé uniquement en mémoire pour éviter tout accès au lecteur CD.
- Le parcours vérifié est Bibliothèque → Export Android → Retour. `MainWindow` reste la fenêtre visible, le stack principal reste sur Bibliothèque, `AndroidExportPage.isWindow()` vaut `False`, et le retour restaure la vue précédente.
- Vérification visuelle native Qt à **1100×720** et **760×560** : titre, appareil, arbre album/pistes, sélection et commandes restent dans la fenêtre. La capture étroite finale montre les titres complets après réduction des libellés d’état; aucune barre de défilement verticale n’est nécessaire à cette taille.
- La recherche ADB en lecture seule a affiché le Motorola moto g24 power en état `device`. Aucun scan de pistes, transfert, création de dossier ou autre écriture Android n’a été lancé dans AVM-32B.
- Captures temporaires hors dépôt : `%TEMP%\avm32b-final-ui-7r0kyy84\wide.png`, `%TEMP%\avm32b-final-ui-7r0kyy84\narrow.png`, `%TEMP%\avm32b-proof-yxjc21yi\narrow.png`.

## Limite et incident de validation

Lors du tout premier lancement réel, avant neutralisation du déclencheur, le comportement existant d’AVM a détecté le CD présent, lu sa TOC et lancé l’identification MusicBrainz/CAA. L’application était occupée, ce qui a également empêché la navigation pendant cette première capture. **Aucune extraction n’a été lancée**, aucun fichier de bibliothèque ni base réelle n’a été touché. Les lancements de capture suivants ont neutralisé ce seul déclencheur d’exploration optique à l’exécution et n’ont effectué que la détection ADB en lecture seule.

Le transfert physique Android reste non testé et non requis pour ce mandat UX; il demeure soumis à l’autorisation déjà demandée dans AVM-32. Aucun changement CD/DVD, aucun commit et aucun push.

## Verdict

**VALIDÉ** pour le critère AVM-32B : l’export s’ouvre et se ferme dans le contenu de la fenêtre principale AVM, respecte le style actif, et conserve l’accès à Widgets/QML sans refonte de la navigation générale. La fonctionnalité ADB est restée inchangée; le transfert réel sur Android n’est pas couvert par ce verdict UX.