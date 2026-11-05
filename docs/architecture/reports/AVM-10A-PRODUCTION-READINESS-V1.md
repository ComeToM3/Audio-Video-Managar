# Rapport AVM-10A — Audit transversal de préparation V1

**Date :** 2026-11-03  
**Version auditée :** 0.5.0 (`pyproject.toml` / `audio_video_manager`)  
**Baseline produit :** AVM-08E (Brume pastel — GO technique ; validation visuelle **EN ATTENTE**)  
**Contrainte :** **lecture seule** — aucun correctif, refactoring, migration, commit ni mutation des données utilisateur  
**Suspendus jusqu’à décision explicite :** AVM-09 · FFmpeg/HTTP applicatif · rip physique non autorisé ici  
**Environnement de preuve :** Windows 10 build 26300 · Python 3.12.10 · PySide6 6.12.0 · fre:ac 1.1.7 (`freaccmd.exe` présent) · libdiscid vendor OK · ffmpeg `C:\Tools\ffmpeg\bin\ffmpeg.EXE`

---

## Verdict exécutif

| Question | Réponse |
|----------|---------|
| L’application est-elle **distribuable** en V1 aujourd’hui ? | **NON** |
| Le **cœur métier** CD → FLAC → tags → publish C est-il crédible ? | **Oui (partiel)** — gates D-011…D-015 / 06K / hardlinks P1 solides ; **1** album Queen réellement publié en labo |
| Stabilité runtime utilisateur (hors rip prolongé) | **Acceptable** après 07B ; crash `0xC0000409` QThread **corrigé** ; `0xC0000005` pytest **non résolu** |
| UX Brume pastel (08E) | **GO technique** ; **pas de GO visuel utilisateur** |
| **Verdict global V1** | **NO-GO** |

**Bloquants V1 (P0) :** absence de packaging/installateur ; reprise de jobs (F-13) absente alors que jobs orphelins existent ; suite de tests / CI non fiables sur codes de sortie ; validation visuelle 08E non signée ; couverture matérielle multi-CD insuffisante pour une promesse « V1 distribuable ».

---

## 0. Méthode et limites

### 0.1 Sources

| Source | Usage |
|--------|--------|
| Code `audio_video_manager/` (72 modules) | Inspection + citations lignes |
| Rapports AVM-06* … AVM-08E, AVM-07A/B, validation 04/05 | Confrontation claims ↔ code |
| Tests `tests/` (31 modules) | Exécution **non destructive** hors rip |
| `%LOCALAPPDATA%\AudioVideoManager\avm.sqlite3` | Lecture seule (états jobs) |
| freaccmd `--list-drives` | Probe sans extraction |

### 0.2 Vérifications exécutées (non destructives)

| Vérification | Résultat process | Notes |
|--------------|------------------|-------|
| `freaccmd --list-drives` | **rc=0** | Lecteur `0` · ATAPI iHAS324 |
| Import libdiscid (loader AVM) | **OK** | DLL vendor + package `discid` |
| Lot domaine (database, duplicates, hardlinks, archive pipeline, recovery staging, flac, rip_check, cd_ripper, freaccmd, diagnostics, perf, qthread_07b, …) | **Assertions PASS · EXIT=0** | Pas d’UI Qt lourde |
| Lot méta (disc_metadata, musicbrainz_identify, edition_ranker, approval_fingerprint, drives, config, logging, cover_cache) | **PASS · EXIT=0** | |
| Suite UI complète / `pytest tests/` | **Non relancée ici** | Crash teardown `0xC0000005` documenté 07A — **ne pas confondre PASS et rc process** |
| Rip optique / publish réel | **Non exécuté** | Interdit par mandat |
| Validation visuelle Brume pastel | **Non signée** | AVM-08E |

### 0.3 Légende maturité

