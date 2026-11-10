# AVM-31 — Faisabilité de l’export Android par ADB

**Date :** 2026-11-09
**Verdict : FAISABLE SOUS RÉSERVES**

## Conclusion

Le poste Windows dispose d’ADB et AVM possède déjà les sources architecturales nécessaires pour un export manuel et un historique local. Un Motorola moto g24 power autorisé a maintenant été interrogé en lecture seule : `/sdcard/Music` existe, environ 175,6 Gio sont libres et Toybox fournit une commande SHA-256. Les permissions d’écriture, une copie réelle, la promotion sans écrasement et la visibilité dans un lecteur n’ont pas été testées.

L’export est techniquement raisonnable sans synchronisation : cibler uniquement les pistes du catalogue AVM, mémoriser leur empreinte par numéro de série ADB, contrôler uniquement les chemins enregistrés et copier dans un espace AVM dédié. Aucun code de production, schéma SQLite réel, téléphone, test ou installation n’a été modifié ou lancé.

## 1. État réel ADB sur Windows

- `adb.exe` est présent sous `%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe`; il n’est pas résolu par `PATH`.
- Version observée : Android Debug Bridge `1.0.41`, version plateforme `36.0.2-14143358`, sur Windows `10.0.26300`.
- `adb devices -l` a retourné un appareil à l’état `device` : numéro de série `ZT322P23HJ`, produit `fogorow_gp`, appareil `fogorow`, modèle `moto_g24_power`. `adb -s ZT322P23HJ get-serialno` a renvoyé le même numéro pendant cette session.
- Propriétés lues : fabricant `motorola`, modèle `moto g24 power`, Android `14`, API `34`. L’état `unauthorized` et l’état `offline` n’ont pas été observés.
- `/sdcard/Music` existe (`drwxrws---`, propriétaire `u0_a195`, groupe `media_rw`). `df -k /sdcard` indique `184120000` KiB disponibles, soit environ `175,6` Gio (22 % utilisés). Cela ne prouve pas que l’utilisateur ADB peut écrire dans ce dossier.
- Le chemin exact `/sdcard/Music/AudioVideoManager` n’existe pas. Son contenu n’a pas été parcouru et aucun dossier n’a été créé.
- Toybox `0.8.9-android` accepte `toybox sha256sum` : le calcul de `printf AVM31` sur stdin s’est terminé avec le code `0`. L’aide de `toybox mv` expose l’option `-n`; son comportement sans remplacement n’a pas été exercé sur des fichiers.
- L’aide locale confirme les commandes `devices -l`, `push` et `shell`. `adb push` expose notamment `--sync` et `-n`; `--sync` ne compare que les horodatages et ne convient pas à l’identité de contenu requise.
- La stabilité du numéro de série après déconnexion/reconnexion et l’état `unauthorized` / `offline` restent non vérifiés. Les commandes distantes exécutées étaient des lectures de propriétés, de métadonnées de répertoire, d’espace et de capacité SHA-256; aucune écriture n’a été effectuée.
- Aucun téléchargement ni installation n’a été effectué.

Commandes de diagnostic exécutées : `adb version`, `adb devices -l`, `adb help`, `getprop`, `get-serialno`, `ls -ld`, `df -k` et un test SHA-256 sur stdin. Elles n’ont pas lancé de transfert ni écrit de fichier sur le téléphone.

## 2. Composants AVM réutilisables

