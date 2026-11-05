# Rapport AVM-10E — Validation réelle de l’archivage CD sous Windows

**Date :** 2026-11-03  
**Version produit :** 0.5.0  
**Précédent :** AVM-10D **GO** technique  
**Distribution V1 :** toujours **NO-GO** jusqu’à mandats restants  
**Arrêt :** ne pas engager AVM-10F sans validation explicite

---

## Verdict

| Critère GO 10E | Résultat |
|----------------|----------|
| Parcours réel **complet** (TOC→MB→rip→publish) | **NON EXÉCUTÉ** — en attente d’accord sur le protocole |
| Intégrité / publication cohérentes (preuve Queen lecture seule) | **GO partiel** (archive existante) |
| Absence de perte de données (campagne 10E) | **GO** (aucune mutation ; Queen intacte) |
| Protections doublons opérationnelles | **GO** (06K + gate `require_confirm` sur Disc ID Queen) |
| Fermeture Windows stable | **GO** (repris 10C.2 ; pas de nouveau rip UI ici) |

**Verdict AVM-10E : NO-GO** pour le critère « parcours réel complet validé ».  
Les preuves **lecture seule** et **fixtures** sont solides ; l’extraction physique et les interruptions volontaires n’ont **pas** été lancées (contrainte de sécurité du mandat).

---

## 1. Inventaire environnement

| Ressource | Preuve |
|-----------|--------|
| fre:ac | `C:\Program Files\freac\freaccmd.exe` (v1.1.7) |
| FFmpeg | `C:\Tools\ffmpeg\bin\ffmpeg.EXE` |
| Lecteur | `0` — ATAPI iHAS324 C (`1:0:0`) |
| SQLite prod | `...\AppData\Local\AudioVideoManager\avm.sqlite3` (110 592 o) |
| Archive Queen | `C:\Users\ComeToM3\Music\AVM-06C-Test-Library\Queen\Greatest Hits (1992)` |
| Espace Music | mesuré au moment de l’audit (voir `.ci` / shell) |
| Processus fre:ac orphelin | aucun `freaccmd.exe` / `freac.exe` listé |

**Disque actuellement dans le lecteur (TOC lecture seule) :**  
Disc ID `HKAtvzd2gALbaC2d4HONIWPCE0Q-` · **22** pistes · **≠** Queen (`DsXlPG1OQWhceSELb2Eiq5rx1wU-`).

---

## 2. Matrice exécuté / non exécuté

| # | Scénario | Statut | Preuve |
|---|----------|--------|--------|
| E1 | Lecteur CD détecté | **Exécuté** | freaccmd `--list-drives` |
| E2 | TOC / Disc ID (lecture) | **Exécuté** | disc 22 pistes présent |
| E3 | MusicBrainz + édition + approbation UI | **Non exécuté** | nécessite parcours UI + accord rip |
| E4 | Extraction fre:ac physique | **Non exécuté** | **protocole ci-dessous — accord requis** |
| E5 | F-08a / F-08b / decode sur rip neuf | **Non exécuté** | dépend E4 |
| E6 | Tags / pochette / publish / historique (nouveau) | **Non exécuté** | dépend E4 |
| E7 | Album simple physique | **Non exécuté** | CD 22 pistes disponible mais non ripé |
| E8 | Compilation physique | **Non testé** | pas de CD compilation confirmé |
| E9 | Multidisque physique | **Non testé** | pas de set physique |
| E10 | Queen 17 FLAC lecture seule | **Exécuté** | `.ci/avm10e-queen-readonly.json` |
| E11 | Doublons 06K / CD déjà archivé | **Exécuté** | gate `require_confirm` + tests pytest |
| E12 | Annulation / close pendant rip | **Non exécuté** | **accord requis** |
| E13 | Redémarrage / réconciliation 10B | **Partiel** | job `a31763…` Interrupted (historique) + tests 10B/10C |
| E14 | Récupération contrôlée staging | **Exécuté (fixture)** | `test_archive_recovery_staging` |
| E15 | Mesures ressources rip réel | **Non exécuté** | dépend E4 |
| E16 | UX Windows parcours complet | **Partiel** | stabilité close 10C.2 ; pas de rip UI observé en 10E |
| E17 | Fixtures intégrité 10D / Replace off | **Exécuté** | pytest domaine |

---

## 3. Queen — contrôle lecture seule (aucune mutation)

**Artefact :** `.ci/avm10e-queen-readonly.json` · `mutations: none`

