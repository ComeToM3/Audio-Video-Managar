# Rapport AVM-06E — Audit intégrité, fiabilité et ergonomie

**Date :** 2026-11-03  
**Version :** 0.5.0  
**Base de preuves :** code, SQLite job `bd40…`, zone A (17 FLAC), rapports F1/F2/06C, **96 tests PASS**  
**Périmètre d’implémentation autorisé dans ce mandat :** correctif argv fre:ac uniquement  

---

## 1. Synthèse exécutive

| Domaine | Constat |
|---------|---------|
| **Fiabilité rip** | Cause F2 corrigée : `--pattern=<track>` (un jeton) + test de régression exact |
| **Pipeline métier** | Gates D-011…D-015 et D-009 solides ; publication non destructive OK |
| **Échec 06C** | Extractions audio **réussies** ; arrêt AVM sur returncode ≠ 0 **avant** F-08a/publish |
| **Zone A actuelle** | 17/17 FLAC passent F-08a + mapping 1…17 ; **récupérables** via staging |
| **UX** | Wizard compréhensible mais feedback d’erreur technique, W3 dense, stubs trompeurs si mal lus |
| **Refonte UI** | **Non entreprise** — propositions P1/P2 seulement |

**Arrêt :** aucune autre implémentation ; attendre arbitrages mandant.

---

## 2. Correctif appliqué (seul changement code)

| | |
|--|--|
| Fichier | `audio_video_manager/extraction/cd_ripper.py` |
| Avant | `--pattern`, `<track>` (2 jetons) → fre:ac traite `<track>` comme fichier → exit **-3** |
| Après | `--pattern=<track>` (1 jeton) |
| Compatibilité | Probe freaccmd 1.1.7 sans rip : **plus** de `File not found: <track>` |
| Test | `tests/test_cd_ripper.py::test_build_argv_pattern_equals_form_avm06c_f2` — argv exact |
| Suite | **96 passed** |

Aucun rip, aucune modification des FLAC `bd40…`, aucune publication.

---

## 3. Audit pipeline (intégrité)

### 3.1 Cartographie

```text
Lecteur → TOC/Disc ID → MB + ranker CA → fiche Pending
  → W3 Approuver (D-011) → fre:ac zone A → F-08a → tags/cover
  → inbox B → confirm publish → zone C (Skip/Rename/Replace)
  → SQLite jobs + checkpoints
```

### 3.2 Invariants vérifiés (code + preuves)

| Invariant | Statut | Preuve |
|-----------|--------|--------|
| Pas de rip sans `Approved` | OK | `assert_can_start_archive_rip` |
| Pas d’auto-approve | OK | D-015 ; checkbox grisée |
| Pas d’écrasement silencieux C | OK | `FileExistsError` + trash Replace |
| Album incomplet → pas de publish C | OK | `len(staged) != len(layout)` |
| Workdir rip non réutilisé non vide | OK | `create_job_workdir` / `FreacCdRipper.rip` |
| A3 fingerprint | OK | sync/revoke métier + tests |
| Pref pays = départage, pas preuve | OK | messages ranker / W2 |
| Replace UI sans confirm | Mitigé | radio désactivée (06C) |
| Test technique hors wizard | OK | Settings → Avancé |

### 3.3 Points de fragilité (fiabilité)

| ID | Gravité | Sujet | Cause | Impact |
|----|---------|-------|-------|--------|
| **R-01** | **P0** (corrigé) | argv `--pattern` | Confirmée F2 | Job Failed alors que FLAC OK |
| **R-02** | **P0** | `success = (returncode==0) and flacs` | Trop strict si fre:ac code ≠0 avec FLAC complets | Perte de parcours publish |
| **R-03** | P1 | stdout/stderr fre:ac non persistés | Logging | Diagnostic opaque (`avm.log` sans « File not found ») |
| **R-04** | P1 | Pas de reprise UI depuis zone A | R2 / UI-1 | Utilisateur doit re-rip ou outil staging manuel |
| **R-05** | P1 | F-08a = magic + STREAMINFO tête | By design F-08a faible | N’attrape pas corruption mid-stream / AccurateRip |
| **R-06** | P2 | `match_flacs` heuristique nom | Noms fre:ac variables | Risque mapping si pattern change |
| **R-07** | P2 | `.flac.temp` orphelins 0 o | fre:ac | Bruit FS ; pas lus par `*.flac` |
| **R-08** | P1 | Publish rollback partiel | Exception mid-copy | Trash Restore best-effort Windows |
| **R-09** | Info | Job Failed laisse FLAC | OK données | État SQLite ≠ réalité audio |

