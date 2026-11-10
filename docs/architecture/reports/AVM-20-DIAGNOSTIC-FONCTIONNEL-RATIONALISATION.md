# AVM-20 — Diagnostic fonctionnel et rationalisation du dépôt

**Statut : diagnostic uniquement — aucune modification, suppression, déplacement, migration, réextraction ou nouveau test effectué.**
**Toutes les données personnelles (`%LOCALAPPDATA%\AudioVideoManager`, `C:\Users\ComeToM3\Music\AVM-06C-Test-Library`) ont été inspectées en lecture seule exclusivement.**

---

## 1. Priorité absolue — pourquoi un seul des deux CD apparaît dans la bibliothèque

### 1.1 Méthode

Inspection directe et en lecture seule des données réelles de production, indépendamment du dépôt de code :
- `%LOCALAPPDATA%\AudioVideoManager\config.json`
- `%LOCALAPPDATA%\AudioVideoManager\avm.sqlite3` (requête SQLite en mode `ro`)
- `%LOCALAPPDATA%\AudioVideoManager\logs\avm.log`
- Contenu disque de `%LOCALAPPDATA%\AudioVideoManager\jobs\*`
- Contenu disque de `C:\Users\ComeToM3\Music\AVM-06C-Test-Library`

### 1.2 Faits démontrés

| Fait | Preuve |
|---|---|
| Une seule base SQLite existe, un seul fichier `config.json` existe | Un seul exemplaire de chacun trouvé sur disque ; aucune confusion multi-base possible |
| `library_root` effectif = `C:\Users\ComeToM3\Music\AVM-06C-Test-Library` (pas le défaut `~/Music/AudioVideoManager`) | `config.json` réel de l'utilisateur |
| Table `releases` : **1 seule ligne** — Queen, *Greatest Hits* (1992), `disc_id=DsXlPG1OQWhceSELb2Eiq5rx1wU-`, importé le 2026-11-03 | Requête directe sur `avm.sqlite3` |
| Table `jobs` : **4 lignes** — `bd40b604…` (Failed, erreur freaccmd), `c43af993…` (Cancelled), `8e23e82d…` (**Completed**, Queen, seul job ayant publié), `a31763ee…` (**Interrupted**, `mode=technical_test`) | Requête directe sur `avm.sqlite3` |
| Le job `a31763ee…` a bien ripé ~17 pistes FLAC (~363 Mo) mais elles ne sont présentes que dans sa zone de travail `rip/`, jamais publiées | Inspection disque du dossier job |
| `mode=technical_test` est **documenté et volontaire** : publication (zone C) toujours interdite dans ce mode, quel que soit l'état de la fiche | `audio_video_manager/orchestration/rip_job.py` (docstring, lignes ~67-83) : « Rip technical_test avec fiche Approved — publish C toujours interdit » |
| Un second disque (`disc_id=HKAtvzd2gALbaC2d4HONIWPCE0Q-`, 22 pistes) a été **lu (TOC) et identifié via MusicBrainz à trois reprises distinctes** (4, 5 et 6 novembre) | `avm.log`, lignes de lecture TOC + lookup MusicBrainz pour ce disc_id, sur 3 dates |
| **Aucune ligne « Démarrage rip » ni aucune entrée `archive_job`/`rip_job` n'existe pour ce disc_id, à aucune des 3 dates** | Grep exhaustif de `avm.log` sur ce disc_id ; aucune ligne de job trouvée |
| **Aucune ligne dans la table `jobs` ne correspond à ce disc_id** | Requête directe sur `avm.sqlite3` |
| `list_releases()` (bibliothèque) n'applique aucun filtre par `library_root`, statut ou date — elle renvoie simplement les lignes de `releases` | `audio_video_manager/storage/catalog.py:135-156` |
| Une ligne `releases` n'est créée que si `run_archive_job(confirm_publish=True)` réussit jusqu'à `publish_album()` ; le wizard appelle toujours `confirm_publish=True` en usage normal | `audio_video_manager/orchestration/archive_job.py:708-834` ; `audio_video_manager/ui/wizard/archive_wizard.py:1518` |

