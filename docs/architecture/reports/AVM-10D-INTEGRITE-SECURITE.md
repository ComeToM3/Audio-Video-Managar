# Rapport AVM-10D — Intégrité, sécurité des données et fiabilité de publication

**Date :** 2026-11-03  
**Version produit :** 0.5.0  
**Précédents :** AVM-10A (NO-GO V1) · 10B · 10C · **10C.2 GO** (fixtures Qt)  
**Autorisation :** 10D ouvert ; V1 globale reste **NO-GO** jusqu’aux mandats restants.  
**Arrêt :** ne pas engager AVM-10E sans validation explicite de ce rapport.

---

## Verdict

| Critère GO 10D | Résultat |
|----------------|----------|
| Aucune perte silencieuse (sources / job / trash) | **GO** |
| Aucun état de vérification mensonger (`flac_ok` / `rip_check_status`) | **GO** |
| Aucune publication partielle présentée comme réussie | **GO** |
| Conservation des fichiers récupérables (pas de purge auto) | **GO** |
| Replace silencieux | **Impossible** (désactivé sauf `allow_replace` explicite) |
| Rip physique / mutation archives Queen | **Non entrepris** |

**Verdict technique AVM-10D : GO** (correctifs minimaux + tests reproductibles).  
La V1 distribuable reste **NO-GO** (mandats 10E+ / rip réel / packaging hors scope).

---

## 1. Matrice avant / après (risques 10A → 10D)

| ID 10A | Risque | Avant | Après 10D |
|--------|--------|-------|-----------|
| C-06 | `_record_release` hardcode `flac_ok=1`, `weak_ok` | Catalogue menteur | Persistance des contrôles **réels** (`flac_ok` structurel + `rip_check_status` avec `decode=…`) |
| FFmpeg | `decode` absent → `ok=True` | Succès fictif | `attempted=False`, `ok=False` ; warn V1 ; blocage si `AVM_REQUIRE_FLAC_DECODE=1` |
| C-11 | `sanitize` laisse `CON`/`NUL`/`PRN`/`COM1` | CreateFile cassé | Deny-list réservés + préfixe `_` ; titres musicaux préservés |
| Disque plein | Pas de pré-check | Échec mid-write opaque | `preflight_archive_paths` jobs+library, marge ×1.15, volumes distincts |
| Publish | Replace possible via API | Atomicité douteuse | `allow_replace=False` par défaut ; UI Replace déjà inaccessible |
| Rollback partiel | Fichiers écrits annulés | OK | + suppression dossier album vide ; sources intactes |
| Chemins longs | Non signalés | Risque MAX_PATH | Avertissement aperçu si ≥240 caractères |

---

## 2. Vérification FLAC — garanties réelles

| Couche | Exécution | Persistance catalogue | Effet pipeline |
|--------|-----------|----------------------|----------------|
| F-08a structurelle | Toujours | `flac_ok=1/0` (jamais 1 si échec) | **Bloquant** si échec |
| Décodage intégral (ffmpeg) | Si outil trouvé | `…;decode=ok\|failed\|not_run` | Échec CRC **bloquant** ; absence = warn (défaut) ou **bloquant** si `AVM_REQUIRE_FLAC_DECODE=1` |
| F-08b faible | Après F-08a | préfixe `weak_ok` / `weak_warn` / `failed` | Aligné `evaluate_rip_check` |
| AccurateRip | Non | — | Hors V1 (interdit) |

**Exemple honnête sans ffmpeg :** `flac_ok=1`, `rip_check_status=weak_ok;decode=not_run`  
**Interdit désormais :** `weak_ok` nu hardcodé.

Modules : `verification/track_status.py`, `verification/flac_decode.py`, `orchestration/archive_job.py::_record_release`.

---

## 3. Politique FFmpeg (pas de feature produit)

| Situation | Comportement V1 |
|-----------|-----------------|
| ffmpeg absent | Avertissement utilisateur ; catalogue `decode=not_run` ; publish autorisé si F-08a OK |
| `AVM_REQUIRE_FLAC_DECODE=1` + absent | **Échec** avant publish |
| ffmpeg présent + CRC fail | **Échec** ; job Failed ; FLAC staging/job conservés |
| Encode / HTTP / AVM-09 | **Non ajoutés** |

