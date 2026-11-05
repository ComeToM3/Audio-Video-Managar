# 02 — Wizard Archiver (5 étapes)

## 1. Vue d’ensemble

```text
[1 Disque] → [2 Identification] → [3 Approbation] → [4 Extraction / publication] → [5 Terminé]
```

Stepper toujours visible en haut de la section Archiver.  
Étapes futures grisées ; complétées = coche ; courante = accent.

## 2. Préconditions globales

- Mode = archive normale (pas test technique).
- Langue UI FR (A10).
- Aucune auto-approbation (D-015 / A9).

## 3. Règles de navigation stepper

| Transition | Condition |
|------------|-----------|
| 1 → 2 | TOC lue avec succès (Disc ID + pistes) |
| 2 → 3 | Au moins une édition sélectionnée **ou** saisie manuelle amorcée ; pas d’erreur fatale MB bloquante (offline → manuel OK) |
| 3 → 4 | `approval == Approved` **et** validation OK |
| 4 → 5 | Job terminé (succès, succès+warnings, échec, annulé) |
| Retour i → i−1 | Autorisé sauf pendant rip actif ; **A3** : ne révoque pas seul |
| Saut avant | Interdit (pas de clic étape 4 depuis 1) |

## 4. Étape 1 — Disque

**But :** confirmer lecteur + présence CD + TOC mesurée.

| Élément | Détail |
|---------|--------|
| Infos | Lecteur, N pistes, durée totale estimée |
| Actions | Relire le disque · Continuer |
| Détails techniques (replié) | Disc ID, offsets |
| Vide | « Insérez un CD audio dans le lecteur. » |
| Chargement | « Lecture de la table des matières… » |
| Erreur | libdiscid / pas de disque — message + Relire |

## 5. Étape 2 — Identification

**But :** proposer l’édition (smart select CA) + pochette ; permettre autre choix.

| Élément | Détail |
|---------|--------|
| Infos | Cover 120–160 px, titre, artiste, année, pays, label, catalogue, avertissements TOC |
| Texte légal produit | « La préférence pays sert au départage, pas de preuve de provenance. » |
| Actions | Continuer · Voir autres éditions · Continuer en saisie manuelle (si 0 résultat) |
| Chargement | « Recherche MusicBrainz… » (rate-limit possible → patience) |
| Erreur réseau | Continuer hors ligne / réessayer |

Sélection d’une autre édition → marque fiche dirty si déjà Approved (A3).

## 6. Étape 3 — Approbation

**But :** corriger, valider, **Approuver** explicitement (D-011).

| Élément | Détail |
|---------|--------|
| Infos | Champs obligatoires en premier ; pistes ; aperçu chemins C ; erreurs / warnings |
| Actions | Enregistrer brouillon · Approuver la fiche · Retour |
| Bloquant Approuver | Erreurs validation (placeholders, TOC, compilation missing, etc.) |
| Après Approuver | Badge « Approuvée » ; CTA « Continuer vers l’extraction » |

Dirty après Approuver → badge « Modifications non approuvées » + Approuver de nouveau.

## 7. Étape 4 — Extraction / publication

**But :** confirmer publish + politique doublon + lancer `run_archive_job`.

| Élément | Détail |
|---------|--------|
| Infos | Rappel édition Approved ; chemins cibles ; politique doublon |
| Obligatoire | Confirmation explicite « Publier dans ma bibliothèque » (case ou dialog) |
| Progression | Sous-étapes nommées (voir matrice états) |
| Actions | Lancer · Annuler |

Garde-fous au lancement :
1. `assert_can_start_archive_rip`
2. Match Disc ID (sinon stop FR clair)
3. `confirm_publish=True` seulement si confirmé UI

## 8. Étape 5 — Terminé

**But :** comprendre le résultat et enchaîner.

| Résultat | Affichage |
|----------|-----------|
| Succès | Chemin album · Ouvrir dossier · Archiver un autre CD · Voir Historique |
| Succès + warnings | Idem + liste courte warnings (TOC, pochette unavailable…) |
| Échec / annulé | Cause · Workdir / inbox si utile · Réessayer / Historique |

« Archiver un autre CD » → reset wizard étape 1 (nouvelle session fiche).

## 9. Affichage progressif (anti-surcharge)

| Toujours visible | Sur demande / secondaire |
|------------------|---------------------------|
| Titre, artiste, année, pays, cover | Disc ID, offsets, MBID |
| Warnings actionnables (max 5 + « et N autres ») | Score TOC technique brut |
| Chemins C (aperçu) | Journal fre:ac complet |
| Sous-étapes progression | stdout/stderr |

## 10. Vérifications sans surcharge

| Contrôle | Où l’afficher |
|----------|----------------|
| Métadonnées cohérentes | Étape 3 erreurs/warnings |
| Pochette | Étape 2 image ; étape 4/5 si unavailable |
| FLAC / F-08a | Progression étape 4 « Contrôle des fichiers » |
| Collisions | Étape 4 choix doublon (libellés FR) |
| Destination | Aperçu 3 + rappel 4 + ouvrir 5 |
