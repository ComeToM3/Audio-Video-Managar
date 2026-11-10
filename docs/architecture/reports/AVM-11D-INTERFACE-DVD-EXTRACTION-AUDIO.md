# AVM-11D — Interface DVD et extraction audio autonome

Date : 2026-11-06 · AudioVideoManager 0.5.0 · Windows 11.

**Verdict : VALIDÉ sur une structure DVD-Video synthétique autorisée pour les parcours MKV maître et audio seul.** Depuis PySide6, le dialogue DVD inspecte les titres et pistes, suggère le titre de durée maximale, exige l’attestation de droits et une confirmation explicite, puis propose la copie intégrale vers MKV ou la copie de pistes audio sélectionnées vers MKA. Les deux sorties de référence ont été réellement générées par FFmpeg depuis `VIDEO_TS`, relues par ffprobe et parcourues intégralement sans réencodage. Aucun DVD commercial ni le lecteur `D:` n’a été utilisé; aucune validation sur disque optique physique n’est revendiquée.

## 1. Interface livrée

- Un bouton **DVD** est ajouté au rail latéral de `MainWindow`. Il ouvre un dialogue modal séparé et ne change ni les quatre pages ni leurs index; le wizard CD, la bibliothèque et l’historique restent inchangés.
- Paramètres comporte deux chemins facultatifs : `ffmpeg_path` et `dvdnav_library_dir`. Les anciens JSON de configuration restent compatibles, ces champs prenant une chaîne vide par défaut. Le dossier DVD doit fournir `libdvdnav-4.dll` et `libdvdread-8.dll` compilées CSS-off; le binaire ffprobe doit être voisin du FFmpeg configuré.
- Le dialogue permet de détecter les lecteurs optiques Windows sans lire leur contenu, de sélectionner un dossier/lecteur, puis de lancer l’inspection en arrière-plan. Il présente le numéro de titre, la durée, le nombre de chapitres, les angles, les flux vidéo/sous-titres et les pistes audio (codec, langue disponible, canaux et fréquence).
- Le titre le plus long est marqué comme suggestion, pas comme choix définitif. L’utilisateur choisit le titre et l’angle, puis relit les pistes de cette sélection. Tout changement de source, titre ou angle invalide l’inspection précédente et bloque le démarrage jusqu’à une nouvelle inspection des pistes.
- Deux radios d’opération sont proposées : **MKV maître complet** et **Audio seulement (MKA)**. En audio seul, la liste des pistes devient cochable; le démarrage reste désactivé tant qu’aucune piste n’est choisie.
- Le formulaire demande une destination neuve, montre progression et état, propose l’annulation, explique les erreurs et affiche le résultat avec un bouton d’ouverture du dossier.
- Une case distincte demande à l’utilisateur d’attester les droits de reproduction. Une boîte de confirmation rappelle encore le titre, l’angle, l’opération et le chemin. Cette attestation est une déclaration utilisateur, pas une vérification juridique.

La preuve UI automatisée est portée par `tests/test_ui_shell.py` : quatre sections conservées, ouverture du dialogue depuis le bouton, suggestion du titre, affichage des chapitres/pistes, invalidation au changement d’angle, bascule MKV/MKA, sélection audio et garde de l’attestation de droits. Aucune capture d’écran n’est jointe; cette preuve d’interface est fournie par les tests Qt hors écran.

## 2. Services et choix techniques

`DvdExtractionService` conserve les préflight/validation AVM-11C et ajoute `extract_audio()` :