| Contrôle | Résultat |
|----------|----------|
| Nombre FLAC | **17 / 17** |
| F-08a structurel | **tous OK** |
| Décodage FFmpeg | **tous OK** (≈ 2,9 s audit) |
| Tags titre/album | présents (0 manquant) |
| Pochette embarquée | présente sur les 17 |
| `cover.jpg` | présent (28 980 o) |
| Volume | ≈ **364 MiB** |
| Chemins vs SQLite | **0 fichier manquant** |
| `flac_ok` DB | 1 |
| `rip_check_status` DB | `weak_ok` **nu** (historique **pré-10D** — non modifié) |

Job historique de publication : `8e23e82d…` · `Completed` · `library_path` = dossier Queen.

---

## 4. Doublons (06K)

Réévaluation **sans écriture** avec le Disc ID Queen en base :

- **Gate :** `require_confirm`
- **Message :** réarchivage bloqué par défaut ; confirmation explicite requise ; **aucun écrasement silencieux**

Pytest : `test_duplicates_06k`, `test_ui_collision_replace_disabled` — PASS (Replace inaccessible).

---

## 5. Interruptions / réconciliation (sans provocation)

| Élément | Observation |
|---------|-------------|
| Job `a31763eed2ae423eb78ded45b125667a` | `Interrupted` — message 10B, « Fichiers non modifiés » |
| Job `c43af993…` | `Cancelled` utilisateur |
| Tests `test_reconciliation_10b/10c` | PASS |
| **Nouvel** arrêt pendant rip | **Non provoqué** (interdit sans accord) |

---

## 6. Protocole proposé — extraction & interruptions (ACCORD REQUIS)

Avant toute action destructive / rip, **attendre votre accord explicite**.

### 6.1 Bibliothèque de test isolée (obligatoire)

| Paramètre | Valeur proposée |
|-----------|-----------------|
| `library_root` | `C:\Users\ComeToM3\Music\AVM-10E-Test-Library` (à créer vide) |
| `jobs_dir` | `C:\Users\ComeToM3\AppData\Local\AudioVideoManager\jobs-10e` (nouveau) |
| Config temporaire | ne pas pointer vers `AVM-06C-Test-Library` (Queen) |
| Queen / jobs historiques | **lecture seule** — hors cible |

### 6.2 CD candidat

- Lecteur 0 contient aujourd’hui un CD **22 pistes**, Disc ID `HKAtvzd2gALbaC2d4HONIWPCE0Q-` (**pas Queen**).
- Confirmer si ce disque peut être archivé en bibliothèque 10E, **ou** insérer un autre CD « album simple ».

### 6.3 Étapes rip (après accord)

1. Lancer l’app avec chemins 10E isolés.  
2. Identifier (TOC → MusicBrainz → édition → approbation).  
3. Extraire fre:ac → vérifier F-08a / decode / F-08b.  
4. Publier (Rename only).  
5. Tracer : fichiers zone C ↔ SQLite ↔ UI Historique.  
6. Mesurer : durée, PIC mémoire process, espace libre avant/après, absence orphelins fre:ac.

### 6.4 Interruptions (après accord séparé)

Uniquement sur job **10E** (jamais Queen) :

| Test | Méthode | Interdit |
|------|---------|----------|
| Annulation UI | Bouton annuler mid-rip | Kill -9 / reset brutal |
| Fermeture fenêtre | close pendant rip → dialogue | Couper l’alimentation |
| Reprise | redémarrage app → dialogue 10B | Purge jobs |

### 6.5 Ce que vous devez répondre pour débloquer

1. **Accord rip** : oui/non + confirmation du CD (actuel 22 pistes ou autre).  
2. **Accord interruptions** : oui/non (sur lib 10E seulement).  
3. **Chemins isolés** : OK propositions §6.1 ou chemins alternatifs.

---

## 7. Anomalies classées

| ID | Sévérité | Description | Action |
|----|----------|-------------|--------|
| A1 | P3 | Catalogue Queen : `rip_check_status=weak_ok` sans suffixe `decode=` (pré-10D) | Ne pas migrer / ne pas toucher l’archive ; nouveaux publishes suivent 10D |
| A2 | P2 | Parcours rip physique non rejoué sous chemins isolés 10E | Bloqué jusqu’à accord protocole |
| A3 | P2 | Compilation / multidisque physiques | Non testés (pas de supports) |
| A4 | P3 | TOC actuel ≠ Queen — normal | Documenté |

**Aucune P0/P1** sur perte de données ou écrasement lors de cette campagne (rien n’a été écrit hors artefacts `.ci`).

---

## 8. Corrections minimales

**Aucune correction code** dans ce lot : les écarts GO tiennent à l’**absence d’exécution physique autorisée**, pas à un défaut démontré bloquant hors rip.

