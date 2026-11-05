# 06 — Matrice fonctionnelle

Légende statut : **E** existant backend · **U** UI à adapter · **M** manquant · **F** futur · **X** superflu (ne pas faire)

## 1. Essentiel MVP UI (AVM-06B proposé)

| Fonction | Classe | Statut | Notes |
|----------|--------|--------|-------|
| Nav 4 sections | Essentiel | M | Coquille |
| Wizard archivage 5 étapes | Essentiel | M/U | Orchestre capacités E |
| Détection lecteur + TOC | Essentiel | E+U | Clarifier libellés |
| Identification MB + smart CA | Essentiel | E+U | Pochette visuelle |
| Corrections + Approuver | Essentiel | E+U | Messages FR |
| Aperçu chemins C | Essentiel | E+U | Dans étape 3 |
| Match Disc ID avant rip | Essentiel | E+U | Message humain |
| Archive publish confirmé | Essentiel | E+U | Étape 4 |
| Progression étapes nommées | Essentiel | U | Worker déjà async |
| Résumé + ouvrir dossier | Essentiel | M | Fin wizard |
| Ma bibliothèque (liste FS/SQLite) | Essentiel | M | Lecture |
| Historique jobs | Essentiel | M | SQLite déjà là |
| Paramètres regroupés | Essentiel | U | Sortir du main |
| Doublons langage clair | Essentiel | U | Skip/Rename/Replace |
| Test technique | Essentiel (avancé) | E+U | En Paramètres ▸ Avancé seulement |

## 2. Futur (ne pas implémenter dans 06B)

| Fonction | Classe | Notes |
|----------|--------|-------|
| DVD detect/extract | F | D-010 — placeholder UI optionnel « Bientôt » |
| AccurateRip / F-08b fort | F | |
| Auto-approve haute confiance | F | D-015 OFF |
| Reprise mid-piste fre:ac | F | Limite outil |
| Multi-lecteurs parallèles | F | |
| Sync cloud / streaming | X/F | Hors principes |
| Lecteur audio in-app riche | X | Ouvrir dossier suffit |
| Éditeur tags batch hors import | F | |
| Sidecar JSON | F | D-007 reporté |

## 3. Superflu / à retirer du parcours principal

| Élément actuel | Décision conception |
|----------------|---------------------|
| Probes fre:ac toujours visibles | → Avancé seulement |
| Schéma SQLite en page d’accueil | → Avancé / À propos |
| Auto-approve checkbox visible désactivée | → Avancé + texte « non disponible » |
| Log technique plein écran | → Panneau « Journal » repliable pendant archive |
| Terminologie DiscMetadata dans titres | → « Fiche du disque » |

## 4. Mapping écrans → modules code (sans changer les règles)

| UI cible | Modules existants |
|----------|-------------------|
| Étape 1–2 | `toc_reader`, `apply_lookup`, `edition_ranker`, `cover_art` |
| Étape 3 | `validation`, `path_preview`, `repository` |
| Étape 4–5 | `archive_job`, `ArchiveWorker`, `publish` |
| Bibliothèque | `releases` SQLite + scan `library_root` (nouveau mince) |
| Historique | table `jobs` (+ checkpoints) |
| Paramètres | `AppConfig` |

**Aucune règle métier D-011…D-015 à assouplir pour l’UI.**
