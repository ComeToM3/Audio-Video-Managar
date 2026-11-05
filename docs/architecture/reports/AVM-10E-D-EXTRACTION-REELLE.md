# AVM-10E-D — Extraction réelle du CD de 22 pistes

**Date :** 2026-11-04  
**Version AVM :** 0.5.0  
**Disc ID autorisé :** `HKAtvzd2gALbaC2d4HONIWPCE0Q-`  
**Résultat du mandat :** arrêt avant approbation et avant extraction, conformément à la politique d'arrêt en cas d'anomalie.

## Verdict

**NON VALIDÉ. AVM-10E-E ne peut pas commencer.** Le préflight et l'identification du média ont réussi, mais la fiche proposée par MusicBrainz est encore `Pending` et présente des erreurs de validation. L'année n'est pas renseignée/confirmée, la nature compilation n'a pas été confirmée par l'utilisateur, et la correspondance des durées TOC est partielle. Aucune approbation humaine n'a été effectuée et aucun rip n'a été lancé.

L'extraction reste à reprendre après examen humain de l'édition et résolution des champs obligatoires dans l'application. L'interface AVM est laissée ouverte sur l'écran d'approbation ; le bouton « Approuver la fiche » n'a pas été activé.

## 1. Préflight et identité du média

| Contrôle | Statut | Preuve |
|---|---|---|
| Launcher isolé | **PASS** | `scripts/diag10e/run_app_10e_isolated.bat`, mode normal ; préflight retourne `0` |
| Python | **PASS** | `.venv\Scripts\python.exe`, Python 3.12.10 x64 |
| Chemins effectifs | **PASS** | `AVM_DATA_DIR=...\AudioVideoManager-10E`, bibliothèque `...\AVM-10E-Test-Library`, SQLite/config/logs/jobs sous les racines 10E allowlistées |
| fre:ac `--list-drives` | **PASS** | Retour `0`; lecteur `0`, path `1:0:0`, `ATAPI iHAS324 C` |
| TOC physique relue | **PASS** | Logs à 19:32:17 et 19:32:50 : device `D:`, Disc ID autorisé, 22 pistes |
| Concordance Disc ID / pistes | **PASS** | `HKAtvzd2gALbaC2d4HONIWPCE0Q-`, exactement 22 pistes |
| Espace libre | **PASS** | 337 783 967 744 octets, soit 322 135,9 MiB sur jobs et bibliothèque (même volume C:) |
| fre:ac, libdiscid, FFmpeg | **PASS** | fre:ac et libdiscid utilisés pour les probes ; le runner domaine détecte fre:ac, `discid` et FFmpeg ; binaire FFmpeg déjà vérifié dans AVM-10E-C |
| Python 3.11 | **SKIP** | Non installé parmi les interpréteurs détectés ; cet essai utilise Python 3.12.10, sans certifier 3.11 |

TOC mesurée, pistes 01–22, en millisecondes : `214000, 215000, 192000, 246000, 187000, 144000, 191000, 143000, 144000, 186000, 188000, 171000, 153000, 356000, 227000, 230000, 222000, 225000, 158000, 205000, 186000, 111000`.

## 2. Protection et état initial

Le manifeste `.ci/avm10e-d-protected-before.json` a été créé avant le lancement de l'application. Il contient les SHA-256, tailles et dates de modification de **144 fichiers** couvrant la racine de données de production et l'archive Queen.

| Contrôle | Résultat |
|---|---|
| Bibliothèque 10E avant parcours | 0 fichier |
| `jobs-10e` avant parcours | 0 entrée |
| SQLite 10E avant parcours | `jobs=0`, `releases=0`, `tracks=0` |
| SHA-256 production + Queen après le parcours et les tests | **Identiques** au manifeste ; aucun changement détecté |
| Bibliothèque / jobs 10E à l'arrêt | Toujours vides |
| SQLite 10E à l'arrêt | `jobs=0`, `releases=0`, `tracks=0`, `disc_metadata=0` |

## 3. Identification et approbation

Le parcours applicatif a relu le disque, avancé à l'identification et présenté **un seul candidat** MusicBrainz :

| Champ | Valeur observée |
|---|---|
| Artiste album | Charles Aznavour |
| Titre | *Ses plus grands succès (pour vous au Québec)* |
| Pays | CA |
| Release MBID | `09bdc53c-46a6-4825-8ccf-b0608f56d746` (journal CAA) |
| Candidats retournés | 1 |
| État de la fiche | `Pending` ; aucune ligne `disc_metadata` persistée |
| Approbation humaine | **Non effectuée** |

L'application signale une correspondance TOC partielle : piste 9, TOC `144000 ms` contre MusicBrainz `139000 ms`; piste 21, TOC `186000 ms` contre MusicBrainz `183000 ms`. Le statut `toc_match=partial` est conservé ; il n'a pas été transformé en correspondance exacte.

