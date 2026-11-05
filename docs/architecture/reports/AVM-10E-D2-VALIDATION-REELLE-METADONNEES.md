# AVM-10E-D2 — Validation réelle de l'enrichissement des métadonnées

**Date :** 2026-11-04  
**Version AVM :** 0.5.0  
**Support :** CD audio physique, Disc ID autorisé `HKAtvzd2gALbaC2d4HONIWPCE0Q-`  
**Périmètre respecté :** préflight, lecture physique, lancement isolé, essai du flux jusqu'au garde MusicBrainz et non-régression. Aucun rip, aucune approbation et aucune interruption.

## Verdict

**NON VALIDÉ** pour le parcours réel d'identification/enrichissement et d'approbation. Le disque et les destinations sont correctement identifiés, mais l'interface bloque l'identification en ligne avant la requête MusicBrainz parce que `AVM_MUSICBRAINZ_CONTACT` n'est pas configuré. Aucun candidat n'a donc été affiché dans cette exécution D2; ni proposition Discogs ni approbation réelle ne sont possibles.

**AVM-10E-D demeure suspendu.** L'extraction est interdite dans ce mandat et n'a pas été tentée.

## 1. Préflight et observation physique

| Contrôle | Statut | Observation |
|---|---|---|
| Batch isolé `run_app_10e_isolated.bat` | **PASS** | Préflight uniquement : code retour `0`, `.venv` Python 3.12.10 et chemins allowlistés |
| fre:ac `--list-drives` | **PASS** | Code retour `0`; lecteur `0`, path `1:0:0`, ATAPI iHAS324 C |
| TOC physique relue avec libdiscid | **PASS** | Device `D:`, 22 pistes |
| Disc ID physique | **PASS** | `HKAtvzd2gALbaC2d4HONIWPCE0Q-`, égal à l'ID autorisé |
| Bibliothèque et jobs 10E avant/après | **PASS** | Vides; 0 fichier publié, 0 job |
| SQLite 10E en lecture seule après le parcours | **PASS** | `jobs=0`, `releases=0`, `tracks=0`, `disc_metadata=0` |
| Espace libre | **PASS** | Environ 324 479 MiB sur les deux cibles, même volume C: |
| Extraction et vérification FLAC | **SKIP** | Non autorisées/non exécutées |

Les mesures TOC observées à cette session sont : `214000, 215000, 192000, 246000, 187000, 144000, 191000, 143000, 144000, 186000, 188000, 171000, 153000, 356000, 227000, 230000, 222000, 225000, 158000, 205000, 186000, 111000` ms. Le wizard affichait « CD 22 pistes » après la relecture.

## 2. Configuration API et blocage réseau

Les variables ont été vérifiées par présence seulement; aucune valeur secrète n'a été lue ni affichée.

| Prérequis | Statut effectif | Effet |
|---|---|---|
| `AVM_MUSICBRAINZ_CONTACT` | **ABSENT** | Le client D1 refuse avant toute requête réseau; l'UI affiche explicitement le besoin d'une URL HTTPS ou d'un `mailto:` joignable |
| `AVM_DISCOGS_TOKEN` | **ABSENT** | Au 4 novembre 2026, Discogs indique que l'accès anonyme reste disponible jusqu'au 1 décembre 2026; le jeton n'est pas encore un blocage à cette date |
| Reachability MusicBrainz dans cette exécution D2 | **NON TESTÉE** | Aucun HTTP n'a été émis, le garde de User-Agent a échoué avant réseau |
| Reachability Discogs dans le flux D2 | **SKIP** | Aucun candidat MB sélectionné; pas d'appel Discogs depuis AVM |
| Python | **PASS** | Python 3.12.10 x64, autorisé pour cet essai |

Le message UI observé est : « Impossible d’identifier en ligne : MusicBrainz requiert un contact joignable dans le User-Agent; définissez AVM_MUSICBRAINZ_CONTACT (URL HTTPS ou mailto). Vous pourrez compléter la fiche manuellement à l’étape suivante. » Ce garde est correct et n'a pas été contourné.

Le token Discogs n'est lu que dans l'environnement et n'est jamais affiché, écrit dans `config.json` ou persisté dans la fiche. Une distribution Windows destinée à un utilisateur non technique ne fournit actuellement aucun champ Paramètres pour le contact MusicBrainz ni pour le jeton Discogs; configurer ces valeurs demande une action hors application. Le contact ne peut pas être remplacé par le placeholder `github.com/local` ni par une URL inventée.

## 3. Résultat du parcours UI

| Étape | Statut | Preuve / motif |
|---|---|---|
| Lancement dans l'environnement AVM-10E | **PASS** | Fenêtre AVM 0.5.0 lancée via le batch isolé |
| Relecture physique TOC | **PASS** | Log 10E `TOC lue device=D: disc_id=HKAtvzd2gALbaC2d4HONIWPCE0Q- tracks=22` à 21:04:15 |
| Lookup MusicBrainz depuis l'UI D2 | **FAIL / BLOQUÉ** | Le garde de configuration a arrêté le worker avant l'appel réseau |
| Candidats proposés en D2 | **SKIP** | Aucun résultat n'a été retourné par le worker; le candidat observé lors de D1 n'est pas une réponse de cette exécution |
| Suggestions d'enrichissement Discogs affichées en D2 | **SKIP** | Le flux n'a pas atteint l'étape d'enrichissement |
| Approbation humaine | **SKIP** | L'écran des candidats/approbation n'a pas été atteint; aucune valeur n'a été approuvée |
| Correction de fiche réelle | **SKIP** | Aucune fiche candidate n'a été créée ou persistée |
| Extraction | **SKIP / INTERDITE** | Aucun rip ni processus fre:ac d'extraction lancé |

