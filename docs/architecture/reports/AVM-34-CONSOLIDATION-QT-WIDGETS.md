# AVM-34 — Consolidation de l’interface Qt Widgets

**Date :** 2026-11-09
**Verdict : VALIDÉ SOUS RÉSERVES**

## 1. Architecture avant intervention

`run_app()` crée une fenêtre `MainWindow` à navigation latérale. `LibraryHost` contenait un stack hybride : `LibraryPage` Widgets, une page `QQuickWidget` chargée depuis `ui/qml/LibraryPage.qml`, une page d’export Android Widgets, plus la section vidéo/DVD séparée. Le choix QML/Widgets provenait de `AppConfig.library_ui_mode` avec surcharge `AVM_LIBRARY_UI`; Paramètres proposait un sélecteur.

Le QML communiquait avec SQLite via `LibraryBridge` et `AlbumListModel`. Il ne possédait pas de service métier propre.

## 2. Parité fonctionnelle observée

| Fonction QML | Qt Widgets réutilisé après retrait |
|---|---|
| Grille responsive d’albums, pochettes, artiste, titre, statut prêt/manquant | `LibraryPage.list`, `_load_cover_pixmap`, état `path_exists` |
| Recherche artiste/album | `LibraryPage.search` et `_apply_filter` |
| Détail artiste, album, année, dossier et nombre de pistes | `LibraryPage.lbl_detail` |
| Pistes sélectionnées, numéros, titres, durées et état de fichier manquant | `LibraryPage.tbl_tracks` |
| Ouverture du dossier album | `LibraryPage._open_album` |
| Actualisation du catalogue | `LibraryPage.refresh` |
| État vide | `empty_state_card` et labels compatibles existants |
| Export Android intégré | `AndroidExportPage` déjà hébergée par `LibraryHost` |
| Contenu vidéo/DVD et navigation vers les autres sections | `VideoLibraryPage`, onglets de `LibraryHost`, navigation `MainWindow` |

Le bridge QML limitait les pistes de détail à 60 et son `ListView` de pistes avait une hauteur nulle; Widgets présente la table des pistes réellement navigable avec durée. Aucune fonction produit indispensable n’est restée sans équivalent.

## 3. Réutilisation, retrait et dépendances

- `LibraryPage` est maintenant l’unique vue Albums du stack; aucun nouveau catalogue ou composant métier n’a été créé.
- `LibraryHost` ne choisit plus de mode, ne crée plus de `QQuickWidget`, ne conserve plus de bridge ou de page QML et n’a plus de toggle de mode. Il conserve l’onglet Vidéos/DVD et l’export Android intégré.
- Le champ `library_ui_mode` a été retiré de `AppConfig` et le sélecteur QML a été retiré des Paramètres. `AppConfig.from_dict` ignore les anciennes clés JSON inconnues; une ancienne valeur `library_ui_mode` est donc inerte et disparaîtra à la prochaine sauvegarde de configuration.
- Les assets QML `LibraryPage.qml`, `AlbumCard.qml`, `DetailPane.qml`, `EmptyState.qml`, `SearchBar.qml`, `Theme.qml`, `qmldir` et le pont `library_bridge.py` ont été supprimés du package.
- Les globs QML ont été retirés de `pyproject.toml`. Aucune dépendance Qt Quick séparée n’était déclarée; `PySide6` reste nécessaire aux Widgets.
- `QT_QUICK_CONTROLS_STYLE`, la sélection `AVM_LIBRARY_UI`, les tests d’intégration/teardown exclusivement QML et le branchement QML du teardown `MainWindow` ont été supprimés ou adaptés.
- Les captures, prototypes et rapports historiques AVM-08 hors package/runtime sont conservés comme archives; ils ne sont plus importés par l’application.

## 4. Fichiers modifiés

- [`library_host.py`](../../../audio_video_manager/ui/sections/library_host.py), [`settings_page.py`](../../../audio_video_manager/ui/sections/settings_page.py), [`main_window.py`](../../../audio_video_manager/ui/main_window.py) : hôte Widgets unique, retrait du sélecteur QML et du teardown Quick devenu inutile.
- [`config.py`](../../../audio_video_manager/config.py), [`pyproject.toml`](../../../pyproject.toml), [`ci-windows.yml`](../../../.github/workflows/ci-windows.yml), [`run_tests_ci.py`](../../../scripts/run_tests_ci.py) : retrait du mode et des réglages/package data Qt Quick.
- [`conftest.py`](../../../tests/conftest.py), [`qt_support.py`](../../../tests/qt_support.py), [`test_config.py`](../../../tests/test_config.py), [`test_ui_library_history_06h.py`](../../../tests/test_ui_library_history_06h.py), [`test_qt_teardown_10c1.py`](../../../tests/test_qt_teardown_10c1.py), [`test_qt_teardown_10c2.py`](../../../tests/test_qt_teardown_10c2.py), [`test_ui_design_06l.py`](../../../tests/test_ui_design_06l.py), [`test_ui_shell.py`](../../../tests/test_ui_shell.py) : tests adaptés au seul parcours Widgets.
- [`architecture.md`](../../product/architecture.md), [`decisions.md`](../../product/decisions.md) : couche UI déclarée Widgets et D-016 mise à jour après exécution d’AVM-34.
- Suppressions : `audio_video_manager/ui/qml/LibraryPage.qml`, `audio_video_manager/ui/qml/library_bridge.py` et six fichiers sous `ui/qml/AvmLibrary/`; `tests/test_library_qml_08b.py` remplacé par les assertions Widgets déjà présentes dans les tests Bibliothèque.

