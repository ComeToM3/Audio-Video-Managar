# AVM-11B3 — Validation physique DVD et étude des protections

Date : 2026-11-06 · AudioVideoManager 0.5.0 · Windows 11 · lecteur `D:`.

**Verdict : VALIDÉ pour l’inspection en lecture seule de ce DVD physique avec le backend standard CSS-off; NON DÉCIDÉ pour les DVD commerciaux protégés.** L’énumération des deux titres, la sélection heuristique du plus long et le probe des flux ont réussi. Aucun déchiffrement, extraction, conversion ou écriture de média n’a été effectué. La réussite de lecture ne prouve pas l’absence de CSS sur l’ensemble du contenu ni ne valide un traitement de DVD protégés.

## 1. Résumé exécutif

- Le volume UDF `USE_YOUR_ILLUSION_1` est lisible en `D:`. La structure `AUDIO_TS/` et `VIDEO_TS/` est présente; deux jeux VTS (`01`, `02`) ont été trouvés.
- libdvdnav énumère 2 titres, 5 et 15 parties, 1 angle chacun. Le candidat le plus long est le titre 2, 5 403,6 s (1:30:03,6). L’option AVM `auto_select_main_title=True` l’a sélectionné et ffprobe a fini en 4,66 s. C’est une heuristique de durée, pas une preuve d’intention éditoriale.
- Les deux titres ont un flux vidéo MPEG-2 720×480 et un flux audio AC-3 anglais, 48 kHz, 2 canaux stéréo. Aucun flux sous-titre n’a été signalé. Les champs non fournis, notamment langue vidéo, restent inconnus.
- Une erreur d’intégration démontrée (journaux natifs mélangés au JSON) et une erreur d’interprétation démontrée (libdvdnav renvoie les fins cumulées des parties) ont été corrigées. Les 16 tests DVD passent; la CI complète passe avec 302 tests.
- libdvdcss sait déchiffrer CSS et possède un build Windows, mais cela ne le rend pas juridiquement neutre au Canada. L’architecture peut isoler un backend facultatif; l’isolation technique ne crée aucune autorisation légale.

## 2. Méthode et résultats physiques

Toutes les commandes étaient des probes/lectures de métadonnées. Aucun outil de sortie média n’a été lancé. Le DVD n’a pas été copié sur disque, et il n’y a eu ni `preindex`, ni décodage de séquence vidéo, ni création de MKV/MP4.

| Élément | Observation |
|---|---|
| Lecteur/volume | `D:`, lecteur optique, UDF, label `USE_YOUR_ILLUSION_1`, taille déclarée 4 522 240 488 octets. |
| Structure | `AUDIO_TS/`, `VIDEO_TS/`; `VIDEO_TS.IFO` (14 336 octets), `VTS_01_0.IFO` (30 720 octets), `VTS_02_0.IFO` (75 776 octets). Le parseur AVM a reconnu la structure VMG et libdvdnav a ouvert les IFO nécessaires à l’énumération. |
| Capacité backend | ffprobe Gyan `9.0.2-full_build-www.gyan.dev`, démultiplexeur `dvdvideo` présent; libdvdnav/libdvdread CSS-off UCRT64 utilisés pour la navigation. |
| Informations rapportées par libdvdnav | Titre du disque `USE_YOUR_ILLUSION_1`; masque de régions `0x00c00000`, annoncé comme régions 1 à 6. Ce masque n’est pas un indicateur CSS. |
| Résultat de protection | Aucun message CSS explicite. Le disque a été lu sans DLL libdvdcss installée; cela prouve que les métadonnées sondées étaient accessibles, pas que tous les secteurs/VOB sont dépourvus de CSS. État de protection : **inconnu/non établi**. |

### Titres, chapitres et flux

Les valeurs de chapitre ci-dessous sont les frontières confirmées par libdvdnav après conversion des temps cumulés de fin en intervalles; elles concordent avec les chapitres ffprobe du titre sondé.

| Titre | Durée | Parties/chapitres | Angles | Frontières des chapitres (secondes) |
|---:|---:|---:|---:|---|
| 1 | 46,7667 s | 5 | 1 | 0; 11,8; 23,0; 33,2; 40,5667; 46,7667 |
| 2 | 5 403,6 s (1:30:03,6) | 15 | 1 | 0; 201,6; 510,8; 808,3; 1 023,3; 1 249,3; 1 698,7; 1 870,1; 2 192,9; 2 507,2; 2 837,6; 3 375,9; 3 968,9; 4 094,4; 4 524,3; 5 403,6 |

