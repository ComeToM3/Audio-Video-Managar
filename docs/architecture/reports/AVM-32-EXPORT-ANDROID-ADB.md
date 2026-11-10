# AVM-32 — Export musical vers Android par ADB

**Date :** 2026-11-09
**Verdict : PARTIEL**

## 1. Résultat

L’action manuelle **Exporter vers Android** est intégrée à la Bibliothèque. Elle détecte les appareils ADB à la demande, expose la sélection album/piste, garde l’historique v6, et transfère séquentiellement dans l’espace AVM avec staging et vérification SHA-256/taille. Les essais simulés et les contrôles de lecture sur le téléphone sont concluants.

Le transfert physique n’a pas été exécuté : il écrirait sur le téléphone et exige l’autorisation explicite prévue par AVM-32. L’écriture dans `/sdcard/Music`, la promotion réelle sans écrasement et la visibilité par un lecteur restent donc non démontrées.

## 2. Fichiers modifiés

- [`.gitignore`](../../../.gitignore) : exception de suivi limitée au nouveau service Android, car `audio_video_manager/library/*` était ignoré.
- [`schema.py`](../../../audio_video_manager/storage/schema.py), [`database.py`](../../../audio_video_manager/storage/database.py) : schéma et migration v6.
- [`catalog.py`](../../../audio_video_manager/storage/catalog.py) : expose `tracks.id` dans les pistes catalogue.
- [`android_transfers.py`](../../../audio_video_manager/storage/android_transfers.py) : lecture et écriture des lignes d’historique.
- [`android_export.py`](../../../audio_video_manager/library/android_export.py) : détection ADB, scan ciblé, hachage source/distant, espace disponible, staging et promotion sans remplacement.
- [`android_export_worker.py`](../../../audio_video_manager/ui/android_export_worker.py), [`android_export_dialog.py`](../../../audio_video_manager/ui/sections/android_export_dialog.py), [`library_host.py`](../../../audio_video_manager/ui/sections/library_host.py) : worker Qt, dialogue de sélection et action dans l’en-tête Bibliothèque.
- [`test_android_export.py`](../../../tests/test_android_export.py), [`test_database.py`](../../../tests/test_database.py), [`test_ui_library_history_06h.py`](../../../tests/test_ui_library_history_06h.py) : couverture ciblée.

Les modifications locales préexistantes, notamment celles de `main_window.py`, du moteur CD et des parcours DVD, ont été laissées intactes. Aucun commit ni push.

## 3. Composants réutilisés et comportement

- Réutilisation de `list_releases`, `list_tracks_for_release`, des chemins publiés et du nouvel ID `tracks.id`; aucun second catalogue musical.
- Réutilisation de `Database`, de son système de migrations, du patron `QObject`/`QThread` et de `attach_worker_thread`.
- `adb.exe` est recherché sous `ANDROID_SDK_ROOT`, `ANDROID_HOME`, `%LOCALAPPDATA%\Android\Sdk`, puis `PATH`. Si absent, le dialogue permet de choisir `adb.exe` pour la session.
- Chaque commande est ciblée avec `adb -s <serial>`. La recherche et l’analyse démarrent uniquement après clic; aucun branchement automatique.
- Le scan ne parcourt pas le téléphone : il vérifie uniquement les chemins calculés depuis les pistes AVM et ceux enregistrés dans l’historique. Une destination présente mais inconnue, ou différente de son empreinte connue, est un conflit non sélectionnable.
- Le cache de source réutilise SHA-256 lorsque chemin, taille et `mtime_ns` sont inchangés. Les sources sélectionnées sont toujours re-hachées avant copie.
- Les albums simples conservent leur chemin publié; les pistes multidisques conservent les sous-dossiers `Disc N` via leur chemin relatif réel sous `library_root`.
- Les opérations ADB s’exécutent dans le worker. L’interface montre le fichier actif et un décompte de fichiers terminés; aucun pourcentage de progression par octets n’est présenté.

## 4. Historique SQLite

