# Rapport AVM-06C-F1 — Préremplissage métadonnées W3

**Date :** 2026-11-03  
**Version :** 0.5.0  
**Périmètre :** correctif ciblé wizard UI-1 (pas de rip, pas de refonte archive)

---

## Verdict

**Corrigé.** W3 « Vérifier et approuver » affiche à nouveau artiste, album, année, label, catalogue, pays et les 17 pistes après identification / sélection d’édition.

**Arrêt :** attendre validation mandant avant reprise AVM-06C (rip réel).

---

## Cause exacte

Flux nominal OK côté métier :

`IdentifyWorker` → `identify_disc` / `apply_release_candidate` → `DiscMetadata` en mémoire (`self._sheet`) → W2 affiche correctement.

Bug **uniquement UI** dans `_refresh_w3()` :

1. Seule la `QTableWidget` avait `blockSignals(True)`.
2. `edit_artist.setText(...)`, `edit_album.setText(...)`, etc. émettaient `textChanged` / `valueChanged`.
3. Ces signaux appelaient `_on_sheet_edited` → `_apply_form_to_sheet` **pendant** le peuplement.
4. À ce moment la table avait encore `rowCount() == 0` → `sheet.tracks = []`.
5. Les `setText` suivants lisaient une fiche déjà vidée → formulaire vide / pistes perdues.

**Repro confirmée (avant correctif) :** 17 pistes + « Greatest Hits » → après `_set_step(2)` → **0 pistes**, album `''`.

Ce n’était ni un mauvais objet métier, ni un échec MusicBrainz, ni A3.

---

## Correctif

Fichier : `audio_video_manager/ui/wizard/archive_wizard.py`

| Mesure | Détail |
|--------|--------|
| `_w3_loading` | Garde réentrance sur edit / apply |
| `blockSignals` | Sur **tous** les widgets formulaire W3 pendant le peuplement |
| Filet `_apply_form_to_sheet` | Refuse d’écraser des pistes existantes si la table est vide |
| `_advisory_warnings` | Conserve avertissements identify/TOC affichés en W3 (`apply_validation` réécrit sinon `sheet.validation_warnings`) |
| Changement d’édition | Si déjà sur W3, `_refresh_w3()` après apply candidat |

A3 / D-011…D-015 inchangés : pas d’auto-approve ; fingerprint toujours révoqué sur edit pertinent.

---

## Tests

Nouveau : `tests/test_ui_w3_prefill.py`

- W2→W3 préremplit édition + 17 pistes  
- Retour W3→W2→W3 conserve les données  
- Changement d’édition rafraîchit W3 (US vs CA)  
- Edit manuel après préremplissage  
- A3 : edit post-approve → Pending  

```text
python -m pytest
# 95 passed
```

---

## Limites

1. Les avertissements TOC d’identification sont affichés via `_advisory_warnings` (session UI), pas re-persistés dans `sheet.validation_warnings` après `apply_validation` — volontaire pour ne pas élargir le moteur de validation.
2. Aucun rip réel dans ce correctif.
3. Replace reste désactivé (AVM-06C préparation).

---

## Reprise AVM-06C

Après **GO** sur ce correctif : reprendre la checklist rip dans [`AVM-06C-VALIDATION-CD-REEL.md`](AVM-06C-VALIDATION-CD-REEL.md) (W3 prérempli → Approuver → autorisation rip).
