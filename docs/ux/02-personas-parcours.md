# 02 — Profils, exigences et parcours

## 1. Profils d’utilisation

### P1 — Collectionneur prudent (primaire)
- Possède des CD originaux ; veut une archive FLAC fidèle et bien nommée.
- Peu à l’aise avec fre:ac / Disc ID / SQLite.
- Accepte de vérifier l’édition (pays, catalogue) une fois, clairement.
- Veut retrouver les fichiers dans l’Explorateur Windows / VLC / téléphone.

### P2 — Archiviste technique (secondaire)
- Comprend TOC, MB, collisions Replace.
- Veut logs, reprise de job, test zone A, réglages fins.
- Accède aux fonctions avancées **sans** polluer le parcours P1.

### P3 — Futur usage DVD (hors MVP UI)
- Même besoin d’identification + qualité + organisation.
- Extractions et modèles différents — **ne pas mélanger** dans le wizard CD.

## 2. Exigences essentielles (utilisateur)

| ID | Exigence | Source |
|----|----------|--------|
| U-01 | Voir clairement « qu’est-ce que je fais maintenant » | Audit |
| U-02 | Archiver un CD en &lt; N étapes guidées avec validations | Produit |
| U-03 | Comprendre l’édition choisie (pochette, pays, cat.) avant Approuver | D-011 |
| U-04 | Savoir où vont les fichiers (aperçu + ouverture dossier) | D-005 |
| U-05 | Ne jamais perdre un album déjà en bibliothèque (doublons explicites) | D-009 |
| U-06 | Corriger une erreur sans recommencer tout le jargon | UX |
| U-07 | Consulter ce qui a déjà été importé | Manquant |
| U-08 | Régler bibliothèque / lecteur / préférence pays hors du flux principal | UX |
| U-09 | Fichiers utilisables hors app | Fondements |
| U-10 | Mode test clairement séparé et non dominant | D-013 |

## 3. Parcours complet — Archiver un CD (cible)

```text
[Idle] Insérer CD
   → Détection lecteur + présence disque
   → Lecture TOC (pistes/durées mesurées)
   → Identification MB (+ sélection intelligente)
   → Revue édition (pochette, avertissements TOC)
   → Corrections si besoin
   → Aperçu chemins bibliothèque
   → Approuver la fiche                    ← GATE (inchangée)
   → Confirmation « Extraire et publier »
   → Match Disc ID (si échec → stop clair)
   → Extraction FLAC
   → Vérification intégrité
   → Tags + pochette
   → Inbox puis publication C (politique doublon)
   → Résumé succès + Ouvrir le dossier album
   → Prêt pour le CD suivant
```

**Points d’arrêt utilisateur :** revue édition, Approuver, confirmation publish, résolution doublon, erreur Disc ID.

## 4. Parcours secondaires

| Parcours | But | Entrée |
|----------|-----|--------|
| Corriger fiche avant Approuver | Fix champs | Étape revue |
| Changer d’édition MB | Réédition | Liste alternatives (repliable) |
| Publier plus tard | Job en attente confirmation | Historique |
| Reprendre / abandonner job | Interruption | Historique |
| Test technique | Valider fre:ac seulement | Paramètres → Avancé |
| Explorer bibliothèque | Vérifier album | Ma bibliothèque |

## 5. CD existant vs DVD futur

| Sujet | CD (maintenant) | DVD (plus tard, D-010) |
|-------|-----------------|------------------------|
| Support | Audio CD Red Book | DVD-Video / DVD-Audio |
| Identité | TOC + Disc ID | Title/stream — modèle distinct |
| Extraction | freaccmd → FLAC | Outil dédié (non choisi) |
| Organisation | D-005 audio | Arborescence média à définir |
| UI | Section Archiver = **CD** | Même section avec sélecteur support **désactivé** ou onglet « Bientôt » |
| Gate meta | DiscMetadata audio | Extension format — pas dans MVP UI |

**Règle de conception :** le wizard parle « disque audio » / « CD ». Toute mention DVD = badge « Prévu » sans parcours actif.
