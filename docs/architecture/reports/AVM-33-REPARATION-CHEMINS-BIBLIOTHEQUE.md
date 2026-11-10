# AVM-33 — Chemins de bibliothèque après renommage

**Date :** 2026-11-09
**Verdict : NON VALIDÉ**

## 1. Cause démontrée

La configuration persistée dans `%LOCALAPPDATA%\AudioVideoManager\config.json` indique comme racine `C:\Users\ComeToM3\Music\AVM-Library`. La base réelle `%LOCALAPPDATA%\AudioVideoManager\avm.sqlite3` (schéma v6, lue en mode SQLite `read-only` / `query_only`) contient **6 releases et 86 pistes** dont les chemins absolus désignent `C:\Users\ComeToM3\Music\AVM-06C-Test-Library`. Cette ancienne racine n’existe plus.

Le nom `library text` donné dans le mandat n’apparaît pas dans les chemins SQLite examinés et n’existe pas dans les emplacements directs vérifiés (Music, Desktop, Documents et racine du dépôt). Il n’est donc pas possible d’établir que les chemins enregistrés correspondent à cette ancienne bibliothèque.

## 2. Chemins et fichiers présents

- **Racine configurée :** `C:\Users\ComeToM3\Music\AVM-Library`.
- **Préfixe absolu enregistré :** `C:\Users\ComeToM3\Music\AVM-06C-Test-Library`.
- **Ancienne racine attendue par le mandat :** aucun chemin `library text` n’est présent dans SQLite ni dans les emplacements directs vérifiés.
- Une projection purement relative de `AVM-06C-Test-Library` vers `AVM-Library` trouve les 6 dossiers d’album, les 86 FLAC et un `cover.jpg` par release; les deux disques Bee Gees ont aussi leurs `Disc 1` et `Disc 2` attendus.
- Mais `AVM-Library` contient `.avm-06c-isolated`, dont le texte UTF-8 est : **« Bibliothèque de test isolée AVM-06C — ne pas utiliser comme collection principale. »** Le dossier comprend aussi `_inbox` et `Charles Aznavour`, sans release correspondante dans les six lignes actuellement listées.

Les chemins relatifs concordants prouvent une association avec les données du jeu AVM-06C, pas avec la bibliothèque personnelle `library text` mentionnée. Le marqueur interdit explicitement de considérer cette racine comme collection principale.

## 3. Composants affectés et cause du bouton Actualiser

- [`SettingsPage._save`](../../../audio_video_manager/ui/sections/settings_page.py) persiste `library_root` dans la configuration et émet `config_saved`.
- [`MainWindow._on_config_saved`](../../../audio_video_manager/ui/main_window.py) transmet la configuration à `LibraryHost`.
- [`LibraryPage.set_config`](../../../audio_video_manager/ui/sections/library_page.py) met à jour le label de racine; il ne réécrit pas les chemins SQLite.
- [`list_releases`](../../../audio_video_manager/storage/catalog.py) relit `releases.path` tel quel. `ReleaseRow.path_exists` teste ce chemin absolu enregistré.
- Les pochettes sont cherchées dans le dossier album dérivé de `ReleaseRow.path`; **Ouvrir le dossier album** ouvre ce même chemin. Les pistes proviennent de `tracks.path` absolu.
- **Actualiser** rappelle `list_releases()` puis reconstruit la vue à partir des mêmes chemins inchangés. Il ne rebase ni `releases.path` ni `tracks.path`; l’échec d’affichage/ouverture se répète donc.

Les observations confirment des chemins absolus obsolètes dans le catalogue actif. Elles ne démontrent pas une corruption SQLite.

## 4. Vérification sur copie isolée

La base réelle a été ouverte en lecture seule et copiée via l’API SQLite `backup` vers une base temporaire. Sur cette copie uniquement, une transaction conditionnelle a projeté les chemins sous le suffixe relatif connu vers `AVM-Library`, après vérification de chaque dossier, FLAC et pochette.

Résultat de simulation : **6 releases / 86 pistes mises à jour dans la copie**, `PRAGMA integrity_check = ok`, IDs et nombres d’enregistrements conservés. La copie temporaire a été supprimée à la fin de son contexte.

Cette simulation démontre que le mécanisme de rebase fonctionnerait pour le jeu AVM-06C. Elle **n’autorise pas** à modifier la base réelle, car `AVM-Library` porte le marqueur test-only et ne correspond pas à la racine utilisateur identifiée dans le mandat.

## 5. Écritures et médias laissés intacts

- La base réelle n’a subi aucune transaction de modification, migration, sauvegarde persistante ni changement de chemin.
- Aucun album, piste, pochette, historique ou identifiant SQLite n’a été modifié.
- Aucun fichier FLAC, dossier, marqueur `.avm-06c-isolated`, `_inbox` ou dossier `Charles Aznavour` n’a été déplacé, renommé, écrasé ou supprimé.
- Aucune réimportation, aucun transfert Android et aucune extraction CD/DVD n’ont été lancés.

Aucune sauvegarde de la base réelle n’a été créée : aucune écriture réelle n’a été jugée sûre ou nécessaire avant d’identifier la bibliothèque principale.

## 6. Décision Qt Widgets

La décision demandée est consignée dans le registre architectural existant [`decisions.md`](../../product/decisions.md) sous **D-016 — Technologie UI de référence** : PySide6 / Qt Widgets pour toute nouvelle fonctionnalité; le QML existant est conservé jusqu’à une décision d’exécution distincte. Aucune migration ou suppression QML n’a été entreprise.

## 7. Validations et limites

- **Réel, lecture seule :** configuration, version et lignes de catalogue SQLite, chemins absolus, présence de la racine configurée, dossiers/FLAC/couvertures correspondants et marqueur d’isolation.
- **Copie temporaire :** simulation transactionnelle de la réassociation, intégrité, IDs et comptages.
- **Tests automatisés :** aucun ajouté ni exécuté; aucun code de production n’a été modifié.
- **Interface Windows réelle :** non relancée pour ce mandat. Le seul chemin avec correspondance exacte est explicitement une racine de test; l’ouverture de la bibliothèque configurée n’aurait pas validé la collection personnelle demandée.
- **Bloqueur :** le chemin exact de la bibliothèque principale après déplacement n’est pas établi. Le chemin enregistré est AVM-06C-Test-Library, tandis que le chemin proposé/configuré AVM-Library est marqué « ne pas utiliser comme collection principale ».

## 8. Verdict

**NON VALIDÉ.** La cause technique des symptômes est démontrée : la configuration utilise une racine tandis que le catalogue continue de tester des chemins absolus d’une autre racine; le bouton Actualiser ne répare pas ces références. Cependant, la seule association fichier par fichier trouvée mène au jeu isolé AVM-06C, et non de façon démontrable à la bibliothèque utilisateur déplacée depuis `library text`.

Pour reprendre sans risque, il faut identifier le chemin exact de la collection principale attendue et confirmer que ce n’est pas la racine marquée `.avm-06c-isolated`. D’ici là, la base réelle et tous les fichiers doivent rester intacts.