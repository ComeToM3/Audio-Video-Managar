# Rapport AVM-06I — Humanisation UX/UI et finition

**Date :** 2026-11-03  
**Version :** 0.5.0  
**Suite :** **146 passed** (≥ 136 préservés)  
**Arrêt :** attendre validation avant tout autre mandat

---

## Verdict

| Critère | Résultat |
|---------|----------|
| Pas d’identifiant matériel brut dans le parcours normal | **GO** |
| Titres réels en progression (mapping fiable) | **GO** |
| Pas de % inventé | **GO** |
| Bibliothèque avec miniatures | **GO** |
| Historique compréhensible + récupérables | **GO** |
| D-011…D-015 / Queen / jobs historiques | **Préservés** |
| Tests | **146 passed** |

**Recommandation : GO technique AVM-06I.**

---

## 1. Avant / après (preuves)

| Zone | Avant | Après |
|------|-------|-------|
| Combo lecteur | `0: ATAPI iHAS324   C (1:0:0)` | **`Lecteur CD/DVD (D:)`** (lettre Win32 unique) ou `Lecteur CD/DVD n°1` |
| Matériel brut | Visible | **Info-bulle** uniquement (`CdDrive.label()`) |
| Progression fre:ac | `Processing file: 3.flac` | **`Piste 3/17 — Killer Queen`** (titres fiche approuvée) |
| Titre inconnu | — | `Piste 9/17 — titre non déterminé` (honnête) |
| Disc ID W1 | `Disc ID : …` | `Référence technique du disque (pour diagnostic) : …` |
| freaccmd UI | « freaccmd introuvable » | « L’outil d’extraction est introuvable… » |
| Bibliothèque | Texte seul | **Miniatures** `cover.jpg` + fiche enrichie |
| Historique Failed | État brut + erreur technique | État FR + **« fichiers récupérables »** + résumé / détail séparé |

---

## 2. Lecteur optique

- `CdDrive.friendly_label(drive_letter)` — jamais d’invention de lettre.
- Lettre Windows via `list_cdrom_device_letters()` **seulement** s’il existe **un** CD-ROM.
- Multi-lecteurs → `Lecteur CD/DVD n°N` (index fre:ac + 1).
- Backend : `drive_number` / `designation` inchangés.

---

## 3. Progression musicale

Module `ui/progress_labels.py` :

- Parse `Processing file: N.flac`, `trackNN.flac`, `track N / M`.
- Mapping vers titres `sorted(sheet.tracks)` de la fiche **approuvée**.
- Barre de progression : mise à jour **uniquement** si une `fraction` réelle est fournie par fre:ac / pipeline (pas d’invention).

---

## 4. Bibliothèque / Historique

| Bibliothèque | Historique |
|--------------|------------|
| Icônes 56×56 depuis `cover.jpg` | États FR + badge récupérable |
| Pochette 120×120 en détail | Message user vs détail technique |
| Pistes « fichier manquant » | Bouton « Ouvrir les fichiers temporaires » |
| Recherche conservée | Modes « Archivage » / « Test technique » |

---

## 5. Accessibilité & finition

- Noms accessibles déjà posés (06H) conservés.
- Focus QSS inchangé / contrastes muted `#4A4A4A`.
- Info-bulles pour matériel et actions temporaires.
- Narrator : non automatisé ; libellés accessibles sur contrôles clés.

---

## 6. Tests ajoutés

`tests/test_humanisation_06i.py` + extensions `test_progress_labels` / `test_drives` :

- friendly_label, parse piste fre:ac, titres, fallback, humanize erreur, recoverable, cover path.

---

## 7. Limites

| Limite | Note |
|--------|------|
| Multi CD-ROM | Pas de lettre dans le libellé (évite erreur iHAS324 « C ») |
| fre:ac sans numéro de piste | Libellé générique « Extraction audio » |
| Miniatures | Lecture `cover.jpg` locale ; pas de re-téléchargement CAA |
| Narrator E2E | Manuel |
| Aucun rip réel dans ce mandat | Contraint |

---

## 8. Fichiers

| Chemin | Rôle |
|--------|------|
| `extraction/drives.py` | `friendly_label` |
| `ui/progress_labels.py` | Titres + humanize erreur |
| `ui/wizard/archive_wizard.py` | Lecteur FR, progression titres |
| `ui/sections/library_page.py` | Miniatures / fiche |
| `ui/sections/history_page.py` | Récupérables / libellés |
| `ui/sections/settings_page.py` | Libellé outil |
| `ui/main_window.py` | Messages test technique |
| `storage/catalog.py` | `files_recoverable` |
| `tests/test_humanisation_06i.py` | Régressions |
| `docs/ux/reports/AVM-06I-HUMANISATION-UX.md` | Ce rapport |

---

**Fin AVM-06I — arrêt obligatoire. Attendre validation explicite.**
