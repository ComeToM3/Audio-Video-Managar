# 04 — Wireframes textuels

Légende : `[bouton]` · `(champ)` · `{badge}` · `« texte »` · `···` zone scroll.

---

## W0 — Coquille application

```text
+------------------------------------------------------------------+
| AudioVideoManager 0.5+          Lecteur D: · CD détecté    [?]   |
+--------------+---------------------------------------------------+
| * Archiver   |                                                   |
|   un disque  |               (contenu section)                   |
|              |                                                   |
|   Ma biblio  |                                                   |
|              |                                                   |
|   Historique |                                                   |
|              |                                                   |
|   Paramètres |                                                   |
+--------------+---------------------------------------------------+
```

---

## W1 — Archiver · Étape 1 Disque

```text
Étapes:  [1 Disque]——2 Identif.——3 Approuver——4 Archiver——5 Fin

« Insérez un CD audio, puis continuez. »

Lecteur: [ ATAPI iHAS324 (D:) ▼ ]

{CD détecté}  17 pistes · ≈ 58 min

[ Relire le disque ]              [ Continuer → ]

── Détails techniques (replié) ──
Disc ID: DsXl…  TOC offsets…
```

---

## W2 — Archiver · Étape 2 Identification

```text
Étapes:  1——[2 Identification]——3——4——5

+--------+  Greatest Hits
| COVER  |  Queen
|        |  1992 · Canada · Hollywood · CD 61265
+--------+  {Sélection automatique · préférence pays CA}

« Édition proposée. Ce n’est pas une preuve du pressage exact :
  vérifiez catalogue / pochette physique si besoin. »

Avertissement:
• Durée piste 17 légèrement différente de MusicBrainz (~3 s)
  → on conserve l’écart (pas forcé « exact »).

[ Voir les autres éditions ▾ ]     (US 1991 · HR 61265-2 …)

[ ← Retour ]     [ Choisir une autre ]     [ Continuer → ]
```

---

## W3 — Archiver · Étape 3 Approuver

```text
Étapes:  1——2——[3 Vérifier & Approuver]——4——5

Titre album   (Greatest Hits)
Artiste album (Queen)
Année         (1992)
Compilation   [ ] Non  [ ] Oui     {requis}
…

Pistes
#  Titre                 Artiste      Durée
01 We Will Rock You      Queen        2:02
…

Chemins dans la bibliothèque
  Queen/Greatest Hits (1992)/01 - We Will Rock You.flac
  …
  Queen/Greatest Hits (1992)/cover.jpg

Erreurs: (aucune) | Avertissements: TOC piste 17…

[ Enregistrer brouillon ]  [ ← Retour ]  [ Approuver la fiche ]
```

---

## W4 — Archiver · Étape 4 Lancement

```text
Étapes:  1——2——3——[4 Extraire & publier]——5

Fiche approuvée: Queen — Greatest Hits (1992, CA) {Approved}

Si cet album existe déjà:
  (•) Créer un dossier « import-2 »
  ( ) Ne pas publier (garder l’existant)
  ( ) Remplacer (ancien déplacé vers corbeille locale)

[x] Publier dans ma bibliothèque après extraction

« Le CD doit rester le même que celui de la fiche. »

[ ← Retour ]                    [ Lancer l’archivage ]
```

---

## W5 — Archiver · Progression

```text
Étapes:  1——2——3——[4 …]——5

  ✓ Vérification du disque
  ► Extraction audio (piste 4/17)     ████████░░░░  45%
  · Contrôle des fichiers
  · Organisation & publication

[ Annuler ]
```

---

## W6 — Archiver · Terminé

```text
Étapes:  1——2——3——4——[5 Terminé]

{Succès}  Album ajouté à la bibliothèque

  Queen / Greatest Hits (1992)
  17 fichiers FLAC + cover.jpg

  Avertissements conservés: TOC piste 17…

[ Ouvrir le dossier ]  [ Voir dans Historique ]  [ Archiver un autre CD ]
```

---

## W7 — Ma bibliothèque

```text
Ma bibliothèque — C:\Users\…\Music\AVM-Library          [Changer…]

(Rechercher artiste ou album________)  [🔍]

+------+  Queen — Greatest Hits (1992)
| cover|  17 pistes · importé 2026-11-03
+------+
+------+  …
```

Détail:

```text
← Liste

[cover] Greatest Hits · Queen · 1992
[ Ouvrir le dossier ]

01 We Will Rock You.flac
02 …
```

---

## W8 — Historique

```text
Date        Album / job     Mode      État
2026-11-03  Greatest Hits   Archive   Completed
2026-11-02  (job abc…)      Test      CompletedTechnical

Sélection → détails warnings · [Ouvrir album] [Workdir] [Reprendre?]
```

---

## W9 — Paramètres (extrait)

```text
Bibliothèque
  Dossier: (……………………) […]
  Doublons par défaut: [Renommer ▼]

Identification
  Pays préféré pour départage: (CA)
  « N’indique pas le pays réel du pressage. »

Extraction
  fre:ac: détecté ✓ / chemin […]
  Compression FLAC: [5]

▸ Avancé
  Test technique zone A… | Dossiers jobs/logs | Probes
```