- Préflight : capacité `dvdvideo`, structure et titres énumérés, validation des chemins, refus d’écrasement, destination hors de la source, vérification de l’espace libre avec marge, suggestion du candidat unique le plus long.
- Confirmations : le titre/angle doit figurer dans le plan; MKV et MKA exigent `confirmed=True` et `rights_attested=True`. Les opérations d’inspection restent en lecture seule et ne requièrent pas ces confirmations.
- MKV : FFmpeg reçoit le titre/angle choisis, `-map 0`, `-map_chapters 0`, `-map_metadata 0`, `-c copy` et `-f matroska`.
- Audio seul : les index FFprobe des flux audio sélectionnés sont mappés individuellement; la commande utilise `-vn`, `-c:a copy`, `-map_chapters 0`, `-map_metadata 0` et `-f matroska`, vers un fichier `.mka`. Aucun changement de codec n’est tenté. Si le codec ne peut pas être muxé tel quel, FFmpeg échoue et AVM n’annonce pas de réussite.
- Progression : FFmpeg `-progress pipe:1`; `DvdTaskWorker` transmet les callbacks par les signaux Qt depuis un `QThread` créé avec `attach_worker_thread`. `threading.Event` interrompt le processus; le timeout d’inactivité par défaut est 180 s, puis terminate/kill borné.
- Validation : ffprobe confirme le conteneur, le multiensemble des codecs/types/langues/caractéristiques, la durée et les bornes/nombre de chapitres. FFmpeg parcourt ensuite tous les paquets du staging vers `null` en copie de flux. Un échec ou une différence entraîne le nettoyage du staging.
- Publication : staging sous `.avm-dvd-*` dans le dossier destination; publication par lien dur sans remplacement. Un système de fichiers qui ne peut garantir cette publication fait échouer l’opération de façon fermée.
- Sécurité CSS : le worker FFmpeg reçoit un PATH réduit aux répertoires nécessaires et refuse de démarrer si `libdvdcss-2.dll` est présent dans ses répertoires de recherche. Aucun déchiffrement ou fallback CSS n’est implémenté.

Commandes représentatives (les arguments de sortie réels sont des chemins absolus créés dans le staging AVM) :

```text
ffmpeg -hide_banner -nostdin -n -v warning -progress pipe:1 -stats_period 0.5 -f dvdvideo -title N -angle A -i <DVD-Video> -map 0 -map_chapters 0 -map_metadata 0 -c copy -f matroska <staging.mkv>
ffmpeg -hide_banner -nostdin -n -v warning -progress pipe:1 -stats_period 0.5 -f dvdvideo -title N -angle A -i <DVD-Video> -map 0:<audio-index> -map_chapters 0 -map_metadata 0 -vn -c:a copy -f matroska <staging.mka>
ffprobe -v error -show_format -show_streams -show_chapters -of json <staging.mkv-or-mka>
ffmpeg -hide_banner -nostdin -v error -i <staging.mkv-or-mka> -map 0 -c copy -f null -
```

Aucune commande n’utilise `-y`, aucun encodeur vidéo/audio, aucun filtre, aucune sortie MP4 et aucun composant CSS. Le `-n` s’applique au staging neuf; le fichier final est publié sans remplacement.

## 3. DVD-Video synthétique autorisé

Le contenu original a été généré localement : `testsrc2` pour la vidéo, sinusoïdes 440/660 Hz pour l’audio. Deux sources DVD compatibles ont été multiplexées en MPEG-2/AC-3 720×480 NTSC, 48 kHz, stéréo, puis authorées en deux PGC dans `reference-dvd/VIDEO_TS` :

| Titre | Source | Durée | Chapitres authorés |
|---:|---|---:|---|
| 1 | `title-short.mpg` | 4 s | 0; 1,8; 4,0 s |
| 2 | `title-feature.mpg` | 10 s | 0; 3,0; 7,2; 10,0 s |

Le service a énuméré les deux titres et a suggéré le titre 2 comme unique candidat le plus long. L’extraction a été lancée avec titre 2, angle 1, confirmation explicite et attestation des droits sur le contenu synthétique.

### MKV maître final

- Chemin conservé : `%LOCALAPPDATA%\Temp\AVM-11C\test-library\AVM-11C-reference-final.mkv`.
- Taille : 4 055 998 octets; durée : 10,011 s; SHA-256 : `b27babcc4997cbb84891c8f85ddf5c53fee799d23b094212e0bbb612a13f4343`.
- ffprobe indépendant : `matroska,webm`, score 100; vidéo `mpeg2video` 720×480; audio `ac3` 48 000 Hz, 2 canaux stéréo; 3 chapitres 0–3,0, 3,0–7,2 et 7,2–10,0 s; code retour 0.
- Temps extraction + validation : 2,59 s. Scan complet des paquets sans erreur. Aucune ré-encodeuse n’a été appelée.