L'écran d'approbation affiche les erreurs suivantes :

- `is_compilation` n'a pas de confiance confirmée ; la case « Cet album est une compilation » est actuellement décochée, mais cet état par défaut n'a pas été interprété comme une décision de l'utilisateur.
- Année affichée `(aucune)` ; le validateur exige une année confirmée ou une indisponibilité justifiée. Aucun justificatif d'indisponibilité n'a été saisi.
- L'aperçu du chemin de bibliothèque est incomplet, en conséquence des champs obligatoires non confirmés.

Les champs artiste, titre, année (spinbox) et compilation (case) sont visibles dans l'interface. Ils n'ont pas été modifiés par l'agent : la nature compilation et l'année ne doivent pas être inventées. Le bouton d'approbation, bien que présent, n'a pas été actionné.

La pochette Cover Art Archive a été récupérée : le log indique `CAA cover OK release=09bdc53c-46a6-4825-8ccf-b0608f56d746`. Une image de 59 567 octets se trouve dans le cache isolé `AudioVideoManager-10E\cache\covers\18325d720481927d5bb58889.jpg`. Elle n'a pas été intégrée à un FLAC ni publiée ; aucune publication n'a commencé.

## 4. Extraction, intégrité et publication

| Contrôle | Statut | Résultat |
|---|---|---|
| Commande de rip fre:ac / code retour | **SKIP** | Aucune commande d'extraction émise |
| Processus `freaccmd.exe` / `freac.exe` à l'arrêt | **PASS** | Aucun processus correspondant actif |
| FLAC extraits | **SKIP** | 0 fichier ; aucune taille, durée de fichier ou erreur par piste disponible |
| Décodage intégral / contrôle FLAC | **SKIP** | Aucun FLAC à vérifier |
| Comparaison durée FLAC ↔ TOC | **SKIP** | Les seules durées disponibles sont les durées TOC et MusicBrainz ci-dessus |
| Tags, pochette intégrée, `cover.jpg` | **SKIP** | Aucun fichier de sortie |
| Nommage, doublons, collision | **SKIP** | Aucune publication tentée ; bibliothèque isolée vide |
| Cohérence publication ↔ SQLite | **PASS pour l'absence de publication** | Base sans jobs/releases/tracks et aucun fichier en bibliothèque/jobs ; cohérence post-publication non applicable |
| Interruptions physiques | **SKIP** | Aucune interruption réelle ou simulation sur média réel n'a été lancée |

Il n'existe donc aucun code retour de rip, rapport d'extraction ou résultat FLAC à présenter. L'absence de ces preuves est un blocage de validation, pas un succès implicite.

## 5. Régressions

La suite domaine de `scripts/run_tests_ci.py` a été exécutée sous Windows avec Python 3.12.10 : **185 tests PASS, 0 échec, 0 erreur, 0 skip**, code retour global `0`. Les SHA-256, tailles et dates de modification des 144 fichiers protégés ont été recalculés après les tests et correspondent au manifeste initial.

Résultats : `.ci/avm10e-d-domain-results.json` et JUnit sous `.ci/avm10e-d-domain-junit/`.

## 6. Chronologie et traçabilité

- Préflight batch isolé : retour `0`; aucun démarrage en mode production.
- Probe `freaccmd --list-drives` : retour `0`; lecteur détecté comme indiqué ci-dessus.
- Lecture TOC initiale et lecture dans le wizard : Disc ID et 22 pistes concordants.
- MusicBrainz : le journal 10E indique `candidates=1`.
- Cover Art Archive : récupération réussie pour le MBID indiqué.
- Wizard déplacé jusqu'à l'écran d'approbation ; fiche toujours Pending ; aucune action sur « Approuver ».
- Aucun processus fre:ac d'extraction ; aucun rip, fichier FLAC, job ou release créé.
- Tests domaine exécutés ; empreintes production/Queen inchangées.

Le journal applicatif est `...\AudioVideoManager-10E\logs\avm.log`. Le cache de pochette et les autres traces restent dans les emplacements 10E ; aucune purge n'a été faite.

## 7. Blocage et suite requise

Le mandat s'arrête sur la validation humaine des métadonnées. L'utilisateur doit confirmer l'édition, décider si l'album est une compilation et fournir une année vérifiée si elle est connue, puis effectuer l'approbation dans l'interface AVM. Si l'année est réellement indisponible, l'écran courant ne fournit pas de contrôle visible pour enregistrer une justification d'indisponibilité ; ne pas contourner le validateur ni modifier directement SQLite.

Après une approbation valide, reprendre le préflight et relire le Disc ID immédiatement avant tout rip. Si le média, les chemins, l'état vide des destinations ou les champs approuvés ont changé, arrêter. Ce rapport ne certifie ni l'extraction ni la publication et ne donne pas le feu vert à AVM-10E-E.