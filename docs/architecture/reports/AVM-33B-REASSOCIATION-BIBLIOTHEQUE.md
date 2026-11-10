# AVM-33B — Réassociation de la bibliothèque principale

**Date :** 2026-11-09
**Verdict : VALIDÉ**

## 1. Sauvegarde et préconditions

La configuration active pointait toujours vers `C:\Users\ComeToM3\Music\AVM-Library`. Avant toute écriture, SQLite en lecture seule a confirmé 6 releases, 86 pistes, 86 transferts Android réussis et 6 pochettes. Chaque chemin relatif des releases et pistes a une cible unique et existante sous la racine configurée; aucun chemin projeté ne sort de cette racine et aucune collision n’a été trouvée.

Les 86 références `android_transfers.source_path` correspondaient aux `tracks.path` par ID et chemin relatif. Les tailles et SHA-256 des fichiers sources sous `AVM-Library` correspondaient aux valeurs enregistrées; les destinations Android et statuts étaient des données indépendantes à conserver. Les 6 `jobs.library_path` se projetaient aussi vers les dossiers correspondants; leurs états étaient `Completed` ou `CompletedWithWarnings`.

Sauvegarde persistante créée avec `sqlite3.Connection.backup` avant transaction :

- Chemin : `%LOCALAPPDATA%\AudioVideoManager\backups\avm33b-pre-reassociation-20261109T130533Z.sqlite3`
- Taille : `413696` octets
- SHA-256 : `2bc58e7f76fdbea6aac809ea5e224f31cf57f44bcddcec17fdff309af31600f3`
- `PRAGMA integrity_check` : `ok`; comptages sauvegardés : 6 releases, 86 tracks, 86 transferts.

La sauvegarde n’existait pas auparavant; aucune sauvegarde n’a été écrasée.

## 2. Correction réelle

Dans une seule transaction `BEGIN IMMEDIATE`, avec contrôles conditionnels sur les anciens chemins et rollback sur incohérence, les chemins ont été réassociés par leur suffixe relatif sous `C:\Users\ComeToM3\Music\AVM-Library` :

- `releases.path` : **6** lignes.
- `tracks.path` : **86** lignes.
- `android_transfers.source_path` : **86** lignes.
- `jobs.library_path` : **6** lignes historiques.

Total : **184 colonnes de chemin modifiées**. Les destinations Android, IDs d’appareil, statuts, dates, empreintes, tailles et autres colonnes sont restés identiques. Les identifiants, métadonnées et associations release/piste ont été comparés à la sauvegarde. Aucun schéma ni migration n’a été modifié.

## 3. État de la bibliothèque après correction

- SQLite réel : 6 releases et 86 pistes, IDs inchangés.
- Les 6 dossiers d’album, 86 FLAC et 6 `cover.jpg` existent sous la nouvelle racine.
- Bee Gees conserve `Disc 1` et `Disc 2`, 10 pistes chacun.
- Toutes les références corrigées de releases, pistes, transferts Android et jobs sont sous `AVM-Library`; aucune ne commence encore par l’ancien préfixe `AVM-06C-Test-Library`.
- Les 86 transferts Android restent `succeeded`; leurs chemins Android, statuts et SHA-256 enregistrés n’ont pas changé.
- `PRAGMA integrity_check` après transaction : `ok`.
- Les dossiers `_inbox` et `Charles Aznavour` ont été laissés intacts.

## 4. Validation réelle de l’interface Windows

Le point d’entrée AVM (`run_app`) a été lancé sous Windows avec la configuration et la base réelles. Le scan optique automatique a été neutralisé uniquement en mémoire pour éviter une nouvelle lecture CD. Résultats observés dans la Bibliothèque Widgets :

- 6 albums affichés; les 6 icônes de pochette chargent une image non nulle.
- Les 86 pistes restent interrogeables; Bee Gees Disc 1 et Disc 2 affichent chacun 10 pistes.
- Le bouton **Ouvrir le dossier album** a appelé Windows avec `C:\Users\ComeToM3\Music\AVM-Library\Bee Gees\Greatest (1984)\Disc 1`; ce dossier existe.
- **Actualiser** recharge les 6 albums et les pochettes sans perte.
- Capture de l’interface réelle : `%TEMP%\avm33b-real-library.png`.

Aucune extraction CD/DVD, aucun transfert Android ni ouverture en écriture de la bibliothèque musicale n’a eu lieu pendant cette validation.

## 5. Marqueur de test

La recherche dans le code, les tests, les scripts et la documentation n’a trouvé aucune utilisation de `.avm-06c-isolated`. Son contenu étant un avertissement vestigial, il a été déplacé, sans suppression, vers :

`%LOCALAPPDATA%\AudioVideoManager\backups\avm33b-legacy-marker-20261109T130533Z\.avm-06c-isolated`

SHA-256 avant/après déplacement : `ee16ab525d5072ec127414ca75cc05ec1b463c254dee462201b9f16b67ce65d6`.

## 6. Tests et prévention

Tests ciblés : `tests/test_ui_library_history_06h.py` et `tests/test_android_export.py` — **14 passed**. Les diagnostics Pylance sur catalogue, bibliothèque et paramètres ne signalent aucune erreur.

Le changement de `library_root` dans Paramètres persiste la configuration et actualise l’étiquette, mais ne réassocie pas actuellement les chemins absolus SQLite. Une réassociation automatique n’a pas été ajoutée : distinguer une bibliothèque déplacée d’une bibliothèque différente exige une confirmation et des contrôles complets; faire cela implicitement risquerait de lier le catalogue à la mauvaise collection. Ce comportement est documenté comme limitation pour un changement futur.

La décision **D-016 — PySide6 / Qt Widgets** demeure consignée dans [`decisions.md`](../../product/decisions.md); QML n’a pas été migré ni supprimé.

## 7. Intégrité et fichiers laissés intacts

Aucun FLAC, fichier de pochette, album ou dossier existant n’a été déplacé, supprimé ou écrasé. Les seules écritures de données réelles ont été les mises à jour transactionnelles des quatre colonnes de chemin énumérées ci-dessus et le déplacement réversible du marqueur. Aucun transfert Android, commit ou push.

**Verdict : VALIDÉ.** La bibliothèque principale configurée est réassociée, visible et ouvrable dans AVM; les pochettes, pistes, multidisques, historiques et destinations Android sont conservés.