| Titre inspecté | Flux | Métadonnées ffprobe |
|---:|---|---|
| 1, angle 1 | Vidéo, index 0 | `mpeg2video`, 720×480. |
| 1, angle 1 | Audio, index 1 | `ac3`, `eng`, 48 000 Hz, 2 canaux, stéréo. |
| 2, angle 1 | Vidéo, index 0 | `mpeg2video`, 720×480. |
| 2, angle 1 | Audio, index 1 | `ac3`, `eng`, 48 000 Hz, 2 canaux, stéréo. |
| 1 et 2 | Sous-titres | Aucun flux sous-titre présent dans la sortie ffprobe. |

Le probe AVM avec auto-sélection a pris **4,66 s** et a inspecté le titre 2. Le probe explicite du titre 1 a pris **2,61 s**. L’énumération seule après correction a pris **1,67 s**. Ces temps sont ceux de ce lecteur/disque et ne constituent pas une garantie de performance générale.

### Diagnostic et corrections AVM-11B2

Le premier appel complet a fini en 1,23 s avec `worker ... réponse invalide`. Une relance diagnostique unique a montré que libdvdnav écrivait ses journaux dans stdout autour de la ligne JSON valide. Le parseur AVM sélectionne maintenant la réponse JSON structurée parmi ces lignes. La source amont de `dvdnav_describe_title_chapters` montre que le tableau fourni contient les temps cumulés de fin de chaque partie; AVM les interprétait auparavant comme des débuts et fabriquait un chapitre terminal de durée nulle. La conversion utilise désormais la fin précédente comme début et commence le premier chapitre à 0.

`DvdInspector.inspect(..., auto_select_main_title=True)` choisit le candidat de durée maximale seulement lorsqu’il est unique à une tolérance d’une seconde et possède une durée positive. L’option est désactivée par défaut. Les égalités et durées manquantes exigent une sélection manuelle. Le nom « titre principal » reste une convention UX : le choix automatique est explicitement signalé comme heuristique et peut sélectionner un bonus ou un autre programme long.

## 3. Backend protégé : faits et options

| Solution | Compatibilité/intégration Windows | Licence/maintenance | Limites et statut AVM |
|---|---|---|---|
| `libdvdread` + `libdvdnav` sans CSS | Build UCRT64 testé; lit les structures IFO, titre/parties/chapitres/angles. | MSYS2 publie libdvdread 7.1.1 et libdvdnav 7.0.0, `GPL-2.0-or-later`. | Navigation et parsing, pas de déchiffrement. C’est le backend standard recommandé; sa construction AVM exclut le chargeur CSS dynamique. |
| `libdvdcss` | VideoLAN annonce Windows; MSYS2 UCRT64 offre `libdvdcss-2.dll` (version 1.6.0-1 au 2026-11-06). libdvdread peut le charger dynamiquement ou être configuré avec lui. | `GPL-2.0-or-later`; paquet MSYS2 mis à jour le 2026-07-26. Maintenu par VideoLAN, mais dépend des clés/lecteurs/disques et de mécanismes CSS historiques. | Déchiffreur CSS, pas seulement une bibliothèque de lecture. Clés, comportement région et stratégies de secours peuvent varier. **Non installé, non chargé et non testé dans AVM-11B3.** |
| VLC / libVLC | Disponible sous Windows; peut lire des DVD via la pile VideoLAN. | Projet open source, composants à licences distinctes; vérifier le bundle/version exact. | Ce n’est pas une alternative indépendante à CSS : l’usage de libdvdcss reste possible. Lancer VLC comme processus ne change pas la question légale ni le périmètre d’AVM. |
| FFmpeg `dvdvideo` | FFmpeg Windows existe; le build testé fournit `dvdvideo`. | FFmpeg est LGPL par défaut; l’activation GPL/de bibliothèques GPL impose une revue de conformité. | FFmpeg déclare explicitement qu’il n’embarque aucun déchiffrement. Le démultiplexeur requiert un titre ou un PGC/PG; le défaut FFmpeg est le titre 1, pas une énumération. Le binaire n’accorde aucune autorisation CSS. |
| `libbluray` / `libaacs` | Outils de navigation Blu-ray, pas une pile DVD-Video. | Open source, licences et composants séparés à vérifier. | AACS concerne Blu-ray, pas CSS/DVD. Ce n’est pas un remplaçant pertinent pour ce besoin. |
| MakeMKV | Application Windows existante selon l’éditeur; usage en mode beta sous ses conditions. | Produit éditeur fermé, pas une dépendance open source AVM. | Peut lire des médias protégés selon l’éditeur, mais n’est pas retenu pour une architecture open source; non installé ni testé. |

