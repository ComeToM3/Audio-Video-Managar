# AVM-11C — Première extraction DVD vers MKV maître

Date : 2026-11-06 · AudioVideoManager 0.5.0 · Windows 11 · AVM-11C, DVD-Video synthétique original.

**Verdict : VALIDÉ pour une extraction réelle sans réencodage depuis une structure DVD-Video de référence locale.** Le titre 2 a été extrait vers un MKV maître, relu par ffprobe et parcouru intégralement par FFmpeg avant publication sans écrasement. Aucun DVD commercial ni le lecteur `D:` n’a été utilisé dans AVM-11C. Le test utilise un dossier `VIDEO_TS` authoré avec des motifs et tonalités générés localement; ce n’est pas un support optique gravé.

## 1. Architecture livrée

Le service est exposé par `audio_video_manager.extraction.DvdExtractionService` dans `audio_video_manager/extraction/dvd_extractor.py`; il réutilise `DvdInspector`, `DvdTitleCandidate`, `DvdTitleInspection`, `VideoStream` et `VideoChapter`.

1. `prepare(source, destination)` vérifie ffprobe/ffmpeg et `dvdvideo`, inspecte la structure et les candidats, vérifie le dossier/extension de destination, refuse une destination existante ou incluse dans la source, estime l’espace maximal requis et retourne une suggestion non contraignante du titre de durée maximale. Une durée maximale ex æquo ou absente ne produit aucune suggestion.
2. `extract(plan, title_index, angle_index, confirmed=True, ...)` revalide la destination, le titre et l’angle. `confirmed` est faux par défaut; sans confirmation explicite, aucun processus FFmpeg ne démarre. Le consommateur UI doit présenter le plan et obtenir cette confirmation.
3. FFmpeg écrit d’abord dans un sous-dossier temporaire `.avm-dvd-*` du volume de destination. La commande mappe tous les flux et chapitres et copie les paquets sans encoder. La progression FFmpeg est remontée par callback; `threading.Event` annule le sous-processus. Une absence de progression au-delà du délai configuré (180 s par défaut) provoque terminate puis kill après le délai de grâce.
4. ffprobe vérifie que le conteneur est Matroska, que le multiensemble des codecs/types/langues/caractéristiques des flux correspond à l’inspection DVD, que durée et chapitres restent dans les tolérances, puis FFmpeg relit tous les paquets du MKV vers le muxer `null` en copie de flux. Le seul code de retour FFmpeg ne suffit donc jamais à déclarer le succès.
5. Le fichier est publié par lien dur sans remplacement; si le système de fichiers ne supporte pas cette opération, l’extraction échoue de façon fermée. En cas d’erreur, annulation ou validation insuffisante, le fichier temporaire est nettoyé et aucune destination finale n’est créée.

### Commandes représentatives

Les chemins réels sont absolus et viennent du plan confirmé; `STAGING.mkv` désigne le fichier dans le dossier temporaire AVM.

```text
ffmpeg -hide_banner -nostdin -n -v warning -progress pipe:1 -stats_period 0.5 -f dvdvideo -title 2 -angle 1 -i <DVD-Video source> -map 0 -map_chapters 0 -map_metadata 0 -c copy -f matroska <STAGING.mkv>
ffprobe -v error -show_format -show_streams -show_chapters -of json <STAGING.mkv>
ffmpeg -hide_banner -nostdin -v error -i <STAGING.mkv> -map 0 -c copy -f null -
```

Aucun `-y`, encodeur, filtre vidéo/audio, déchiffreur CSS ou chemin de sortie MP4 n’est utilisé. `-map 0` et `-map_chapters 0` font échouer la muxification si un flux incompatible ne peut pas être écrit; le contrôle ffprobe compare ensuite les flux attendus et présents afin de refuser une perte silencieuse.

## 2. DVD-Video de référence

Le contenu a été généré localement à partir des sources FFmpeg `testsrc2` et `sine`; les fichiers MPEG ne proviennent d’aucune œuvre existante. Le source `dvdauthor` 0.7.2 (tar Debian, SHA-256 `fd66b92f6c67bd406030ff0f1c3233175768b534df4d341c3f380ecd61de91b5`) a été compilé temporairement dans MSYS2 UCRT64. Le binaire `dvdauthor.exe` résultant (SHA-256 `1b7ecf921a7bdf57b35ba55f1f6ad560881361e75db477696a02847f8996bb38`) a authoré un seul VTS avec deux PGC/titres. Le build temporaire a nécessité des adaptations Windows locales à `mkdir`, `fsync`, au macro Autoconf libxml2, au charset, et un défaut de format NTSC; ces changements sont uniquement sous `%LOCALAPPDATA%\Temp\AVM-11C\source`, pas dans le dépôt AVM.

| Média source | Contenu généré | Taille |
|---|---|---:|
| `title-short.mpg` | 4 s, MPEG-2 720×480, AC-3 48 kHz stéréo, ton 440 Hz | 1 755 136 octets |
| `title-feature.mpg` | 10 s, MPEG-2 720×480, AC-3 48 kHz stéréo, ton 660 Hz | 4 159 488 octets |
| `reference-dvd/VIDEO_TS` | VMG, un VTS, IFO/BUP et VOB authorés localement | Dossier temporaire, non gravé |

Le préflight AVM a énuméré le titre 1 à 4 s/2 parties et le titre 2 à 10 s/3 parties. Le titre 2, unique candidat le plus long, a été suggéré puis explicitement confirmé dans l’appel d’extraction. Le calcul du titre le plus long reste une heuristique; le service n’extrait pas automatiquement un titre sans confirmation.

