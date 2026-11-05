# 08 — Critères d’acceptation, tests et plan d’implémentation

## 1. Découpage d’implémentation (post-GO specs)

Conforme **A2** + **A8**.

| Étape | Contenu | Débloque |
|-------|---------|----------|
| **UI-0** | Shell 4 sections ; Paramètres ; masquer probes/test en Avancé | Nav propre |
| **UI-1** | Wizard W1–W5 branché AVM-05 ; pochettes ; A3 dirty ; messages FR | **AVM-06C rip réel** |
| **UI-2** | Historique jobs | Traçabilité |
| **UI-3** | Bibliothèque SQLite+exists | Consultation |
| **UI-4** | Polish a11y, textes, perf cover cache | Qualité |

**Premier rip réel contrôlé :** dès **UI-1** validé (pas besoin UI-2/3). Mandat séparé **AVM-06C**.

## 2. Critères d’acceptation UI-0

| ID | Critère |
|----|---------|
| AC-U0-1 | Lancement → section Archiver visible, pas de probes |
| AC-U0-2 | 4 sections accessibles ; &lt;900 px → tabs |
| AC-U0-3 | Test technique seulement sous Paramètres → Avancé |
| AC-U0-4 | Aucune mention DVD dans Archiver |

## 3. Critères d’acceptation UI-1 (wizard)

| ID | Critère |
|----|---------|
| AC-U1-1 | Stepper 5 étapes ; pas de saut avant |
| AC-U1-2 | W3 : Approuver appelle `approve_sheet` ; rip bloqué sinon |
| AC-U1-3 | Nav vers Bibliothèque puis retour : **garde** Approved (A3) |
| AC-U1-4 | Edit post-approve → Pending + message dirty |
| AC-U1-5 | Disc ID change (relire autre disque) → Pending |
| AC-U1-6 | W4 : mismatch Disc ID → pas d’extraction |
| AC-U1-7 | Publish exige confirmation explicite |
| AC-U1-8 | Progression : sous-étapes FR nommées |
| AC-U1-9 | W5 : ouvrir dossier album si succès |
| AC-U1-10 | Pochette affichée si CAA OK (A7) |
| AC-U1-11 | Tests auto gate AVM-03…05 toujours verts |
| AC-U1-12 | Aucun auto-approve |

## 4. Critères UI-2 / UI-3 (résumé)

| ID | Critère |
|----|---------|
| AC-U2-1 | Jobs Completed listés avec état FR |
| AC-U2-2 | Abandonner ne supprime pas zone C |
| AC-U3-1 | Releases SQLite + badge si dossier absent |
| AC-U3-2 | Ouvrir dossier Explorateur |

## 5. Tests à prévoir (implémentation)

| Type | Exemples |
|------|----------|
| Unit / integration existants | Ne pas casser `test_archive_pipeline`, metadata, ranker |
| Nouveaux tests UI-logique | Fingerprint A3 ; mapping collision ; translation progress |
| Smoke manuel UI-1 | Parcours Queen GH simulé staging **ou** rip 06C |
| Non-régression | Test technique toujours isolé zone A |

Pas de rip réel dans la phase code UI-0/UI-1 automatisée (staging injecté OK).

## 6. Checklist AVM-06C (rip réel — après UI-1)

1. Wizard UI-1 livré + AC-U1-* OK.  
2. CD connu (ex. Queen GH) ; fiche Approuvée via wizard.  
3. Archiver avec publish confirmé.  
4. Vérifier FLAC tags, cover.jpg, chemins C, job SQLite.  
5. Rapport validation 06C.

## 7. Hors découpage

DVD, AccurateRip, i18n EN, lecteur audio, auto-approve.
