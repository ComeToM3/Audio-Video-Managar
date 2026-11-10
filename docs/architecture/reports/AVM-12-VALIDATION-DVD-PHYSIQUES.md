# AVM-12 — Validation DVD physiques

Date : 2026-11-06 · AVM 0.5.0 · Windows 11 x64 · Python 3.12.10.

## 1. Verdict

**PARTIEL : énumération physique validée et métadonnées accessibles; inspection des flux non validée sans réserve; numérisation physique MKV/MKA non validée.** Le lecteur et le DVD-Video présent sont détectés, libdvdnav énumère deux titres et leurs chapitres/angles. ffprobe fournit des métadonnées, mais signale des erreurs de lecture pour les deux titres malgré un code de retour 0. AVM ignorait ces erreurs : ce faux succès a été corrigé et les deux titres sont désormais classés `read_error`.

**Protection technique : non établie. Droits de reproduction : non établis.** L’utilisateur a confirmé « Inspection uniquement; droits de reproduction non établis ». Aucune extraction, conversion, capture, lecture audiovisuelle intégrale ou publication du disque commercial n’a été lancée. Une collection personnelle n’est pas une permission de reproduction implicite; un échec de lecture n’est pas une preuve de CSS.

## 2. Opérations disponibles et méthode

Le moteur existant fournit déjà :

- `DvdInspector.inspect()` : détection de `VIDEO_TS`, signature VMG de 12 octets, présence des IFO VTS et vérification du démultiplexeur dvdvideo.
- `DvdNavigator.enumerate_titles()` : énumération libdvdnav/libdvdread dans un sous-processus Windows borné, titres/parties/angles/durées et intervalles de chapitres.
- Inspection ffprobe d’un titre/angle explicitement choisis : JSON des flux, langues disponibles, caractéristiques vidéo/audio et chapitres. Aucun fichier média n’est créé par cette opération.
- `DvdExtractionService` et le dialogue PySide6 : remux MKV ou pistes audio vers MKA, attestation et confirmation, staging, validation et publication sans écrasement. Ces opérations n’ont pas été utilisées sur le support physique de ce mandat.

Script de preuve : [inspect_physical.py](../../../scripts/diag12/inspect_physical.py). Il instrumente les appels subprocess sans remplacer les backends par des fixtures, conserve les commandes/codes/stdout/stderr et ne comporte aucune fonction d’extraction. Les appels FFprobe portent uniquement sur version, démultiplexeurs et métadonnées; les processus natifs sont timeoutés à 30 s.

```powershell
.\.venv\Scripts\python.exe scripts/diag12/inspect_physical.py --source 'D:\'
```

Les outils proviennent de `%LOCALAPPDATA%\Temp\AVM-11B2` : ffprobe Gyan 9.0.2 full avec dvdvideo et les DLL x64 CSS-off déjà validées. Le script utilise un profil Temp isolé, un cwd Temp neuf et un PATH limité aux outils et à Windows/System32. Il vérifie l’absence de `libdvdcss-2.dll` dans les répertoires de recherche envisagés; `DvdNavigator` refuse les marqueurs de chargement CSS interdits dans libdvdread. Aucun composant CSS n’a été ajouté.

Hashes DLL vérifiés : libdvdnav `33b0c2131d6447c0ff5b66f3aacd8614b7ff42c2403bf3b2bd56ca195244c542`; libdvdread `2066e90e736c3df2aea66a29fd43fa876afdf681918ee70bab23f351c0d84f3e`.

## 3. Support examiné

