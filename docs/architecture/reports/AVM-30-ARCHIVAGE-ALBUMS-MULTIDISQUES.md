# AVM-30 — Archivage d’albums multidisques

**Verdict : PARTIEL — cause confirmée et gate corrigée; CD2 n’a pas encore été extrait physiquement.**

## Cause démontrée

La release MusicBrainz unique « Bee Gees — Greatest » (`2da82468-7997-368e-8424-c2b5f91ecd1f`) est correctement associée à deux Disc IDs : CD1 (`uy1acux0II6bvUj3APXMrKiiVy8-`) et CD2 (`MBbYin6VMJ_ZwxzOzVSmma5n1Gg-`). SQLite réel contient la publication CD1 avec 10 pistes sous `.../Greatest (1984)/Disc 1` et deux fiches approuvées CD2 en position 2/2; aucun job ni répertoire publié CD2 n’existe.

`assess_duplicates` traitait le même MBID comme doublon avant de considérer le Disc ID différent et le chemin `Disc 1`. Il produisait donc `REQUIRE_CONFIRM` pour CD2. Ce n’était ni une erreur de sélection du medium ni une collision de noms de pistes.

## Correction

La gate reçoit maintenant `disc_number`/`disc_total` depuis la fiche. Si l’album est multidisque et que le chemin déjà publié encode `Disc N` différent du disque entrant, ce MBID partagé n’est pas assimilé à un doublon. Le même Disc ID reste bloqué comme réinsertion; une position absente, un chemin legacy sans numéro ou le même numéro conserve la confirmation existante. Aucun schéma SQLite ni migration n’est nécessaire.

Le générateur de chemins existant produit déjà `Artiste/Album (Année)/Disc N/NN - Titre.flac`; les tags écrivent `DISCNUMBER`/`DISCTOTAL`, et la publication vérifie les collisions à l’intérieur du dossier du disque. CD2 vise donc `.../Disc 2`, tandis que CD1 et sa pochette restent intacts. La ligne SQLite de chaque publication garde son Disc ID propre et le MBID commun.

## Vérification

- Inspection réelle en lecture seule : bibliothèque contient `Disc 1`, 10 FLAC et `cover.jpg`; `Disc 2` est absent. Fiches SQLite réelles CD1 1/2 et CD2 2/2; aucun job CD2.
- Appel de la gate existante sur les fiches SQLite réelles avec connexion `query_only` : CD2 → `ALLOW`, sans hit; CD1 réinséré → `REQUIRE_CONFIRM`, hit `DISC_AND_EDITION`.
- Tests ciblés `test_duplicates_06k.py` + `test_archive_pipeline.py` : **25 réussis**, incluant l’autre medium même MBID, le même Disc ID et la publication; aucun rip réel.
- Aucun FLAC, dossier, job, configuration ou enregistrement SQLite réel n’a été modifié; aucune extraction lancée. Pas de CI complète (modification localisée à la gate doublons).

## Limite et étape utilisateur

L’application Windows n’a pas été utilisée pour lancer CD2, et la publication physique CD2/visibilité dans Widgets n’est donc pas démontrée. La validation proposée est : insérer le vrai CD2, vérifier la fiche « Disque 2 sur 2 » et la destination `Disc 2`, puis cliquer « Continuer »; arrêter à l’écran « Extraire » et confirmer que l’alerte de réarchivage a disparu. Le bouton « Extraire » ne doit être utilisé qu’après votre autorisation explicite. Réinsérer CD1 doit toujours déclencher la confirmation de doublon.

**Aucun fichier existant déplacé/écrasé, aucun commit ni push.**