# Fiche disque (`DiscMetadata`) — gate avant extraction

Spécification **AVM-02B** ; gate code **AVM-03** ; identification MB/CAA **AVM-04** (`audio_video_manager.metadata`).

**Règle produit :** en **mode normal**, aucune extraction ne démarre sans fiche **complète**, **cohérente** (notamment vs TOC) et **explicitement approuvée**.  
Aucun champ inventé ; aucun nom générique (`Unknown Artist`, etc.) publié en bibliothèque définitive (zone C).

---

## 1. Statuts de confiance (par champ ou par groupe)

| Statut | Signification | Peut servir à l’approbation ? |
|--------|---------------|------------------------------|
| `confirmed` | Saisi ou choisi par l’utilisateur, ou unique match MB accepté | Oui |
| `ambiguous` | Plusieurs candidats / conflit non tranché | **Non** — correction obligatoire |
| `missing` | Absent, pas encore recherché ou non renseigné | **Non** si le champ est obligatoire |
| `unavailable` | Recherche faite ; vérifié comme indisponible (ex. pas de pochette CAA, pas d’entrée MB) | Oui **seulement** si le champ est optionnel **ou** si une alternative manuelle `confirmed` le remplace |

Une fiche n’est approuvable que si **tous les champs obligatoires** sont `confirmed` (ou `unavailable` là où explicitement autorisé — voir §3).

---

## 2. Modèle `DiscMetadata`

Hiérarchie : **Release (édition)** → **Disc (support physique)** → **Track[]**.

### 2.1 Release / édition exacte

| Champ | Type | Obligatoire mode normal | Notes |
|-------|------|-------------------------|--------|
| `album_title` | str | Oui | Titre de l’album / release. |
| `album_artist` | str | Oui | Artiste d’album ; compilations : valeur réelle (souvent « Various Artists ») **confirmée**, jamais placeholder publié. |
| `sort_album_artist` | str? | Non | Optionnel. |
| `year` | int? | Oui* | Année de **l’édition** archivée si connue ; sinon `unavailable` + justification textuelle courte **ou** année `confirmed` minimale acceptée par l’utilisateur. |
| `label` | str? | Non† | Label de l’édition. |
| `catalog_number` | str? | Non† | N° catalogue. |
| `country` | str? | Non† | Pays d’édition (code ou libellé). |
| `barcode` | str? | Non | UPC/EAN si connu. |
| `edition_notes` | str? | Non | Réédition, remaster, club edition, etc. |
| `is_compilation` | bool | Oui | Doit être tranché (`confirmed`). |
| `is_reissue` | bool? | Non | Si vrai, édition originale vs présente à clarifier dans `edition_notes`. |
| `musicbrainz_release_id` | str? UUID | Non‡ | Si MB utiliséé. |
| `musicbrainz_release_group_id` | str? UUID | Non | |
| `cover_status` | enum | Oui | Voir pochettes. |
| `cover_path_or_url` | str? | Conditionnel | Fichier local ou URL CAA si `cover_status=confirmed`. |
| `field_trust` | map | Oui | Statut de confiance par champ clé. |

\* Année : obligatoire en pratique pour le motif D-005 ; si réellement inconnue → `unavailable` + l’utilisateur accepte un chemin **sans** `(Year)` (voir conventions), jamais une année inventée.  
† Fortement recommandés pour distinguer les rééditions ; exigibles si plusieurs éditions candidates (`ambiguous`).  
‡ Obligatoire dès qu’une source MB a été sélectionnée ; absent OK si fiche 100 % manuelle `confirmed`.

### 2.2 Disc (unité physique dans le lecteur)

| Champ | Type | Obligatoire | Notes |
|-------|------|-------------|--------|
| `disc_number` | int | Oui | 1…N dans le coffret / set. |
| `disc_total` | int | Oui | ≥ `disc_number`. |
| `disc_title` | str? | Non | Titre de face / disc subtitle. |
| `disc_id` | str? | Oui si calculable | MusicBrainz Disc ID (libdiscid) — `missing` tant que non lu ; bloquant pour lookup auto. |
| `toc` | object | Oui | Voir §2.4 — lu depuis le lecteur, **pas inventé**. |
| `medium_format` | enum | Oui | `audio_cd` (MVP) ; futurs : `dvd_video`, `dvd_audio`, … |
| `musicbrainz_disc_id` | str? | Alias / même que disc_id | |

### 2.3 Track