| Symbole | Signification |
|---------|---------------|
| **I** | Implémenté dans le code |
| **T** | Couvert par tests automatisés (assertions) |
| **H** | Validé sur matériel / Windows réel (rapport ou labo) |
| **—** | Absent / non vérifié |

---

## 1. Matrice de couverture (12 axes)

| # | Axe | I | T | H | Note courte | Niveau V1 |
|---|-----|---|---|---|-------------|-----------|
| 1 | Architecture | Oui | Partiel | — | Frontières métier/UI globalement saines ; wizard monolithique ; hybride QML biblio | P1 dette |
| 2 | Extraction CD | Oui | Mock + argv | Partiel | freaccmd + cancel + disc mismatch ; rip archive réel **1** parcours labo post-06E ; multi-CD **non** | P0 couverture |
| 3 | Intégrité | Oui | Oui | Partiel | F-08a structurel ; decode ffmpeg **optionnel** si outil absent ; F-08b faible | P1 |
| 4 | Bibliothèque | Oui | Oui | Partiel | 06K + hardlinks P1 + publish ; Replace UI désactivé ; 1 album Queen | P1 |
| 5 | Persistance | Oui | Oui | Partiel | SQLite v4 + migrations ; **pas** de reprise F-13 ; job `Ripping` orphelin | **P0** |
| 6 | Stabilité | Oui | Partiel | Oui* | 07B OK ; *sans rip long systématique ; pytest AV résiduel | P1 CI / P2 runtime |
| 7 | UX/UI | Oui | Oui | Partiel | W1–W5 + 4 sections ; 08E technique OK ; visuel **attente** ; stepper horizontal | P0 visuel / P2 écarts |
| 8 | Performance | Partiel | Banc 06G-P | Partiel | Hardlinks mesurés ; biblio limite 500 ; refresh sync coûteux | P1 |
| 9 | Sécurité | Partiel | Partiel | — | Pas d’injection shell ; sanitize incomplet (CON/NUL) ; deps non pinnées | P1–P2 |
| 10 | Distribution | **Non** | Non | Non | `.bat` + venv seulement ; pas d’exe/icône/installer/licences bundlées | **P0** |
| 11 | Qualité | Partiel | Oui† | — | †PASS ≠ rc ; **pas de CI** ; pas de couverture mesurée | **P0** |
| 12 | Évolutivité | Oui | — | — | DVD stub ; workers fins ; FFmpeg déjà en vérif optionnelle — AVM-09 suspendu | OK isolation |

---

## 2. Synthèse par axe

### 2.1 Architecture

**Implémenté.** Package découpé selon l’architecture documentée (`extraction` / `metadata` / `library` / `verification` / `storage` / `orchestration` / `ui`). Les workers Qt (`archive_worker`, `rip_worker`, `identify_worker`) restent minces ; le métier `run_archive_job` / `run_rip_job` est appelable sans UI (confirmé 07B inventaire).

**Couplages / dette :**

| Constat | Preuve | Gravité |
|---------|--------|---------|
| Wizard Widgets monolithique (~1300+ lignes) | `ui/wizard/archive_wizard.py` | P2 |
| Bibliothèque hybride QML + Widgets (08B/08E) | `ui/sections/library_host.py`, `ui/qml/` | P2 (intentionnel) |
| Historique / Paramètres / Wizard **non** migrés QML | 08E §5 NO-GO migration | Info |
| `extraction/dvd.py` placeholder D-010 | Module stub | Info |
| Version User-Agent CAA incohérente `0.4.0` vs `0.5.0` | `metadata/cover_art.py` vs `library/cover.py` | P3 |

**Maintenabilité :** bonne séparation domaine ; dette UI concentrée dans le wizard et le cycle de vie Qt des tests.

---

### 2.2 Extraction CD

