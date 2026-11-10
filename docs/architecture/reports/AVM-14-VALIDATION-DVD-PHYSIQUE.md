# AVM-14 — Validation DVD physique non protégé

Date : 2026-11-07 · Windows local · Python 3.12 · branche `main`, commit `b4c00071cab4a151bcf524b96a7c654064c15a1f`.

## Verdict final : PARTIEL

Le MKV provisoire issu du DVD physique est lisible par ffprobe et son décodage audio et vidéo complet ne signale aucune erreur. Un MKA produit à partir de ce MKV conserve les mêmes échantillons audio. La chaîne complète depuis le DVD jusqu'à la publication reste toutefois non validée : la comparaison PCM intégrale avec la source a été interrompue et le MKA natif depuis le DVD n'a pas été testé après correction. La synchronisation perçue et la qualité sonore exigent une écoute humaine.

## Source et inspection

- Lecteur confirmé : `D:\`, volume `IMPORT_PIERRE_MERCURE_2006`. La présence d'un nom de volume n'est pas une condition d'identification des titres DVD.
- Structure `VIDEO_TS` et IFO détectés. Empreinte SHA-256 de `VIDEO_TS.IFO` : `150ae230b969563f23e877c15c81df74a77468be727309d29f473c3a6c3e4e8d`. Le pilote vérifie le volume et l'empreinte avant l'opération.
- Un titre interne, titre 1, angle 1, durée annoncée 02:21:34, six chapitres. Vidéo MPEG-2 720 × 480; une piste audio PCM DVD stéréo 48 kHz, 16 bits, langue inconnue. Aucun sous-titre n'a été signalé par l'inspection.
- Chapitres : 00:00–00:42, 00:42–24:20, 24:20–49:28, 49:28–52:33, 52:33–01:26:00 et 01:26:00–02:21:34. Aucun nom de chapitre n'a été fourni; l'interface affiche les numéros et les durées sans inventer de titres.
- Les titres internes et les chapitres sont des structures distinctes. Les entrées du menu de pistes ne sont pas identifiées par l'inspection disponible : les six chapitres ne doivent pas être présentés comme six entrées de menu.
- libdvdread et libdvdnav ont signalé un avertissement `Zero check failed` pour `vmgi_mat->zero_3`. Son origine n'est pas déterminée; il ne démontre ni protection ni échec systématique de lecture.

## Parcours et correction ciblée

Le parcours Archiver a inspecté le titre et affiché ses chapitres et flux avec les vrais workers Qt. La source, la destination temporaire et les droits de reproduction ont été confirmés par l'utilisateur; la conversion PCM ciblée a également été autorisée explicitement.

Les premiers essais MKV et MKA, en copie directe, ont échoué sans publication : FFmpeg signale `No wav codec tag found for codec pcm_dvd`. Le parcours autorise désormais, après consentement distinct, la conversion du seul PCM DVD explicitement identifié comme 16 bits, 48 kHz stéréo vers PCM `pcm_s16le`; les autres flux restent copiés. La validation compare les empreintes des échantillons décodés de la source et de la sortie avant publication. Les profondeurs ou caractéristiques non établies sont refusées.

Un essai physique court de trois secondes a produit des empreintes source et MKA identiques : `e905db97380e1a8e89f26031f931976f3d2e56d03bee48cbabc60f7e2aedcc99`. Il ne constitue pas une validation complète du disque.

La première tentative complète après correction a été interrompue pendant la vérification PCM : un fichier provisoire de 4 409 371 372 octets a été conservé, sans publication ni validation complète. `ffprobe` y identifie une vidéo MPEG-2 et un audio PCM 16 bits stéréo 48 kHz, pour une durée de 8 502,536 s. Une lecture complète des paquets par FFmpeg en copie de flux s'est terminée avec le code 0 et sans erreur; elle ne prouve ni le décodage complet ni l'égalité des échantillons.

La seconde tentative MKV, dans `%LOCALAPPDATA%\Temp\AVM-14-validation-20261107\pcm-reprise`, a achevé la copie et atteint 97 % pendant la relecture PCM source. Le délai maximal d'une heure du pilote a alors provoqué l'annulation et le nettoyage du fichier provisoire, sans publication. Cette limite du pilote a été portée à quatre heures pour les prochaines tentatives. La première copie provisoire a ensuite fait l'objet des vérifications locales ci-dessous, sans comparaison PCM intégrale avec le DVD.

## Validation du MKV existant

- Fichier examiné, conservé dans son emplacement provisoire : `%LOCALAPPDATA%\Temp\AVM-14-validation-20261107\pcm-verifie\.avm-dvd-s5q7k36g\master.mkv`. Taille : **4 409 371 372 octets**. Son SHA-256 avant et après les contrôles est `b21519462e3391b5582686050f5ea589078540e9dd4b3d2aae35f66a52744c1a`.
- `ffprobe -v error -show_format -show_streams -show_chapters -of json` : code 0, aucune erreur; Matroska, 8 502,536 s (02:21:42,536), vidéo MPEG-2 Main 720 × 480, 29,97 images/s, audio `pcm_s16le` 16 bits, 48 kHz, deux canaux; aucun flux sous-titre, six chapitres.
- La fin du sixième chapitre est à 8 494,400 s : le conteneur dure **8,136 s de plus**. Les flux vidéo et audio se prolongent jusqu'à environ 8 502,527 s et 8 502,536 s respectivement. L'origine de cet écart n'est pas établie; il ne démontre pas à lui seul un défaut ni que la fin du concert est complète.
- Décodage complet sans fichier de sortie média : `ffmpeg -v error -xerror -i <MKV> -map 0:v:0 -map 0:a:0 -f null -`. Code 0, aucune erreur signalée, 39,84 s. La précédente lecture des paquets en copie de flux avait aussi réussi. Le fichier original n'a été ni remplacé ni modifié.
- Trois fenêtres de 30 s, à 00:00:00, 01:10:36 et 02:21:12, ont été décodées séparément avec `-xerror` : trois codes 0, sans erreur. Les images extraites à 10 s, 4 251 s et 8 495 s montrent bien la scène du concert; elles ne prouvent pas la qualité de toutes les images.
- Dans ces fenêtres, les écarts maximaux entre paquets audio consécutifs mesurés par ffprobe sont de 2 ms et les décalages entre les premières estampilles audio et vidéo présentes dans chaque fenêtre sont de 0, -32 et -30 ms. Ces mesures dépendent des limites de fenêtres et de la granularité des paquets; elles ne constituent pas une mesure de synchronisation perceptive ni une garantie de continuité pour toute la durée.
- Avec `silencedetect` à -60 dB pendant au moins une seconde, aucun silence n'est détecté dans ces trois fenêtres. Les niveaux moyens `volumedetect` sont respectivement -41,9, -23,5 et -22,6 dB; le début est nettement plus faible. Ces mesures ne déterminent pas si le niveau ou le contenu sonore est correct.
- Images locales conservées sous `%LOCALAPPDATA%\Temp\AVM-14-validation-20261107\controle-local-final\` : `debut.png`, `milieu.png`, `fin.png`. Aucune écoute ni comparaison perceptive des lèvres ou instruments avec le son n'a été réalisée.

## MKA à partir du MKV

- Fichier distinct : `%LOCALAPPDATA%\Temp\AVM-14-validation-20261107\controle-local-final\audio-depuis-mkv.mka`, **1 638 267 398 octets**, SHA-256 `fe29a9efd718330e56fd28fbb76c2ff14aaf72b647a6162b291e9148456429fc`.
- Produit à partir du MKV uniquement, par `ffmpeg -n -i <MKV> -map 0:a:0 -map_chapters 0 -map_metadata 0 -vn -c:a copy -f matroska <MKA>` : code 0, aucune erreur; destination absente avant création, aucun écrasement.
- ffprobe : un flux audio `pcm_s16le` 16 bits, 48 kHz, deux canaux, aucun flux vidéo, six chapitres, durée 8 502,535 s. Le décodage audio des deux fichiers vers une empreinte SHA-256 donne pour chacun `ea4182c21e0c27f960b127f8cf23e89d6fa1ee842ae8c4f705c8fd07af923cc4`, sans erreur. Cela démontre l'identité des échantillons du MKV et du MKA, pas leur identité avec le DVD.
- Cette opération valide un remux local depuis le MKV, **pas** le parcours MKA natif depuis le DVD ni sa publication par l'interface.

## Analyse du timeout

Le journal `%LOCALAPPDATA%\Temp\AVM-14-validation-20261107\pcm-reprise\avm14-mkv-evidence.json` rapporte à 3 601,6 s une progression de 97 % en `Vérification PCM source` à 02:02:32, puis `TimeoutError: Délai de validation dépassé; annulation demandée`. La fonction `wait_for_worker` du pilote annulait l'opération après 3 600 s; le nettoyage a supprimé le staging de cette seconde tentative. Ce délai global du pilote est la cause documentée de l'annulation, non une erreur de décodage démontrée. Le délai a été porté à quatre heures, sans nouvel essai physique pour en certifier la durée suffisante.

## Tests

- Tests ciblés inspection DVD, extraction DVD et shell UI réexécutés après correction du pilote : **49 réussis**. `py_compile` du pilote : code 0.
- CI complète antérieure à l'ajustement du délai du pilote : **329 tests**, 14 groupes, aucun échec, aucune erreur, aucun skip ni crash natif. Résultats : `.ci/avm14-ci-results.json`; JUnit : `.ci/junit/avm14/`. Elle n'a pas été relancée pour cette finalisation.
- Les tests ajoutés couvrent notamment l'attestation de conversion, les profondeurs non prises en charge, les formats MKV/MKA et le refus de publication lorsque les empreintes PCM diffèrent.

## Limites

- L'égalité des échantillons entre le DVD et le MKV complet n'a pas été établie; seule la comparaison physique de trois secondes a réussi. Le MKV reste en staging et n'a pas été publié par AVM.
- Le MKA natif depuis le DVD après correction et la publication finale dans l'interface restent non validés; le MKA local n'est pas une preuve de ce parcours.
- Aucune lecture physique supplémentaire ni nouvelle extraction DVD n'a été lancée durant cette finalisation. Une vérification intégrale de fidélité à la source exigerait une nouvelle lecture et l'autorisation préalable de l'utilisateur.
- Aucune association fiable entre menu et chapitres n'a été établie; les noms de pistes et la langue ne sont pas inventés.
- Aucun mécanisme CSS ou contournement de protection n'a été ajouté. Le moteur CD et l'identité visuelle n'ont pas été modifiés dans ce mandat.