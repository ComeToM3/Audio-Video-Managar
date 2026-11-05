# AVM-10E-D1 — Diagnostic et enrichissement fiable des métadonnées

**Date :** 2026-11-04  
**Version AVM :** 0.5.0  
**État du support physique :** suspendu; aucun rip, aucune interruption et aucune approbation n'ont été effectués pendant D1.

## Verdict

**VALIDÉ SOUS RÉSERVES** pour le diagnostic, les corrections de métadonnées et les tests automatisés. Le parcours de provenance, l'année inconnue justifiée, la classification compilation, l'enrichissement optionnel et les régressions sont couverts par le code et les tests.

**Réserves avant usage réseau normal :** AVM exige maintenant une coordonnée de mainteneur MusicBrainz (`AVM_MUSICBRAINZ_CONTACT`) et aucune coordonnée réelle n'est fournie dans ce dépôt. À compter du 1er décembre 2026, Discogs annonce la fin de l'accès API non authentifié; AVM demande alors un jeton `AVM_DISCOGS_TOKEN`. L'API Discogs a été accessible pour cette recherche au 4 novembre 2026, mais sa qualité pour cette fiche est `Needs Vote`. La V1 ne doit pas interpréter ses propositions comme des faits certifiés.

L'extraction physique reste suspendue. La fiche de la phase D n'a pas été modifiée ni approuvée. Aucun mandat ultérieur n'est engagé.

## 1. Parcours audité

1. `read_disc_toc` fournit l'identité du support et les durées mesurées; le Disc ID ne désigne pas à lui seul une édition commerciale.
2. `lookup_releases_by_discid` appelle l'API MusicBrainz à raison d'au plus une requête/seconde, récupère release, medium, recordings, labels et release-group.
3. `rank_and_select_releases` peut pré-sélectionner un candidat unique ou une édition sans ambiguïté bloquante. Cela ne vaut pas approbation.
4. `apply_release_candidate` préremplit la fiche avec la provenance MusicBrainz et un niveau de confiance. La fiche reste `Pending`; `approve_sheet` est le gate métier avant archive.
5. Le formulaire de l'assistant et le dialogue DiscMetadata rendent les valeurs modifiables et la validation visible; SQLite persiste un JSON de la fiche et les événements de correction.

**Défauts établis et corrigés :**

- La durée de piste était choisie à partir de `recording.length` avant `track.length`. Une durée de recording peut décrire une autre édition ou un autre montage; elle n'est pas la durée de la piste sur ce medium.
- Le release-group fournissait `first-release-date`, mais AVM ne le conservait pas. Il ne faut pas substituer cette date à celle du release exact.
- `is_compilation` était un booléen par défaut `False`; toute édition d'un champ dans le wizard pouvait le confirmer sans décision explicite.
- Le wizard possédait déjà `year_unavailable_justification` et une validation `UNAVAILABLE`, mais ne permettait pas de la saisir. L'année du release-group ne pouvait donc pas être distinguée d'une année d'édition inconnue dans le flux principal.
- Le dialogue DiscMetadata réécrivait la provenance et les champs source à la validation, même sans changement, et pouvait conserver un état Approved après modification.
- Les données de correction des pistes et les IDs de recordings étaient perdus lors de la reconstruction de la table.

## 2. Sources et résultats pour le CD candidat

