# Rapport de validation — AVM-05

**Date :** 2026-11-03  
**Version :** 0.5.0  
**Objectif :** pipeline archivage FLAC → bibliothèque définitive (zones A/B/C).

---

## Verdict

### **GO** pour un premier archivage réel **contrôlé**

Sous réserve de suivre la procédure utilisateur §8 (fiche Approved, Disc ID concordant, confirmation publish).  
**Aucun rip réel exécuté dans ce mandat** — couverture par staging injecté + tests auto.

---

## Livrables

| Élément | Statut |
|---------|--------|
| `mutagen` tags FLAC (album, artistes, titres, disc/track, date, label, cat., MB IDs) | **OK** |
| Pochette : téléchargement/validation, embed, `cover.jpg` | **OK** |
| Organisation D-005 (compilations, Disc N, sanitisation, collisions Skip/Rename/Replace) | **OK** |
| Vérification TOC/Disc ID avant extraction | **OK** |
| Pipeline staging → F-08a → tags → inbox B → publish C | **OK** |
| Publication non destructive + refus album incomplet | **OK** |
| SQLite v3 (mbid, collision, warnings, library_path, releases/tracks) | **OK** |
| UI PySide6 ArchiveWorker (thread) + confirmation publish | **OK** |
| Tests automatisés | **OK** — **72 passed** |
| Pas d’auto-approve / pas de DVD / pas de suppression destructive | **OK** |

---

## Modules

| Module | Rôle |
|--------|------|
| `library/tags.py` | mutagen write/read |
| `library/cover.py` | CAA/URL/fichier → octets validés |
| `library/paths.py` | layout zone C |
| `library/publish.py` | Skip / Rename / Replace+trash |
| `library/disc_match.py` | Disc ID + TOC vs fiche |
| `orchestration/archive_job.py` | pipeline + hooks `staged_flac_files` |
| `ui/archive_worker.py` | progression non bloquante |

---

## Tests (simulation)

`tests/test_archive_pipeline.py` — tags, match Disc ID, collisions, incomplet, publish, refus non-Approved, blocage mismatch.

Rip fre:ac **non** invoqué dans les tests (staging injecté).

---

## Limitations

1. Noms de fichiers fre:ac variables → heuristique numéro de piste ; rip réel à valider une fois.
2. Replace : bascule dossier + trash locale ; pas de transaction FS atomique multi-fichiers Windows.
3. F-08b reste faible (pas AccurateRip).
4. Inbox B toujours remplie ; publish C exige confirmation UI explicite.
5. Reprise mid-rip fre:ac non magique (doc architecture inchangée).

---

## Procédure utilisateur — premier archivage réel contrôlé

### Prérequis

1. Python venv + `pip install -e ".[dev]"` (mutagen inclus).
2. `freaccmd.exe` détecté ; `discid.dll` vendor OK.
3. CD audio dans le lecteur (lettre Win32, souvent `D:`).
4. Racine bibliothèque configurée (ex. `Music\AVM-Library`).

### Lancement

```bash
cd /chemin/AudioVideoManager
source .venv/Scripts/activate   # ou .venv\Scripts\Activate.ps1
python -m audio_video_manager
```

### Import d’un CD

1. **Rafraîchir détection** — freaccmd + lecteur OK.
2. **Ouvrir / éditer la fiche** → *Lire TOC + chercher MusicBrainz*.
3. Vérifier l’édition auto (préférence CA) ou appliquer une autre ; corriger si besoin (`is_compilation`, etc.).
4. **Approuver la fiche** (obligatoire — pas d’auto-approve).
5. Choisir politique **doublons** (Rename recommandé).
6. **Archiver CD → bibliothèque…** → lire l’aperçu chemins → **Oui** pour confirmer le publish.
7. Attendre progression (match Disc ID → rip → tags → inbox → C).
8. Contrôler le dossier album sous `library_root` + entrée SQLite `releases`/`jobs`.

### En cas d’échec

| Symptôme | Action |
|----------|--------|
| Disc ID ≠ fiche | Réinsérer le bon CD ou refaire la fiche |
| freaccmd absent | Réinstaller fre:ac CLI |
| Collision Skip | Choisir Rename/Replace ou autre dossier |
| Album incomplet | Rester en A/B ; ne pas forcer C |
| Annulation | Job `Cancelled`/`Interrupted` ; FLAC partiels non publiés |

### Mode test (sans bibliothèque)

Utiliser **Test technique (zone A)…** — jamais de zone C.

---

## GO/NO-GO checklist entrée archivage réel

| Critère | |
|---------|--|
| Pipeline + tests verts | Oui |
| Gate Approved + Disc match | Oui |
| Publish confirmé utilisateur | Oui |
| Non-écrasement silencieux | Oui |
| Rip réel déjà exécuté par l’agent | Non (volontaire) |

**GO** — premier rip archive réel autorisé **par l’utilisateur** selon §8.
