# 03 — Architecture de navigation et spécifications d’écrans

## 1. Structure cible (4 sections)

```text
┌──────────────────────────────────────────────────────────┐
│  AudioVideoManager          [état lecteur] [aide ?]      │
├────────────┬─────────────────────────────────────────────┤
│ Archiver   │  Contenu de la section active               │
│ un disque  │                                             │
│            │                                             │
│ Ma         │                                             │
│ bibliothèque│                                            │
│            │                                             │
│ Historique │                                             │
│            │                                             │
│ Paramètres │                                             │
└────────────┴─────────────────────────────────────────────┘
```

- Navigation latérale (ou onglets haut sur fenêtre étroite).
- Une section = un job mental.
- Pas de probes fre:ac en page d’accueil.

## 2. Section A — Archiver un disque

### Rôle
Parcours guidé unique pour importer un CD jusqu’à la bibliothèque.

### Sous-étapes (stepper horizontal)

| # | Étape UI | Backend | CTA principal |
|---|----------|---------|---------------|
| 1 | Disque détecté | lecteurs + TOC | Continuer / Relire |
| 2 | Identification | MB + ranker | Continuer / Changer d’édition |
| 3 | Vérifier & Approuver | validation + approve_sheet | Approuver la fiche |
| 4 | Extraire & publier | archive_job | Lancer l’archivage |
| 5 | Terminé | report | Ouvrir dossier / CD suivant |

### Informations par étape

**1 — Disque**
- Lecteur sélectionné (langage : « Lecteur CD D: »).
- Nombre de pistes, durée totale, Disc ID (secondaire, repliable « Détails techniques »).
- État : pas de disque / lecture / erreur libdiscid.

**2 — Identification**
- Pochette (image), titre, artiste, année, pays, label, catalogue.
- Badge confiance / avertissements (TOC partial, alternatives US/CA).
- Alternatives en panneau repliable (pas de combo obscure seule).

**3 — Vérifier & Approuver**
- Formulaire champs obligatoires manquants uniquement en premier plan.
- Table pistes éditable.
- Aperçu chemins zone C.
- Liste erreurs bloquantes vs avertissements (français actionnable).
- Boutons : Enregistrer brouillon · Approuver · Retour.

**4 — Extraire & publier**
- Rappel édition approuvée + politique doublon (Skip/Renommer/Remplacer) en langage clair.
- Case/confirmation « Publier dans ma bibliothèque ».
- Progression par sous-étapes nommées (Vérification disque → Extraction → Contrôle → Organisation → Publication).
- Annuler.

**5 — Terminé**
- Succès / succès avec avertissements / échec.
- Chemin album + bouton Ouvrir.
- Lien vers Historique du job.

### Transitions & garde-fous
- Impossible d’atteindre 4 sans `Approved`.
- Impossible de lancer 4 si Disc ID mismatch (message : « Ce n’est pas le même CD que la fiche approuvée »).
- Retour arrière : 4→3 invalide l’approbation ? **Proposition à valider (A3)** — défaut recommandé : retour 3 remet `Pending` avec avertissement.

## 3. Section B — Ma bibliothèque

### Rôle
Vue lecture de la zone C (et optionnel inbox B), sans lecteur audio intégré complexe.

### Contenu
- Racine bibliothèque (chemin + Changer… → Paramètres).
- Liste / grille albums (pochette si `cover.jpg`, artiste, album, année).
- Filtre recherche simple (artiste/album).
- Détail album : pistes (noms de fichiers), ouvrir dossier, statut import si connu SQLite.
- Badge inbox : « En attente de publication » si jobs `AwaitingPublishConfirmation`.

### Actions
- Ouvrir dans l’Explorateur.
- (Futur) Relancer publish depuis inbox — pas MVP si trop risqué.
- Pas de lecture FLAC in-app (hors scope).

### États
Vide / chargement / erreur chemin inaccessible / album sélectionné.

## 4. Section C — Historique

### Rôle
Traçabilité jobs (SQLite) : archive, test technique, échecs, reprises.

### Contenu
- Tableau : date, album/artiste (si connus), mode, état, Disc ID court, actions.
- Détail : warnings, library_path, workdir, checkpoints.
- Actions : Reprendre (si `Interrupted` et FLAC présents), Abandonner, Ouvrir workdir, Ouvrir album C.

### Protections
- Abandonner ≠ supprimer zone C.
- Reprendre rip fre:ac seulement si règles architecture (pas mid-piste magique).

## 5. Section D — Paramètres

### Groupes
1. **Bibliothèque** — `library_root`, politique doublon par défaut.
2. **Identification** — pays préféré (CA), rappel « départage, pas provenance ».
3. **Extraction** — freaccmd (avec assistant détection), compression FLAC, éjecter après.
4. **Avancé** (replié) — jobs_dir, logs, test technique, auto-approve grisé (D-015), probes fre:ac, schéma SQLite.

### Validations
- Chemins existants / créables ; freaccmd fichier ; pays code 2 lettres.

## 6. Composants transverses

| Composant | Usage |
|-----------|--------|
| `StatusPill` | Pending / Approved / Erreur / En cours |
| `StepHeader` | Titre étape + 1 phrase d’aide |
| `CoverThumb` | 120–160 px, placeholder si absent |
| `WarningList` | Avertissements non bloquants |
| `ErrorList` | Bloquants + suggestion |
| `PathPreviewList` | Chemins C monospace court |
| `ConfirmDialog` | Texte court + conséquence |

## 7. Messages (principes)

- Français courant ; jargon en « Détails techniques ».
- Toujours : **quoi** / **pourquoi** / **que faire**.
- Exemple : « Il manque le type d’album (compilation ou non). Cochez l’option puis Approuver. »
