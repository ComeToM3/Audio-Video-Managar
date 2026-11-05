# AVM-10E-D2A — Configuration d'identité MusicBrainz

**Date :** 2026-11-04  
**Version projet :** 0.5.0  
**Périmètre :** construction et validation du User-Agent MusicBrainz; tests unitaires/intégration mockés, CI et intégrité production.  
**Hors périmètre :** requête live, UI d'approbation, Discogs, rip et modification d'archives.

## Verdict

**VALIDÉ** pour le mandat de configuration d'identité. Le client MusicBrainz utilise maintenant une identité unique dérivée du nom de l'application et de la version réelle du package, avec le contact officiel autorisé par défaut. Les surcharges sont optionnelles et validées strictement; une valeur invalide échoue avant la fonction de lookup. Le User-Agent complet a été vérifié avec un test d'intégration mocké.

La configuration effective de cet environnement utilise le défaut `AudioVideoManager / 0.5.0 / mailto:johan_dominguez@hotmail.com`; aucune surcharge `AVM_MUSICBRAINZ_CONTACT` n'est présente. Le test D2A n'a émis aucune requête réseau réelle et ne reprend pas AVM-10E-D.

## 1. Modifications

- Nouveau `audio_video_manager/metadata/musicbrainz_identity.py` : source centrale de l'identité, version tirée de `audio_video_manager.__version__`, contact par défaut autorisé et validation des contacts `mailto:`/HTTPS.
- `AVM_MUSICBRAINZ_CONTACT` reste une surcharge facultative. Une variable explicitement définie mais vide/invalide est refusée; elle ne retombe pas silencieusement sur le défaut.
- `musicbrainz_client.configure_musicbrainz` délègue désormais à ce résolveur et transmet `(AudioVideoManager, 0.5.0, contact)` à `musicbrainzngs.set_useragent`. Le paramètre `user_agent` existant reste compatible, mais son tuple est validé par le même composant.
- Le placeholder non joignable `https://github.com/local/AudioVideoManager` a été supprimé. Aucun fallback fictif ne subsiste.
- `tests/test_musicbrainz_identity.py` est inclus dans la suite domaine du runner CI.

## 2. Validation et comportement

| Cas | Résultat |
|---|---|
| Identité par défaut | **PASS** — nom `AudioVideoManager`, version `0.5.0`, contact `mailto:johan_dominguez@hotmail.com` |
| Surcharge `mailto:` valide | **PASS** |
| Surcharge HTTPS valide | **PASS** |
| Contact absent/chaîne vide dans le résolveur pur | **FAIL-CLOSED** — rejet; le chemin applicatif normal choisit le défaut si la variable n'existe pas |
| Surcharges mal formées (scheme non permis, hôte absent, identifiant/mot de passe dans URL, mailto invalide) | **PASS** — refusées |
| Intégration client → `set_useragent` → lookup | **PASS** — le test vérifie l'ordre et le tuple exact avant un lookup mocké |
| Surcharge invalide dans le client | **PASS** — exception `MusicBrainzError` avant l'appel de lookup mocké |
| Requête live MusicBrainz | **SKIP** — aucune requête réelle exécutée pendant D2A |
| Discogs | **SKIP / inchangé** — aucun changement de comportement ni de configuration Discogs |

Tests ciblés : `tests/test_musicbrainz_identity.py` — **15 PASS**. L'essai runtime de résolution a observé le défaut exact et l'absence de surcharge; aucune valeur secrète n'a été affichée.

## 3. Non-régression et intégrité des données

La CI complète `scripts/run_tests_ci.py` passe sous Windows x64/Python 3.12.10 : **286 tests, 0 échec, 0 erreur, 0 skip**, 14 groupes de processus, code retour `0`, `skipped_unavailable=[]`.

SHA-256, tailles et dates de modification avant/après CI : **144 fichiers** de la racine de données de production et de l'archive Queen; aucune différence détectée. Aucun accès en écriture à la base production ou à la bibliothèque Queen n'a été fait.

Résultats : `.ci/avm10e-d2a-final-results.json` et JUnit sous `.ci/avm10e-d2a-final-junit/`.

Python 3.11 n'est pas installé dans les environnements détectés; D2A est validé sous 3.12.10 uniquement, sans déclarer 3.11 équivalent.

## 4. Limites

1. Le contact autorisé est un contact de mainteneur fourni par le mandat. Il n'a pas été vérifié par envoi de courriel, et aucune requête API n'a été envoyée pendant D2A.
2. La requête réelle doit respecter le plafond MusicBrainz (une requête/seconde) et l'API peut rester indisponible; cette validation teste le transport via des mocks, pas la reachability du service.
3. La surcharge HTTPS accepte seulement une URL sans credentials, query ni fragment; les surcharges `mailto:` doivent être une adresse simple valide.
4. Aucun changement de dépendance, licence, Discogs, UI, extraction ou production n'a été effectué.

## Conclusion

L'identité est centralisée, liée à la version réelle du package et utilisable sans configuration manuelle grâce au contact par défaut autorisé. Toute surcharge invalide bloque avant réseau. Les tests ciblés, la CI complète et le contrôle cryptographique des fichiers protégés passent.

**Verdict D2A : VALIDÉ.** La validation ne certifie pas la disponibilité live de MusicBrainz et ne valide pas AVM-10E-D; toute reprise physique reste suspendue jusqu'à une autorisation distincte.