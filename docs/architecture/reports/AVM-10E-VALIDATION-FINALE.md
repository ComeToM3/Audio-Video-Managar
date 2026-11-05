# AVM-10E — Rapport de validation finale

**Date d'audit :** 2026-11-04  
**Version projet :** 0.5.0  
**Périmètre :** preuves de la phase B CD 22 pistes, intégrité de publication, régressions automatisées et risques de validation réelle.

## Verdict

**NON VALIDÉ** pour AVM-10E phase B. Aucune preuve d'extraction des 22 pistes n'existe dans les artefacts vérifiés. La bibliothèque 10E ne contient aucun fichier inventoriable, la base 10E a zéro job, zéro release et zéro piste, et le log 10E ne documente que le démarrage, la détection du lecteur et une réconciliation à zéro job.

**AVM-10F ne peut pas commencer** selon le critère de sortie AVM-10E : le parcours physique complet requis n'est pas démontré. Les tests de régression réussis ne remplacent pas cette preuve matérielle.

## 1. Sources examinées

- `docs/architecture/reports/AVM-10E-VALIDATION-CD-WINDOWS.md` (rapport de phase A / préparation B).
- `.ci/avm10e-phaseb-prep.json` (snapshot de préparation).
- `.ci/avm10e-queen-readonly.json` (audit antérieur de Queen, pas du CD candidat).
- `scripts/diag10e/run_app_10e_isolated.bat`.
- Configuration, log et base SQLite du répertoire `AudioVideoManager-10E`.
- Base SQLite de production et bibliothèque Queen, ouvertes/inspectées en lecture seule.
- `scripts/run_tests_ci.py`, tests `cd_ripper` et `freaccmd`, ainsi que les résultats JUnit générés.

Le rapport historique indique que l'extraction était **non exécutée**. Le snapshot de préparation conserve `extraction_started: false` et un arrêt avant rip. Le lanceur confirme les chemins de données et de bibliothèque 10E, mais sa ligne d'activation de l'environnement est malformée dans le fichier présent ; ce batch ne constitue donc pas une preuve d'exécution correctement isolée.

## 2. Extraction physique et fichiers

| Contrôle | Résultat | Preuve / limite |
|---|---|---|
| Disc ID candidat | `HKAtvzd2gALbaC2d4HONIWPCE0Q-`, 22 pistes | Snapshot de préparation antérieur ; aucune nouvelle lecture du lecteur entreprise pour ce rapport |
| Processus fre:ac d'extraction / code retour | **SKIP** | Aucun journal de rip ni résultat de processus relié au Disc ID candidat |
| FLAC candidats | **0 trouvé dans les chemins 10E examinés** | Bibliothèque 10E absente ; `jobs-10e` vide ; base 10E sans jobs/releases/tracks |
| Décodabilité, durée, taille et erreur par piste | **SKIP / impossible** | Aucun FLAC candidat à analyser |
| Mesures de durée, mémoire et espace après rip | **SKIP** | Aucune exécution d'extraction prouvée |

Les mesures du snapshot de préparation (environ 323 575 MiB libres, besoin estimé 2 783 MiB) sont des précontrôles historiques, pas des mesures après extraction.

## 3. Métadonnées

| Contrôle | Résultat | Preuve / limite |
|---|---|---|
| MusicBrainz et édition sélectionnée pour le Disc ID candidat | **SKIP** | Aucune fiche ou approbation associée à un job 10E |
| Titres, artiste, numéros de piste et conventions de nommage | **SKIP** | Pas de métadonnées ni de fichiers du CD candidat en base 10E ou dans la bibliothèque 10E |
| Pochette, intégration FLAC et `cover.jpg` du candidat | **SKIP** | Aucun artefact du candidat |
| Audit Queen | **PASS historique uniquement** | `.ci/avm10e-queen-readonly.json` décrit 17 pistes Queen ; ne prouve rien sur le CD 22 pistes |

Aucune métadonnée manquante ou erronée du CD candidat ne peut être établie sans enregistrement de l'identification.

## 4. Publication et cohérence des données

La base 10E a été ouverte en mode lecture seule : `jobs=0`, `releases=0`, `tracks=0`. Le répertoire `jobs-10e` est vide et `AVM-10E-Test-Library` ne contient aucun fichier inventoriable. Il n'y a donc ni publication 10E à contrôler, ni preuve de fichiers partiels publiés ou de doublons issus de ce parcours.

La base de production consultée en lecture seule contient le release Queen existant et 17 pistes ; aucune ligne n'est associée au Disc ID candidat. L'archive Queen contient 17 FLAC et `cover.jpg` aux tailles observées antérieurement. Ces observations confirment l'absence de release 22 pistes dans ces bases, mais ne constituent pas une comparaison cryptographique exhaustive avec tous les snapshots antérieurs.