---

## 4. Chemins Windows

`metadata/path_preview.py::sanitize_segment` :

- Caractères interdits `<>:"/\|?*` + contrôles
- Réservés : `CON`, `PRN`, `AUX`, `NUL`, `COM1–9`, `LPT1–9` (avec ou sans extension)
- Strip trailing `.` / espaces
- Avertissement chemins ≥240 caractères dans l’aperçu

---

## 5. Espace disque

`library/disk_space.py` :

- `MARGIN_RATIO = 1.15`, plancher 64 MiB
- Estimation ~55 MiB/piste × 2 copies (même volume) ou ×3 (volumes distincts)
- Appel `preflight_archive_paths` en tête de `run_archive_job` (jobs + library)
- Échec → aucun rip/publish ; message explicite

---

## 6. Publication & récupération

| Règle | Statut |
|-------|--------|
| Zone C = copie indépendante (`independent=True`) | Conservé |
| Hardlink inbox/staging OK ; pas vers C | Conservé |
| Refus écrasement si cible existe | Conservé |
| Album incomplet → pas de publish | Conservé |
| Rollback fichiers écrits + rmdir album vide | Renforcé |
| Replace UI | Toujours désactivé (06C) |
| Replace API | Refusé sauf `allow_replace=True` |
| Suppression auto originaux / Queen / jobs | **Aucune** |
| 06K / 07B / 10B / 10C.2 | Préservés |

---

## 7. Tests reproductibles

```bash
python -m pytest tests/test_integrity_10d.py -q -o addopts=-q
python scripts/run_tests_ci.py --domain-only \
  --junit-dir .ci/avm10d-junit \
  --report .ci/avm10d-domain-results.json
```

| Scénario (`test_integrity_10d`) | Attendu |
|----------------------------------|---------|
| Noms `CON`/`NUL`/… | Segment préfixé `_` |
| ffmpeg absent | `ok=False`, `decode=not_run` en DB |
| Disque plein (mock) | Failed, source intacte |
| `AVM_REQUIRE_FLAC_DECODE` sans outil | Failed |
| FLAC corrompu | Failed, 0 release |
| Replace défaut | Refusé, ancien intact |
| Copie interrompue (ENOSPC) | RuntimeError rollback, sources OK, 0 FLAC partiel |
| Publish pipeline existant + hardlinks | Régression OK |

**Orchestrateur domaine local :** `OVERALL: GO` · **168** tests · 0 fail · 0 native (`.ci/avm10d-domain-results.json`).

---

## 8. Risques résiduels

1. Remplissage disque **entre** précontrôle et copie — course possible ; rollback mitige la zone C.
2. Replace même avec `allow_replace` n’est pas transactionnel NTFS (trash + copie) — d’où le défaut off.
3. Estimation 55 MiB/piste peut sous/sur-estimer selon compression FLAC réelle.
4. Lignes catalogue historiques (pré-10D) peuvent encore contenir `weak_ok` nu — pas de migration rétroactive des archives Queen (interdit).
5. Pas de rip physique ni campagne multi-CD dans ce mandat.

---

## 9. Fichiers touchés

| Fichier | Rôle |
|---------|------|
| `verification/flac_decode.py` | Pas de succès fictif ; `require_flac_decode()` |
| `verification/track_status.py` | Composition catalogue honnête |
| `orchestration/archive_job.py` | Disk preflight ; politique decode ; `_record_release` réel |
| `metadata/path_preview.py` | Réservés Windows + warn MAX_PATH |
| `library/disk_space.py` | Précontrôles |
| `library/publish.py` | Guard Replace ; rollback dossier vide |
| `tests/test_integrity_10d.py` | Non-régression 10D |
| `tests/test_diagnostics_06g.py` / `test_archive_pipeline.py` | Alignés |
| `scripts/run_tests_ci.py` | Inclut `test_integrity_10d` |

---

## 10. Suite

| Lot | Statut |
|-----|--------|
| AVM-10C.2 | GO (prérequis) |
| **AVM-10D** | **GO** technique |
| **AVM-10E** | **Suspendu** — attendre validation humaine |
| V1 distribuable | **NO-GO** global |

---

**Fin du rapport AVM-10D — verdict GO intégrité / publication (sans rip physique).**