| Capacité | I | T | H |
|----------|---|---|---|
| Liste lecteurs fre:ac | Oui | Oui | Oui (probe 10A rc=0) |
| Mapping fre:ac ≠ lettre Win32 | Oui | Oui | Oui (04B / 06C) |
| TOC + Disc ID libdiscid | Oui | Oui | Oui (Queen GH) |
| MusicBrainz + ranking CA | Oui | Oui (mock/live partiel) | Oui (04B/04C/06C identify) |
| freaccmd rip zone A | Oui | Mock + argv | Partiel (bd40 Failed rc ; 8e23 Completed archive) |
| Changement de disque pré-rip | Oui (`DiscMismatchError`) | Tests pipeline | H limité |
| Annulation coopérative | Oui (`terminate`/`kill`) | Partiel | H limité |
| Éjection optionnelle | Oui (`--eject`) | — | **Non vérifié** |

**Confirmé :**

1. Politique stricte `returncode == 0` (`cd_ripper.py` ~279–281) — volontaire post-06E/F/G.  
2. Correctif argv `--pattern=<track>` (06E) — cause racine Failed `bd40…` avec FLAC pourtant présents.  
3. Staging recovery sans rip (`staged_flac_files`) — **I+T** (`test_archive_recovery_staging.py`).  
4. Job labo `a31763…` reste `Ripping` / `technical_test` / `finished_at=NULL` (lecture SQLite 10A) — fre:ac orphelin après crash UI historique 07B.

**Risques :**

| ID | Sévérité | Nature | Commentaire |
|----|----------|--------|-------------|
| EXT-01 | P0 (couverture) | Un seul album archive réel documenté (`8e23…`) | Multi-CD / lecteurs multiples / éjection CD **non** validés pour V1 |
| EXT-02 | P1 | fre:ac rc≠0 avec FLAC OK | Strictness correcte pour intégrité process ; UX recovery staging non produit |
| EXT-03 | P2 | Durées TOC via `track.seconds` (entier) en priorité | `toc_reader.py` 103–110 — précision secteur sous-utilisée |
| EXT-04 | P2 | `.flac.temp` orphelins | Bruit FS documenté 06E |
| EXT-05 | P3 | IdentifyWorker **sans** `cancel` | `identify_worker.py` — shutdown attend fin |

**Non vérifié ici :** éjection physique ; absence de CD / tray open pendant rip ; multi-lecteur.

---

### 2.3 Intégrité

| Couche | Comportement | Bloquant publish ? |
|--------|--------------|--------------------|
| F-08a magic + STREAMINFO | `verification/flac_integrity.py` | Oui |
| Décodage intégral ffmpeg null | `verification/flac_decode.py` | Oui **si** outil trouvé ; si absent → `ok=True` non bloquant |
| F-08b | Faible (Red Book tipique) | Non gate UI post-check |
| Durées vs TOC | Warning > 1,5 s | Non bloquant |
| AccurateRip | Hors MVP (I-02) | — |

**Confirmé :** `_record_release` écrit toujours `flac_ok=1` et `rip_check_status="weak_ok"` (`archive_job.py` 808–809) — **dérive catalogue** vs résultats réels (anomalie confirmée, P1).

**Risque plausible :** machine sans ffmpeg → seuls contrôles structurels ; corruption mid-stream possible. Sur le labo 10A, ffmpeg **est** présent.

---

### 2.4 Bibliothèque

**Forces (I+T, H partiel Queen) :**

- Doublons 06K : gates Disc ID / MBID / jobs actifs / réarchivage confirmé (`library/duplicates.py`, tests `test_duplicates_06k.py`).  
- Hardlinks : staging/inbox OK ; zone C **toujours copie** (`publish.py` `independent=True`) ; `ensure_exclusive_file` avant mutagen (06G-P1).  
- Publish non silencieux ; Skip / Rename ; Replace FS implémenté mais **radio UI désactivée** (06C).  
- Rollback mid-copy : unlink dest + tentative restore trash (`publish.py` 181–196) — best-effort Windows.