Les pages MSYS2 indiquent une dépendance importante : leur paquet précompilé `libdvdread` dépend de `libdvdcss`. Il ne faut donc pas installer aveuglément le paquet `libdvdread` standard dans le backend AVM. Le build AVM-11B2 a été fait depuis les sources avec `-Dlibdvdcss=disabled`, puis une macro locale supprime le chargement dynamique. Cette séparation est vérifiée par inspection du binaire. Aucun paquet ni DLL libdvdcss n’est installé dans l’environnement AVM-11B3.

Sources techniques : [documentation FFmpeg dvdvideo](https://ffmpeg.org/ffmpeg-formats.html#dvdvideo), [libdvdcss VideoLAN](https://www.videolan.org/developers/libdvdcss.html), [libdvdcss MSYS2](https://packages.msys2.org/packages/mingw-w64-ucrt-x86_64-libdvdcss), [libdvdread MSYS2](https://packages.msys2.org/packages/mingw-w64-ucrt-x86_64-libdvdread), [libdvdnav MSYS2](https://packages.msys2.org/packages/mingw-w64-ucrt-x86_64-libdvdnav), [licence et avis VideoLAN](https://www.videolan.org/legal.html), [licence/notes FFmpeg](https://ffmpeg.org/legal.html), [site MakeMKV](https://www.makemkv.com/).

## 4. Canada : limites juridiques et de licence

L’article 41.1 de la [Loi sur le droit d’auteur, L.R.C. 1985, ch. C-42](https://laws-lois.justice.gc.ca/eng/acts/C-42/section-41.1.html) est le point de départ pour les mesures techniques de protection : il vise la neutralisation d’une TPM et certains services/dispositifs associés. Les articles 41.11 et suivants prévoient des exceptions précises, sous conditions. Une fin de sauvegarde personnelle, la possession du disque ou le fait que libdvdcss soit open source ne suffit pas à démontrer qu’une exception s’applique. Ne pas traiter les exceptions d’interopérabilité ou de recherche comme une permission générale de déchiffrer un DVD de détail.

Limite de vérification : les pages du texte consolidé sur `laws-lois.justice.gc.ca` ont renvoyé une erreur CSP au navigateur de recherche; CanLII a renvoyé 403. Les numéros d’articles sont fournis pour vérification humaine auprès du texte officiel. Le [CIPO](https://ised-isde.canada.ca/site/canadian-intellectual-property-office/en/guide-copyright) rappelle que son guide est introductif et renvoie vers un avocat pour un avis adapté; la [Direction générale de la politique du droit d’auteur](https://www.canada.ca/en/canadian-heritage/services/copyright-policy-branch.html) précise aussi qu’elle ne fournit pas de conseil juridique.

VideoLAN publie une explication technique de libdvdcss et une position juridique française dans sa [page légale](https://www.videolan.org/legal.html). Cette position, fondée sur une décision française, **ne détermine pas le droit canadien**. La licence GPL régit la redistribution du logiciel, pas le droit de contourner une TPM ni les droits sur le contenu du DVD. Le build FFmpeg `dvdvideo` avec libdvdnav/libdvdread est GPL; AVM déclare `GPL-3.0-or-later`. La compatibilité de l’ensemble exact, les obligations de sources/avis et toute distribution d’un backend CSS doivent être revues séparément avant packaging.

**Conclusion juridique prudente :** ne pas implémenter ni distribuer la prise en charge libdvdcss pour le Canada avant un avis juridique écrit portant sur l’usage envisagé (copie privée/archivage, œuvre et support, utilisateur, distribution du logiciel et TPM concernée). Aucune conclusion juridique définitive n’est donnée ici.

## 5. Backend facultatif : faisabilité et barrières

Techniquement, un backend séparé peut éviter de fragiliser le chemin standard, mais une simple DLL facultative sur le `PATH` ne suffit pas : libdvdread peut la charger dynamiquement dès qu’elle est trouvée. Pour une future décision positive, la séparation minimale serait :

1. conserver le backend standard compilé et testé sans CSS, avec absence de recherche globale de DLL;
2. placer le backend éventuellement autorisé dans un paquet/plugin séparé, jamais livré ou activé par défaut;
3. l’exécuter dans un worker distinct avec chemin de DLL privé et explicite, protocole d’échange de métadonnées/résultats, timeout et journaux distincts;
4. exiger une activation consciente, un motif/autorisation documenté et un contrôle de disponibilité/licences; ne jamais basculer automatiquement du backend standard vers le backend CSS;
5. garder les erreurs de lecture, de région et de structure distinctes de la détection explicite de CSS; ne jamais proposer de contournement de protections non prises en charge.

Cette architecture préserve techniquement le backend standard, mais **n’efface ni la portée de l’article 41.1, ni les obligations GPL, ni les risques de distribution**. Sans décision juridique et politique produit, le backend protégé doit rester absent.

## 6. Prérequis et périmètre proposé AVM-11C

### Périmètre recommandé

- Commencer par DVD-Video lisibles sans backend de contournement. L’inspection physique de ce support valide la chaîne standard sur un vrai DVD, pas la couverture de tous les lecteurs, auteurs et états de disque.
- Faire un préflight en lecture seule, énumérer les titres/PGT, durées, angles, langues/flux et chapitres; présenter le candidat de durée maximale comme suggestion et demander confirmation humaine avant toute opération d’archivage.
- Pour le MKV maître, remuxer en copie de flux sans réencodage; conserver tous les flux vidéo/audio utiles, les sous-titres disponibles, les métadonnées de langue, les chapitres et la durée. Tester les sous-titres DVD/VobSub, les programmes multi-PGC, les changements d’angle et les titres bonus sur fixtures/disques autorisés.
- Produire d’abord dans une zone temporaire contrôlée, sans écrasement par défaut; vérifier présence/codec/langue/nombre des flux, chapitres/durée, intégrité du MKV et espace disque avant validation. Garder la future MP4 H.264/AAC comme dérivé séparé, hors de la première tranche 11C.
- Sur refus explicite, timeout, erreur IFO/secteur, titre ambigu ou soupçon de protection non caractérisé, arrêter et rendre un diagnostic, sans tentative de secours par CSS.

### Prérequis de sortie 11C

- Décision produit sur le périmètre initial limité aux DVD sans déchiffrement; confirmation que le titre proposé doit toujours être confirmé par l’utilisateur.
- Revue de licence d’un binaire FFmpeg GPL exact et de toutes ses dépendances, avec sources correspondantes, avis et commande de build avant toute redistribution.
- Tests reproductibles couvrant plusieurs titres, durées proches/égales, angles multiples, audio alternatif, sous-titres DVD, chapters de menu, échec de lecture et absence d’écrasement; suite CD maintenue inchangée.
- Critères d’acceptation physique : capture des métadonnées seulement, temps bornés, aucun fichier média créé pendant le probe, écart source/sortie contrôlé lors de la future extraction, journal d’audit sans faux classement CSS.
- Une validation juridique distincte est obligatoire avant d’élargir aux DVD dont la lecture exige la neutralisation d’une TPM.

## 7. Assurance qualité et invariants

- `tests/test_dvd_inspector_11b.py` : **16/16 PASS**, incluant JSON worker bruité, conversion des fins cumulées de chapitres, choix unique du candidat le plus long, refus en cas d’égalité et garde CSS.
- CI complète : **14 groupes, 302 tests (229 domaine + 73 UI), 0 échec, 0 erreur, 0 skip, 0 crash natif**. Rapport `.ci/avm11b3-ci-results.json`; JUnit dans `.ci/junit/avm11b3/`.
- Aucun paquet/DLL libdvdcss n’a été installé pour AVM-11B3. Le DLL libdvdread standard de l’environnement local reste le build CSS-off AVM-11B2. Le `ffprobe` Gyan utilisé pour lire les métadonnées est un build full GPL avec un chargeur dynamique générique; aucun `libdvdcss-2.dll` n’était disponible dans les répertoires PATH/FFmpeg vérifiés. Cette absence n’est pas une preuve de l’état CSS du disque.
- Les modules CD, la bibliothèque et la base n’ont pas été modifiés par AVM-11B3. Les tests de domaine/UI n’ont rapporté aucun échec ou skip.

## 8. Décisions à prendre et clôture

1. Approuver AVM-11C uniquement pour le flux MKV sans réencodage sur DVD accessibles sans déchiffrement, avec validation humaine du titre proposé.
2. Décider si AVM-11C doit rester sans support des DVD protégés. Recommandation : **oui, tant qu’un avis juridique canadien n’a pas confirmé le cas d’usage et une stratégie de distribution licite**.
3. Ne considérer un backend CSS séparé qu’après ces validations; son caractère facultatif constitue une isolation technique, pas une exception juridique.
4. Maintenir le travail d’encodage MP4 et toute politique de redistribution distincts du master MKV.

**Verdict final :** le backend AVM standard a inspecté physiquement le DVD `USE_YOUR_ILLUSION_1` en lecture seule et a correctement énuméré/probé les deux titres après deux corrections ciblées. Le titre 2 est le candidat le plus long et a été sélectionné automatiquement uniquement comme heuristique. La prise en charge des DVD commerciaux protégés demeure **NON AUTORISÉE / NON VALIDÉE** pour AVM : `libdvdcss` est techniquement disponible sous Windows mais déchiffre CSS, et la question canadienne n’est pas résolue par ce rapport. AVM-11C peut être cadré sur les DVD accessibles sans déchiffrement; aucun AVM-11C n’est implémenté ou lancé par ce livrable.