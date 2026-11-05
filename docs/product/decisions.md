# Décisions — AudioVideoManager

Légende statut : `ACCEPTÉ` · `PROPOSÉ` · `ACCEPTÉ SOUS RÉSERVE` · `REPORTÉ` · `OUVERT` · `BLOQUANT`

Précisions AVM-03 : distinguer **identification disque** (TOC/Disc ID) et **édition physique exacte** ; conserver **provenance** + journal de corrections ; `unavailable` uniquement pour exceptions documentées (année + pochette).

---

## Décisions validées (AVM-00 → AVM-02)

### D-001 — Licence — `ACCEPTÉ` — GPL-3.0-or-later

### D-002 — Backend CD MVP — `ACCEPTÉ` — fre:ac / `freaccmd` (CLI validée AVM-01)

### D-003 — Stack — `ACCEPTÉ` — Python 3.11+, PySide6, SQLite, mutagen, MusicBrainz, libdiscid

### D-004 — Source métadonnées — `ACCEPTÉ` — MusicBrainz primaire ; hors ligne / manuel possible

### D-005 — Organisation — `ACCEPTÉ` — `{AlbumArtist}/{Album} ({Year})/{NN} - {Title}.flac` + `cover.jpg`

### D-006 — Pochettes — `ACCEPTÉ` — embarquée + `cover.jpg`

### D-007 — Sidecar JSON — `REPORTÉ` — SQLite seul au MVP

### D-008 — Nommage — `ACCEPTÉ` — AudioVideoManager / package `audio_video_manager`

### D-009 — Doublons — `ACCEPTÉ` — jamais d’écrasement silencieux

### D-010 — DVD extraction — `REPORTÉ` — métadonnées DVD prévues en doc (AVM-02B), pas d’extract

---

## Décisions AVM-02B / AVM-03 — acceptées

### D-011 — Gate métadonnées avant rip normal — `ACCEPTÉ` (implémenté AVM-03)

### D-012 — Interdiction placeholders archive — `ACCEPTÉ`

### D-013 — Mode test technique isolé — `ACCEPTÉ` (UI + `run_rip_job`)

### D-014 — Ordre meta → rip archive — `ACCEPTÉ`

### D-015 — Sélection intelligente d’éditions (AVM-04C) — `ACCEPTÉ`

- `preferred_release_country` (défaut `CA`) = **départage**, jamais preuve de provenance.
- Auto-sélection d’édition si équivalence musicale + TOC non bloquante.
- **Auto-approbation** fiche : option `auto_approve_high_confidence` **désactivée** (préparée pour plus tard).
- Divergences de pistes / TOC bloquantes / éditions réellement différentes → choix manuel.

---

## Hypothèses

| ID | Hypothèse |
|----|-----------|
| H-01 | Archivage de supports légitimement possédés. |
| H-02 | Un lecteur optique suffit au MVP CD. |
| H-03 | FLAC 16/44,1 pour CD, sans resampling artificiel. |
| H-04 | fre:ac = dépendance runtime séparée. |
| H-05 | Internet occasionnel pour MB ; manuel offline possible si fiche complète. |
| H-06 | L’utilisateur accepte de corriger / choisir l’édition exacte avant chaque rip normal. |

---

## Incertitudes

| ID | Statut | Sujet |
|----|--------|-------|
| I-02 | Ouvert | AccurateRip via fre:ac |
| I-03 | Ouvert | Couverture MB vs collection |
| I-04 | Ouvert | Détection insertion disque |
| I-07 | **Tranché AVM-04** | TOC / Disc ID via **libdiscid** ; fre:ac reste backend rip uniquement |
| I-08 | Ouvert | Tolérance exacte durées TOC vs tags (valeur 500 ms proposée) |

---

## Risques

| Risque | Sévérité | Mitigation |
|--------|----------|------------|
| Rip archive sans identification | Haute | D-011 gate |
| Confusion test technique / archive | Haute | D-013 UI séparée + flags job |
| Fiches MB ambiguës (rééditions) | Moyenne | Forcer choix édition + label/catalogue |
| Friction utilisateur | Moyenne | Brouillon + aperçu chemins + offline manuel + D-015 |
| Faux positif édition (mauvais pays) | Moyenne | Départage explicite + warnings + override UI |

---

## Historique

| Date | Événement |
|------|-----------|
| 2026-11-03 | D-001…D-010 ; AVM-00…02 |
| 2026-11-03 | **AVM-02B** : D-011…D-014 proposés ; spec [disc-metadata.md](../domain/disc-metadata.md) |
| 2026-11-03 | **AVM-03** : D-011…D-014 acceptés ; implémentation gate + UI + SQLite v2 |
| 2026-11-03 | **AVM-04** : libdiscid + MusicBrainz + CAA ; I-07 tranché ; pas d’auto-approve |
| 2026-11-03 | **AVM-04B** : ID réelle Queen GH ; mapping fre:ac≠lettre ; GO AVM-05 |
| 2026-11-03 | **AVM-04C** : D-015 sélection intelligente ; préférence CA ; pas d’auto-approve |
| 2026-11-03 | **AVM-05** : pipeline archive A→B→C ; mutagen ; SQLite v3 ; GO rip contrôlé |