**Confirmé labo :** jobs `%LOCALAPPDATA%\…\jobs` ≈ **1,5 Go** (8e23 728 Mo, bd40/a31763 364 Mo chacun) — **aucune politique de purge**.

**Risques :**

| ID | Sévérité | Sujet |
|----|----------|-------|
| LIB-01 | P1 | Croissance disque jobs sans cleanup |
| LIB-02 | P1 | `_inbox` / `.avm-trash` sous `library_root` → indexation scanners externes |
| LIB-03 | P2 | Replace : move-then-copy (fenêtre sans album) ≠ bascule atomique doc architecture §6 |
| LIB-04 | P2 | `sanitize_segment` laisse `CON`/`NUL`/`PRN`/`COM1` (preuve 10A) |
| LIB-05 | P2 | Pas de troncature MAX_PATH / longueur |
| LIB-06 | P3 | PNG écrit sous nom `cover.jpg` |

---

### 2.5 Persistance

| Élément | Statut |
|---------|--------|
| Schéma versionné v1→v4 | **I+T** (`storage/database.py`, `schema.py`) |
| `PRAGMA foreign_keys=ON` | Oui |
| WAL / `busy_timeout` | **Absent** |
| Transactions multi-étapes archive | Commits ponctuels ; pas de transaction unique rip→publish |
| Checkpoints | Présents ; **reprise UI absente** |
| F-13 Reprendre | Bouton masqué / désactivé (`history_page.py` 193–198, 492–494) |
| Abandon | `mark_job_abandoned` — fichiers **non** supprimés |

**Anomalie confirmée (données labo, lecture seule) :**

```text
jobs: Completed=1, Failed=1, Cancelled=1, Ripping=1 (a31763… technical_test, finished_at NULL)
schema: 4
```

Impact : démarrage app **ne propose pas** de reprise/abandon automatique (contrairement à architecture.md §5.3) ; 06K peut DENY/WARN selon disc_id si job actif.

**Gravité :** **P0** pour une V1 qui promet robustesse après crash (exigence F-13).

---

### 2.6 Stabilité

| Code | Cause | Statut |
|------|-------|--------|
| `0xC0000409` | QThread parenté à la fenêtre détruit pendant rip | **Corrigé** 07B (`thread_lifecycle.py`) ; repro 5/5 |
| `0xC0000005` | GC pytest / Shiboken teardown | **Non corrigé** (07A) — harness |
| Fermeture pendant op | `closeEvent` + shutdown 12 s | **I** ; timeout → refuse quit |
| fre:ac orphelin si kill OS | Documenté 07B | P2 résiduel |

`closeEvent` : `main_window.py` 282–308.  
Navigation verrouillée pendant busy / tech test : `_on_busy`.

**Non vérifié 10A :** crash pendant rip archive long post-07B (interdit).

---

### 2.7 UX / UI

| Surface | Maturité |
|---------|----------|
| Shell 4 sections + rail Brume pastel | I · captures 08E · **visuel utilisateur non signé** |
| Wizard W1–W5 | I · tests 06O/06L · stepper **horizontal** (écart 08E P2) |
| Bibliothèque QML | I · bridge intact · repli Widgets |
| Historique | I · abandon OK · Reprendre honnêtement indisponible |
| Paramètres | I · freaccmd / biblio / eject / mode QML |
| Accessibilité | AccessibleName nombreux ; tab order smoke only |
| Erreurs FR | Taxonomie 06G + messages doublons 06K |
| Fenêtre hors écran | **Pas** de `saveGeometry` / restore — **non traité** |
| Validation visuelle 08E | **EN ATTENTE** → **P0 process** avant « V1 UX » |

Écarts 08E résiduels : backdrop-filter approximé ; barre « Interface classique… » ; intensité voile QML.

---

### 2.8 Performance

