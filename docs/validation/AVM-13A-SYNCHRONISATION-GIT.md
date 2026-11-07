# AVM-13A — Vérification et synchronisation du dépôt Git

Date d'observation : 7 novembre 2026, UTC.

**Verdict : DIVERGENCE IDENTIFIÉE.**

Deux ensembles de développements accessibles existent sur des branches
différentes et aucun n'est une base complète AVM-12. Les implémentations
AVM-11D–12 et les « 321 tests CI réussis » annoncés ne sont pas retrouvés
dans les références GitHub accessibles. Leur emplacement local ou externe
reste inconnu : leur récupération nécessite des preuves du PC Windows.
Ce constat ne signifie pas qu'ils ont été perdus ou qu'ils n'existent pas.

## 1. Dépôt et état initial

- Dépôt GitHub : <https://github.com/ComeToM3/Audio-Video-Managar>.
- Racine du clone :
  `/home/runner/work/Audio-Video-Managar/Audio-Video-Managar`.
- Branche active : `copilot/avm-11b-inspection-dvd`.
- HEAD initial : `530a01fda8beb4fc1c0ea41aa1f422d209b7c7ba`.
- Upstream : `origin/copilot/avm-11b-inspection-dvd`, même SHA.
- Remote unique, fetch et push :
  `http://localhost:26831/ComeToM3/Audio-Video-Managar`.
  C'est l'adresse du relais Git du sandbox, pas une adresse à configurer
  sur le PC Windows. Aucun autre remote n'est configuré ici.
- Arbre de travail initial propre : aucun fichier modifié, indexé, non suivi
  ou ignoré signalé lors des vérifications.
- Clone initial superficiel : seuls deux commits visibles et une seule
  branche distante suivie. Le refspec configuré était
  `+refs/heads/copilot/avm-11b-inspection-dvd:refs/remotes/origin/copilot/avm-11b-inspection-dvd`.
- Reflog initial : uniquement le clonage du 7 novembre à 13:21:28 UTC.
  Ce reflog n'est pas celui du PC local et ne permet pas d'en déduire ses
  anciens commits.

Les résultats `git ls-remote --symref origin` et l'API GitHub des branches
concordent : branche par défaut `main`, trois branches, aucun tag annoncé
par le remote lors de la recherche. Aucune branche n'est signalée protégée
par cette API à cet instant.

## 2. Historiques chargés sans synchronisation du code

Commande exécutée dans le clone, sans checkout, fusion ou changement de HEAD :

```text
git -C /home/runner/work/Audio-Video-Managar/Audio-Video-Managar fetch --no-tags --unshallow origin '+refs/heads/*:refs/remotes/origin/*'
```

Elle a chargé `origin/main`, `origin/copilot/vscode-mw5bwf8y-coab` et les
parents manquants. Le clone n'est ensuite plus superficiel. Le refspec
configuré n'a pas été modifié : un futur fetch ordinaire peut encore ne
suivre que la branche initiale.

| Branche accessible | Commit de pointe avant le présent rapport | Contenu distinct |
|---|---|---|
| `main` | `b4c00071cab4a151bcf524b96a7c654064c15a1f` | Initial commit ; DVD placeholder |
| `copilot/vscode-mw5bwf8y-coab` | `2531b419c4ac77723f4b43e60aff55f03a29b010` | Checkpoint VS Code ; évolutions CD et cadrage AVM-11A |
| `copilot/avm-11b-inspection-dvd` | `530a01fda8beb4fc1c0ea41aa1f422d209b7c7ba` | Inspecteur DVD AVM-11B et rapport |

Historique parent/enfant complet des branches annoncées :

```text
b4c0007 Initial commit
├── 2531b41 Checkpoint from VS Code for cloud agent session
└── d02013c Initial plan
    └── 47b6569 Add guarded read-only DVD inspector and source video metadata
        └── 530a01f Document AVM-11B evidence, safety limits and non-validated hardware verdict
```

Les SHA complets des deux commits intermédiaires sont
`d02013c197f492bdd785b2209c85134cd4de9e65` et
`47b6569a10ceeb21c7e49c0ecac084c10e1ab342`.

`git rev-list --left-right --count origin/main...HEAD` donne **0 / 3**.
La branche AVM-11B descend de main, sans les évolutions du checkpoint VS Code.
La comparaison `origin/copilot/vscode-mw5bwf8y-coab...HEAD` donne **1 / 3** :
les deux branches divergent depuis `b4c0007`.
Il ne faut donc pas désigner l'une comme un remplacement intégral de l'autre.

## 3. Fonctionnalités et rapports retrouvés

Les recherches ont porté sur les arbres et messages de commits de toutes les
branches annoncées, dans le code, les tests, les scripts et les documents.
Les fichiers binaires ne constituent pas des occurrences de preuve textuelle.

### Checkpoint VS Code, absent de main et de la branche active

