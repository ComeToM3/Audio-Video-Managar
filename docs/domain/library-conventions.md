# Conventions bibliothèque — préparation phases organisation

Aligné **AVM-02B** (D-011…D-012). Fiche disque : [disc-metadata.md](disc-metadata.md).  
Décisions : D-005, D-006, D-007, D-009, D-011, D-012.

**Principe :** en mode archive, la fiche est **approuvée avant** le rip ; les chemins zone C sont prévisualisés à l’approbation. Aucun nom générique en zone C.

## 1. Zones de stockage (séparation stricte)

| Zone | Rôle | Exemple de chemin | Règles |
|------|------|-------------------|--------|
| **A — Jobs / temp** | Sortie brute freaccmd, logs job, partiels | `%LOCALAPPDATA%/AudioVideoManager/jobs/{job_id}/rip/` | Jamais la bibliothèque définitive. Un job = un dossier neuf. Pas d’écrasement si non vide. |
| **B — À valider (inbox)** | Albums candidats après rip + tags | `{library_root}/_inbox/{job_id}/` | Toujours remplie par le pipeline AVM-05. **Pas** de publication auto vers C. |
| **C — Bibliothèque définitive** | Collection organisée | `{library_root}/{AlbumArtist}/…` | Uniquement après validation explicite (intégrité + métadonnées + confirmation utilisateur). |

Flux archive (après gate métadonnées) :

```text
CD → TOC → DiscMetadata → AwaitingMetadataApproval (aperçu chemins C)
   → [A] job/rip/*.flac
   → F-08a / F-08b
   → [B] _inbox (optionnel)
   → publish explicite
   → [C] arborescence D-005
```

Mode test technique : CD → confirm test → [A] seulement (pas B/C).

**Interdit :** freaccmd → C direct ; publier incomplet / non approuvé ; placeholders en C ; écrasement silencieux (D-009).

## 2. Motif de fichiers (D-005)

```text
{AlbumArtist}/{Album} ({Year})/{NN} - {Title}.flac
cover.jpg
```

| Élément | Règle |
|---------|--------|
| `AlbumArtist` | Artiste d’album ; compilations → `Various Artists` (ou équivalent MB). |
| `Album` | Titre d’album sanitizé Windows. |
| `Year` | Année de sortie si connue ; **omise** (pas de `()` vides) si inconnue → `{Album}/`. |
| `NN` | Numéro de piste sur 2 chiffres (`01`, `02`…). |
| `Title` | Titre de piste sanitizé. |
| Placeholders | **Interdits** en fiche `Approved` et en zone C (D-012). Uniquement brouillon UI non approuvé, jamais publiés. |

### Compilations

- `AlbumArtist` = `Various Artists` (ou tag MB `albumartist`).
- Pistes : conserver l’artiste de piste dans les tags (phase 2) ; le chemin reste sous `Various Artists/{Album}…` sauf décision contraire ultérieure.

### Coffrets / multi-disques

```text
{AlbumArtist}/{Album} ({Year})/Disc {D}/{NN} - {Title}.flac
```

ou, si un seul dossier album est préféré plus tard :

```text
…/{NN} - {Title}.flac  avec tag discnumber
```

**Tranché** : sous-dossier `Disc {N}` si `disc_total > 1` (voir `path_preview` / `library.paths`).

## 3. Pochettes (D-006)

- `cover.jpg` (ou `.png` si source CAA) dans le dossier album.
- Art **embarqué** dans chaque FLAC (phase 2+, mutagen).
- Ne pas bloquer la publication définitive uniquement pour pochette manquante : statut `CompletedWithWarnings` possible.

## 4. Tags MusicBrainz (AVM-05 — mutagen)

Vorbis Comment écrits depuis la fiche **approuvée** : `ARTIST`, `ALBUMARTIST`, `ALBUM`, `TITLE`, `TRACKNUMBER`/`TRACKTOTAL`, `DISCNUMBER`/`DISCTOTAL`, `DATE`/`YEAR`, `LABEL`, `CATALOGNUMBER`, `BARCODE`, `MUSICBRAINZ_*`.  
Art embarqué + `cover.jpg`. Pas de valeurs inventées ; publish C uniquement après confirmation UI.

## 5. Caractères Windows et collisions

Caractères interdits dans les segments de chemin : `< > : " / \ | ? *` et contrôles.  
Remplacement proposé : `_` ou suppression ; trim espaces / points finaux (contrainte Windows).  
Longueur : viser &lt; 240 caractères par chemin complet ; raccourcir `Album`/`Title` si besoin.

Collisions (même chemin cible) :

1. **Skip** — ne rien écrire.
2. **Rename** — suffixe ` [import-2]`, ` [import-3]`, …
3. **Replace** — staging → vérif → swap → trash locale (jamais unlink direct de C).

Jamais d’écrasement silencieux (D-009).

## 6. Critères avant entrée en bibliothèque définitive (C)

Tous requis :

1. Job terminé sans annulation.
2. Nombre de fichiers FLAC = nombre de pistes audio attendues (TOC), sauf justification documentée (piste data, HTOA reporté).
3. **F-08a** OK sur chaque piste.
4. **F-08b** au moins `weak_ok` ou `weak_warn` explicitement accepté par l’utilisateur (ce n’est **pas** AccurateRip).
5. Fiche `DiscMetadata` **Approved** (D-011) — aucun placeholder (D-012).
6. Confirmation utilisateur « Publier vers la bibliothèque ».

Un album **incomplet**, **non approuvé** ou **non vérifié** reste en A ou B ; il n’est ni supprimé automatiquement ni publié vers C.

## 7. Lien avec le rip technique AVM-02

Tout rip sans gate métadonnées = **mode test technique** (zone A uniquement).  
`library_root` n’est pas modifié par ce mode.