| Mesure / constat | Source | Gravité |
|------------------|--------|---------|
| Hardlink staging/inbox vs copy | 06G-P banc | OK |
| Publish C = copie (sécurité > perf) | 06G-P1 | Accepté |
| `list_releases(..., limit=500)` | `library_bridge.py` 48 | P1 collections >500 |
| Refresh biblio sync (décodage pochettes) | Bench agent ~5–6 s / 500 albums synthétiques | P1 |
| Jobs 1,5 Go retenus | Mesure 10A | P1 disque |
| Decode intégral ~2 s / album 17 pistes | 06G-P | OK attendu |

---

### 2.9 Sécurité

| Contrôle | Statut |
|----------|--------|
| freaccmd via argv liste (pas shell) | OK |
| SQL paramétré | OK |
| Gate anti-placeholders D-012 | OK |
| User-Agent MusicBrainz | OK (`musicbrainz_client.py`) |
| Sanitize caractères Windows `<>:"/\|?*` | Partiel — **pas** noms réservés |
| Lecture pochette : tout `Path.is_file()` | Pas de jail sous library_root — **risque plausible** chemin absolu arbitraire |
| `urlopen` sans limite taille explicite | Risque DoS mémoire plausible (P2) |
| Permissions fichiers créés | Défauts OS — non audités |
| Dépendances | Non pinnées (`PySide6>=6.6`, etc.) — P2 supply-chain |
| Secrets / télémétrie | Aucune télémétrie (conforme) |

---

### 2.10 Distribution

| Livrable attendu V1 | Présent ? |
|---------------------|-----------|
| Exécutable autonome (PyInstaller/Nuitka/…) | **Non** |
| Installateur / désinstallateur | **Non** (fre:ac a le sien ; AVM non) |
| Icône `.ico` multi-résolution | **Non** (concepts JPG 08C seulement) |
| Bundle DLLs Qt / discid / fre:ac | **Non** — fre:ac = dépendance système séparée (H-04) |
| Notices licences (GPL-3 AVM, GPL-2 fre:ac, Qt, fonts OFL, libdiscid) | **Incomplet** pour distribution |
| Lanceur quotidien | `Lancer-AudioVideoManager.bat` (06D) — **dev/labo** |
| CI build artifacts | **Absent** (pas de `.github/workflows`) |

**P0 bloquant** pour « V1 distribuable ».

---

### 2.11 Qualité

| Élément | Constat |
|---------|---------|
| Modules tests | 31 |
| Domaine (échantillon 10A) | PASS + **EXIT=0** |
| UI | Assertions souvent PASS puis process **3221225477** (`0xC0000005`) — 07A |
| CI | **Aucune** |
| Couverture code | Non mesurée |
| Logs | `%LOCALAPPDATA%/…/logs` + freac_* par job |
| Reproductibilité deps | Pas de lockfile |
| Distinction PASS ≠ succès process | **Documentée** 07A — **pas outillée** en CI |

---

### 2.12 Évolutivité (FFmpeg / HTTP / AVM-09)

| Point | Évaluation |
|-------|------------|
| Isolation ripper derrière `FreacCdRipper` | Favorable à un second backend |
| Vérif déjà capable d’appeler ffmpeg **en lecture** | Présent — **ne pas** confondre avec pipeline HTTP/FFmpeg produit |
| DVD | Stub clair D-010 |
| AVM-09 | Suspendu (08E / mandat 10A) — packaging/icône restent hors scope jusqu’à décision |

**Recommandation :** ne pas démarrer AVM-09 tant que P0 distribution + reprise + GO visuel + matrice rip multi-CD ne sont pas arbitrés.

---

## 3. Cas limites