- **Bibliothèque et pistes :** [library_page.py](../../../audio_video_manager/ui/sections/library_page.py) utilise `list_releases` puis `list_tracks_for_release`, affiche les pistes et signale les fichiers Windows manquants. Il n’existe pas encore d’action d’export Android.
- **Catalogue :** [catalog.py](../../../audio_video_manager/storage/catalog.py) lit les albums et les pistes. Chaque ligne `tracks` a un `id` SQLite, une clé unique `(release_id, number)`, un chemin source, un titre et un état `flac_ok`; `list_tracks_for_release` ne renvoie actuellement pas l’`id`.
- **Indexation des sources :** [archive_job.py](../../../audio_video_manager/orchestration/archive_job.py) inscrit dans `tracks.path` les chemins publiés retournés par `publish_album`. Ce sont les chemins des FLAC de la bibliothèque, et non les fichiers temporaires du rip. La publication gère déjà les collisions sans remplacement silencieux dans [publish.py](../../../audio_video_manager/library/publish.py).
- **Multidisques :** [path_preview.py](../../../audio_video_manager/metadata/path_preview.py) et [library-conventions.md](../../domain/library-conventions.md) placent les disques sous `Disc N`; AVM-30 confirme que chaque piste publiée est indexée avec son propre chemin et que la publication d’un disque utilise ce sous-dossier.
- **SQLite :** [database.py](../../../audio_video_manager/storage/database.py) fournit les connexions, transactions et migrations; [schema.py](../../../audio_video_manager/storage/schema.py) est à la version 5. La base par défaut est `%LOCALAPPDATA%\AudioVideoManager\avm.sqlite3`, définie dans [paths.py](../../../audio_video_manager/paths.py). `Database.initialize()` applique des migrations et écrit : il n’a pas été appelé pendant ce mandat.
- **Travail hors interface :** [thread_lifecycle.py](../../../audio_video_manager/ui/thread_lifecycle.py) et [archive_worker.py](../../../audio_video_manager/ui/archive_worker.py) montrent le patron `QObject`/`QThread`, signaux de progression/résultat/erreur et annulation coopérative. [cd_ripper.py](../../../audio_video_manager/extraction/cd_ripper.py) lance des arguments de processus séparés avec `Popen`, sans shell système. Ces patrons sont réutilisables; le worker d’export ne doit pas être greffé au moteur d’extraction.
- **Configuration et dépendances :** `pyproject.toml` ne déclare ni ADB ni bibliothèque ADB. L’intégration la plus limitée consiste à appeler le binaire ADB installé/détecté, sans installation automatique.

## 3. Faisabilité FLAC par USB

ADB sait pousser un fichier local vers un chemin du téléphone. Une copie binaire conserve le contenu FLAC et ses métadonnées sans conversion. Sur l’appareil observé, `/sdcard/Music` existe et le système annonce environ 175,6 Gio libres; `/sdcard/Music/AudioVideoManager/` n’existe pas encore. Son accessibilité en écriture et sa visibilité dans les lecteurs Android restent à vérifier.

Une fois l’appareil autorisé, AVM pourra créer les seuls sous-dossiers de son espace, puis envoyer les fichiers sélectionnés. L’export doit utiliser `adb -s <serial>` pour chaque appel; ne pas employer `adb sync`, qui concerne une synchronisation de répertoires et n’établit pas l’identité du contenu.

## 4. Historique SQLite minimal proposé

Ajouter une seule table dans une migration AVM v5 → v6, sans dupliquer les métadonnées de piste déjà présentes :

```sql
CREATE TABLE android_transfers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_serial TEXT NOT NULL,
    track_id INTEGER NOT NULL REFERENCES tracks(id) ON DELETE RESTRICT,
    source_path TEXT NOT NULL,
    source_sha256 TEXT NOT NULL,
    source_size_bytes INTEGER NOT NULL CHECK (source_size_bytes >= 0),
    destination_path TEXT NOT NULL,
    staging_path TEXT,
    status TEXT NOT NULL CHECK (status IN ('pending', 'succeeded', 'failed')),
    attempted_at TEXT NOT NULL,
    verified_at TEXT,
    error_summary TEXT,
    UNIQUE (device_serial, track_id, source_sha256)
);
```

`tracks.id` est l’identité durable locale déjà créée par AVM; `release_id + number` en est la clé métier alternative. L’interface de catalogue devra exposer `tracks.id` ou utiliser une requête d’export dédiée. Aucun identifiant de piste MusicBrainz n’est actuellement stocké dans `tracks`.

Le numéro de série ADB est la clé d’appareil; le modèle peut être affiché depuis `devices -l` sans le dupliquer dans chaque enregistrement. L’empreinte SHA-256 identifie la version source; le chemin et la taille servent à diagnostiquer et prévalider. `attempted_at` est mis à jour à chaque tentative et `verified_at` n’est rempli qu’après contrôle distant. Si conserver chaque tentative séparément devient une exigence, il faudra une décision distincte; ce modèle minimal conserve l’état courant par appareil, piste et version du FLAC.

## 5. Identification et disponibilité de l’appareil

- Interroger `adb devices -l` à la demande de l’utilisateur, puis sélectionner explicitement le numéro de série affiché. Persister ce numéro, pas `transport_id`, qui est un identifiant de transport et ne constitue pas l’identité durable recherchée.
- `device` signifie que la session ADB est disponible; `unauthorized` exige l’acceptation du dialogue de débogage sur le téléphone; `offline` signifie que la session n’est pas utilisable. Dans les deux derniers cas, suspendre toute opération et expliquer comment rétablir la connexion, sans basculer vers un autre appareil.
- L’appareil observé est à l’état `device`; la série ADB est cohérente entre `devices -l` et `get-serialno` pendant cette connexion. Sa stabilité après reconnexion n’est pas encore démontrée. Ne pas enregistrer un appareil non identifiable comme cible durable.