| Élément | Observation nouvelle AVM-12 |
|---|---|
| Lecteur Windows | `D:`, `ATAPI iHAS324   C`, CIM `MediaLoaded=true`, `Status=OK`. Ce statut du périphérique ne certifie pas la lecture de tous les secteurs du disque. |
| Volume | `USE_YOUR_ILLUSION_1`, UDF, taille CIM 4 522 242 048 octets, espace libre 0. |
| Structure | `AUDIO_TS` et `VIDEO_TS`; `VIDEO_TS.IFO` : 14 336 octets, signature lue `DVDVIDEO-VMG`; `VTS_01_0.IFO` : 30 720 octets; `VTS_02_0.IFO` : 75 776 octets. Les numéros VTS seuls ne sont pas assimilés aux titres. |
| Identification | Nom de volume et nom rapporté par libdvdnav; aucune édition/catalogue ni identité juridique déduite de ces chaînes. |
| Région | Le journal natif rapporte `0x00c00000`, régions 1 à 6. Ce masque n’est pas un indicateur de CSS. |
| Autorisation | Inspection seulement, confirmée par l’utilisateur. Aucune permission de reproduction établie pour ce disque. |

Un seul support physique a été examiné. Aucun DVD physique original/synthétique autorisé à reproduire n’a été fourni dans ce mandat. Le dossier synthétique AVM-11C est un contrôle logiciel, pas un disque optique; il n’est pas compté comme deuxième support physique.

## 4. Titres, chapitres, angles et flux

### Navigation libdvdnav

L’énumération est terminée en 1,92 s avant correction et 1,84 s lors de la vérification. Les candidats concordent entre les appels.

| Titre | Durée annoncée | Parties/chapitres | Angles |
|---:|---:|---:|---:|
| 1 | 46,7667 s | 5 | 1 |
| 2 | 5 403,6 s, soit 1 h 30 min 03,6 s | 15 | 1 |

Frontières en secondes, énumérées par libdvdnav et présentes dans le JSON ffprobe :

- Titre 1 : `0; 11,8; 23,0; 33,2; 40,5667; 46,7667`.
- Titre 2 : `0; 201,6; 510,8; 808,3; 1023,3; 1249,3; 1698,7; 1870,1; 2192,9; 2507,2; 2837,6; 3375,9; 3968,9; 4094,4; 4524,3; 5403,6`.

Le titre 2 est le plus long, mais ce fait ne prouve pas son rôle éditorial. Aucun autre angle n’était annoncé.

### Métadonnées retournées par ffprobe, avec erreur de lecture

Pour chaque titre, angle 1, le JSON brut décrit : vidéo index 0, MPEG-2 720×480; audio index 1, AC-3 `eng`, 48 000 Hz, deux canaux stéréo; respectivement 5 et 15 chapitres. Aucun flux sous-titre n’est signalé dans les sorties examinées. Cela ne certifie pas l’absence de sous-titres dans toutes les structures du disque. La langue vidéo non fournie reste inconnue.

Ces valeurs sont des métadonnées réellement retournées, **pas la preuve d’un titre entièrement lisible**. Les sondes avant correction ont pris 3,70 s et 2,89 s; après correction 3,56 s et 2,88 s. Elles ne parcourent pas l’œuvre de bout en bout et aucune qualité d’image/son n’a été évaluée.

## 5. Diagnostic factuel et correction

Les deux appels de titre retournent le code 0, du JSON et les erreurs suivantes sur stderr :

```text
Unable to read next block of PGC
dvdnav error (... cell=1): Error reading from DVD.
```

Les champs titre/PGC/PG de cette ligne FFmpeg comportent des valeurs incohérentes avec les deux candidats; ils ne sont pas repris comme numéros réels. Une anomalie du backend ou de son diagnostic est plausible, mais sa cause n’est pas établie. Aucun message explicite correspondant aux marqueurs CSS/encrypted/scrambled du moteur n’a été observé dans les journaux enregistrés.

| Dimension | Conclusion permise |
|---|---|
| Structure et IFO | Accessibles en lecture seule. |
| Navigation | Énumération des candidats/chapitres/angles réussie avec le backend natif CSS-off. |
| Lecture audiovisuelle | Erreur rapportée par ffprobe/libdvdnav lors de la sonde; lecture complète inconnue. |
| Matériel | Aucun défaut matériel identifié; `Status=OK` et lecture IFO ne permettent pas d’exclure un problème de média/lecteur. |
| Backend | Présent et expose dvdvideo, donc pas simplement absent/incompatible par capacité. Son accès physique ou sa gestion de ce disque peut néanmoins être en cause. |
| Protection | Non identifiée : ni le statut commercial, ni ces erreurs, ni la réussite partielle ne démontrent présence ou absence de CSS sur tout le disque. |
| Reproduction | Non autorisée dans ce mandat selon le périmètre confirmé; indépendante du diagnostic technique. |

