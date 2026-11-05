# Rapport de validation — AVM-04

**Date :** 2026-11-03  
**Version :** 0.4.0  
**Objectif :** identification automatique CD (libdiscid + MusicBrainz + Cover Art Archive) sans auto-approbation.

---

## Résultats

| # | Livrable | Statut |
|---|----------|--------|
| 1 | `libdiscid` / `python-discid` + diagnostic DLL | **OK** — `vendor/libdiscid/…/x64/discid.dll` ; `LibdiscidMissingError` + `diagnose_libdiscid()` |
| 2 | Client MusicBrainz (UA, rate-limit 1,1 s, erreurs) | **OK** — `musicbrainz_client.py` |
| 3 | Candidats édition (artistes, titres, durées, année, label, pays, cat#, barcode, MBIDs) | **OK** |
| 4 | Comparaison TOC vs medium ; ambiguïtés / rééditions | **OK** — `toc_match` exact/partial/mismatch |
| 5 | Cover Art Archive (aperçu URL, 404 → unavailable) | **OK** — `cover_art.py` |
| 6 | Préremplissage `DiscMetadata` + provenance + non-écrasement corrections manuelles | **OK** — `apply_lookup.py` |
| 7 | UI PySide6 sélection édition / pistes / correction | **OK** — `DiscMetadataDialog` |
| 8 | Aucune auto-approbation ; verrou AVM-03 conservé | **OK** — `approval` reste `Pending` |
| 9 | Tests mock réseau / erreurs / 0 / N candidats | **OK** — `tests/test_musicbrainz_identify.py` |
| 10 | Documentation limites / blocages | **OK** — ce fichier + [domain/disc-metadata.md](../domain/disc-metadata.md) §9 |

**Tests automatisés :** **52 passed** (38 AVM-03 + 14 AVM-04 mock MB/CAA/libdiscid).

**Contraintes respectées :** aucun rip réel dans ce mandat ; aucune publication zone C ; pas de DVD.

---

## Modules

| Module | Rôle |
|--------|------|
| `metadata/libdiscid_loader.py` | PATH / `add_dll_directory`, import `discid` |
| `metadata/toc_reader.py` | TOC réelle → `TocSnapshot` + Disc ID |
| `metadata/musicbrainz_client.py` | Lookup + scoring TOC |
| `metadata/cover_art.py` | Métadonnées CAA (URLs) |
| `metadata/apply_lookup.py` | Pipeline identify / apply (jamais Approve) |
| `ui/metadata_dialog.py` | Identifier · candidats · appliquer · Approuver manuel |

---

## Limites

1. **Mapping lecteur** : freaccmd expose un chemin SCSI (`1:0:0`) ; libdiscid attend une lettre (`D:`). Heuristique UI : dernière lettre du *designation* fre:ac, sinon périphérique par défaut libdiscid.
2. **Préremplissage unique** : 1 candidat MB → champs édition en `ambiguous` jusqu’à « Appliquer l’édition » (confirmation UI), puis `confirmed` — **jamais** `Approved` auto.
3. **CAA** : URLs d’aperçu uniquement ; téléchargement `cover.jpg` zone C reporté (phase bibliothèque).
4. **Offline** : fiche 100 % manuelle toujours possible (AVM-03).
5. **Pas d’invention** : champs absents de MB restent vides / `missing` ; `is_compilation` non déduit automatiquement.
6. **Rate limit** partagé MB + CAA (~1,1 s) — lookups lents en série.

---

## Blocages / hors scope

| Item | Note |
|------|------|
| Rip archive réel | Hors mandat ; gate Approved inchangée |
| Publication bibliothèque C | Phase roadmap suivante |
| DVD | D-010 |
| AccurateRip | Phase qualité |
| Submit Disc ID vers MB | Lien `submission_url` lu si dispo ; pas d’envoi auto |

---

## Preuve machine (TOC live, hors tests auto)

Lecture locale réussie précédemment : lecteur `D:`, Disc ID `DsXlPG1OQWhceSELb2Eiq5rx1wU-`, 17 pistes — valide le chargement DLL + TOC. Les tests CI/pytest **ne** touchent **pas** le lecteur ni le réseau MB réel.

---

## Critères d’acceptation AVM-04

| ID | Critère | Preuve |
|----|---------|--------|
| AC-MB1 | Disc ID depuis TOC réelle (ou mock injecté) | `toc_reader` + test vendor DLL |
| AC-MB2 | Lookup MB mock : 0 / 1 / N | `test_lookup_*` / `test_identify_*` |
| AC-MB3 | Erreurs réseau / 404 gérées | `test_lookup_network_error`, CAA 404 |
| AC-MB4 | Ambiguïté réédition signalée | multi-candidats + message |
| AC-MB5 | Pas d’auto-approve | `approval == Pending` + gate |
| AC-MB6 | Corrections manuelles conservées | `test_manual_correction_not_overwritten` |
| AC-MB7 | UI sélection édition | `DiscMetadataDialog` |