## 6. Comparaison des transferts

Pour l’appareil sélectionné, AVM parcourt uniquement les pistes publiées du catalogue :

1. Confirmer que le chemin source indexé existe, relever taille et SHA-256; une source absente ou illisible n’est pas sélectionnable.
2. Chercher un enregistrement pour `(device_serial, track_id, source_sha256)`.
3. Sans réussite correspondante, proposer la piste comme nouvelle (ou version source modifiée).
4. Pour une réussite connue seulement, vérifier le chemin Android enregistré. S’il existe, comparer taille et empreinte distante; seule une correspondance est affichée comme présente et vérifiée.
5. Si le chemin manque, proposer la piste à nouveau. Si le chemin existe mais diffère, signaler un conflit et ne pas le remplacer.

Aucun parcours du stockage Android n’est nécessaire : l’inspection distante porte uniquement sur les destinations conservées dans `android_transfers`. Les fichiers d’autres applications et les fichiers présents mais inconnus de l’historique AVM ne sont ni recensés ni adoptés automatiquement.

## 7. Collisions, transferts partiels et reprises

- Construire les noms depuis les chemins publiés déjà sûrs ou depuis des segments d’album/piste sanitizés; conserver artiste, album, disque (`Disc N`) et nom de piste. Refuser les segments vides, `.` / `..`, séparateurs, NUL et caractères de contrôle; ne jamais utiliser une métadonnée brute comme commande shell.
- Vérifier la destination finale juste avant publication. Si elle existe et n’est pas reconnue par une réussite AVM correspondant à l’empreinte, la traiter comme conflit. Pour une source modifiée, demander une destination alternative non collisionnelle (par exemple suffixe de version); ne pas remplacer l’ancien FLAC.
- Après confirmation explicite, enregistrer `pending`, puis pousser vers un chemin temporaire propre à cette tentative sous l’espace AVM. Vérifier taille et SHA-256 avant de promouvoir vers le chemin final avec une opération de renommage sans remplacement (à valider sur l’appareil). Vérifier de nouveau le chemin final avant de passer à `succeeded`.
- Après déconnexion, conserver l’état non réussi. À la reprise, contrôler le chemin final et le temporaire enregistrés : ne marquer réussi qu’un fichier complet dont la taille et l’empreinte correspondent. Si un temporaire est incomplet, ne pas l’écraser ni le supprimer; recommencer sous un nouveau nom temporaire unique et signaler l’ancien partiel comme élément à examiner.
- Une vérification distante par SHA-256 (`toybox sha256sum`) est préférable. Toybox `0.8.9-android` et le calcul sur stdin ont été vérifiés; la lecture d’un FLAC distant et la comparaison de son empreinte ne l’ont pas été. Toybox `mv` expose `-n`, mais le non-remplacement effectif n’a pas été testé. Si ces vérifications échouent sur un fichier réel, AVM doit garder le transfert non réussi/non vérifié plutôt que le déclarer réussi sur le seul code retour ou la seule existence.
- Toute nouvelle tentative est déclenchée par l’utilisateur, ciblée sur les éléments échoués/absents et précédée d’un nouveau contrôle d’état, de source et de destination. Aucune suppression de partiel n’est prévue.

## 8. Architecture technique minimale

- Un module de service d’export prépare la liste de pistes, contrôle empreintes/collisions et exécute des appels ADB argumentés; il reçoit le chemin de base de données existant et le numéro de série sélectionné.
- Un `AndroidExportWorker(QObject)` s’exécute via `attach_worker_thread`, ouvre sa propre connexion `Database` dans le thread, et émet progression, résultats par piste et erreurs. Il vérifie l’annulation et l’état ADB entre chaque fichier; il ne lance aucune commande avec `shell=True`.
- Les commandes distantes restent limitées à l’espace AVM : contrôle de répertoire/fichier, espace libre, création de sous-dossiers après confirmation, empreinte et promotion sans remplacement. Tous les appels ciblent explicitement le même numéro de série.
- Aucune détection automatique à la connexion, aucun service en arrière-plan, aucune synchronisation, MTP, Wi-Fi ou application Android.

## 9. Interface proposée

