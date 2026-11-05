# Documentation — AudioVideoManager

Point d’entrée unique. Contenu en français ; chemins de fichiers stables.

```text
docs/
├── README.md                 ← vous êtes ici
├── product/                  Produit : exigences, archi, décisions, roadmap
├── domain/                   Métier : fiche disque, conventions bibliothèque
├── engineering/              Dev : fre:ac, setup, tests manuels
├── validation/               Rapports de validation par mandat AVM-XX
└── ux/                       Conception UX + specs 06B + rapports UI
```

## Produit

| Document | Description |
|----------|-------------|
| [product/requirements.md](product/requirements.md) | Exigences MVP, F-08a/F-08b, erreurs |
| [product/architecture.md](product/architecture.md) | Couches, jobs, zones A/B/C |
| [product/decisions.md](product/decisions.md) | Décisions D-001…D-015 |
| [product/roadmap.md](product/roadmap.md) | Phases et jalons |

## Domaine

| Document | Description |
|----------|-------------|
| [domain/disc-metadata.md](domain/disc-metadata.md) | Fiche disque, TOC, MB/CAA, gate |
| [domain/library-conventions.md](domain/library-conventions.md) | Motifs chemins, doublons, portabilité FS |

## Ingénierie

| Document | Description |
|----------|-------------|
| [engineering/development.md](engineering/development.md) | Install, venv, variables, lancement |
| [engineering/freac-cli.md](engineering/freac-cli.md) | Constat CLI fre:ac |
| [engineering/manual-rip-test.md](engineering/manual-rip-test.md) | Test technique zone A |

## Validations (rapports)

| Document | Mandat |
|----------|--------|
| [validation/avm-04-musicbrainz.md](validation/avm-04-musicbrainz.md) | AVM-04 — libdiscid / MB / CAA |
| [validation/avm-04b-live-identify.md](validation/avm-04b-live-identify.md) | AVM-04B — identification réelle |
| [validation/avm-04c-edition-selection.md](validation/avm-04c-edition-selection.md) | AVM-04C — sélection intelligente |
| [validation/avm-05-archive-library.md](validation/avm-05-archive-library.md) | AVM-05 — archive FLAC → bibliothèque |

## UX / UI

| Document | Description |
|----------|-------------|
| [ux/README.md](ux/README.md) | Hub UX (06A + 06B + UI) |
| [ux/specs/README.md](ux/specs/README.md) | Spécifications détaillées AVM-06B |
| [ux/reports/AVM-06-UI-0-UI-1.md](ux/reports/AVM-06-UI-0-UI-1.md) | **Rapport UI-0 + UI-1 (à valider)** |

## Convention de nommage

| Dossier | Règle |
|---------|--------|
| `product/`, `domain/`, `engineering/` | Noms stables, sans numéro de mandat |
| `validation/avm-NN-…` | Un rapport par mandat, préfixe `avm-` + slug court |
| `ux/NN-…` | Chapitres ordonnés d’un dossier de conception |

Ne pas déposer de nouveaux `.md` à la racine de `docs/` (sauf ce README).
