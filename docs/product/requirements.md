# Exigences — AudioVideoManager

Décisions : [decisions.md](decisions.md). Fiche disque : [disc-metadata.md](../domain/disc-metadata.md).  
Conventions FS : [library-conventions.md](../domain/library-conventions.md).

## 1. Objectifs

Archiver localement des **CD** (puis DVD) **originaux** en **FLAC**, dans une bibliothèque **parfaitement identifiée et structurée** : édition exacte connue, chemins prévisibles, pas de fichiers orphelins ni de noms inventés.

## 2. Modes d’exécution

| Mode | Gate métadonnées | Destination | Publication zone C |
|------|------------------|-------------|-------------------|
| **Normal (archive)** | **Obligatoire** — fiche approuvée | A puis B/C selon pipeline | Seulement après validations + règles D-009 |
| **Test technique** | Non (confirmation explicite distincte) | **A uniquement** | **Interdite** |

## 3. Périmètre MVP CD — exigences fonctionnelles

| ID | Exigence |
|----|----------|
| F-01 | Détecter présence d’un CD audio. |
| F-02 | Lire la TOC ; afficher pistes / durées **mesurées**. |
| F-03 | Constituer / corriger une fiche `DiscMetadata` (MB plus tard ; manuel dès l’implémentation gate). |
| F-03a | Distinguer `confirmed` / `ambiguous` / `missing` / `unavailable` par champ. |
| F-03b | Valider concordance fiche ↔ TOC (nombre, numéros, durées). |
| F-03c | Étape **`AwaitingMetadataApproval`** ; bouton **Approuver** explicite. |
| F-03d | Aperçu **exact** des chemins/fichiers futurs (zone C) avant approbation. |
| F-03e | **Bloquer** le rip normal si fiche incomplète, incohérente ou non approuvée. |
| F-03f | Cas supportés dans les règles : réédition, compilation, coffret, absent MB. |
| F-04 | Extraire en FLAC via `freaccmd` **après** F-03c en mode normal (D-002). |
| F-04t | Mode test technique : rip isolé zone A, confirmation forte, pas de publish C (D-013). |
| F-05 | Tags (phase dédiée) : artistes, album, titres, année, IDs MB si connus — **sans invention**. |
| F-06 | Pochettes : embarquée + `cover.jpg` si `cover_status` le permet (D-006). |
| F-07 | Organisation D-005 en zone C **après** rip + règles de publication. |
| F-08a | Intégrité FLAC ≠ preuve de rip. |
| F-08b | Vérification rip (faible puis AccurateRip plus tard). |
| F-09 | Journal + SQLite (jobs, fiche, checkpoints). |
| F-10 | Doublons : jamais d’écrasement silencieux (D-009). |
| F-11 | Éjection optionnelle (défaut off). |
| F-12 | UI : TOC, fiche, aperçu chemins, approbation, rip, progression, annulation. |
| F-13 | Reprise de jobs (checkpoints). |
| F-14 | Aucun nom générique dans fiche approuvée / zone C (D-012). |

### Hors MVP / reporté

- Extraction DVD (D-010) — **métadonnées DVD** spécifiées dans [disc-metadata.md](../domain/disc-metadata.md) §7.
- Contournement DRM, cloud, AcoustID, multi-lecteurs parallèles.
- Sidecar `.avm-import.json` (D-007).

## 4. Non fonctionnel

| ID | Exigence |
|----|----------|
| NF-01 | Windows 10/11 x64. |
| NF-02 | Pas d’install silencieuse d’outils système. |
| NF-03 | Mode normal offline si fiche manuelle complète `confirmed`. |
| NF-04 | Logs structurés. |
| NF-05 | Annulation propre du rip. |
| NF-06 | Noms Windows-safe ; aperçu = chemins réellement utilisables. |
| NF-07 | UI FR ; package `audio_video_manager`. |
| NF-08 | GPL-3.0-or-later. |
| NF-09 | Aucun champ métadonnée inventé par le logiciel. |

## 5. Qualité audio

Inchangé : FLAC, CD 16/44,1, DSP off par défaut ; F-08a ≠ F-08b.

## 6. Erreurs (extrait gate)

| Situation | Comportement |
|-----------|--------------|
| Fiche `ambiguous` / `missing` obligatoire | Approuver désactivé ; rip normal désactivé. |
| TOC ≠ liste pistes | Erreur bloquante. |
| Tentative rip normal sans `Approved` | Refus explicite. |
| Mode test sans confirmation | Refus. |
| Publication C depuis test technique | Refus. |

## 7. Impact sur AVM-02 (phase 1 livrée)

- Le code rip actuel = **capacité test technique / fondation extract**, **pas** le parcours archive final.
- Un rip réel « archive » **ne doit plus** être présenté comme workflow normal tant que D-011 n’est pas implémenté.
- AVM-02 validation CD (si reprise) : uniquement sous **mode test technique** (zone A).

## 8. Critères d’acceptation doc AVM-02B

Voir AC-M1…AC-M9 dans [disc-metadata.md](../domain/disc-metadata.md) §8.