**Limitation du fixture :** l’encodeur FFmpeg `dvdsub` ne transforme pas directement le texte SRT en bitmap; `spumux` amont n’a pas pu être compilé car `netinet/in.h` est absent de cette source Windows. Le DVD de référence ne contient donc pas de piste sous-titre. La copie des sous-titres disponibles est couverte par un test de service avec une piste `dvd_subtitle` simulée; un faux MKV où cette piste manque est rejeté. Les tags de langue audio/vidéo du DVD généré ne sont pas fournis par dvdauthor dans ce fixture; le service conserve les métadonnées présentes et ne les invente pas. Le test unitaire vérifie les tags `eng`/`fra` lorsqu’ils sont présents.

## 3. Résultat d’extraction

- Source : `%LOCALAPPDATA%\Temp\AVM-11C\reference-dvd`, jamais `D:`.
- Titre/angle confirmés : **2 / 1**.
- Durée DVD inspectée : **10,000 s**; durée MKV : **10,011 s**.
- Temps extraction, validation ffprobe et scan paquet complet : **2,59 s** sur cette machine.
- Résultat : `%LOCALAPPDATA%\Temp\AVM-11C\test-library\AVM-11C-reference-final.mkv`.
- Taille : **4 055 998 octets**.
- SHA-256 : `b27babcc4997cbb84891c8f85ddf5c53fee799d23b094212e0bbb612a13f4343`.
- Conteneur : `matroska,webm`, ffprobe probe score 100.
- Flux 0 : vidéo `mpeg2video`, 720×480, aucun tag de langue fourni.
- Flux 1 : audio `ac3`, 48 000 Hz, 2 canaux, stéréo, aucun tag de langue fourni.
- Chapitres : 0–3,0 s; 3,0–7,2 s; 7,2–10,0 s.
- Vérification : ffprobe indépendant renvoie code 0; le service a aussi parcouru le MKV complet vers `null` en `-c copy`, sans erreur. Aucun processus ffmpeg/ffprobe ne reste actif.

Le MKV final a été généré une seconde fois après l’ajout de l’isolation CSS du worker, puis conservé dans la bibliothèque de test temporaire pour inspection manuelle.

## 4. Sécurité des processus et garde-fous

- Le service ne déchiffre aucun flux et n’installe ni ne charge `libdvdcss`.
- Le build ffmpeg Gyan `9.0.2-full_build` contient des références à un chargeur dynamique générique et au nom libdvdcss. Le worker AVM n’hérite donc pas du PATH utilisateur : son PATH est réduit au répertoire de l’exécutable, au staging et aux répertoires Windows nécessaires. Il refuse de démarrer si `libdvdcss-2.dll` est trouvé dans ces répertoires de recherche. Aucun DLL CSS n’était présent dans les emplacements vérifiés. La navigation native emploie, séparément, le build libdvdread AVM-11B2 CSS-off.
- L’extraction du DVD physique est exclue de ce mandat. Le support commercial `D:` n’a pas été lu ou modifié; aucune bibliothèque/base de production ni source CD n’a été touchée.
- Les seuls médias créés sont les deux sources originales, le DVD-Video synthétique et le MKV final dans `%LOCALAPPDATA%\Temp\AVM-11C`.
- Les outils de génération DVD et leurs dépendances restent dans le MSYS2 temporaire existant; aucun PATH système ni installation Windows globale n’a été modifié.

## 5. Tests et assurance qualité

`tests/test_dvd_extractor_11c.py` : **10/10 PASS**. Couverture : suggestion de titre, confirmation obligatoire, copie de tous les flux/angle choisi, vérification anti-perte, refus d’écrasement, protection de la source même avec un plan altéré, refus d’un DLL CSS, annulation avant démarrage et pendant progression, timeout d’inactivité, nettoyage de staging.

Tests DVD réunis (`test_dvd_inspector_11b.py` + `test_dvd_extractor_11c.py`) : **26/26 PASS**.

CI complète : **14 groupes, 312 tests (239 domaine + 73 UI), 0 échec, 0 erreur, 0 skip, aucun crash natif**. Rapport `.ci/avm11c-ci-results.json`; JUnit dans `.ci/junit/avm11c/`. Les tests CD disponibles sont inclus dans le groupe domaine; aucun fichier CD n’a été modifié.

## 6. Limites et suites possibles

- Le DVD de référence est une structure `VIDEO_TS` sur disque créée depuis du contenu généré localement, pas un disque optique gravé. Il valide le démultiplexeur réel, libdvdnav/libdvdread, la copie de paquets, l’inspection MKV et la publication, mais pas les défaillances physiques de lecture d’un média vieillissant.
- Les sous-titres ne sont pas validés sur un VobSub physique; leur mapping est implémenté par `-map 0`, leur présence comparée aux métadonnées sources et les cas de perte sont couverts par fixtures.
- Les métadonnées de langue ne sont conservables que si présentes dans les IFO/flux. AVM ne fabrique pas une langue lorsqu’elle est inconnue.
- Le service dispose de callbacks de progression et de `threading.Event` pour annulation, mais aucun écran/wizard Qt n’a été branché dans cette première tranche. L’appelant doit présenter `DvdExtractionPlan`, afficher la suggestion et transmettre `confirmed=True` uniquement après consentement explicite de l’utilisateur.
- Aucun DVD commercial protégé, lecteur physique, CSS, MP4 ou réencodage n’est inclus dans le périmètre validé.

**Verdict final : VALIDÉ** — un MKV maître Matroska de 10,011 s, sans réencodage, a été réellement produit à partir du DVD-Video synthétique original, vérifié indépendamment et par lecture complète des paquets, avec une sélection de titre confirmée, sans écrasement, sans déchiffrement CSS et sans modification du pipeline CD. Le MKV reste dans la bibliothèque de test temporaire pour inspection manuelle. AVM-11C s’arrête ici; aucun mandat ultérieur n’est lancé automatiquement.
