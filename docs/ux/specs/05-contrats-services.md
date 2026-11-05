# 05 — Contrats d’interaction avec les services AVM-05

L’UI **orchestre** ; elle **ne recalcule pas** TOC/MB/validation/publish.

## 1. Cartographie écran → API

| Écran / action | Module / symbole | Entrées UI | Sorties consommées |
|----------------|------------------|------------|-------------------|
| W1 Relire | `read_disc_toc` / `resolve_optical_device_for_discid` | device letter | `DiscReadResult` |
| W1 lecteurs | `FreacCdRipper.list_drives` | freaccmd path | `CdDrive[]` |
| W2 Identify | `identify_disc(...)` | device, `preferred_release_country`, disc_read optionnel | sheet, lookup, cover, `SelectionDecision` |
| W2 Apply alt. | `apply_release_candidate(..., user_selected=True)` + `fetch_cover_art_info` | candidate | sheet mutée |
| W2 Cover image | HTTP GET URL CAA (cache fichier sous jobs/cache ou temp) | thumbnail_url / front_url | `QPixmap` |
| W3 Validate | `apply_validation` / `validate_disc_metadata` | sheet | errors, warnings, path_preview |
| W3 Preview | `build_path_preview` | sheet | `list[str]` |
| W3 Brouillon | `DiscMetadataRepository.save` | sheet | id |
| W3 Approuver | `approve_sheet` puis save | sheet, note | Approved ou `ApprovalError` |
| W3 Dirty revoke | UI : `sheet.approval=Pending`, clear `approved_at` (+ optionnel save) | — | gate bloque rip |
| W4 Gate | `assert_can_start_archive_rip` | sheet | raise si non |
| W4 Match | `assert_disc_matches_sheet` / `verify_disc_matches_sheet` | sheet, fresh `read_disc_toc` | mismatch |
| W4 Run | `run_archive_job` via `ArchiveWorker` | sheet, library_root, jobs_root, freaccmd, drive, collision, confirm_publish=True, optical_device | `ArchiveJobReport` |
| W4 Cancel | `ArchiveWorker.cancel` → `cancel_event` | — | Interrupted/Cancelled |
| W5 Open dir | `QDesktopServices.openUrl` | library_path / album_dir | — |
| Lib liste | SQL `releases` + `Path.exists` | db, library_root | rows |
| Hist liste | SQL `jobs` (+ checkpoints détail) | db | rows |
| Hist abandon | UPDATE jobs state (contrat à aligner code existant ; **pas** unlink C) | job_id | — |
| Settings | `load_config` / `save_config` | `AppConfig` | path |
| Test technique | `RipWorker` + `run_rip_job(mode=TECHNICAL_TEST)` | confirm UI | zone A only |

## 2. Threading

| Travail long | Mécanisme |
|--------------|-----------|
| identify (réseau) | `QThread` worker dédié ou réutiliser pattern ArchiveWorker ; progress « Recherche… » |
| archive_job | `ArchiveWorker` existant |
| test technique | `RipWorker` existant |
| cover download | thread / `QNetworkAccessManager` ; UI placeholder en attendant |

**Interdit :** appels réseau ou freaccmd sur le thread UI.

## 3. Mapping progression archive → libellés FR

| Phase interne (logique) | Libellé UI |
|-------------------------|------------|
| disc match | Vérification du disque |
| rip / staging | Extraction audio |
| F-08a | Contrôle des fichiers |
| tags + cover | Mise en tags et pochette |
| inbox B | Organisation |
| publish C | Publication |

`ArchiveWorker.progress(str, fraction)` : adapter les messages côté worker **ou** traduire dans le slot UI (préférence : messages FR émis par une fine couche UI, pas modifier le métier sauf besoin).

## 4. Politique collision UI → enum

| Libellé UI | `CollisionPolicy` |
|------------|-------------------|
| Créer import-2 | `RENAME` |
| Ne pas publier | `SKIP` |
| Remplacer (corbeille locale) | `REPLACE` |

## 5. Ce que l’UI ne doit pas faire

- Recalculer Disc ID / TOC.
- Inventer tags ou éditions.
- Publier avec `confirm_publish=False` en le contournant.
- Activer auto-approve.
- Appeler `run_rip_job(..., allow_library_publish=True)`.
- Supprimer des dossiers zone C depuis Historique « Abandonner ».

## 6. Snapshot A3 (contrat UI)

Pour détecter « données approuvées changées » :

```text
approved_fingerprint = hash stable de:
  identity.disc_id + toc offsets/count
  + edition (title, artist, year, country, label, cat, barcode, mbid, cover_status)
  + tracks (number, title, artist, duration_ms)
  + disc_number/total + is_compilation
```

- Au succès de `approve_sheet` : stocker fingerprint.
- À chaque edit / apply candidate / nouvelle TOC : si fingerprint ≠ courant et était Approved → Pending + message dirty.
- Navigation section : **ne pas** comparer / ne pas révoquer.