### 3.4 Erreurs « intégrité » — taxonomie

| Symptôme utilisateur | Distinction technique | Cas 06C |
|----------------------|----------------------|---------|
| « Intégrité » / échec archive | Souvent **returncode fre:ac** ou gate, pas F-08a | **returncode -3**, F-08a jamais atteint |
| FLAC invalide | F-08a `ok=False` | Non — 17/17 OK post-mortem |
| Mauvais mapping pistes | `match_flacs` / count mismatch | Non — `1.flac`…`17.flac` ordonnés |
| Lecture CD | TOC / DiscMismatch | Disc ID OK avant rip |
| État incohérent | SQLite Failed + fichiers valides | **Oui** — job Failed, zone A complète |

**Contrôle lecture seule post-06C :** `match_flacs_to_tracks` + `check_many` → **all_ok**, 44100 Hz / 2 ch / 16 bit.

### 3.5 Récupération après échec (état actuel)

- **Possible techniquement** : `run_archive_job(..., staged_flac_files=[...])` sans fre:ac.  
- **Pas exposé UI-1** (R2) — reprise = mandat / outil contrôlé.  
- Nouveau rip dans le même `rip/` : **refusé** (non vide) — correct anti-écrasement.

---

## 4. Audit UX / UI

### 4.1 Principes (Nielsen / WCAG — lecture qualitative)

| Principe | Observation |
|----------|-------------|
| Visibilité du statut | Stepper présent mais **non cliquable** ; progression W4 OK mais messages fre:ac bruts possibles |
| Correspondance monde réel | Termes FR globalement bons ; « Approved », Disc ID, ms en table = jargon |
| Contrôle utilisateur | Approuver explicite OK ; annulation rip OK ; pas de reprise claire après échec |
| Cohérence | 4 sections + 5 étapes alignés specs ; `metadata_dialog` legacy encore dans le package |
| Prévention erreurs | Gates métier OK ; Replace désactivé ; pattern fre:ac était un piège invisible |
| Reconnaissance > rappel | W2 montre édition ; W3 redemande beaucoup de champs |
| Flexibilité | Corrections manuelles OK (F1) |
| Design minimaliste | W3 dense (table 4 colonnes + chemins + erreurs) |
| Aide à la récupération | Échec = code technique `4294967293` peu actionnable |
| Accessibilité | Peu d’`AccessibleName` ; focus/clavier non audités en profondeur ; contrastes thème OK-ish |

### 4.2 Wizard (5 étapes) — frictions

| Étape | Problème | Gravité UX |
|-------|----------|------------|
| W1 Disque | OK ; « Relire » clair | Faible |
| W2 ID | Liste alternatives dense ; TOC/MB warnings techniques | Moyenne |
| W3 Approuver | Colonne « ms » ; état `Approved` EN ; erreurs validation verbeuses | Moyenne |
| W4 Extract | Échec = jargon returncode ; pas d’explication « fichiers peut‑être OK » | **Haute** (prouvé 06C) |
| W5 Terminé | Succès seulement si publish — bien ; échec peu guidant | Haute si échec |

### 4.3 Shell (4 sections)

| Section | Constat |
|---------|---------|
| Archiver | Principal — OK |
| Bibliothèque / Historique | Stubs honnêtes (« prochainement ») — OK si libellé reste clair |
| Paramètres | Test technique bien isolé ; chemin config raw dans toast |

### 4.4 Direction UI proposée (pas d’implémentation)

**Principes visuels :** conserver tokens verts `#0B6E4F` / fond `#F7F6F3` ; une action primaire par écran ; stepper avec états « fait / courant / à venir » en FR.

**Textes exemples :**

| Contexte | Aujourd’hui | Proposition |
|----------|-------------|-------------|
| Échec rip | `freaccmd returncode=4294967293` | « L’extraction s’est terminée avec un avertissement de fre:ac. Vérifiez les fichiers extraits avant de recommencer. » + détail technique repliable |
| État fiche | `État : Approved` | « Fiche approuvée — vous pouvez lancer l’archivage » |
| Table pistes | `ms` | « Durée » (mm:ss) |
| W4 | « Lancer l’archivage » | garder ; sous-texte « Le CD doit rester dans le lecteur » |
| Post-échec | (rien) | « Des fichiers sont peut‑être déjà dans le dossier temporaire. Ne relancez pas sans consignes. » |

**Composants :** bannière d’erreur avec actions « Voir le dossier temporaire » / « Réessayer » (réessayer = nouveau job) ; indicateur de confiance édition (départage CA) en une phrase non technique.