La comparaison à main donne **40 fichiers différents, 4 703 lignes ajoutées,
181 supprimées**. Elle contient notamment :

- Consolidation des métadonnées :
  `audio_video_manager/metadata/consolidation.py`.
- Changements CD dans `extraction/cd_ripper.py`, les jobs d'archive/rip,
  `metadata/enrichment.py`, la validation, le wizard, le thème et la progression.
- Rapports CD D3, D4, D5, D5B, D7 et D8 sous
  `docs/architecture/reports/`, ainsi que D et D2B/D2C.
- Tests `test_consolidation_10e_d5.py`,
  `test_rip_integration_10e_d3.py`, `test_ui_approval_layout_10e_d4.py`,
  `test_ui_archive_progress_10e_d8.py`, `test_ui_consolidation_10e_d5.py`,
  fixtures associées et modifications de l'orchestrateur CI.
- Rapport `docs/architecture/reports/AVM-11A-INTEGRATION-DVD-VIDEO.md`.
  Son verdict explicite est **« capacité DVD non livrée et non validée »** :
  il s'agit d'un cadrage, pas d'une extraction MKV/MKA implémentée.

Ces développements sont **commités et poussés**, puisque leur objet et leur
branche sont annoncés par GitHub et récupérables depuis origin.
Ils ne sont pas présents sur la branche active ; ils ne sont pas perdus.

### Branche active AVM-11B, absente de main et du checkpoint VS Code

La comparaison à main donne **5 fichiers différents, 843 lignes ajoutées,
1 supprimée** :

- `audio_video_manager/extraction/dvd.py` : inspection de structure DVD et
  sonde ffprobe conditionnelle, pas d'extraction.
- `audio_video_manager/metadata/video.py` : modèles de source vidéo.
- `tests/test_dvd_inspector.py`.
- `docs/validation/AVM-11B-INSPECTION-PHYSIQUE-DVD.md`.
- Une entrée de tests supplémentaire dans `scripts/run_tests_ci.py`.

La sonde reste protégée par `known_unprotected=True` et
`no_css_environment=True`, cette dernière étant une attestation externe.
La recherche ne modifie pas ces garde-fous.

