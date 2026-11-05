# 01 — Audit fonctionnel et UI (état v0.5.0)

## 1. Architecture UI actuelle

```text
QApplication
└── MainWindow (scroll vertical unique, ~780–900 px)
    ├── GroupBox « Outils détectés »     (freaccmd, SQLite, schéma)
    ├── GroupBox « Paramètres »          (chemins, FLAC, pays, auto-approve grisé)
    ├── GroupBox « Fiche DiscMetadata »  (statut + bouton dialog)
    ├── GroupBox « Extraction CD → FLAC» (lecteur, collisions, archive/test, progress, log)
    ├── GroupBox « Probes non destructifs» (stdout fre:ac brut)
    └── Boutons bas : Rafraîchir | Enregistrer config

Dialogues / workers
├── DiscMetadataDialog (modal) — identify MB, édition, pistes, Approuver
├── RipWorker (QThread) — test technique zone A
└── ArchiveWorker (QThread) — pipeline A→B→C
```

**Pas de navigation par sections.** Tout le produit tient dans une seule page technique + un dialogue dense.

## 2. Inventaire des composants PySide6

| Zone | Widgets | Rôle |
|------|---------|------|
| Main | `QGroupBox`, `QFormLayout`, `QLabel`, `QLineEdit`, `QSpinBox`, `QCheckBox`, `QComboBox`, `QPushButton`, `QProgressBar`, `QTextEdit` | Config + déclenchement |
| Dialog fiche | Idem + `QTableWidget`, `QMessageBox` | Identification / correction / gate |
| Feedback | `QMessageBox` information/warning/question | Confirmations et résultats |
| Async | `QThread` + `Signal` progress/finished/failed | Non-blocage UI pendant rip/archive |

## 3. Capacités réellement opérationnelles (backend vs UI)

| Capacité | Backend | Exposition UI | Qualité UX |
|----------|---------|---------------|------------|
| Détection freaccmd / lecteurs | Oui | Oui (jargon) | Faible |
| TOC + Disc ID (libdiscid) | Oui | Via dialog « Identifier » | Moyen |
| MusicBrainz + sélection intelligente CA | Oui | Dialog | Moyen |
| CAA aperçu URL | Oui | Texte URL, pas d’image | Faible |
| Corrections manuelles + provenance | Oui | Formulaire dialog | Moyen |
| Approuver / Refuser / brouillon | Oui | Dialog | OK métier, jargon |
| Gate rip sans Approved | Oui | Bouton désactivé + erreurs | OK |
| Test technique zone A | Oui | Bouton + confirm | Confus vs archive |
| Archive A→tags→B→C | Oui | Un bouton + 1 confirm | Opaque |
| Match Disc ID avant rip | Oui | Invisible (implicite) | Risque surprise |
| Collisions Skip/Rename/Replace | Oui | Combo technique | Jargon |
| Parcourir bibliothèque C | Non | Absent | Manquant |
| Historique jobs / reprises UI | Partiel SQLite | Absent | Manquant |
| Wizard étapes | Non | Absent | Manquant |
| DVD | Non (D-010) | Absent | Futur |

## 4. Parcours utilisateur actuel (archivage CD)

```text
1. Lancer app
2. Comprendre freaccmd / schéma / probes (charge cognitive)
3. (Optionnel) régler chemins et pays CA
4. Ouvrir fiche → Identifier → éventuellement Appliquer édition
5. Compléter is_compilation etc. → Valider → Approuver
6. Fermer dialog → voir 1 ligne de statut fiche
7. Choisir collision → Archiver → confirmer long texte
8. Attendre barre + log technique
9. Lire QMessageBox résultat (chemins inbox/C)
10. Aller explorer le FS à la main pour vérifier
```

**Friction :** étapes 2–3 et 10 dominent ; le cœur métier (identifier → approuver → archiver) est noyé.

## 5. Problèmes d’ergonomie (constats)

### Navigation & structure
- Monolithe : paramètres, debug, archive et statut mélangés.
- Aucune vue « où en suis-je ? » (étape du pipeline).
- Dialog modal coupe le contexte (lecteur, bibliothèque).

### Terminologie
- `DiscMetadata`, `freaccmd`, `F-08a/F-08b`, `zone A/B/C`, `toc_match=partial`, `schema v3`.
- Boutons « Test technique » vs « Archiver » mal différenciés visuellement.

### Hiérarchie visuelle
- Probes fre:ac (debug) au même niveau que l’action principale.
- Paramètres avancés toujours visibles.
- Pas de hero / CTA unique « Archiver ce disque ».

### Surcharge informationnelle
- Logs bruts et chemins SQLite en permanence.
- Messages d’erreur métier corrects mais peu actionnables (« confiance=missing »).

### Feedback & confiance
- Pochette = URL texte, pas d’aperçu image.
- Progression = fraction générique, étapes non nommées pour l’humain.
- Succès = boîte de dialogue, pas de résumé « album publié ici » cliquable.
- Aucun historique des imports réussis dans l’app.

### Protections
- Gate et non-écrasement **présents** (à conserver).
- Test technique trop accessible à côté d’Archiver (risque de mauvais mode).

## 6. Synthèse audit

| Dimension | Note | Commentaire |
|-----------|------|-------------|
| Complétude métier CD | Bonne | Backend AVM-05 solide |
| Première archive réelle guidée | Faible | UI non conçue pour un néophyte |
| Évolutivité DVD | Neutre | Pas de place prévue dans la nav |
| Maintenabilité UI | Faible | 1 fichier main window dense |

**Conclusion :** prioriser une **réorganisation UX** (4 sections + parcours guidé) sans changer les règles D-011…D-015 ; le backend est prêt, l’interface ne l’est pas.
