# Architecture technique — AudioVideoManager

Décisions consolidées : [decisions.md](decisions.md). Constat CLI : [freac-cli.md](../engineering/freac-cli.md).

Package Python : **`audio_video_manager`**. Licence : GPL-3.0-or-later.

## 1. Vue d’ensemble

Processus GUI unique ; outils externes en sous-processus. Pas de microservices.

```text
┌─────────────────────────────────────────────────────────┐
│  UI (PySide6)                                           │
│  TOC · fiche DiscMetadata · aperçu chemins · approbation│
│  rip (normal | test technique) · progression            │
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────┐
│  Orchestration (ImportJob)                              │
│  detect → toc → identify → AwaitingMetadataApproval     │
│       → rip → tag → organize → F-08a → F-08b → ready    │
│  (mode test technique : rip zone A sans gate complète)  │
└──┬──────────┬───────────┬──────────┬──────────┬─────────┘
   │          │           │          │          │
   ▼          ▼           ▼          ▼          ▼
 Extract   Metadata    Library    Storage    Logging
 freaccmd  DiscMetadata FS D-005  SQLite     fichiers
           + trust      doublons  jobs+fiche
```

* AVM-11B autorise l'inspection DVD-Video en lecture seule pour les supports non protégés. L'archivage DVD reste non validé; DVD-Audio et contournement des protections sont hors périmètre (D-010). Modèle vidéo : [disc-metadata.md](../domain/disc-metadata.md).

## 2. Modules (package `audio_video_manager`)

| Module | Responsabilité | Ne fait pas |
|--------|----------------|-------------|
| `ui` | Présentation, confirmations Skip/Replace/Rename, reprise | Logique métier longue |
| `orchestration` | Machine à états, checkpoints, reprise | I/O CD brut |
| `extraction.cd` | Encapsulation `freaccmd` | MusicBrainz |
| `extraction.dvd` | Inspection DVD-Video lecture seule (`DvdInspector`) | Archivage, conversion et contournement des protections |
| `metadata` | Modèle `DiscMetadata`, validation TOC, trust, (plus tard MB/CAA) | Rip |
| `library` | Motif D-005, aperçu chemins, doublons, replace non destructif | Encodage |
| `verification` | F-08a / F-08b distincts | Identification |
| `storage` | SQLite (jobs, fiche, releases, tracks, checkpoints) | Fichiers média |
| `logging` / `config` | Logs, chemins, mode normal vs test | Télémétrie |

Interfaces stables : `CdRipper`, `DiscMetadataValidator`, `MetadataProvider`, `PathPreview`, `LibraryOrganizer`, `FlacIntegrityChecker`, `RipQualityChecker`.

## 3. Intégration fre:ac

### 3.1 Faits locaux (AVM-00)

| Sujet | Constat |
|-------|---------|
| GUI | `C:\Program Files\freac\freac.exe` **1.1.7** |
| Licence | GPL-2.0 (`COPYING`) |
| CLI | **`freaccmd.exe` absent** — aucune capacité CLI observée sur cette machine |
| Doc publique | Options listées dans [freac-cli.md](../engineering/freac-cli.md) §2 — **hypothèses** jusqu’à re-test |

### 3.2 Stratégie d’appel (quand la CLI sera disponible)

1. Résoudre `freaccmd.exe` (config + détection).
2. Profil fre:ac « AVM-FLAC » (FLAC, DSP off).
3. Rip vers un **répertoire de travail de job** (`workdir`), jamais directement vers la destination finale en écrasement.
4. Codes retour + inventaire des FLAC attendus.
5. Jamais modifier les binaires / sources fre:ac.

Détail des options : [freac-cli.md](../engineering/freac-cli.md).

## 4. Métadonnées (D-004)

```text
TOC → Disc ID (libdiscid) → MusicBrainz (si réseau)
    → choix release (UI si ambigu)
    → Cover Art Archive
    → mutagen (tags + art embarqué) + cover.jpg
```

Hors ligne : saisie manuelle / reprise de métadonnées déjà choisies pour le job. CDDB fre:ac = secours optionnel.

## 5. Stockage et reprise des jobs

### 5.1 Système de fichiers

Trois zones (détail : [library-conventions.md](../domain/library-conventions.md)) :

| Zone | Chemin typique | Usage |
|------|----------------|--------|
| A — Jobs / temp | `%LOCALAPPDATA%/AudioVideoManager/jobs/{job_id}/rip/` | Rip brut phase 1 |
| B — À valider | `{library_root}/_inbox/…` | Staging futur (phase 3) |
| C — Définitive | `{library_root}/{AlbumArtist}/…` | Après validation explicite seulement |

- Sidecar `.avm-import.json` : **non** (D-007).
- Phase 1 n’écrit **jamais** en B ni C.