Correctifs éventuels post-rip (messages UX, perf) seront traités après la campagne autorisée.

---

## 9. Artefacts

| Chemin | Contenu |
|--------|---------|
| `.ci/avm10e-queen-readonly.json` | Audit Queen + TOC + doublons |
| `docs/architecture/reports/AVM-10E-VALIDATION-CD-WINDOWS.md` | Ce rapport |

---

## 10. Suite

| Lot | Statut |
|-----|--------|
| AVM-10D | GO (prérequis) |
| **AVM-10E** | **NO-GO** (parcours réel complet non exécuté) |
| **AVM-10F** | **Suspendu** |

Dès accord sur §6, reprise 10E phase B (rip + mesures) et mise à jour du verdict.  
*(Interruptions : toujours non autorisées — décision phase B.)*

---

## 11. Phase B — Étape 1 (préparation) — STOP avant extraction

**État :** environnement isolé **créé** · extraction physique **non démarrée** ·  
**`STOP : WAIT_EXPLICIT_CONFIRMATION_BEFORE_PHYSICAL_EXTRACTION`**

**Artefact :** `.ci/avm10e-phaseb-prep.json` · lanceur `scripts/diag10e/run_app_10e_isolated.bat`

### Chemins absolus isolés (tous les composants)

| Rôle | Chemin |
|------|--------|
| `AVM_DATA_DIR` | `C:\Users\ComeToM3\AppData\Local\AudioVideoManager-10E` |
| SQLite 10E | `C:\Users\ComeToM3\AppData\Local\AudioVideoManager-10E\avm.sqlite3` |
| Config 10E | `C:\Users\ComeToM3\AppData\Local\AudioVideoManager-10E\config.json` |
| Jobs 10E | `C:\Users\ComeToM3\AppData\Local\AudioVideoManager-10E\jobs-10e` |
| Logs 10E | `C:\Users\ComeToM3\AppData\Local\AudioVideoManager-10E\logs` |
| Bibliothèque 10E | `C:\Users\ComeToM3\Music\AVM-10E-Test-Library` |

### Hors portée (snapshots lecture seule — ne pas modifier)

| Artefact | Snapshot |
|----------|----------|
| Config prod | `...\AudioVideoManager\config.json` (library = `AVM-06C-Test-Library`) |
| SQLite prod | `...\AudioVideoManager\avm.sqlite3` (110 592 o) |
| Jobs historiques | `...\AudioVideoManager\jobs` |
| Queen 17 FLAC | `...\AVM-06C-Test-Library\Queen\Greatest Hits (1992)` |

Contrôles d’isolation : `library_ne_queen_lib`, `data_ne_prod`, `db_ne_prod`, `jobs_ne_prod`, `lib_has_no_queen` = **tous true**.

### Vérifications pré-rip

| Check | Résultat |
|-------|----------|
| Disc ID | `HKAtvzd2gALbaC2d4HONIWPCE0Q-` · **22** pistes · **matches_authorized=true** |
| Lecteur | `0` ATAPI iHAS324 C |
| fre:ac | `C:\Program Files\freac\freaccmd.exe` |
| FFmpeg | `C:\Tools\ffmpeg\bin\ffmpeg.EXE` |
| Espace | ≈ 323 575 MiB libres · requis estimé ≈ 2 783 MiB · **ok** |
| Replace | désactivé |
| Interruptions expérimentales | **toujours interdites** |

### Opérations prévues **après** ta confirmation explicite

1. Lancer `scripts/diag10e/run_app_10e_isolated.bat` (force `AVM_DATA_DIR` 10E).  
2. Contrôler Paramètres : library + jobs = chemins 10E.  
3. Un seul archivage du CD 22 pistes (MB → édition → approbation → fre:ac → F-08a/b → decode → tags → cover → publish Rename → historique).  
4. Audit 22 pistes + SQLite 10E + UI ; re-vérifier snapshots Queen/prod inchangés.  
5. Mesures + fermeture normale.  
6. Mettre à jour ce rapport (GO/NO-GO phase B).

### Ce qu’il faut répondre pour débloquer l’étape 2

Confirmation explicite du type : **« OK extraction Phase B »** (éventuellement avec réserve sur le CD / chemins).  
Sans ce message : **aucune** extraction.

**Verdict phase B à ce stade :** préparation **GO** · extraction **non exécutée** · verdict global 10E reste **NO-GO** jusqu’à preuve physique.

---

**Fin du rapport AVM-10E (phase A + phase B étape 1 — STOP).**