Les modifications locales préexistantes hors de ces fichiers, y compris les données SQLite et la bibliothèque corrigées par AVM-33B, n’ont pas été modifiées.

## 5. Tests ciblés

Résultats exécutés séparément :

- `tests/test_config.py` : **4 passed**.
- `tests/test_ui_library_history_06h.py` : **10 passed**.
- `tests/test_ui_design_06l.py` : **8 passed**.
- `tests/test_qt_teardown_10c1.py` : **1 passed**.
- `tests/test_qt_teardown_10c2.py` : **2 passed**.
- Sous-ensemble navigation/CD/Paramètres/layout de `tests/test_ui_shell.py` : **5 passed**, 29 deselected.
- `tests/test_android_export.py` : **4 passed**.

Total ciblé : **34 tests passés**. Diagnostics Pylance sur les modules et tests modifiés : aucune erreur. Le rapport terminal du lot complet `test_ui_shell.py` n’était pas disponible; ses scénarios pertinents à AVM-34 ont été exécutés individuellement/sélectivement, sans lancer une campagne générale DVD.

## 6. Validation réelle Windows

Le vrai point d’entrée `run_app()` a été lancé avec la configuration et la base AVM réelles. Pour respecter l’interdiction d’écriture, la connexion SQLite était en `mode=ro` et `query_only`; `Database.initialize`, réconciliation, création des répertoires et scan optique automatique ont été neutralisés uniquement en mémoire pour ces processus de validation.

Constats :

- Une seule fenêtre principale `MainWindow`; l’export Android est un QWidget enfant, pas une fenêtre.
- 7 albums et 98 pistes actuellement présents (dont Leonard Cohen, ajouté après AVM-33B); toutes les pochettes sont chargées.
- Bee Gees Disc 1 et Disc 2 sont affichés, 10 pistes chacun.
- Navigation validée entre Archivage, Bibliothèque, Historique et Paramètres.
- La Bibliothèque Widgets est identique à la seule implémentation active; Actualiser recharge le catalogue.
- La page Export Android s’ouvre et revient dans le même hôte. ADB était à l’état « aucun appareil » pendant cette validation; aucun transfert ni scan distant n’a été lancé. Les 86 transferts `succeeded` locaux sont restés intacts.
- Aucun module `audio_video_manager.ui.qml` n’a été importé. Les captures réelles à 1100×720 et 760×560 sont dans `%TEMP%\avm34-library-wide.png`, `%TEMP%\avm34-library-narrow.png`, `%TEMP%\avm34-android-wide.png` et `%TEMP%\avm34-android-narrow.png`.

Les sections CD/DVD restent accessibles par les mêmes entrées et panneaux Widgets; le sous-ensemble MainWindow/section CD ciblé est passé. Aucun rip ni parcours DVD n’a été exécuté.

## 7. Références QML et limites

Recherche finale dans `audio_video_manager/**/*.py` : aucune référence QML/Qt Quick. Aucun `.qml` n’est présent dans `audio_video_manager/ui/qml`; les assets sont supprimés et exclus du packaging. La seule chaîne `library_ui_mode` encore présente dans les tests vérifie que les anciennes configurations la contenant sont chargées sans cette clé.

Les scripts de capture et prototypes AVM-08 ainsi que les rapports UX/validation historiques restent archivés hors du package de production. Ils peuvent encore mentionner QML, mais ne sont pas chargés ni appelés par `run_app()`.

Réserve : la validation réelle de la détection et de l’historique Android était limitée à l’absence d’appareil connecté; le service Android a été validé par ses tests ciblés séparés. Aucune donnée réelle SQLite ou média n’a été écrite.

## 8. Verdict

**VALIDÉ SOUS RÉSERVES.** La dépendance fonctionnelle QML a été retirée du package/runtime, la Bibliothèque Widgets existante est l’unique vue active, et les parcours principaux ainsi que l’export Android intégré sont conservés. Le seul point non validé matériellement est l’interaction avec un appareil Android, absent pendant cette session; aucun transfert n’était autorisé ni nécessaire pour ce mandat.