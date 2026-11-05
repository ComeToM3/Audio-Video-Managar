# 04 — Wireframes structurés et hiérarchie visuelle

Référence visuelle : [../05-systeme-visuel.md](../05-systeme-visuel.md).  
Densité : une colonne principale wizard ≤ 720 px centrée dans le panneau droit.

---

## Layout shell

```text
+---------------------------------------------------------------+
| AudioVideoManager 0.5.x     ● CD détecté · 17 pistes    Aide  |
+----------+----------------------------------------------------+
| Archiver*|  [1●][2][3][4][5]   titre d’étape                  |
| Biblio   |  -----------------------------------------------   |
| Histor.  |  |                                             |   |
| Param.   |  |         contenu étape (scroll)              |   |
|          |  |                                             |   |
|          |  -----------------------------------------------   |
|          |  [secondaire]                    [CTA primaire]    |
+----------+----------------------------------------------------+
```

**Hiérarchie :** 1) titre étape 2) contenu métier (cover/meta) 3) warnings 4) CTA.  
Debug / mono jamais au-dessus du CTA.

---

## W1

```text
Disque
« Confirmez le lecteur et le CD à archiver. »

Lecteur: [ ATAPI … (D:) ▼]

┌ état: CD détecté ─────────────────────┐
│ 17 pistes · environ 58 minutes        │
└───────────────────────────────────────┘

▸ Détails techniques

[Relire le disque]              [Continuer →]
```

---

## W2

```text
Identification
« Vérifiez l’édition proposée. »

+------+  Greatest Hits
|COVER |  Queen
|      |  1992 · Canada · Hollywood · CD 61265
+------+  {Proposition automatique}

Note: préférence pays = départage seulement.

⚠ Durée piste 17 : léger écart MusicBrainz (~3 s)

▸ Autres éditions (1)

[← Retour]     [Continuer →]
```

Cover : 140×140, pas d’overlay badge sur l’image (badge à côté).

---

## W3

```text
Vérifier et approuver
« Corrigez si besoin, puis approuvez explicitement. »

Compilation: ( ) Non  ( ) Oui     ← mis en avant si missing

Artiste album [____________]
Titre album   [____________]
…

Pistes (table)
Chemins futurs (liste mono courte)

Erreurs: …   Avertissements: …

[Enregistrer brouillon]  [← Retour]  [Approuver la fiche]
```

---

## W4

```text
Extraire et publier
« Le CD doit rester le même jusqu’à la fin. »

Récap: Queen — Greatest Hits (1992, CA)  {Approuvée}

Si l’album existe déjà:
  (•) Créer un dossier « import-2 »
  ( ) Ne pas publier
  ( ) Remplacer (corbeille locale)

[x] Publier dans ma bibliothèque

Progression (si lancé):
  ✓ Vérification du disque
  ► Extraction audio  ████░░  40%
  · Contrôle des fichiers
  …

[Annuler]                    [Lancer l’archivage]
```

---

## W5

```text
Terminé
{Succès}

Queen / Greatest Hits (1992)
17 fichiers FLAC + cover.jpg
Dossier: …\Queen\Greatest Hits (1992)

Avertissements: …

[Ouvrir le dossier]  [Historique]  [Archiver un autre CD]
```

---

## Bibliothèque

```text
Ma bibliothèque                    [Rafraîchir]
Dossier: C:\…\Music\AVM-Library

[Rechercher…………]

[cover] Queen — Greatest Hits (1992)     17 pistes
[cover] …                                {Dossier manquant}

Détail → liste fichiers · [Ouvrir le dossier]
```

---

## Dimensions adaptatives

| Zone | Règle |
|------|--------|
| Nav | 200 px (≥1100), 160 px (≥900), tabs &lt;900 |
| Cover | 140 px fixe wizard ; 64 px liste biblio |
| Table pistes | stretch ; colonnes # 40 / titre * / artiste 160 / durée 70 |
| Stepper | wrap labels si étroit (numéros seuls + tooltip) |

## Accessibilité (rappel spec)

- Focus ring accent ; tab order = flux CTA.
- Erreurs associées au champ (`setBuddy` / accessible name).
- Ne pas reposer sur la seule couleur des badges.