| Champ | Type | Obligatoire | Notes |
|-------|------|-------------|--------|
| `number` | int | Oui | Aligné TOC (1-based audio). |
| `title` | str | Oui | Titre `confirmed` ; pas de `Track 01` générique en mode normal. |
| `artist` | str | Oui | Artiste de piste (peut = album_artist). |
| `duration_ms` | int | Oui | Depuis TOC (référence) ; durée tag post-rip pour contrôle. |
| `isrc` | str? | Non | |
| `musicbrainz_recording_id` | str? | Non | |
| `musicbrainz_track_id` | str? | Non | |

### 2.4 TOC (source lecteur)

```text
TocSnapshot:
  first_track: int
  last_track: int
  track_offsets_sectors: list[int]   # ou équivalent
  track_durations_ms: list[int]      # dérivé, pour affichage / validation
  audio_track_count: int
  raw_source: str                    # ex. libdiscid / fre:ac — traçabilité
```

La TOC est **mesurée**, jamais complétée par des durées fictives.

### 2.5 Pochette

| `cover_status` | Signification |
|----------------|---------------|
| `confirmed` | Image choisie (CAA ou fichier local). |
| `unavailable` | Recherche faite, aucune pochette ; utilisateur accepte rip sans cover fichier (tags plus tard). |
| `missing` | Pas encore traité — **bloque** l’approbation. |
| `ambiguous` | Plusieurs images / releases — choix requis. |

### 2.6 Conteneur fiche

```text
DiscMetadata:
  schema_version: int
  mode: normal | technical_test
  approval: Pending | Approved | Rejected
  approved_at / approved_by_note
  release: …
  disc: …
  tracks: list[Track]
  toc: TocSnapshot
  path_preview: list[str]          # chemins relatifs zone C proposés
  validation_errors: list[str]
  validation_warnings: list[str]
```

---

## 3. Règles de validation (mode normal)

### 3.1 Complétude

- Tous les champs marqués obligatoires en §2 sont `confirmed`, sauf exceptions `unavailable` listées (année réellement inconnue, pochette introuvable après recherche).
- Aucun titre de piste / album / artiste égal à un placeholder interdit : `Unknown Artist`, `Unknown Album`, `Track N`, `Audio CD`, chaînes vides, `TBD`, etc.
- `approval == Approved` uniquement après action UI explicite **Approuver la fiche**.

### 3.2 Cohérence TOC

| Contrôle | Règle |
|----------|--------|
| Nombre de pistes | `len(tracks) == toc.audio_track_count` |
| Numéros | `tracks[i].number` = séquence audio TOC sans trou |
| Durées | `|tracks[i].duration_ms - toc.track_durations_ms[i]| ≤ tolérance` (ex. 500 ms) — sinon `ambiguous` / erreur |
| Disc ID | Si présent, compatible avec la TOC courante (recalcul) |

Échec → **pas d’approbation**, **pas de rip normal**.

### 3.3 Édition exacte / réédition

- Si plusieurs releases MB (ou manuelles) matchent le Disc ID → état `ambiguous` jusqu’au choix d’**une** édition (label, pays, catalogue, année).
- Réédition : `edition_notes` ou champs label/catalogue `confirmed` pour lever l’ambiguïté.

### 3.4 Compilation

- `is_compilation=true` `confirmed`.
- `album_artist` confirmé (pas inventé).
- Chaque piste a un `artist` `confirmed` (souvent distinct).

### 3.5 Coffret multidisque

- `disc_number` / `disc_total` `confirmed`.
- `path_preview` inclut `Disc {N}/` (recommandation [library-conventions.md](library-conventions.md)) ou convention tranchée.
- Les autres disques du coffret peuvent être `missing` **hors lecteur** ; seule la fiche du disque **présent** doit être approuvée pour ce rip.

### 3.6 Absent de MusicBrainz

- Autorisé : fiche 100 % manuelle, tous obligatoires `confirmed`.
- `musicbrainz_*` = `unavailable` (recherche tentée) ou `missing` si offline volontaire avec saisie manuelle complète.
- **Interdit** : inventer un MBID.

---

## 4. Pipeline d’états (extrait)

```text
Idle → DiscDetected → TocRead → Identifying
    → AwaitingMetadataApproval    ← GATE OBLIGATOIRE (mode normal)
        → (Approve) → Ripping → …
        → (Reject / Edit) → reste / revient Identifying
```