Migration **v5 → v6** implémentée, ajoutant la seule table `android_transfers`. Elle référence `tracks.id` avec `ON DELETE RESTRICT` et stocke numéro de série, chemin source, SHA-256, taille, `mtime_ns` (cache de fingerprint), chemin distant, staging éventuel, statut (`pending`, `succeeded`, `failed`), dates et erreur. Des contraintes empêchent de dupliquer une version de piste ou de réserver deux pistes sur le même chemin appareil.

La migration est couverte depuis v5 et conserve les releases et pistes existantes. La base réelle `%LOCALAPPDATA%\AudioVideoManager\avm.sqlite3` a été ouverte en lecture seule : elle est toujours en **v5**. Elle n’a pas été migrée pendant AVM-32; `Database.initialize()` appliquera v6 au prochain démarrage normal de l’application.

Un succès n’est inscrit qu’après comparaison de la taille et du SHA-256 distant du staging, promotion `toybox mv -n`, confirmation que le staging a disparu et nouvelle vérification du fichier final. Toute interruption/erreur après démarrage laisse un état non réussi; aucun partiel n’est supprimé.

## 5. Tests ciblés

Commande finale :

```text
.venv\Scripts\python.exe -m pytest -o addopts= -q tests/test_android_export.py tests/test_database.py tests/test_ui_library_history_06h.py tests/test_library_qml_08b.py tests/test_archive_pipeline.py tests/test_cd_ripper.py tests/test_dvd_extractor_11c.py
```

Résultat : **58 passed**. Les cas ajoutés couvrent nouvelle piste, succès uniquement après empreinte conforme, piste transférée, fichier distant absent reproposé, version source modifiée envoyée à un chemin distinct, destination inconnue, collision apparue après scan, et échec d’intégrité conservant staging et statut échoué. Les tests UI couvrent sélection album/piste, source absente non sélectionnable et purge de l’ancienne sélection au changement d’appareil.

Pylance `get_errors` : aucune erreur sur les fichiers Python touchés. `git diff --check` : aucune erreur d’espacement.

## 6. État réel Android et catalogue

- ADB : `1.0.41`, version plateforme `36.0.2-14143358`.
- Appareil observé : état `device`, Motorola moto g24 power, Android 14 / API 34, série ADB `ZT322P23HJ` pendant cette connexion.
- L’implémentation Python confirme `adb devices -l`, `toybox stat`, `toybox sha256sum` et `df`. Espace libre observé : `188540813312` octets. `/sdcard/Music/AudioVideoManager` est absent.
- L’analyse SQLite réelle en lecture seule trouve **6 albums, 86 pistes et aucune source manquante**. Une copie temporaire de cette base a été migrée en v6 et analysée par le service contre les seules destinations AVM : **86 pistes nouvelles**, aucun conflit. La base réelle et ses médias n’ont pas été modifiés.

## 7. Validation physique et limites

**Réalisé :** détection du Motorola autorisé, lecture des propriétés, du dossier Music et de l’espace, validation des appels ADB réels `stat` et SHA-256, analyse de catalogue sur copie temporaire. Aucun scan général de la musique Android.

**Non réalisé :** aucun `mkdir`, `adb push`, `mv`, changement de fichier ou suppression sur le téléphone. La permission d’écriture, le comportement réel de `mv -n` en collision, une déconnexion pendant copie, la migration du SQLite utilisateur et la visibilité d’un FLAC dans un lecteur ne sont pas démontrés. Le stockage libre peut changer entre le contrôle et l’envoi; l’échec est alors conservé et le staging reste en place.

Le bilan réel de transfert est donc **non disponible**; tous les résultats de copie et de collision sont issus de tests simulés. Le code refuse une destination occupée et n’enregistre pas un succès si la promotion ou sa vérification n’est pas confirmée.

## 8. Verdict et prochaine décision

**PARTIEL.** L’interface, l’historique et le flux de transfert sont implémentés; les tests ciblés passent et le scan réel du catalogue/appareil est validé en lecture seule. Le critère de réussite physique n’est pas atteint faute d’autorisation d’écriture.

Étape suivante nécessitant votre accord : autoriser un essai contrôlé avec **un seul FLAC**, puis vérifier intégrité, destination et visibilité sur le téléphone. Aucun transfert massif ne sera lancé sans nouvelle instruction.