| Cas | Comportement observé / code | I | T | H |
|-----|-----------------------------|---|---|---|
| Absence de CD / tray open | `DiscError` → RuntimeError identify/TOC | Oui | Partiel | Partiel |
| Éjection pendant rip | Non spécialisé ; fre:ac échoue → Failed | Partiel | — | — |
| CD remplacé après identify | `DiscMismatchError` relecture TOC | Oui | Oui | — |
| Fichiers verrouillés (dest ouverte) | `OSError` publish → rollback tenté | Partiel | — | — |
| Disque plein | Pas de pré-check `disk_usage` | **Non** | — | — |
| Noms invalides Windows | Sanitize partiel ; réservés OK non | Partiel | — | — |
| Doublons / réarchivage | 06K gates | Oui | Oui | Partiel |
| Fenêtre hors écran | Pas de géométrie persistée | **Non** | — | — |
| Interruption / Annuler | Cancel event + terminate fre:ac | Oui | Partiel | Partiel |
| Fermeture pendant extraction | closeEvent + wait 12 s (07B) | Oui | Oui synthétique | Crash réel pré-07B documenté |
| freaccmd absent | Message Paramètres / Failed | Oui | Oui | Oui |

---

## 4. Registre des risques

### 4.1 Anomalies confirmées

| ID | Sévérité | Confiance | Preuve | Impact | Correction recommandée | Non-régression |
|----|----------|-----------|--------|--------|------------------------|----------------|
| C-01 | **P0** | Haute | Aucun `.spec`/installer ; 06D explicite « pas d’exe » | Impossible de distribuer V1 | Mandat packaging + notices licences | Smoke install machine propre |
| C-02 | **P0** | Haute | `history_page` Reprendre disabled ; arch.md §5.3 non tenu ; job `a31763` Ripping | Perte de reprise après crash ; états incohérents | Reconciliation démarrage + abandon/reprise zone A | Test DB seed unfinished → dialog |
| C-03 | **P0** | Haute | 07A + politique 10A | CI/dev croit à un échec métier | Harness UI sous-process / juger JUnit | Suite fichier-par-fichier rc=0 |
| C-04 | **P0** | Haute | AVM-08E « EN ATTENTE » | Branding V1 non validé | Signature visuelle mandant | Checklist captures 820–max |
| C-05 | **P0** | Haute | Roadmap 06C rip multi ; labo 1 Completed | Promesse archive fragile | Matrice rip ≥3 CD + 1 lecteur secondaire si dispo | Procédure validation signée |
| C-06 | P1 | Haute | `_record_release` hardcode weak_ok | Catalogue menteur | Persister vrais `flac_ok` / rip_check | Test assert DB = report |
| C-07 | P1 | Haute | `flac_decode` skip = ok | Intégrité affaiblie sans ffmpeg | Exiger outil en V1 **ou** flag config bloquant | Test absence outil → Failed configurable |
| C-08 | P1 | Haute | Jobs 1,5 Go ; pas de purge | Remplissage disque | Retention jobs + UI nettoyage | Test quota / cleanup |
| C-09 | P1 | Haute | `limit=500` + refresh sync | UI inutilisable grandes collections | Pagination async + miniatures | Bench N=500/2000 |
| C-10 | P1 | Haute | Replace UI off | Feature D-009 incomplète UX | Dialog confirm Replace | test_ui + publish |
| C-11 | P1 | Haute | `sanitize` CON/NUL | Dossiers illisibles / erreurs CreateFile | Deny-list réservés | Paramétrisé noms réservés |
| C-12 | P2 | Haute | TOC `seconds` prioritaire | Warnings durée bruités | Prefer `sectors` | Queen piste 17 |
| C-13 | P2 | Haute | User-Agent 0.4.0 vs 0.5.0 | Politesse MB / debug | Unifier version | Grep versions |
| C-14 | P2 | Haute | Identify sans cancel | Fermeture lente identify | Event cancel / timeout | Test shutdown |
| C-15 | P2 | Haute | Pas `busy_timeout`/WAL | Contournement locks futurs | PRAGMA au connect | test concurrent read |
| C-16 | P3 | Haute | PNG→`cover.jpg` | Confusion lecteurs | Convertir JPEG | test mime |

### 4.2 Risques plausibles (non prouvés bout-en-bout)