**Responsive :** tabs &lt;900 px déjà en place (AC-U0-2) — conserver.

**Accessibilité P2 :** labels buddy, ordre de tabulation W3, `QProgressBar` accessible name, contraste warnings.

---

## 5. Matrice d’anomalies

| ID | Gravité | Repro | Impact user | Cause | Correctif | Tests |
|----|---------|-------|-------------|-------|-----------|-------|
| A-01 | P0 | Confirmée | Archive « échouée » à tort | argv pattern | **Fait** `--pattern=` | argv exact |
| A-02 | P0 | Confirmée | Pas de publish | `rip.success` strict | Assouplir : si N FLAC + F-08a OK → continuer avec warning **ou** reprise staging | pipeline + mock rc=-3 |
| A-03 | P1 | Confirmée | Debug difficile | Pas de capture fre:ac I/O | Log fichier job `freac_stdout.txt` | unit mock |
| A-04 | P1 | Confirmée | Blocage après Failed | Pas UI reprise | Flux « Reprendre depuis fichiers extraits » (hors UI-2 si minimal) | staging inject |
| A-05 | P1 | Confirmée F1 | Formulaire vide | Signaux Qt | **Déjà corrigé F1** | test_ui_w3_prefill |
| A-06 | P1 | Observée | Confiance | Replace sans dialog | Rester off ou dialog explicite | UI |
| A-07 | P2 | Hypothèse | Mapping | Heuristique noms | Documenter pattern figé ; test noms fre:ac | match_flacs |
| A-08 | P2 | Observée | Bruit | `.flac.temp` | Ignorer / nettoyer en fin de succès seulement | — |
| A-09 | P2 | Observée | Lexique | EN / ms / codes | Pass FR UI | snapshots textes |
| A-10 | P2 | Observée | Legacy | `metadata_dialog` parallèle | Ne plus exposer ; déprécier | — |
| A-11 | P2 | Observée | a11y | Peu d’attrs accessibles | Pass a11y | manuel |
| A-12 | Info | Observée | État | Job Failed + FLAC OK | Alignement état / recovery | 06C reprise |

---

## 6. Plan priorisé

### P0 — Fiabilité bloquante

1. ~~Corriger `--pattern=<track>`~~ **FAIT (06E)**  
2. **Politique returncode** : ne pas jeter un rip complet uniquement sur code fre:ac négatif si count + F-08a OK (warning + continue) **ou** enchaîner reprise staging documentée pour job `bd40…`  
3. Persister stdout/stderr fre:ac dans le workdir job  

### P1 — Reprise AVM-06C

1. Mandat reprise **sans re-rip** : `staged_flac_files` des 17 FLAC zone A → tags → publish biblio test (Rename)  
2. Compléter `AVM-06C-VALIDATION-CD-REEL.md`  
3. Message W4/W5 d’échec actionnable (texte FR)  
4. Décision Replace : dialog confirm **ou** rester désactivé  

### P2 — UX / polish (pas UI-2…4 fonctionnels)

1. Lexique FR (durées, états fiche)  
2. Bannière erreurs / détails techniques repliables  
3. a11y basique W3  
4. Nettoyage référence `metadata_dialog` hors chemin principal  
5. Guide « que faire si échec » dans Paramètres → Aide courte  

---

## 7. Critères d’acceptation suggérés (prochains mandats)

| ID | Critère |
|----|---------|
| AC-E1 | argv contient exactement `--pattern=<track>` et aucun jeton `<track>` isolé |
| AC-E2 | Simulation fre:ac rc=-3 + 17 FLAC valides → pipeline atteint F-08a (ou reprise staging documentée) |
| AC-E3 | Job Failed affiche message FR + chemin zone A |
| AC-E4 | Reprise 06C : album publié sous `AVM-06C-Test-Library`, 17 FLAC tagués, `cover.jpg`, lecture externe |
| AC-E5 | Aucune régression suite pytest ; D-011…D-015 inchangés |

---

## 8. Hors scope respecté

- Pas de rip relancé  
- Pas de modification/suppression des FLAC `bd40…`  
- Pas de publish  
- Pas de refonte UI ni UI-2…4  
- Pas de DVD  

---

## 9. Décisions demandées au mandant

1. **Valider** le correctif `--pattern=<track>` (déjà dans le code).  
2. Choisir pour la reprise 06C : **A** staging des FLAC existants (recommandé) vs **B** re-rip complet.  
3. Arbitrer **A-02** (assouplir returncode) : oui / non / plus tard.  
4. Prioriser ou reporter le lot UX P2.

**Arrêt obligatoire** — aucune implémentation supplémentaire sans arbitrage.