### 1.3 Cause racine

**Il n'y a pas de bogue logiciel dans la bibliothèque, l'indexation, les filtres d'affichage ou les chemins de publication.** Les mécanismes de gating, la base unique, et `list_releases()` fonctionnent exactement comme prévu et sont cohérents avec un seul album publié.

Le « second CD manquant » s'explique entièrement par le fait que **son extraction (rip) n'a jamais été démarrée**, bien que le disque ait été inséré, lu et identifié à trois reprises distinctes. Le pipeline CD→FLAC n'a donc jamais été exécuté pour ce disque — il n'y a rien à retrouver dans la bibliothèque car rien n'a été archivé.

### 1.4 Ce qui reste une question ouverte (non déductible des journaux)

**Pourquoi l'extraction n'a-t-elle jamais été lancée après identification, à trois reprises ?** Les hypothèses possibles (point de friction dans l'assistant, fiche non confirmée, session interrompue avant le clic « Démarrer », disque retiré avant le lancement) ne sont pas départageables avec les seules preuves journalisées. **Cette question doit être posée à l'utilisateur** ; elle ne doit pas être traitée comme un défaut présumé de l'interface sans reproduction.

### 1.5 Constat annexe — hygiène des jobs non publiés

`jobs_dir` contient actuellement ~1,47 Go répartis sur 4 dossiers de jobs, dont 3 (`bd40b604`, `a31763ee`, `c43af993`) correspondent à des tentatives échouées/annulées/techniques jamais nettoyées. **Aucune suppression n'a été effectuée** (hors périmètre du mandat). Signalé pour décision future uniquement.

---

## 2. Cartographie du parcours CD réellement actif

```
main_window.run_app()
  └─ MainWindow
       ├─ Assistant d'archivage (ui/wizard/archive_wizard.py)
       │     détection lecteur → lecture TOC → identification MusicBrainz
       │     → confirmation fiche → rip_job → archive_job(confirm_publish=True)
       │     → publish_album() → _record_release() → table `releases`
       └─ LibraryHost (ui/sections/library_host.py)
             resolve_library_ui_mode(config) :
               - défaut du code : "qml"
               - **config réel utilisateur : "widgets"** (override explicite)
             → LibraryPage (Widgets, ui/sections/library_page.py) active sur ce poste
             → QML (QQuickWidget) présent dans le code mais non exercé par cet utilisateur
```

**Constat :** le code expose deux chemins d'affichage de bibliothèque (QML prioritaire, Widgets en repli explicite via `library_ui_mode`). Sur la configuration réelle de l'utilisateur, **c'est le chemin Widgets qui est actif**, pas le défaut QML. Les deux chemins restent du code légitime et maintenu (le repli Widgets est un mécanisme de robustesse documenté, « AVM-08B »), mais cela signifie que le chemin QML n'est actuellement pas exercé en usage réel sur ce poste — à garder à l'esprit avant d'investir dans l'un ou l'autre sans confirmer lequel sera utilisé en production.

**`DiscMetadataDialog` (`audio_video_manager/ui/metadata_dialog.py:72`) — confirmation du constat AVM-19 :**
- Recherché dans tout `audio_video_manager/` (code Python) et tout `audio_video_manager/ui/qml/` (QML) : **aucune instanciation** en dehors de son propre fichier et de son test dédié (`tests/test_metadata_dialog_sources.py`).
- Aucune référence dynamique par nom de chaîne dans les fichiers QML.
- **Conclusion confirmée, pas supposée :** ce composant est du code fonctionnel, testé isolément, mais non branché au parcours utilisateur réel. Il ne doit pas être supprimé sans décision produit (il peut représenter un parcours futur), mais ne doit plus recevoir d'investissement tant qu'il n'est pas intégré ou explicitement abandonné.

---

## 3. Inventaire chiffré du dépôt

| Emplacement | Fichiers | Taille | Suivi Git ? | Nature |
|---|---|---|---|---|
| `audio_video_manager/` | 190 | 2,85 Mo | Oui | Code produit actif |
| `tests/` | 44 (.py) | 2,45 Mo | Oui | Suite de tests |
| `docs/` | 237 | 37,3 Mo | Oui | Documentation (dont assets images) |
| `scripts/` | 32 | 0,22 Mo | Oui | Scripts CI + diagnostics historiques |
| `prototypes/` | 39 (34 suivis) | 0,79 Mo | Oui (34/39) | Maquettes HTML/QSS historiques |
| `vendor/` | 15 | 0,22 Mo | Oui | Binaires libdiscid Windows |
| `.ci/` | 826 | 95,1 Mo | **Non (gitignore)** | Résultats de runs de tests accumulés |
| `.capture_avm06*/07*/08*` (7 dossiers) | ~180 au total | ~2,4 Mo | **Non (gitignore)** | Captures de validation ponctuelles (fixture Queen synthétique) |
| `.tmp-avm-smoke/` | 2 | 0,05 Mo | **Non (gitignore)** | Artefact de smoke test |
| `architecture/reports/` | **0** | 0 | **Non, untracked** | Dossier vide — doublon de nom avec `docs/architecture/reports/` |
| `.pytest_cache/`, `*.egg-info/` | — | — | Non (gitignore) | Caches générés standards |

### 3.1 La duplication de nom « architecture/reports » (point soulevé par l'utilisateur)

- `docs/architecture/reports/` : **29 rapports** + 3 sous-dossiers de preuves (`AVM-11E-evidence`, `AVM-11E-evidence-203d6ec2`, `AVM-11F-evidence`, `AVM-12-evidence`, 20 fichiers) — suivi par Git, **emplacement réellement utilisé** (AVM-18 et AVM-19 y ont été déposés).
- `architecture/reports/` (racine) : **dossier vide**, non suivi par Git, absent de `.gitignore`. Aucune trace de contenu historique (vide à l'inspection).

**Conclusion :** `architecture/reports/` à la racine est un dossier vide résiduel, sans contenu ni historique Git — probablement créé par erreur ou par une commande interrompue lors d'un mandat antérieur. Il ne contient aucune preuve à préserver. Candidat à un simple retrait (dossier vide, zéro risque), **mais retrait non effectué ici car hors périmètre du mandat (lecture seule)**.

### 3.2 `.ci/` — accumulation de résultats historiques

826 fichiers, 95 Mo, **déjà exclu de Git**. Contient les logs/JUnit de runs CI passés (`avm10c1-*`, `avm10c2-*`, `avm10d-*`). N'a aucun impact sur le dépôt Git (ignoré), mais représente une accumulation disque locale. Seul `scripts/run_tests_ci.py` y écrit activement (`--junit-dir .ci/junit`), confirmé par `.github/workflows/ci-windows.yml`. Les anciens runs restants (`avm10c1`, `avm10c2`, `avm10d`) sont des traces historiques de mandats de stabilisation Qt déjà clos.

### 3.3 `.capture_avm06*/07*/08*` — captures de validation ponctuelles

7 dossiers (`avm06l`, `avm06m`, `avm06n`, `avm06o`, `avm08b`, `avm08d`, `avm08d1`, `avm08e`), tous **gitignorés** (`.capture_*/` dans `.gitignore`), contenant chacun une bibliothèque de test synthétique identique (Queen — *Greatest Hits*, fixture de test, pas une donnée personnelle réelle). Ce sont des preuves d'exécution de mandats de validation UX antérieurs (AVM-06, AVM-08), déjà clos. Non trackées, sans impact Git, mais occupent l'espace disque local.

### 3.4 `scripts/diag*` — distinction outils maintenus vs scripts ponctuels

- **Seul `scripts/run_tests_ci.py` est actuellement invoqué** par la CI (`.github/workflows/ci-windows.yml`) — c'est le seul script de ce dossier à considérer comme « outil maintenu ».
- `scripts/diag07a/`, `diag07b/`, `diag10c1/`, `diag10c2/`, `diag10e/`, `diag11f/`, `diag12/`, `diag14/` : scripts de reproduction/diagnostic écrits pour des mandats de stabilisation Qt/UI ponctuels et déjà clos (AVM-07, 10, 11, 12, 14). Aucun n'est importé par `audio_video_manager/` ni invoqué par la CI.
- **Point de vigilance identifié :** `audio_video_manager/diag10e_isolation.py` (dans le paquet produit, importé par `__main__.py`) est un **module distinct** du dossier `scripts/diag10e/` (scripts de repro historiques). Ne pas confondre les deux lors d'une éventuelle réorganisation — le premier est du code produit actif, le second est un script ponctuel archivable.
- Les `scripts/capture_avm*.py` (8 fichiers) sont les générateurs des dossiers `.capture_avm*` ci-dessus — historiques, non invoqués par la CI, mais traçabilité utile si une capture doit être rejouée.

### 3.5 `prototypes/` — générations de maquettes UI

4 générations suivies par Git (`avm_06j`, `avm_08a`, `avm_08c`, `avm_08d2`) : maquettes HTML/CSS/QSS d'exploration de design, antérieures à l'implémentation Qt actuelle. Ne sont importées par aucun code Python et ne sont pas exécutées par l'application ni par la CI. Code historique de conception, pas du code produit.

### 3.6 `docs/` — répartition réelle (237 fichiers, 37,3 Mo)

| Sous-dossier | Fichiers | Nature |
|---|---|---|
| `architecture/reports/` (+ 4 sous-dossiers evidence) | 29 + 20 | Rapports de mandats (canonique, actif) |
| `ux/reports/` (+ `assets/`) | 35 + 106 | Rapports UX + captures d'écran — la majorité des 37,3 Mo vient des images ici |
| `ux/specs` | 11 | Spécifications UX |
| `product/` | 4 | Documents produit |
| `validation/` | 4 | Rapports de validation |
| `domain/` | 2 | Documentation du domaine métier |
| `engineering/` | 3 | Documentation technique |
| `roadmap/`, `vision/` | 1 chacun | Vision/roadmap produit |

**Constat :** pas de duplication de contenu identifiée entre ces sous-dossiers (rôles distincts). Le volume (37 Mo) est presque entièrement dû aux images de `ux/reports/assets/` — c'est du contenu suivi par Git (donc présent dans l'historique), pas un emplacement erroné. Pas de preuve de dispersion fautive ; la quantité de rapports (29 + 35 + 11 + …) reflète l'historique réel du nombre de mandats exécutés (AVM-06 à AVM-19), pas une redondance.

---

## 4. Évaluation de la suite de tests

### 4.1 Fait vérifié : aucun test orphelin

Comparaison exhaustive entre les 44 fichiers `tests/test_*.py` présents sur disque et les fichiers explicitement référencés dans `scripts/run_tests_ci.py` (`UI_FILES` + `DOMAIN_GLOBS`) : **correspondance exacte, 44/44, aucun écart dans un sens ou l'autre.** Aucun fichier de test n'est orphelin (jamais collecté) ni fantôme (listé mais absent).

Cela contredit une hypothèse a priori de « tests obsolètes non exécutés » — **ce n'est pas le constat observé ici** : tous les tests écrits sont effectivement exécutés en CI.

### 4.2 Nommage des tests — reflet direct de l'historique des mandats

La majorité des noms de fichiers de test reprennent un identifiant de mandat (`test_ux_06o.py`, `test_history_06n.py`, `test_qt_teardown_10c1.py`, `test_qt_teardown_10c2.py`, `test_perf_06gp.py`, `test_10e_isolation.py`, `test_reconciliation_10b.py`/`10c.py`, `test_hardlink_security_06gp1.py`…). Ce n'est pas en soi un défaut : ces tests couvrent des comportements réels et actifs (verrous, téléportation Qt, sécurité des hardlinks, etc.), mais le nommage par mandat rend difficile, sans lecture du contenu, de savoir si un test donné couvre encore un chemin actif ou un comportement aujourd'hui dormant (ex. `test_qt_teardown_10c1.py` et `10c2.py` couvrent potentiellement le même risque sous deux formulations historiques successives — **non vérifié ligne à ligne dans ce mandat, hors périmètre d'un audit récursif**).

### 4.3 Tests liés à `DiscMetadataDialog`

`test_metadata_dialog_sources.py` (3 tests identifiés) exerce exclusivement le composant non branché identifié en §2. Ces tests sont valides et passent, mais valident un composant actuellement hors du parcours utilisateur réel — un exemple concret de **test qui vérifie une hypothèse de code isolé sans vérifier le parcours intégré**, cohérent avec le constat produit soulevé par l'utilisateur.

### 4.4 Ce qui n'a pas été évalué (hors périmètre de ce diagnostic)

Une évaluation fine de la redondance *interne* (deux tests différents vérifiant la même hypothèse avec des noms différents) nécessiterait une lecture complète des 44 fichiers de test — explicitement exclue d'un diagnostic non récursif. Ce travail, s'il est souhaité, devrait faire l'objet d'un mandat dédié et borné (par exemple : liste des tests par composant visé, pas par mandat d'origine).

---

## 5. Classification proposée — CONSERVER / REGROUPER / ARCHIVER / RETIRER

**Aucune action ci-dessous n'a été exécutée. Toutes nécessitent une validation explicite avant toute exécution (AVM-20 est un diagnostic, pas un mandat d'exécution).**

| Élément | Classification proposée | Justification | Risque si exécuté sans vérification |
|---|---|---|---|
| `audio_video_manager/` | **CONSERVER** | Code produit actif, parcours CD vérifié bout en bout | — |
| `tests/` (44 fichiers) | **CONSERVER** | Tous actifs en CI, aucun orphelin constaté | — |
| `docs/architecture/reports/`, `docs/ux/reports/`, etc. | **CONSERVER** | Emplacement canonique confirmé, contenu non redondant | — |
| `architecture/reports/` (racine, vide) | **RETIRER** (dossier vide) | Aucun contenu, non suivi Git, nom dupliqué source de confusion | Nul — dossier vide, rien à perdre |
| `.ci/` (95 Mo, gitignoré) | **ARCHIVER/PURGER localement** (hygiène disque uniquement) | Déjà hors Git ; accumulation de runs historiques clos (10c1/10c2/10d) | Nul pour Git ; perte de logs de debug anciens si purgé — à faire seulement si l'utilisateur confirme ne plus en avoir besoin |
| `.capture_avm06*/07*/08*` (7 dossiers, gitignorés) | **ARCHIVER/PURGER localement** | Preuves de mandats UX déjà clos et déjà rapportés ; fixture synthétique, pas de donnée personnelle | Nul pour Git ; à conserver seulement si une preuve doit être rejouée |
| `scripts/diag07a/07b/10c1/10c2/10e/11f/12/14/` | **ARCHIVER** (regrouper sous un sous-dossier explicite, ex. `scripts/_archive/` ou déplacer en pièce jointe de rapport) | Scripts de reproduction ponctuels liés à des mandats clos, non invoqués par la CI ni le produit | Confirmer qu'aucun rapport existant ne référence leur chemin avant tout déplacement |
| `scripts/capture_avm*.py` | **ARCHIVER** (même traitement que ci-dessus) | Générateurs des captures ci-dessus, non invoqués par la CI | Idem |
| `prototypes/avm_06j/08a/08c/08d2` | **ARCHIVER** (conserver dans Git, déplacer hors du niveau racine si une structure `archive/` est adoptée) | Maquettes de conception historiques, non exécutées par l'app | Aucune référence de code à casser (vérifié : aucun import) |
| `audio_video_manager/ui/metadata_dialog.py` (`DiscMetadataDialog`) | **CONSERVER tel quel, geler les investissements** | Composant fonctionnel mais non branché — décision produit requise (intégrer ou abandonner), pas une suppression technique | Ne pas supprimer sans décision produit explicite ; ne pas continuer à l'améliorer sans décision |
| `scripts/run_tests_ci.py` | **CONSERVER** | Seul script activement invoqué par la CI | — |
| `vendor/libdiscid/` | **CONSERVER** | Dépendance binaire Windows nécessaire à l'exécution | — |

---

## 6. Ce qui est déjà satisfaisant et doit rester intact

- Le mécanisme de publication/indexation (`archive_job.py`, `catalog.py`) fonctionne correctement et n'est pas la cause du problème signalé — **ne pas le modifier** sur la base d'une fausse hypothèse de bogue.
- La base de données unique et le chemin de configuration (`paths.py`, `config.py`) sont cohérents et ne nécessitent aucune correction.
- La couverture de test est exhaustivement reliée à la CI (aucun test orphelin) — la perception d'une « suite de tests qui grossit sans contrôle » ne correspond pas, à ce stade, à un problème de tests fantômes, mais plutôt à une question de pertinence et de regroupement par fonctionnalité plutôt que par mandat d'origine.
- Les fonctionnalités DVD existantes n'ont pas été touchées ni évaluées dans ce diagnostic (hors périmètre, mandat centré CD) — à préserver telles quelles.

---

## 7. Décisions nécessitant votre approbation avant tout mandat d'exécution

1. **Confirmer ou infirmer** la question ouverte du §1.4 : pourquoi l'extraction du second disque n'a jamais démarré malgré 3 identifications — information que vous seul pouvez fournir (pas déductible des journaux).
2. **Approuver ou non** la purge locale de `.ci/` et `.capture_avm*` (aucun impact Git — purement de l'hygiène disque locale, ~97 Mo au total).
3. **Décider du sort de `DiscMetadataDialog`** : l'intégrer au parcours réel, ou le marquer formellement comme abandonné (dans ce cas uniquement, envisager son retrait dans un mandat dédié).
4. **Approuver ou non** le regroupement des scripts `scripts/diag*/` et `scripts/capture_avm*.py` sous un emplacement explicite d'archive (ex. `scripts/_archive_mandats_clos/`), avec vérification préalable qu'aucun rapport déjà publié n'y fait référence par chemin relatif.
5. **Confirmer le mode d'interface réellement souhaité en production** (`library_ui_mode="widgets"` est actuellement actif sur votre poste, alors que le défaut du code est `"qml"`) — à clarifier avant d'investir du temps dans l'un ou l'autre chemin d'affichage.
6. **Décider du nettoyage des jobs non publiés** (~1,47 Go, dossiers `bd40b604`, `a31763ee`, `c43af993`) — hors périmètre de ce diagnostic, mentionné pour information.

---

## Verdict

Les deux CD ne sont pas victimes d'un défaut logiciel : un seul a été réellement archivé (Queen, correctement publié et indexé) ; le second a été identifié à trois reprises mais son extraction n'a jamais été initiée. Le dépôt contient une accumulation réelle mais majoritairement déjà hors Git (`.ci/`, `.capture_avm*`) ou clairement historique et non invasive (`prototypes/`, `scripts/diag*`), sans doublon de contenu dans `docs/`. Le seul doublon structurel avéré est un dossier vide (`architecture/reports/` à la racine). Aucune suppression de code n'est justifiée dans l'immédiat ; `DiscMetadataDialog` reste le seul investissement technique avéré sans branchement produit.

**STABILISATION NON REQUISE AU SENS TECHNIQUE — RATIONALISATION RECOMMANDÉE, SOUS RÉSERVE DE VOS DÉCISIONS CI-DESSUS.**

*(Arrêt du mandat AVM-20 conformément aux garde-fous — aucun nettoyage, déplacement ou mandat suivant engagé automatiquement.)*