| ID | Sévérité | Hypothèse | Indices |
|----|----------|-----------|---------|
| P-01 | P1 | Échec mid-Replace laisse bibliothèque vide brièvement / restore trash foireux | `publish.py` move puis copy |
| P-02 | P1 | Crash entre publish FS et `_record_release` → album orphelin hors doublons | Ordre archive_job |
| P-03 | P2 | Scanners Plex/foobar indexent `_inbox` | Emplacement sous library_root |
| P-04 | P2 | `cover_path_or_url` fichier absolu hors sandbox | `Path.is_file()` sans root check |
| P-05 | P2 | Timeout 12 s insuffisant fre:ac bloqué | 07B P3 |
| P-06 | P2 | Deps non pinnées → break PySide6 mineur | `pyproject.toml` |
| P-07 | P3 | Éjection fre:ac timing (fin vs piste) | Flag `--eject` non H |

### 4.3 Non vérifiés (matériel / mandat)

| ID | Sujet | Pourquoi |
|----|-------|----------|
| U-01 | Rip archive multi-CD post-07B | Interdit 10A |
| U-02 | Éjection / tray open mid-rip | Matériel |
| U-03 | Lecteurs multiples simultanés | H-02 MVP un lecteur |
| U-04 | AccurateRip | I-02 ouvert |
| U-05 | Désinstallation Windows AVM | Pas d’installeur |
| U-06 | Accessibilité lecteur d’écran réel | Smoke AccessibleName seulement |
| U-07 | Débit réseau MB rate-limit production | Labo partiel |
| U-08 | Crash rip long post-07B | Non rejoué |

---

## 5. Critères GO / NO-GO V1

### 5.1 Définition « V1 distribuable » (retenue pour cet audit)

Produit installable par un utilisateur non développeur sur Windows 10/11 x64, capable d’archiver des CD audio en FLAC identifiés dans une bibliothèque durable, avec états cohérents après interruption, sans dépendance à un clone git + `.venv`.

### 5.2 Checklist

| Critère | Seuil | Statut 10A |
|---------|-------|------------|
| Packaging + désinstallation documentée | Exe ou MSI/Inno + fre:ac prereq clair | **NO-GO** |
| Licences bundlées | Notices AVM+Qt+fre:ac+fonts+discid | **NO-GO** |
| Icône fenêtre / raccourci | `.ico` appliqué | **NO-GO** |
| Reprise / réconciliation jobs | F-13 ou abandon auto au start | **NO-GO** |
| Codes sortie tests CI | rc=0 fiables ou JUnit gate | **NO-GO** |
| Validation visuelle 08E | Signature mandant | **NO-GO** |
| Matrice rip réel ≥ N CD | N≥3 recommandé ; ≥1 + staging insuffisant pour « distribuable » | **NO-GO** |
| Gates D-011…D-015 / 06K | Préservés | **GO** |
| Publish non destructif zone C | Préservé | **GO** |
| Stabilité QThread fermeture | 07B | **GO** (sous réserve U-01) |
| F-08a minimal | Présent | **GO** avec réserve ffmpeg |
| DVD / AccurateRip / AVM-09 | Hors V1 OK | **N/A** |

### 5.3 Verdict

```text
NO-GO V1 DISTRIBUABLE
```

Le socine métier est **proche d’un MVP labo** (post-AVM-05…08E), pas d’une **release V1**.

---

## 6. Feuille de route AVM-10B+ (dépendances × criticité)

Ordre proposé — **aucune implémentation dans 10A**.