### 5.2 SQLite (conceptuel MVP)

| Table | Rôle |
|-------|------|
| `releases` | disc_id, mbid, album_artist, album, year, path, status |
| `tracks` | release_id, number, title, path, duration_ms, flac_ok, rip_check_status |
| `jobs` | id, state, step, workdir, started_at, updated_at, finished_at, error_summary, resume_token |
| `job_checkpoints` | job_id, step, payload_json, created_at |

`sqlite3` stdlib ; pas d’ORM imposé.

### 5.3 Reprise des jobs interrompus

États persistés à chaque transition majeure. Au démarrage de l’app :

1. Charger les jobs dont `state ∈ {Ripping, Tagging, Organizing, FlacIntegrity, RipCheck, Interrupted}`.
2. Proposer **Reprendre** / **Abandonner** (abandon = nettoyage workdir + marquage `Abandoned`).
3. Reprise = reprendre à `step` checkpointé ; ne pas relancer un rip complet si les FLAC du workdir sont déjà présents et cohérents avec la TOC.
4. Annulation utilisateur : `Interrupted` ou `Cancelled` + suppression des **partiels incomplets** du workdir (fichiers `.tmp` / taille nulle) ; conserver les pistes FLAC complètes déjà validées pour reprise piste-à-piste (phase 1+).

Pas de reprise « magique » à mi-piste d’un processus `freaccmd` unique : si fre:ac est tué au milieu d’une piste, cette piste est invalidée et retraitée.

## 6. Doublons et remplacement non destructif (D-009)

Détection : Disc ID (fort) puis clé normalisée `album_artist|album|year` (soft).

Actions UI uniquement :

| Action | Comportement |
|--------|----------------|
| **Skip** | Aucune écriture destination ; job clôturé `SkippedDuplicate`. |
| **Rename** | Nouveau dossier/suffixe (`Album (Year) [import-2]/ …). |
| **Replace** | **Non silencieux, non in-place destructif** : écrire d’abord dans un staging (`…/.avm-replace-{job_id}/` ou workdir), vérifier intégrité FLAC du nouveau jeu, **puis** basculer (rename atomique dossier par dossier / fichiers) et déplacer l’ancien jeu vers une corbeille locale `…/.avm-trash/{timestamp}/` (rétention configurable). Échec mid-swap → rollback vers l’ancien dossier si encore présent. |

Aucun `unlink` de la destination finale avant validation du nouveau contenu.

## 7. Vérification : deux concepts séparés

| Couche | Nom | Question | Notes |
|--------|-----|----------|--------|
| A | **Intégrité FLAC (F-08a)** | Fichier FLAC structurellement OK ? | ≠ rip parfait |
| B | **Vérification rip (F-08b)** | Extraction fidèle au CD ? | Faible au MVP ; AccurateRip plus tard |

## 8. Pipeline ImportJob (états) — AVM-02B

### Mode normal (archive)

```text
Idle → DiscDetected → TocRead → Identifying
    → AwaitingMetadataApproval          ← GATE (D-011)
        → Ripping → Tagging → Organizing
        → FlacIntegrity → RipCheck
        → Completed | CompletedWithWarnings | Failed | …
        → ReadyForNext
```

Sans `Approved` : **pas** de transition vers `Ripping`.

### Mode test technique (D-013)

```text
Idle → DiscDetected → (confirm test) → RippingTech → FlacIntegrity
    → CompletedTechnical | Failed
```

Pas d’écriture zone C ; job marqué `technical_test`.

`Failed` / `Interrupted` portent `resume_from=<step>`.

## 9. Stack retenue (D-003)

| Techno | Rôle MVP |
|--------|----------|
| Python 3.11+ (3.12 OK) | Runtime |
| PySide6 Widgets | UI |
| SQLite | Index + checkpoints |
| mutagen | Tags + art embarqué |
| MusicBrainz + CAA | ID / métadonnées / pochettes (réseau optionnel) |
| libdiscid | Disc ID |
| fre:ac `freaccmd` | Rip CD → FLAC (**bloqueur actuel**) |

Hors MVP : FFmpeg, AcoustID, Electron, ORM lourd, cloud.

## 10. Journalisation et config

- Logs : `%LOCALAPPDATA%/AudioVideoManager/logs/` (configurable).
- DEBUG : ligne de commande freaccmd (sans données sensibles).
- Pas de télémétrie.
- Config : chemins `freaccmd`, root bibliothèque, pattern D-005, politique trash replace.

## 11. Sécurité / conformité

- Chemins outils configurables ; pas d’install silencieuse d’outils système.
- `User-Agent` MusicBrainz obligatoire.
- Pas de contournement DRM (D-010 reporté de toute façon).