### Audio seul final

- Chemin conservé : `%LOCALAPPDATA%\Temp\AVM-11C\test-library\AVM-11C-audio-only.mka`.
- Sélection : titre 2, angle 1, piste audio index 1 (`ac3`); taille : 240 886 octets; durée : 9,92 s; SHA-256 : `ca915ec7f190132e69bf9bddd2b7351671e7762f6013013a70b717a87cc81661`.
- ffprobe indépendant : Matroska, un seul flux audio AC-3 48 000 Hz, 2 canaux stéréo, 3 chapitres; code retour 0. Aucun flux vidéo n’est présent. Temps extraction + validation : 2,56 s.

### Limites du média de référence

Le fixture est un dossier DVD-Video valide généré et authoré sous Temp, pas un ISO ni un disque optique gravé. Il contient deux titres et plusieurs chapitres, mais aucun sous-titre VobSub. `spumux` n’a pas pu être compilé car son source 0.7.2 inclut le header POSIX `netinet/in.h`, absent du build MinGW; la fonctionnalité de sélection/conservation de sous-titres est donc vérifiée par fixtures, pas par ce média. Les tags langue n’étaient pas présents dans les IFO/flux synthétiques; AVM les laisse inconnus et ne les invente pas. Un test de service avec tags `eng`/`fra` confirme que les langues disponibles sont comparées et conservées.

## 4. Tests, sécurité et compatibilité CD

- Tests d’extraction DVD (`tests/test_dvd_extractor_11c.py`) : **13/13 PASS**, dont MKV complet, MKA audio seul, sélection de pistes, confirmation, attestation, refus d’écrasement, source protégée contre un plan altéré, garde CSS, annulation et timeout d’inactivité.
- Tests d’interface ciblés : **4 parcours** vérifiés par les tests shell/Qt (navigation, ouverture modale, sélection/suggestion, modes, droits et invalidation des pistes sur changement d’angle).
- CI complète : **14 groupes, 317 tests (242 domaine + 75 UI), 0 échec, 0 erreur, 0 skip, aucun crash natif**. Rapport `.ci/avm11d-final-ci-results.json`; JUnit dans `.ci/junit/avm11d-final/`.
- Les tests CD disponibles sont toujours exécutés; aucun module source CD, aucune bibliothèque de production et aucune base n’ont été modifiés.
- Les chemins FFmpeg et libdvdnav sont optionnels et configurés dans Paramètres. Aucun outil n’a été installé globalement ni ajouté au PATH système. Les outils de génération du fixture restent dans le MSYS2 utilisateur temporaire.
- Le flux UI exige une attestation et une confirmation, mais l’attestation est une déclaration utilisateur, pas un avis juridique ni une vérification automatique des droits. D-010 reste applicable : pas d’extraction sans droits établis; aucune capacité CSS n’est livrée ou activée.

## 5. Verdict et limites

**VALIDÉ pour les deux opérations sur le DVD-Video synthétique original.** Depuis PySide6, AVM permet d’inspecter les titres/angles/durées/chapitres et les flux disponibles, de suggérer le titre le plus long sans verrouillage irréversible, puis de lancer MKV maître ou MKA audio seul avec sélection explicite, progression, annulation et résultat validé.

**Non validé dans AVM-11D :** extraction d’un disque optique physique, sous-titres DVD/VobSub réels, tags de langue venant d’IFO d’un média commercial et tout disque dont l’accès demanderait une neutralisation de TPM. Le lecteur `D:` n’a pas été lu; aucun déchiffrement CSS, contournement, MP4, réencodage ou écrasement n’a été effectué.

Le MKV et le MKA de référence restent dans `%LOCALAPPDATA%\Temp\AVM-11C\test-library` pour inspection manuelle. Le mandat AVM-11D s’arrête ici; aucun mandat ultérieur n’est lancé automatiquement.