Ajouter une entrée explicite **Exporter vers Android** dans le parcours Bibliothèque, sans modifier l’extraction CD/DVD. À l’ouverture, bouton **Rechercher / actualiser les appareils** et état lisible (`aucun appareil`, `autorisation requise`, `hors ligne`, modèle et série partiellement masquée). Ne lancer aucune opération au branchement.

Pour l’appareil choisi, présenter les albums/pistes du catalogue avec états **nouveau**, **déjà vérifié**, **absent**, **source manquante**, **échec** ou **conflit**; permettre sélection album complet ou piste individuelle. Afficher nombre de fichiers, volume estimé depuis les tailles locales et espace disponible lorsque lisible. Avant écriture, récapituler appareil, destination et sélection, puis exiger une confirmation explicite.

Pendant l’envoi, afficher le fichier actif, un avancement global et des compteurs réussite/échec/ignorés. ADB ne fournit pas ici de progression binaire machine-lisible garantie par l’aide observée; l’avancement fiable minimal est par fichier/volume complété, avec le fichier en cours en état indéterminé. Terminer par un bilan consultable et permettre de relancer uniquement les échecs ou absences après nouvelle confirmation.

## 10. Risques et limites

**Validation physique partielle :** un téléphone autorisé et son stockage partagé sont accessibles en lecture. L’écriture dans `Music`, la création du dossier AVM, le hash d’un fichier copié, le renommage sans remplacement en situation réelle, les déconnexions et la découverte par un lecteur restent à valider. Aucun transfert n’a été autorisé ni exécuté.

**Limites acceptables :** ADB n’est pas dans `PATH`, mais son binaire est localisable dans le SDK; l’application peut demander un chemin explicite ou détecter ces emplacements sans installation. La capacité libre est une estimation susceptible de changer avant l’écriture; recontrôler avant le transfert et arrêter proprement si l’espace manque. Un modèle/manufacturer peut exposer un numéro de série absent ou non stable : dans ce cas, ne pas fusionner les historiques d’appareils.

Le succès de copie ne garantit pas que le lecteur audio installé accepte le FLAC, lise les tags comme prévu ou indexe immédiatement le fichier. Cela nécessite une validation de lecture sur le téléphone cible. Aucun élément ne démontre à ce stade une incompatibilité fondamentale d’ADB ou du format FLAC.

## 11. Plan d’implémentation limité (mandat ultérieur)

1. **Validation physique en lecture seule (partiellement réalisée) :** appareil `device`, modèle/API, série pendant la session, `/sdcard/Music`, espace libre et présence de Toybox SHA-256 observés. Restent la stabilité après reconnexion et la validation de la promotion sans remplacement. Critère : cible identifiable et contrôles distants suffisants.
2. **Historique et calcul de candidats :** ajouter une migration unique v6, exposer `tracks.id`, calculer les empreintes des seules sources sélectionnées et lister nouveau/absent/vérifié/conflit. Critère : aucun succès sans correspondance locale et distante; aucun parcours de la bibliothèque Android.
3. **Worker et copie confirmée :** implémenter staging unique, transfert séquentiel, vérification distante, promotion sans écrasement, état `pending` après interruption et reprise contrôlée. Critère : aucun fichier partiel/inconnu déclaré réussi ou remplacé.
4. **UI et validation réelle autorisée :** intégrer l’entrée manuelle, sélection, estimation, confirmation, progression et bilan; vérifier sur appareil les FLAC simples et multidisques, reconnexion, manque d’espace, collision et présence dans un lecteur compatible. Critère : aucune action au branchement et seuls les éléments confirmés sont envoyés.

## 12. Verdict

**FAISABLE SOUS RÉSERVES.** ADB est installé et un téléphone Motorola autorisé répond aux requêtes de lecture. Son numéro de série, modèle, version Android, dossier Music, espace libre et capacité de calcul SHA-256 sur stdin sont observés. AVM dispose d’un index SQLite des chemins FLAC, d’identifiants de piste locaux et d’un patron éprouvé de worker Qt. Un historique minimal peut référencer `tracks.id` et stocker l’empreinte source par numéro de série d’appareil.

La faisabilité opérationnelle reste **partiellement démontrée** : aucun octet n’a été écrit, les permissions d’écriture et le comportement de promotion sans remplacement sont inconnus, et aucun lecteur n’a été testé. Une autorisation explicite est nécessaire avant une éventuelle écriture ou un transfert d’essai. Aucun transfert, installation, test automatisé ni changement de code de production n’a été réalisé dans AVM-31.

**État du dépôt :** plusieurs modifications locales préexistantes, dont `main_window.py`, les chemins et le pipeline d’archive, ont été laissées intactes. Aucun commit ni push.