| Source primaire | Données pertinentes observées |
|---|---|
| [MusicBrainz — lookup Disc ID](https://musicbrainz.org/ws/2/discid/HKAtvzd2gALbaC2d4HONIWPCE0Q-?fmt=json&inc=artists+labels+recordings+release-groups) | Un candidat correspondant à 22 pistes; release CA et Disc ID exact |
| [MusicBrainz — release `09bdc53c-46a6-4825-8ccf-b0608f56d746`](https://musicbrainz.org/ws/2/release/09bdc53c-46a6-4825-8ccf-b0608f56d746?fmt=json&inc=artists+labels+recordings+release-groups) | Charles Aznavour, *Ses plus grands succès (pour vous au Québec)*, pays CA, code-barres `724353848620`, date de release absente, label-info-list vide, 22 tracks |
| [MusicBrainz — release-group `e005180f-f693-4f05-950a-27a4fac6e89d`](https://musicbrainz.org/ws/2/release-group/e005180f-f693-4f05-950a-27a4fac6e89d?fmt=json&inc=artists+releases) | *Ses plus grands succès*, première date `2002`, type principal `Album`, type secondaire `Compilation` |
| [Discogs — recherche API par code-barres](https://api.discogs.com/database/search?barcode=724353848620&artist=Charles%20Aznavour&type=release) | Un résultat exact, release 1169416 |
| [Discogs — release 1169416](https://api.discogs.com/releases/1169416) | Canada, EMI Music Canada, catalogue `72435-38486-2-0`, barcode concordant, `year=0`, formats CD/Compilation/Reissue/Remastered, `data_quality=Needs Vote`, note ℗/© 2002 |

**Interprétation des dates :** le release MBID est une édition CA sans date; le release-group donne sa première publication connue en 2002. La réponse Discogs donne `year=0`, pas une année de release confirmée. Sa note attribue ℗/© 2002 à EMI Music France et liste des dates ℗/© pour des pistes distinctes. Ni la première date du groupe ni une date de copyright ne sont converties en année de cette édition.

**Classification :** MusicBrainz définit Compilation comme une collection de recordings de sources antérieures, notamment best-of/rétrospectives; une simple réédition d'un album n'est pas automatiquement une compilation. Ici, le release-group est explicitement `Album + Compilation`, et Discogs qualifie aussi le pressage de Compilation et Reissue. C'est une preuve concordante, mais l'AVM demande toujours à l'utilisateur de confirmer la classification de son exemplaire.

**Qualité et limites Discogs :** la source API est accessible par l'API documentée, pas par scraping. La fiche porte `Needs Vote`, donc ses champs sont affichés comme confiance faible. Les champs consultés sont ceux déclarés CC0 par les conditions Discogs (titre, notes, date, format, tracklist, barcode, identifiants, labels); aucune image, donnée Marketplace, communauté, rating ou prix n'est téléchargé. Le résultat brut n'est pas mis en cache. Les conditions imposent attribution à proximité des données, un User-Agent distinct et le respect des limites; le panneau le fait. Les conditions permettent de revoir/retirer l'API et les données, et limitent leur fraîcheur/stockage; toute distribution publique ou conservation de valeurs dérivées doit faire l'objet d'une revue juridique des conditions en vigueur.

MusicBrainz documente une requête par seconde par IP et exige un User-Agent significatif; ses données core sont CC0, tandis que des données supplémentaires ont d'autres conditions. Voir [API](https://musicbrainz.org/doc/MusicBrainz_API), [limitation](https://musicbrainz.org/doc/MusicBrainz_API/Rate_Limiting), [licence](https://musicbrainz.org/doc/About/Data_License), [types de release-group](https://musicbrainz.org/doc/Release_Group/Type). Discogs : [conditions API](https://support.discogs.com/hc/articles/360009334593-API-Terms-of-Use), [documentation/API et limites](https://www.discogs.com/developers/).

## 3. Comparaison des pistes

TOC du CD lue physiquement lors d'AVM-10E-D : Disc ID `HKAtvzd2gALbaC2d4HONIWPCE0Q-`, 22 pistes. Les durées MusicBrainz ci-dessous sont celles de `medium.track.length` (la durée du track sur cette édition), et non `recording.length`. Les durées Discogs sont les durées affichées au format minute/seconde, donc arrondies à la seconde.

| # | Titre MusicBrainz / Discogs | TOC ms | MB track ms | Δ ms | Discogs |
|---:|---|---:|---:|---:|---:|
| 1 | Emmenez‐moi / Emmenez-Moi | 214000 | 213693 | 307 | 3:31 |
| 2 | Et moi dans mon coin / Et Moi Dans Mon Coin | 215000 | 215040 | 40 | 3:32 |
| 3 | Je te réchaufferai / Je Te Réchaufferai | 192000 | 191933 | 67 | 3:09 |
| 4 | La Bohème | 246000 | 246493 | 493 | 4:05 |
| 5 | Dans tes bras | 187000 | 186906 | 94 | 3:05 |
| 6 | Les Comédiens | 144000 | 143893 | 107 | 2:23 |
| 7 | Il faut savoir | 191000 | 190600 | 400 | 3:08 |
| 8 | Hier encore | 143000 | 142706 | 294 | 2:20 |
| 9 | For me… formidable / For Me...Formidable | 144000 | 144040 | 40 | 2:21 |
| 10 | J’en déduis que je t’aime / J'En Déduis Que Je T'Aime | 186000 | 186026 | 26 | 3:04 |
| 11 | Mes emmerdes | 188000 | 188240 | 240 | 3:05 |
| 12 | Et pourtant | 171000 | 170826 | 174 | 2:49 |
| 13 | Sur ma vie | 153000 | 153533 | 533 | 2:31 |
| 14 | Les Plaisirs démodés | 356000 | 356080 | 80 | 5:52 |
| 15 | La Mamma | 227000 | 227093 | 93 | 3:45 |
| 16 | Les Deux Guitares | 230000 | 230533 | 533 | 3:48 |
| 17 | Tu t’laisses aller | 222000 | 221946 | 54 | 3:40 |
| 18 | L’amour c’est comme un jour | 225000 | 224920 | 80 | 3:43 |
| 19 | Le Temps | 158000 | 158360 | 360 | 2:35 |
| 20 | Je m’voyais déjà | 205000 | 205173 | 173 | 3:22 |
| 21 | Plus bleu que tes yeux | 186000 | 185600 | 400 | 3:03 |
| 22 | Reste | 111000 | 110040 | 960 | 1:50 |

Les **22 titres et leur ordre concordent** après normalisation Unicode, casse et ponctuation. Les durées du medium MB sont toutes à moins de 1 seconde de la TOC; delta maximal 960 ms. Le vieux comparateur lisait par erreur la durée recording : piste 9, `144000` vs `139000` (5 s), alors que le track de l'édition vaut `144040` (40 ms); piste 21, `186000` vs `183000` (3 s), alors que le track de l'édition vaut `185600` (400 ms). `toc_match` est maintenant calculé sur les tracks du release, sans cacher la différence entre track et recording.

À noter : le dialogue CAA/Discogs porte des titres typographiques/majuscules différentes, non des divergences de contenu. La piste 21 crédite aussi Édith Piaf comme interprète dans MusicBrainz; l'artiste d'album reste Charles Aznavour.

## 4. Changements implémentés

- `musicbrainz_client.py` utilise d'abord la durée du track du medium, conserve séparément la date, le type principal et les types secondaires du release-group, et passe la version User-Agent à 0.5.0.
- `models.py` ajoute `first_release_date` à `ReleaseEdition` et au JSON de `DiscMetadata`; les payloads SQLite existants le lisent comme absent (`None`), sans migration SQL.
- `apply_lookup.py` propose Compilation avec confiance `ambiguous`, provenance MusicBrainz et lien release-group. Il ne change pas cette valeur en confirmé et refuse l'enrichissement direct d'une fiche déjà Approved.
- `enrichment.py` fournit les objets source, valeur, URL, confiance, note, heure de collecte, conflits et comparaison tracklist/durée; recherche Discogs par barcode exact, refuse les résultats multiples, ne scrape pas et ne persiste pas les réponses. Les suggestions ne sont pas appliquées automatiquement.
- `identify_worker.py` effectue les requêtes Discogs hors thread UI; le wizard affiche les propositions et liens à côté du formulaire avant approbation, ainsi que l'information de première date du groupe.
- Le wizard permet `year=None` + justification `UNAVAILABLE`, garde distincte la première date du groupe, et présente la compilation en tri-state. Une valeur ambigüe n'est confirmée que sur choix explicite. Les corrections manuelles conservent leurs URL source dans `FieldMeta.note`.
- `metadata_dialog.py` reçoit les mêmes garde-fous : compilation tri-state, validation passive sans réécriture de provenance/IDs, correction des pistes auditée et révocation de l'approbation si son empreinte change.
- `approval_fingerprint.py` inclut année inconnue justifiée, première date du groupe et MBID du groupe afin qu'une modification impose une réapprobation.
- `scripts/run_tests_ci.py` exécute les tests d'enrichissement et de provenance des deux interfaces.

**User-Agent et secret :** l'ancien contact `https://github.com/local/AudioVideoManager` était un placeholder. Il est supprimé. Les requêtes runtime MusicBrainz exigent désormais `AVM_MUSICBRAINZ_CONTACT`, URL HTTPS réelle ou `mailto:` joignable; sans valeur, le client échoue clairement avant le réseau. Aucun contact public n'est défini dans ce dépôt. `AVM_DISCOGS_TOKEN` est lu seulement depuis l'environnement; il n'est jamais enregistré dans `config.json`, les logs ou la fiche.

## 5. Tests et intégrité

| Vérification | Résultat |
|---|---|
| Tests ciblés enrichissement / durée / dates | **PASS** |
| Tests W3 et dialogue DiscMetadata | **PASS** |
| Provenance, SQLite JSON round-trip, approbation et empreintes | **PASS** |
| CI complète `scripts/run_tests_ci.py` | **PASS** — 272 tests, 0 fail, 0 error, 0 skip, 14 groupes, retour `0` |
| Diagnostics statiques des fichiers modifiés | **PASS** — aucune erreur signalée |
| Python utilisé | Python 3.12.10 x64; Python 3.11 reste non certifié |
| SHA-256, taille et mtime des données production + Queen avant/après CI | **PASS** — 144 fichiers, aucune différence |
| Rip, interruption, DB production et archives réelles | **SKIP** — non exécutés ni modifiés |

Résultats CI : `.ci/avm10e-d1-verified2-results.json` et JUnit sous `.ci/avm10e-d1-verified2-junit/`.

## 6. Limites et décisions à garder

1. La date d'édition exacte reste inconnue : l'application permet de déclarer `UNAVAILABLE` avec justification. La première date du groupe (`2002`) et les dates ℗/© restent des champs contextuels distincts.
2. Discogs `Needs Vote` est une donnée contributive de confiance faible; les informations de format « Compilation/Reissue/Remastered » sont des propositions, pas des corrections automatiques.
3. L'API Discogs non authentifiée cessera selon son annonce le 1 décembre 2026. Pour continuer, configurer un jeton par `AVM_DISCOGS_TOKEN`; l'application n'en propose pas encore la saisie dans Paramètres. Aucun contournement de limite n'est prévu.
4. `AVM_MUSICBRAINZ_CONTACT` doit être fourni par le mainteneur avant toute identification depuis l'application. Aucun contact réel n'est déductible du dépôt et aucun n'a été inventé.
5. L'API Discogs exige attribution et limite la conservation/l'actualité de ses données; AVM ne stocke pas le résultat brut et n'affiche pas d'images Discogs. Les liens source retenus par l'utilisateur dans une correction sont conservés avec cette correction; faire confirmer la compatibilité juridique de ce comportement avant distribution publique.
6. La comparaison éditoriale ne remplace pas l'inspection physique du livret ou le rip. La validation CD reste suspendue et AVM-10E-D n'est pas repris.

## Conclusion

Le défaut de durée, la confusion de date et l'approbation implicite de `is_compilation` sont corrigés et couverts. Les propositions sourcées restent humaines, les valeurs inconnues sont explicites, et la CI comme les empreintes protégées sont PASS.

**Verdict D1 : VALIDÉ SOUS RÉSERVES.** La fonctionnalité d'enrichissement est prête pour essais UI sans rip; les requêtes MusicBrainz nécessitent une vraie coordonnée `AVM_MUSICBRAINZ_CONTACT`, Discogs deviendra dépendant d'un jeton au 1 décembre 2026, et sa conservation publique exige une revue des conditions. L'extraction physique demeure suspendue; AVM-10E-D n'est pas repris sans nouvelle autorisation.