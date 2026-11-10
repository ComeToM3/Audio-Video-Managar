# AVM-21 — Nettoyage contrôlé et organisation du dépôt

**Verdict : VALIDÉ pour le nettoyage structurel à faible risque.** Aucun code produit, test, rapport antérieur, preuve, média personnel, base SQLite ou dossier de job n’a été déplacé ou supprimé.

## Structure et actions

| Zone | Avant | Après |
|---|---|---|
| `architecture/reports/` à la racine | Dossier vide, non suivi | Retiré après vérification qu’il contenait zéro élément |
| `docs/architecture/reports/` | Emplacement canonique, rapports et preuves | Inchangé; rapport AVM-21 ajouté ici |
| `scripts/` | Runner CI, diagnostics et générateurs de captures | Inchangé; aucun déplacement |
| `prototypes/` | Quatre générations déjà regroupées | Inchangé; aucun nouveau niveau d’archive |
| `.ci/`, `.capture_avm*/` | Artefacts locaux ignorés par Git | Conservés; aucune purge |

Les chemins des scripts historiques et prototypes apparaissent dans des rapports, des liens et des commandes reproductibles. Les déplacer rendrait ces références invalides et obligerait à modifier des documents historiques; aucun déplacement sans risque n’a donc été établi. Le lanceur `scripts/diag10e/` et le module produit distinct `audio_video_manager/diag10e_isolation.py` restent à leur place.

## Artefacts locaux à décider

- Candidats anciens dans `.ci/` : les quatre répertoires `avm10c1-junit/` (29 fichiers), `avm10c2-junit/` (17), `avm10c2-orch-junit/` (12), `avm10d-junit/` (1), et les 24 fichiers dont le nom commence par `avm10c1-`, `avm10c2-` ou `avm10d-`. Ensemble : 83 fichiers, 122 606 octets, dernières dates du 3 novembre 2026. **Aucune suppression effectuée; autorisation requise.** Les résultats plus récents, dont AVM-19 du 8 novembre, sont exclus de cette liste.
- Captures locales : neuf dossiers, et non sept comme indiqué dans AVM-20 : `.capture_avm06l/`, `.capture_avm06m/`, `.capture_avm06n/`, `.capture_avm06o/`, `.capture_avm07a/`, `.capture_avm08b/`, `.capture_avm08d/`, `.capture_avm08d1/`, `.capture_avm08e/`. Ils contiennent 183 fichiers (2 903 770 octets), datés du 3 novembre 2026. **Aucune suppression effectuée; autorisation requise.**
- Les sorties de la CI AVM-21 ont été écrites sous `.ci/avm21-structure-results.json` et `.ci/junit/avm21-structure/`, sans écraser d’ancien résultat; ces chemins restent ignorés par Git.

Les modifications Git préexistantes, notamment dans le code produit, les tests, les rapports et `scripts/run_tests_ci.py`, ont été préservées. Les rapports et preuves AVM-11 à AVM-20 ainsi que les dossiers de jobs et données personnelles n’ont pas été touchés.

## Validations

- Références de chemins recherchées dans les sources, scripts et documents; aucune actualisation nécessaire puisque rien n’a été déplacé.
- Runner CI Windows existant : `.venv/Scripts/python.exe scripts/run_tests_ci.py --report .ci/avm21-structure-results.json --junit-dir .ci/junit/avm21-structure` — **14 groupes, 369 tests, 0 échec, 0 erreur, 0 skip, 0 crash natif; GO**.
- Import de `audio_video_manager` et résolution du point d’entrée `audio_video_manager.__main__:main` : OK.
- `git diff --check -- scripts/run_tests_ci.py` : OK; ce fichier contenait déjà des modifications non commitées, conservées sans changement.

**Arrêt AVM-21 :** toute purge de `.ci/` ou `.capture_avm*/` attend une approbation explicite. Aucun mandat de déplacement ou de refactorisation supplémentaire n’est engagé.