Le contexte de l'intervention précédente signale qu'une tentative d'ouverture de l'application a utilisé par erreur le répertoire de données de production et a ajouté une relecture TOC au journal de production. Les artefacts examinés ne fournissent pas de snapshot du journal avant/après permettant de vérifier cette modification indépendamment ; elle est donc consignée comme anomalie de procédure. Aucune extraction fre:ac, aucun job 10E et aucune mutation de l'archive Queen n'ont été observés dans les preuves examinées.

## 5. Interruptions et récupération

Les scénarios d'annulation, d'erreur de lecture, d'arrêt de processus et de relance sur média réel sont **SKIP** : l'extraction préalable n'est pas confirmée et aucune opération destructive n'a été provoquée sur le CD ou les archives réelles.

La suite automatisée comprend des tests logiciels simulés de cancellation et de récupération sur processus factices et répertoires temporaires. Ils valident des branches logicielles de fixture, pas le comportement d'un rip physique interrompu. Ils ne sont pas interprétés comme une validation matérielle.

## 6. Tests automatisés et régressions

Commande exécutée sous Windows :

```powershell
.\.venv\Scripts\python.exe scripts\run_tests_ci.py --junit-dir .ci\avm10e-validation-junit --report .ci\avm10e-validation-results.json
```

| Suite | Résultat | Code retour | Tests | Échecs | Erreurs | Skips |
|---|---:|---:|---:|---:|---:|---:|
| Domaine | **PASS** | 0 | 168 | 0 | 0 | 0 |
| UI (12 processus isolés) | **PASS** | 0 | 67 | 0 | 0 | 0 |
| Total | **PASS** | — | **235** | **0** | **0** | **0** |

Synthèse vérifiée : `.ci/avm10e-validation-results.json` (`ok: true`, `skipped_unavailable: []`) ; rapports JUnit sous `.ci/avm10e-validation-junit/`. L'environnement détecté est Windows x64, Python **3.12.10**, fre:ac trouvé, `discid` chargeable et FFmpeg trouvé. La cible spécifiée pour le projet est Python 3.11 : cette exécution sous 3.12 est une validation utile mais ne certifie pas Python 3.11. Le runner détecte les dépendances ; il n'a pas exécuté de rip matériel.

Aucune correction de code n'a été faite pendant cet audit : aucun défaut d'implémentation directement lié au rip n'est démontré par l'absence d'exécution. Aucun test matériel ni interruption réelle n'a été lancé.

## 7. Anomalies et risques résiduels

| ID | Sévérité | Constat | Suite recommandée |
|---|---|---|---|
| 10E-F-01 | Bloquant | Aucune extraction réelle des 22 pistes prouvée | Refaire un unique parcours avec instrumentation et chemins isolés, puis auditer tous les artefacts |
| 10E-F-02 | Élevée | La tentative d'application précédente a pu écrire dans les logs production | Conserver cette anomalie ; ne pas relancer avec un environnement ambigu ; vérifier les variables et chemins avant démarrage |
| 10E-F-03 | Moyenne | Lanceur batch contient une commande d'activation malformée | Corriger le lanceur avant son prochain usage et vérifier les chemins effectifs dans le processus |
| 10E-F-04 | Moyenne | Tests exécutés sous Python 3.12, pas 3.11 | Rejouer au minimum sous Python 3.11 avant de certifier la version cible |
| 10E-F-05 | Non évaluée | Interruptions et récupération réelles | À planifier uniquement après une extraction confirmée, sur job 10E isolé ; aucune purge/destruction |
| 10E-F-06 | Faible / historique | `rip_check_status=weak_ok` de Queen antérieur à 10D | Ne pas migrer ni modifier Queen dans ce mandat |

## 8. Recommandations et limites de mandat

1. Ne pas déclarer la phase B terminée et ne pas commencer AVM-10F.
2. Corriger l'isolation du lancement et le lanceur avant toute nouvelle tentative ; vérifier `AVM_DATA_DIR`, `AVM_LIBRARY_ROOT`, la base, les jobs et le log effectifs avant d'ouvrir l'application.
3. Exécuter un seul parcours physique autorisé et enregistrer le code retour fre:ac, les sorties, mesures, métadonnées approuvées, résultats F-08a/F-08b/décodage, chemin de publication et état SQLite.
4. Rejouer les tests CI sous Python 3.11. Les tests simulés ne doivent pas être confondus avec une validation matérielle.
5. Après confirmation d'une extraction valide, demander une autorisation distincte avant tout scénario d'interruption réelle. Maintenir les archives Queen et les données de production hors cible.

Aucune étape AVM-10F n'est entreprise dans ce mandat.