Anomalie AVM démontrée : [dvd.py](../../../audio_video_manager/extraction/dvd.py) ne traitait les erreurs de titre que si `returncode != 0`, puis déclarait le JSON `inspected`. La correction minimale reconnaît les deux messages de lecture ci-dessus, même avec code 0, et conserve stderr dans `technical_detail`. Elle ne rejette pas arbitrairement toute sortie stderr et ne transforme pas l’erreur en protection. Les valeurs partielles restent disponibles dans la preuve brute, mais AVM ne les présente plus comme une inspection réussie.

Deux tests de régression ont été ajoutés dans [test_dvd_inspector_11b.py](../../../tests/test_dvd_inspector_11b.py) et passent. La vérification physique unique après correction donne `read_error` pour les deux titres. Le worker UI refuse un tel résultat de lecture de pistes; le dialogue ne peut donc pas obtenir les détails frais requis pour démarrer l’extraction. Aucun nouveau parcours d’extraction UI physique n’a été exécuté.

Cette observation nuance le verdict historique [AVM-11B3](AVM-11B3-VALIDATION-DVD-ET-PROTECTIONS.md) : AVM-12 conserve désormais stderr et ne traite plus le seul code 0 comme preuve suffisante.

## 6. Extractions, lecture et bibliothèque

**Extractions physiques réalisées : zéro.** Aucune commande FFmpeg de sortie média, aucun MKV/MKA/MP4 ni capture n’a été créé depuis le disque; aucun scan/décodage audiovisuel intégral du support commercial n’a été lancé.

Il n’existe donc pas de fichier physique produit à vérifier avec ffprobe, à visionner ou à conserver dans la bibliothèque. Ces étapes sont **non exécutées**, pas réussies par assimilation aux fixtures. Les résultats MKV/MKA de [AVM-11E](AVM-11E-VALIDATION-PARCOURS-UTILISATEUR.md) restent la preuve synthétique antérieure, non une preuve de numérisation optique.

Le dialogue actuel publie le résultat au chemin choisi et permet d’ouvrir son dossier. Il n’implémente pas un lecteur audiovisuel et son handler de résultat ne réalise pas d’enregistrement de film dans SQLite. La conservation d’un fichier dans un dossier bibliothèque et sa présence comme film navigable dans AVM sont deux validations distinctes à effectuer lors d’un futur essai autorisé.

La configuration personnelle conserve le hash SHA-256 `b37a325e1835e5e1c7a943c933c0d54fa103d90c597ee5ac26dcdcea76797c50` avant/après les inspections. Les écritures du mandat sont les journaux métadonnées/preuves et profils Temp; aucune donnée CD, bibliothèque personnelle ou configuration persistante n’a été modifiée par la validation.

## 7. Enregistrement en temps réel : étude seulement

Le build local annonce les entrées `dshow` et `gdigrab` dans `ffmpeg -devices`. Cela établit des capacités de capture génériques, pas une chaîne DVD opérationnelle ni la présence d’un matériel de capture approprié. Aucun périphérique de capture n’a été ouvert et aucune capture implémentée.

Pour une source dont la lecture et l’enregistrement sont permis, sans mesure à neutraliser, une capture audiovisuelle est techniquement envisageable. Elle exige une chaîne de lecture autorisée, une sortie capturable autorisée, des horodatages audio/vidéo synchronisés et des contrôles de pertes d’images, début/fin, niveaux sonores et stockage. Une capture du rendu ne conserve pas les paquets MPEG-2/AC-3 d’origine; elle implique généralement réencodage ou stockage brut, et perd la structure de chapitres, les choix de pistes/angles et les sous-titres séparés.