Transitions **interdites** en mode normal : `TocRead|Identifying → Ripping` sans `AwaitingMetadataApproval` + `Approved`.

---

## 5. Interface

1. Affichage TOC + candidats MusicBrainz + formulaire éditable (`DiscMetadataDialog`).
2. Badges de confiance par champ (`confirmed` / `ambiguous` / `missing` / `unavailable`).
3. Liste d’erreurs bloquantes vs avertissements.
4. **Aperçu exact** des chemins fichiers/dossiers futurs (zone C), calculés depuis la fiche — caractères déjà sanitisés.
5. Boutons : **Lire TOC + chercher MusicBrainz** · Appliquer l’édition · Enregistrer brouillon · Approuver · Refuser.
6. Tant que non approuvé : bouton rip normal **désactivé**.
7. Pochette : statut CAA + URL d’aperçu (pas d’auto-approve).

---

## 6. Mode test technique (isolé)

| | |
|--|--|
| But | Valider freaccmd / FLAC / F-08a sans constituer la collection. |
| Activation | Action UI distincte + case à cocher + texte de confirmation explicite. |
| Destination | Zone **A** uniquement (`jobs/{id}/rip/`). |
| Métadonnées | Gate complète **non** exigée ; avertissement « ne sera pas publié en zone C ». |
| Publication C | **Impossible** depuis ce mode (blocage produit). |
| Traçabilité | `DiscMetadata.mode = technical_test` + job flaggé dans SQLite. |

Le rip technique AVM-02 (si relancé) relève de ce mode — pas du mode normal archives.

---

## 7. DVD (métadonnées seulement — D-010)

Champs additionnels prévus (pas d’extraction) :

- `medium_format`: `dvd_video` | `dvd_audio`
- `dvd_title_index`, `dvd_audio_stream_id`, `audio_codec_source` (PCM/AC3/DTS/…)
- `chapters[]` optionnel
- Même gate d’approbation avant toute extraction future

---

## 8. Critères d’acceptation (AVM-02B doc → futures implémentations)

| ID | Critère |
|----|---------|
| AC-M1 | Modèle `DiscMetadata` documenté avec release / disc / tracks / TOC / confiance. |
| AC-M2 | Mode normal : rip impossible sans `AwaitingMetadataApproval` + `Approved`. |
| AC-M3 | Validation TOC (count, numéros, durées) documentée. |
| AC-M4 | Cas réédition, compilation, multidisque, absent MB couverts. |
| AC-M5 | Placeholders génériques interdits en zone C / en fiche approuvée. |
| AC-M6 | Aperçu chemins futurs exigé avant approbation. |
| AC-M7 | Mode test technique isolé, confirmation explicite, pas de publish C. |
| AC-M8 | DVD : champs prévus, extraction non implémentée. |
| AC-M9 | (AVM-02B) Aucune implémentation MusicBrainz dans ce mandat doc ; reporté AVM-04. |

---

## 9. Identification MusicBrainz / libdiscid / CAA (AVM-04)

### Pipeline

```text
Lecteur → libdiscid (TOC + Disc ID)
       → MusicBrainz get_releases_by_discid
       → compare TOC vs medium (exact | partial | mismatch)
       → [0] fiche TOC seule, champs édition missing
       → [1] préremplissage trust=ambiguous (pas Approved)
       → [N] liste candidates, choix UI obligatoire
       → Cover Art Archive (URL / unavailable)
       → Appliquer édition (user_selected → confirmed)
       → Approuver manuellement (gate D-011)
```

### Règles

- **Jamais** d’approbation automatique (D-015 : option future désactivée).
- Sélection **intelligente** d’édition si équivalentes (préférence `preferred_release_country`, défaut `CA` = départage seulement) — [avm-04c-validation.md](../validation/avm-04c-edition-selection.md).
- Ne pas écraser une correction `user_correction`/`manual` + `confirmed`.
- Ne pas inventer label, année, barcode, MBID ou `is_compilation`.
- User-Agent : `AudioVideoManager/0.4.x` ; intervalle ≥ 1,1 s.
- DLL native : `vendor/libdiscid/libdiscid-0.6.4-win/x64/discid.dll` (ou `AVM_LIBDISCID_DIR`).

Rapports : [avm-04-validation.md](../validation/avm-04-musicbrainz.md) · [avm-04b-validation.md](../validation/avm-04b-live-identify.md) · [avm-04c-validation.md](../validation/avm-04c-edition-selection.md).
