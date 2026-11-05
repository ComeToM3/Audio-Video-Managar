# Rapport AVM-04B — Identification réelle CD

**Date :** 2026-11-03  
**Disque :** présent dans le lecteur (pas d’éjection, pas de rip, pas de publish)  
**Verdict AVM-05 :** **GO** (sous réserve sélection manuelle d’édition + `is_compilation`)

---

## 1. Synthèse

| Contrôle | Résultat | Nature |
|----------|----------|--------|
| TOC + Disc ID stable | **OK** `DsXlPG1OQWhceSELb2Eiq5rx1wU-` · 17 pistes | **Réel** |
| MusicBrainz lookup | **OK** · 2 candidats Queen *Greatest Hits* (US 1991 / CA 1992) | **Réel** |
| Correspondance TOC | `partial` (piste 17 : TOC 262000 ms vs MB 258733 ms) | **Réel** |
| Cover Art Archive | **OK** pochette front pour les 2 releases | **Réel** |
| Prefill / sélection / corrections | **OK** · approval reste `Pending` | **Réel** (pipeline app) |
| Mapping fre:ac ↔ libdiscid | **Anomalie corrigée** (heuristique `C:` fausse → Win32 `D:`) | **Réel** + correctif |
| Gate anti-rip non approuvé | **OK** `ApprovalError` | **Réel** |
| Suite pytest | **54 passed** | **Simulation** (mocks réseau) |

---

## 2. Résultats réels — TOC / identité

| Champ | Valeur |
|-------|--------|
| libdiscid | OK · DLL `vendor/libdiscid/…/x64/discid.dll` |
| Périphérique | `D:` (défaut = explicite) |
| Disc ID | `DsXlPG1OQWhceSELb2Eiq5rx1wU-` (**identique** AVM-04) |
| Pistes | 17 (1…17) |
| Offsets (secteurs) | 150, 9300, 22932, 39207, 52782, 75047, 94282, 107985, 120862, 133140, 152240, 168110, 180740, 201262, 218417, 234235, 247390 |
| Durées TOC (ms, via `seconds`) | 122000 … 262000 (17 valeurs) |
| Submission URL | présente (`musicbrainz.org/cdtoc/attach?id=…`) — **non soumise** |

---

## 3. Résultats réels — MusicBrainz

Appel applicatif : `lookup_releases_by_discid` (User-Agent AVM, rate-limit).

| | |
|--|--|
| `raw_release_count` | 2 |
| Ambiguïté | **Oui** — sélection manuelle obligatoire |
| Message | `2 éditions candidates — sélection manuelle requise (rééditions / pays / labels possibles).` |

### Candidat 1 — US 1991

| Champ | Valeur |
|-------|--------|
| MBID | `aceaf449-ca32-443d-af49-993aeb5a56a7` |
| Titre / artiste | Greatest Hits / Queen |
| Date / pays | 1991 / US |
| Label / cat. | Hollywood Records / `HR 61265-2` |
| Barcode | `720616126528` |
| Pistes | 17 (ex. *We Will Rock You*, *We Are the Champions*, …) |
| `toc_match` | **partial** — note : piste 17 TOC 262000 vs MB 258733 ms |
| CAA | **confirmed** — front + thumb 500 |

### Candidat 2 — CA 1992

| Champ | Valeur |
|-------|--------|
| MBID | `4662a6ff-34e5-462f-bac0-584ac29cfd4d` |
| Titre / artiste | Greatest Hits / Queen |
| Date / pays | 1992 / CA |
| Label / cat. | Hollywood Records / `CD 61265` |
| Barcode | `720616126528` (identique) |
| Pistes | 17 · même écart piste 17 |
| `toc_match` | **partial** |
| CAA | **confirmed** — front + thumb 500 (image distincte) |

**Pas d’invention :** les deux éditions restent candidates ; l’app n’en choisit aucune automatiquement.

---

## 4. Prefill DiscMetadata / verrou (réel, sans Approuver)

| Étape | Observation |
|-------|-------------|
| `identify_disc` multi | `approval=Pending` · titre vide · `album_title` trust=`ambiguous` |
| Après correctif warnings | message multi-éditions conservé dans `validation_warnings` |
| Appliquer candidat US | Queen / Greatest Hits / 1991 / US / cat HR 61265-2 / 17 pistes / cover confirmed · **toujours Pending** |
| Gate rip | `assert_can_start_archive_rip` → **bloqué** (Pending) |
| Correction manuelle cat. | `MANUAL-CAT` + `USER_CORRECTION` **conservée** après apply candidat CA |
| Pays après apply CA | `CA` mis à jour |
| Approuver sans `is_compilation` | **refusé** (champ `missing`) — cohérent D-011 |

---

## 5. Mapping fre:ac ↔ libdiscid

| Source | Observation |
|--------|-------------|
| freaccmd `--list-drives` | `0` · path SCSI `1:0:0` · designation `ATAPI iHAS324   C` |
| Ancienne heuristique UI | suffixe → **`C:`** (faux : « C » = variante modèle Lite-On) |
| Win32 `GetDriveTypeW` | **un seul** CD-ROM : **`D:`** |
| libdiscid | défaut et lecture = **`D:`** · Disc ID OK |

**Correctif AVM-04B :** `list_cdrom_device_letters` + `resolve_optical_device_for_discid` ; l’UI n’utilise plus le suffixe fre:ac quand un CD-ROM Win32 unique existe.

**Incertitude restante :** plusieurs lecteurs optiques → pas d’auto-choix (retour `None` + log) ; fre:ac reste index SCSI, libdiscid lettre Windows — pas d’égalité de chemin native.

---

## 6. Simulations vs réel

| Domaine | Type |
|---------|------|
| TOC, Disc ID, MB, CAA, prefill, gate, mapping | **Réel** (cette session) |
| `tests/test_musicbrainz_identify.py` (+ régressions 04B) | **Simulation** (fn injectées, pas de réseau) |
| Suite complète | **54 passed** (dont 2 tests régression mapping / warnings) |
| Rip / éjection / zone C | **Non exécutés** (contrainte) |

---

## 7. Anomalies corrigées

1. **Heuristique lecteur C:** → résolution Win32 `D:` (`toc_reader.resolve_optical_device_for_discid`, UI).
2. **Warnings MB effacés** par `apply_validation` → notes lookup réinjectées après validation (`apply_lookup.identify_disc`).

Aucune refonte architecturale.

---

## 8. Limitations

- `toc_match=partial` sur la dernière piste : écart durée TOC vs enregistrement MB (~3,3 s) — signalé, pas forcé en `exact`.
- Édition physique exacte (US vs CA) : **à trancher par l’utilisateur** (barcode commun).
- `is_compilation` non déduit de MB — saisie/confirmation manuelle avant Approuver.
- CAA : URLs d’aperçu seulement (pas de `cover.jpg` bibliothèque).
- Un seul lecteur optique sur cette machine ; multi-lecteur non prouvé ici.

---

## 9. Verdict GO/NO-GO → AVM-05

| Critère entrée AVM-05 (organisation / bibliothèque) | |
|------------------------------------------------------|--|
| Identification réelle Disc ID + MB opérationnelle | Oui |
| Ambiguïtés d’édition visibles et non auto-approuvées | Oui |
| CAA répond | Oui |
| Verrou rip sans Approuver | Oui |
| Mapping lecteur corrigé / documenté | Oui |
| Rip / publish hors scope respectés | Oui |

### **GO pour AVM-05**

Sous réserve produit inchangée : chaque archive exige encore choix d’édition + complétion fiche (`is_compilation`, etc.) + **Approuver** explicite avant rip.