Pour le titre 2 annoncé, la seule acquisition durerait au moins environ 90 minutes, hors préparation et validation. Le remux autorisé reste préférable à une capture du rendu lorsqu’il fonctionne. Les APIs Windows et sorties vidéo peuvent imposer des restrictions de capture : il faudrait les respecter, jamais les désactiver ou changer de chaîne pour les éluder. L’enregistrement temps réel ne résout ni l’absence de permission de reproduction ni une protection; ce n’est pas une solution secondaire validée pour le disque présent.

Références : [FFmpeg DirectShow](https://ffmpeg.org/ffmpeg-devices.html#dshow), [FFmpeg capture GDI](https://ffmpeg.org/ffmpeg-devices.html#gdigrab), [Windows Graphics Capture](https://learn.microsoft.com/en-us/windows/uwp/audio-video-camera/screen-capture).

## 8. Tests et preuves

- Tests ciblés après correction : **41 PASS**, inspection/extraction DVD et shell UI; JUnit local `.ci/junit/avm12-targeted-final.xml`.
- CI complète : **14 groupes, 321 tests (244 domaine + 77 UI), 0 échec, 0 erreur, 0 skip, aucun crash natif**. [Rapport conservé](AVM-12-evidence/ci-results.json); JUnit locaux `.ci/junit/avm12-final/`. Les tests CD existants restent exécutés sans modification du pipeline.
- Non-régression native synthétique : le script AVM-11F a été réexécuté après correction. Deux processus Windows, vraie persistance/rechargement, référence synthétique `inspected`, deux titres et deux flux pour le titre 2, configuration personnelle inchangée : [preuve](AVM-12-evidence/synthetic-regression.json).
- Diagnostics des fichiers Python touchés : aucun problème signalé. Aucune installation globale, modification destructive, déchiffrement ou extraction commerciale non autorisée.

Preuves principales : [inspection initiale et journaux bruts](AVM-12-evidence/physical-inspection-before-fix.json), [inspection après correction](AVM-12-evidence/physical-inspection.json). La seconde conserve 11 appels subprocess, tous code 0, mais deux résultats AVM `read_error` : c’est précisément la distinction corrigée. Ces journaux contiennent des métadonnées, pas des copies des flux.

## 9. Prochaine intervention utile

1. **Isoler la lecture physique avant tout nouvel effort de capture ou de packaging.** Fournir un DVD-Video original/synthétique gravé dont la reproduction est expressément permise, puis comparer le même contenu en dossier local et sur lecteur physique avec la chaîne CSS-off. Un contrôle physique connu et reproductible permettra de distinguer une limite du lecteur, du média ou de l’accès dvdvideo; ces causes ne sont pas tranchées aujourd’hui.
2. Si l’erreur persiste, comparer les journaux bornés libdvdnav et ffprobe, et les modes d’accès dossier/racine de lecteur et périphérique Windows pour ce support autorisé. Une comparaison de versions/builds CSS-off pourra être envisagée sous mandat distinct, sans installer de déchiffreur ni présumer que les entiers incohérents du journal prouvent un défaut matériel.
3. Seulement après une inspection sans erreur et une permission établie : MKV puis MKA depuis le dialogue existant, validations structurelles et lecture intégrale des fichiers, contrôle de conservation et ouverture depuis le stockage local. Tester la présentation dans la bibliothèque séparément de la simple publication du fichier.

La permission du disque actuel et sa lecture complète sont deux obstacles ouverts différents. Les limites de packaging/licences recensées dans [AVM-11F](AVM-11F-PREPARATION-WINDOWS-AUTONOME.md) restent applicables, mais ne sont pas la cause démontrée des erreurs physiques présentes.

**Verdict final : PARTIEL pour les DVD physiques; numérisation de la collection commerciale NON VALIDÉE.** AVM énumère ce support et obtient des métadonnées, mais refuse désormais à juste titre les sondes accompagnées d’erreurs. Protection et cause matérielle restent non établies; zéro extraction physique a été réalisée. Le mandat s’arrête ici.