Le rapport D1 et les tests automatisés consignent les données obtenues dans une exécution antérieure : release MBID `09bdc53c-46a6-4825-8ccf-b0608f56d746`, release-group `e005180f-f693-4f05-950a-27a4fac6e89d`, date du release absente, première date du groupe 2002 et classification Compilation. Ces faits servent de contexte/documentation, mais **ne sont pas présentés comme candidats resservis par l'application en D2**.

## 4. Durées, années et compilation

L'exécution D2 a relu une TOC de 22 pistes, mais n'a pas reçu de tracklist MusicBrainz live parce que le prérequis contact manque. La comparaison éditoriale détaillée de D1 reste donc la dernière mesure de sources : piste 9, la durée de recording produisait le faux écart `144000` vs `139000` ms; la durée `medium.track.length` de l'édition est `144040` ms (40 ms de la TOC). Piste 21, le faux écart était `186000` vs `183000` ms; la durée d'édition est `185600` ms (400 ms de la TOC). D1 a aussi comparé les 22 titres/ordres MusicBrainz et Discogs et obtenu 22 concordances après normalisation.

| Élément | Validation D2 |
|---|---|
| Date d'édition | **SKIP** en UI réelle; D1 trouvait la date du release absente et Discogs `year=0` |
| Première date du groupe | Contexte D1 `2002`, distincte de l'année du pressage |
| Année inconnue justifiée | Contrôle UI couvert par les tests Qt; non exercé sur la fiche physique D2 faute de candidat |
| `is_compilation` | Le release-group D1 indique Compilation; la fiche D2 n'a pas été créée, aucun choix utilisateur n'a été fait |
| Réédition | Discogs D1 suggère Reissue/Remastered avec qualité `Needs Vote`; indice non autoritatif, pas de correction automatique |

Les changements UI D1 préservent les valeurs source, exposent l'année inconnue justifiée et gardent la compilation indéterminée jusqu'au choix utilisateur. Les corrections, approbations et révocations sont exercées en tests Qt, pas sur la fiche du disque en D2.

## 5. Régressions et intégrité production

La CI complète `scripts/run_tests_ci.py` a réussi sous Windows/Python 3.12.10 : **272 tests PASS, 0 fail, 0 error, 0 skip**, 14 groupes de processus, code retour global `0`, `skipped_unavailable=[]`.

Un manifeste `.ci/avm10e-d2-protected-before.json` contenait les SHA-256, tailles et dates de modification de **144 fichiers** sous la racine de données de production et l'archive Queen. Après le parcours UI et après la CI, les empreintes, tailles et dates sont identiques; aucune différence n'est détectée. La base 10E reste à zéro ligne dans `jobs`, `releases`, `tracks` et `disc_metadata`; la bibliothèque et `jobs-10e` sont vides.

Résultats CI : `.ci/avm10e-d2-final-results.json` et JUnit sous `.ci/avm10e-d2-final-junit/`.

## 6. Anomalies et risques utilisateurs

1. **Bloquant opérationnel :** la configuration MusicBrainz est absente et le message renvoie à une variable d'environnement non éditable dans l'application. L'utilisateur Windows non technique ne peut pas résoudre ce blocage depuis AVM.
2. **Auth Discogs à venir :** le token est absent; les conditions annoncées changent le 1 décembre 2026. AVM n'a pas de champ UI de configuration.
3. **Pas de candidats D2 :** année inconnue, compilation, réédition et conflit de sources n'ont pas pu être inspectés dans le wizard lors de cette exécution.
4. **Risque d'attribution/licence :** D1 a relevé que les conditions Discogs exigent attribution par donnée et encadrent fraîcheur/conservation. Le rapport D1 recommande une revue juridique avant distribution publique.
5. **Qualité Discogs :** la fiche 1169416 est `Needs Vote`; ses indices restent de confiance faible.
6. **Python :** tests D2 sur 3.12.10 seulement; Python 3.11 non certifié.

## 7. Étapes non exécutées

- Aucun identifiant/contact manquant n'a été inventé et aucun secret n'a été affiché.
- Aucun appel réseau MusicBrainz AVM en D2, car le garde de configuration l'a refusé.
- Aucun appel Discogs depuis le flux UI D2, puisqu'aucun candidat n'a été obtenu.
- Aucune sauvegarde de fiche, aucune approbation, aucune révocation réelle et aucun rip.
- Aucune modification de dépendance, licence, donnée de production ou archive Queen.

## Conclusion

Le contrôle physique et l'isolation sont **PASS**; le comportement fail-closed MusicBrainz est également conforme, et la CI comme l'intégrité production sont **PASS**. Mais le parcours réel d'enrichissement et d'approbation ne peut pas être validé tant qu'un contact MusicBrainz joignable n'est pas fourni à l'application.

**Verdict D2 : NON VALIDÉ** pour l'enrichissement réel et l'approbation. L'exécution a été arrêtée au garde de configuration; aucun contournement ni rip n'a été entrepris. AVM-10E-D reste suspendu.