```text
AVM-10B  Réconciliation jobs + F-13 minimal (abandon/reprise staging)
    │      bloque : états orphelins, confiance crash
    ▼
AVM-10C  Harness qualité : pytest UI isolés + CI (GitHub Actions) + gate JUnit
    │      bloque : confiance régression avant packaging
    ▼
AVM-10D  Matrice validation CD réelle (multi-disques) + procédure signée
    │      // peut chevaucher 10E si rip déjà autorisé
    ▼
AVM-10E  Intégrité catalogue : flac_ok/rip_check réels ; politique ffmpeg V1 ;
    │      sanitize réservés ; pré-check espace disque ; retention jobs
    ▼
AVM-10F  Perf bibliothèque (async, pagination >500, thumbs)
    │
    ▼
AVM-10G  Packaging Windows (exe + installer + icône + licences + fre:ac prereq)
    │      = candidat AVM-09 si arbitrage « packaging = 09 »
    ▼
AVM-10H  GO visuel 08E (bloquant branding) — peut être en parallèle dès maintenant
    │
    ▼
AVM-10I  Replace UI confirmé · géométrie fenêtre · polish P2/P3
    │
    ▼
[GO V1]  puis seulement arbitrage AVM-09 élargi / FFmpeg-HTTP / AccurateRip
```

| Mandat | Entrées | Sorties | Dépend de |
|--------|---------|---------|-----------|
| **10B** | Job `a31763`, checkpoints, staging 06F | Dialog start ; abandon ; reprise `staged_flac_files` | — |
| **10C** | 07A | CI verte rc fiables | — (// 10B) |
| **10D** | Autorisation rip | Rapport multi-CD signé | 10B recommandé |
| **10E** | C-06…C-11 | Intégrité/FS durcis | 10B |
| **10F** | Bench 500 | Biblio scalable | 08E bridge |
| **10G** | 10C+10D+10E | Artefact installable | 10C, 10D, 10E, **10H** |
| **10H** | Captures 08E | GO/NO-GO visuel | Utilisateur |
| **10I** | Backlog P2 | Polish | Post-GO technique |

**Interdits jusqu’à décision :** élargir scope FFmpeg encode / serveur HTTP ; migration QML wizard ; DVD.

---

## 7. Preuves complémentaires (10A)

### 7.1 Environnement

| Probe | Résultat |
|-------|----------|
| freaccmd list-drives | rc=0 · drive 0 ATAPI iHAS324 |
| discid import | OK |
| ffmpeg decode tool | `C:\Tools\ffmpeg\bin\ffmpeg.EXE` |
| SCHEMA_VERSION | 4 |
| Package version | 0.5.0 |
| Workflows CI | 0 |
| Fichiers `.ico` app | 0 |

### 7.2 SQLite utilisateur (lecture seule)

| state | count |
|-------|------:|
| Completed | 1 |
| Failed | 1 |
| Cancelled | 1 |
| Ripping | 1 |

### 7.3 Cartographie tests (31 modules)

`test_approval_fingerprint`, `test_archive_pipeline`, `test_archive_recovery_staging`, `test_cd_ripper`, `test_config`, `test_cover_cache`, `test_database`, `test_diagnostics_06g`, `test_disc_metadata`, `test_drives`, `test_duplicates_06k`, `test_edition_ranker`, `test_flac_integrity`, `test_freaccmd`, `test_hardlink_security_06gp1`, `test_history_06n`, `test_humanisation_06i`, `test_library_qml_08b`, `test_logging`, `test_musicbrainz_identify`, `test_perf_06gp`, `test_progress_labels`, `test_qthread_07b`, `test_rip_check`, `test_rip_job`, `test_ui_collision_replace_disabled`, `test_ui_design_06l`, `test_ui_library_history_06h`, `test_ui_shell`, `test_ui_w3_prefill`, `test_ux_06o`.

---

## 8. Arrêt obligatoire

Ce document constitue le **diagnostic** AVM-10A.  
**Aucune correction n’a été implémentée.**  
AVM-09 et FFmpeg/HTTP restent **suspendus** jusqu’à décision explicite du mandant.  
Prochaine étape attendue : arbitrage sur la feuille de route §6 (priorité suggérée **10H** // **10B** // **10C**).
