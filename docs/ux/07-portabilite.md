# 07 — Portabilité et réutilisation des fichiers

## 1. Objectif

Une archive réussie doit rester **compréhensible et jouable** si AudioVideoManager est désinstallé.

## 2. Contrat fichier (déjà en décisions — à rendre visible dans l’UI)

| Élément | Emplacement | Consommateur typique |
|---------|-------------|----------------------|
| Audio | `.flac` | VLC, Foobar, lecteurs téléphone (selon sync) |
| Tags | Vorbis comments dans chaque FLAC | Tous lecteurs compatibles FLAC |
| Pochette | Embarquée + `cover.jpg` dossier album | Explorateur, lecteurs |
| Organisation | `Artiste/Album (Année)/NN - Titre.flac` | Humain + sync dossiers |
| Identifiants | `MUSICBRAINZ_*` si connus | Picard, outils MB |

## 3. Exigences UX liées à la portabilité

1. **Aperçu des chemins** avant Approuver (déjà) — formuler : « Ainsi, vos fichiers seront rangés même sans cette application. »
2. **Écran Terminé** : rappel « Ces FLAC s’ouvrent dans n’importe quel lecteur compatible. »
3. **Ma bibliothèque** : action dominante = Ouvrir le dossier (pas « Lire dans AVM »).
4. **Pas de format propriétaire** ni base obligatoire pour jouer.
5. SQLite = index de **l’app** ; la source de vérité collection = le disque.

## 4. Classement durable (rappel UI)

- Compilations → artiste d’album explicite (souvent Various Artists).
- Multi-disques → sous-dossier `Disc N`.
- Caractères Windows sanitisés (déjà).
- Doublons : jamais d’écrasement silencieux — expliquer Replace = corbeille locale `.avm-trash`.

## 5. Hors app — non-objectifs

- DRM, comptes cloud, bibliothèque propriétaire verrouillée.
- Dépendance à un service MusicBrainz après import (IDs optionnels dans tags).
