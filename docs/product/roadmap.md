# Roadmap — AudioVideoManager

Révisé par **AVM-02B** (gate métadonnées). Décisions : [decisions.md](decisions.md).  
Spec fiche : [disc-metadata.md](../domain/disc-metadata.md).

## Ordre révisé des phases

| Ordre | Phase | Statut | Objectif |
|-------|-------|--------|--------|
| 0 | Fondations | **Faite** (AVM-01) | Package, config, SQLite, UI shell, détection freaccmd |
| 1 | Capacité rip technique | **Faite** (AVM-02) | `freaccmd` → zone A, F-08a/F-08b faible, tests mock — **reclassé mode test technique** (D-013) |
| **2** | **Gate `DiscMetadata` + UI approbation** | **Faite** (AVM-03) | Modèle, validation TOC, provenance, SQLite v2, UI manuelle, verrou métier, mode test — **sans** MB |
| **3** | **Remplissage MusicBrainz / libdiscid / CAA** | **Faite** (AVM-04) | Lookup, ambiguïtés édition, pochettes — alimente la fiche, n’approuve pas à sa place |
| **3b** | **Validation réelle ID CD** | **Faite** (AVM-04B) | TOC/MB/CAA live · mapping lecteur corrigé · [avm-04b-validation.md](../validation/avm-04b-live-identify.md) |
| **3c** | **Sélection intelligente éditions** | **Faite** (AVM-04C) | Préférence CA · ranking · [avm-04c-validation.md](../validation/avm-04c-edition-selection.md) |
| **4** | **Organisation bibliothèque (zones B/C)** | **Faite** (AVM-05) | mutagen, cover, publish non destructif · [avm-05-validation.md](../validation/avm-05-archive-library.md) · **GO rip réel contrôlé** |
| **4b** | **Conception UX/UI** | **06A/06B validées** | [../ux/](../ux/README.md) · specs [../ux/specs/](../ux/specs/README.md) |
| **4c** | **UI-0 + UI-1** | **Livré** (AVM-06) | Coquille 4 sections + wizard 5 étapes · [rapport](../ux/reports/AVM-06-UI-0-UI-1.md) — **attendre validation avant rip réel** |
| **4d** | **Premier rip réel** | Bloqué | Mandat **AVM-06C** après GO UI-1 |
| 5 | Qualité rip avancée | Plus tard | AccurateRip / secure |
| 6 | DVD | Reporté D-010 | Métadonnées déjà esquissées ; extraction plus tard |

```text
AVANT (implicite AVM-02) :  rip → (meta plus tard)
APRÈS AVM-02B (archive)  :  meta approuvée → rip → organisation
```

## Impacts AVM-02

| Sujet | Impact |
|-------|--------|
| Code `FreacCdRipper` / `run_rip_job` | Conservé comme **moteur** + entrée **test technique** |
| UI « Démarrer l’extraction » actuelle | À scinder : *Test technique…* vs *Archive (après fiche)* |
| Rip réel archive | **Bloqué produit** jusqu’à implémentation phase 2 (gate) |
| Rip réel test | Autorisable sous D-013 + confirmation (zone A only) |
| MusicBrainz | **Pas** dans AVM-02B ; phase 3 roadmap ci-dessus |
| Docs conventions | [library-conventions.md](../domain/library-conventions.md) + disc-metadata |

## Phase 2 — Gate métadonnées (prochaine implémentation)

**Entrée :** validation mandant des D-011…D-014 + AC-M*.

**Livrables :**

- Modèle / validation `DiscMetadata` (trust, TOC).
- UI édition + aperçu chemins.
- État `AwaitingMetadataApproval` ; rip normal disabled sinon.
- Mode test technique explicite branché sur le rip existant.
- Tests auto (fiche incomplète → pas de rip ; TOC mismatch → erreur).

**Sortie :** impossible de lancer un rip *normal* sans `Approved` ; test technique toujours isolé.

## Phase 3 — MusicBrainz / Disc ID / CAA (AVM-04 — faite)

- libdiscid vendored + musicbrainzngs + CAA.
- Ambiguïtés réédition / multi-releases → sélection UI.
- Jamais d’auto-approbation ; rapport [avm-04-validation.md](../validation/avm-04-musicbrainz.md).

## Phase 4 — Bibliothèque (AVM-05 — faite)

- Inbox B + publish C ; Skip/Rename/Replace + trash.
- Tags mutagen + cover.jpg ; Disc ID match avant rip.
- Procédure premier archivage réel : [avm-05-validation.md](../validation/avm-05-archive-library.md).

## Phase 5+ — AccurateRip, DVD

Inchangé dans l’esprit ; DVD metadata déjà dans disc-metadata §7.

## Jalons

| Jalon | Condition |
|-------|-----------|
| V0…V1 | Fondations + rip technique — faits |
| **V-Meta** | Validation doc AVM-02B (D-011…D-014) |
| **V2** | Phase 2 gate implémentée + tests |
| **V3** | Phase 3 MB branchée sur la gate — **AVM-04** |
| **V4** | Phase 4 publish C = MVP archive — **AVM-05** |
| V-DVD | Avant extraction DVD |