La [PR #1](https://github.com/ComeToM3/Audio-Video-Managar/pull/1) est ouverte
de cette branche vers main. C'est la seule PR retournée par la liste accessible
ouverte/fermée. Elle n'a pas intégré ces fichiers à main.

### Éléments non retrouvés

| Élément annoncé | Résultat dans les trois branches accessibles |
|---|---|
| Rapports AVM-11D à AVM-12 | Absents |
| Moteur DVD d'extraction MKV/MKA | Absent ; extraction toujours reportée |
| Fenêtres DVD et sélection audio/sous-titres pour extraction | Absentes |
| Tests d'extraction DVD AVM-11D–12 | Absents |
| Preuve GitHub de 321 tests CI réussis | Non retrouvée |
| Paquet Python `audio_video_manager/library/` | Absent des trois arbres |

La chaîne de version **0.5.0** est identique dans les trois `pyproject.toml`.
Elle n'identifie donc pas la révision fonctionnelle complète.
La présence de ressources QML `AvmLibrary` ne remplace pas le paquet Python
`library` requis par les imports.

## 4. CI et intégrité Git

`git fsck --full` s'est terminé avec **code 0, sans diagnostic** après
chargement de l'historique. Cela valide les objets disponibles ; ce n'est
pas une preuve que les fichiers Windows ou les commits jamais poussés sont
présents. Aucun objet dangling n'a été signalé dans ce clone.

L'API GitHub retourne sept runs au moment du contrôle :
un run `ci-windows` sur main échoué, trois runs `ci-windows` AVM-11B avec
`action_required`, et trois exécutions de l'agent dont une en cours.
Le succès d'une exécution d'agent n'est pas le succès des tests applicatifs.

- [Run main 42031918245](https://github.com/ComeToM3/Audio-Video-Managar/actions/runs/42031918245) :
  journaux consultés par l'outil GitHub ; erreurs de collecte
  `ModuleNotFoundError: No module named 'audio_video_manager.library'`,
  synthèse `OVERALL: NO-GO`, code de sortie 1.
- [Run AVM-11B 42275355168](https://github.com/ComeToM3/Audio-Video-Managar/actions/runs/42275355168) :
  `action_required`, pas une preuve de tests exécutés.
- Aucun run de tests sur le checkpoint VS Code n'est retourné.

Les « 321 tests réussis » peuvent provenir d'une autre exécution ou d'un poste
local, mais aucune provenance SHA/run/JUnit n'est fournie ici.
**Aucun test applicatif n'est relancé dans AVM-13A** : le code complet annoncé
est indisponible, le mandat est documentaire et les imports manquants sont
déjà établis. Aucun résultat précédent n'est présenté comme une validation
nouvelle.

## 5. Ce qui est établi et ce qui exige le PC Windows

| Hypothèse | Conclusion |
|---|---|
| Clone superficiel et limité à une branche | Confirmé, limitation d'inspection levée par fetch |
| Évolutions CD/D8 et cadrage DVD sur une autre branche | Confirmé, commit `2531b41` accessible |
| Inspection AVM-11B non intégrée à main | Confirmé, trois commits propres et PR ouverte |
| AVM-11D–12 non commité sur le PC | Possible, invérifiable sans état local |
| AVM-11D–12 commité mais non poussé | Possible, invérifiable sans log/reflog local |
| AVM-11D–12 sur un autre dépôt/remote ou une branche supprimée | Possible, référence ou sauvegarde nécessaire |
| Développements détruits | Aucune preuve ; ne pas conclure |

Le sandbox ne voit pas le disque Windows, ses autres clones, ses fichiers
ignorés, ses stashes, ses objets orphelins ou ses configurations de remotes.
La recherche GitHub couvre les références accessibles annoncées, pas les
objets supprimés ou les dépôts privés dont aucune adresse n'a été fournie.

## 6. Procédure minimale recommandée — non exécutée

1. **Sauvegarder le projet réellement utilisé sur Windows avant toute action.**
   Faire une copie complète vers un emplacement neuf, y compris `.git`,
   fichiers non suivis et rapports de tests. Ne pas partager de secrets,
   bases personnelles ou médias. Ne pas faire de nettoyage, stash automatique,
   reset, rebase ou suppression de branche.
2. **Identifier cette copie de travail**, avec son chemin absolu réel :
   relever `git rev-parse --show-toplevel`, `git status --short --branch`,
   `git rev-parse HEAD`, `git remote -v`, `git branch -avv`,
   `git log --all --oneline --decorate`, `git stash list` et
   `git reflog --all --date=iso`. Vérifier aussi les fichiers ignorés avec
   `git status --short --ignored`. Les URLs privées/credentials doivent être
   expurgés avant transmission.
3. **Localiser les preuves AVM-11D–12** dans cette copie et ses branches :
   chemins du moteur, fenêtres, tests et rapports ; SHA de la révision testée ;
   lien de run GitHub ou JUnit/rapport local attestant les 321 tests.
   Vérifier particulièrement le paquet Python `library` manquant ici.
4. **Choisir la récupération selon les preuves** :
   - Déjà poussé ailleurs : communiquer dépôt, branche et SHA, puis obtenir
     l'accès en lecture ; ne pas remplacer origin à l'aveugle.
   - Committé seulement localement : conserver les références dans la
     sauvegarde et, après revue de secrets/diff, publier manuellement une
     branche de récupération au nom neuf, sans forcer une branche existante.
   - Non committé : garder la sauvegarde des fichiers, examiner le diff et les
     fichiers non suivis/ignorés, puis effectuer une sauvegarde Git ciblée sur
     une branche neuve après revue. Ne pas utiliser `git add .` aveuglément.
   - Ancienne branche supprimée : rechercher le SHA dans le reflog local et
     sauvegarder une référence vers le commit retrouvé, sans déplacer HEAD.
     Un bundle Git peut conserver les commits/références, mais **ne sauvegarde
     pas** les modifications non committées ni les fichiers non suivis.
5. **Comparer la révision récupérée aux deux lignées connues** avant de choisir
   une base AVM-13 : CD D3–D8 du checkpoint VS Code et inspection AVM-11B.
   Aucun ensemble n'est à écraser. Relever les commits déjà contenus et les
   conflits potentiels, notamment dans l'orchestrateur CI partagé.
   Toute intégration manuelle/PR ultérieure nécessite une décision séparée ;
   aucune fusion automatique n'est recommandée ou effectuée ici.
6. **Fixer une base commune vérifiable**, dépôt + branche + SHA exact, puis
   seulement avec le code complet exécuter les tests CD/DVD/UI et la CI
   existants sur cette révision. Conserver le lien du run et les JUnit.
   Mettre main à jour uniquement par une intégration revue et autorisée ;
   lancer AVM-13 sur le SHA retenu après cette validation.

## 7. Bilan et arrêt

La divergence Git est précisément localisée et les deux ensembles accessibles
sont conservés. La version la plus complète **annoncée** AVM-12 n'est pas
accessible ; la version la plus récente en date n'est pas nécessairement
un surensemble fonctionnel.

**Verdict final : DIVERGENCE IDENTIFIÉE**, avec récupération AVM-11D–12
bloquée jusqu'à identification de sa provenance locale/externe.
Seul ce rapport est ajouté à la branche active ; son commit sera un descendant
du HEAD initial documenté, et ne synchronisera pas les branches fonctionnelles.
Aucun fichier CD/DVD/UI, dépendance, configuration applicative ou donnée
n'est modifié. Aucun reset, push forcé, rebase, checkout ou fusion n'a eu lieu.
Arrêt après ce rapport, sans développement AVM-13 ni mandat suivant.
