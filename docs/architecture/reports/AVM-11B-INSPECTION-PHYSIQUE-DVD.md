# AVM-11B — Inspection physique DVD et fondation du moteur vidéo

Date : 2026-11-06 · AudioVideoManager 0.5.0 · Windows 11 · lecteur `D:`.

**Verdict : NON VALIDÉ pour l'inspection des titres et flux physiques; fondation logicielle prête.** `VIDEO_TS` et ses IFO sont détectés sur le disque réel, mais aucun backend FFmpeg installé ne fournit `dvdvideo`. Le contenu des VOB, titres, chapitres, angles et flux du disque n'a donc pas été inspecté. Aucun contournement, extraction, conversion ou publication n'a été tenté.

## 1. Décision et clôture AVM-11A

D-010 est actualisée dans `docs/product/decisions.md` : le développement et l'inspection en lecture seule de DVD-Video non protégés sont autorisés sous réserve; l'archivage opérationnel ne l'est pas avant une validation matérielle distincte. DVD-Audio et tout contournement de protection restent hors périmètre. `docs/product/architecture.md`, `docs/product/requirements.md`, `docs/product/roadmap.md` et `README.md` distinguent maintenant inspection expérimentale et archivage DVD non disponible.

Le rapport AVM-11A antérieur n'était pas présent dans `docs/architecture/reports/` au moment de ce mandat. Son cadrage est repris ici; D-010 est néanmoins consignée explicitement dans l'historique décisionnel.

## 2. Blocage documentaire et backend

La récupération de la page HTML `https://ffmpeg.org/ffmpeg-formats.html#dvdvideo` n'a pas abouti lors de la tentative précédente. AVM-11B a utilisé la source officielle alternative du dépôt FFmpeg : [`doc/demuxers.texi`](https://raw.githubusercontent.com/FFmpeg/FFmpeg/master/doc/demuxers.texi), section `dvdvideo`.

Cette documentation officielle établit que :

- le démultiplexeur requiert FFmpeg compilé avec le support GPL et `libdvdread`/`libdvdnav`;
- son entrée peut être un lecteur optique, une image ISO ou une structure de fichiers;
- il ne contient **aucun code de déchiffrement**;
- l'utilisateur doit fournir un numéro de titre ou un couple PGC/PG; le défaut ne choisit que le titre 1 et l'énumération des titres n'est pas fournie par le démultiplexeur;
- `preindex` peut améliorer les marqueurs/durées des chapitres, mais impose une seconde passe lente sur un lecteur optique.

Capacités mesurées sur la machine :

| Outil | Faits observés |
|---|---|
| `C:\Tools\ffmpeg\bin\ffprobe.exe` / `ffmpeg.exe` | Version `2025-12-04-git-d6458f6a8b-essentials_build-www.gyan.dev`; build marqué `--enable-gpl`; `-demuxers` expose `mpeg`, mais pas `dvdvideo`. L'appel explicite à `-f dvdvideo` renvoie `Unknown input format: dvdvideo`. |
| `C:\Program Files\freac\codecs\cmdline\ffmpeg.exe` | Détecté; expose `mpeg`, mais pas `dvdvideo`. Il ne peut donc pas servir d'inspecteur DVD-Video sur cette machine. |
| Autres backends | Aucun `makemkvcon`, VLC, mpv, mkvmerge, dvdbackup, vobcopy ou MediaInfo trouvé dans le PATH ou les répertoires vérifiés. Modules Python `pymediainfo`, `av`, `ffmpegio`, `dvdread` et `pydvd` absents. Aucune installation effectuée. |

L'absence de `dvdvideo` est une limitation du build local, pas une preuve de protection du disque. Aucun test de CSS, de déchiffrement ou de contournement n'a été réalisé.

## 3. DVD physique — observations en lecture seule

| Observation | Résultat |
|---|---|
| Lecteur | `D:`; lecteur optique Windows; volume UDF intitulé `LED ZEPPELIN I`; taille déclarée 8 201 007 104 octets. |
| Racine | `AUDIO_TS/` et `VIDEO_TS/` présents. |
| VMG | `VIDEO_TS.IFO`, 14 336 octets; signature de 12 octets `DVDVIDEO-VMG` lisible. |
| VTS principal échantillonné | `VTS_01_0.IFO`, 51 200 octets; signature `DVDVIDEO-VTS` lisible. Des fichiers nommés `VTS_01_0.IFO` à `VTS_04_0.IFO` sont présents. Ces numéros sont tirés des noms; leur contenu n'a pas tous été validé. |
| VOB | L'ouverture directe d'un VOB a renvoyé `OSError: [Errno 22] Invalid argument`; une tentative antérieure d'inspection avait aussi retourné `PermissionError: [Errno 13] Permission denied`. Ces erreurs ne permettent pas de conclure à CSS, à un défaut physique ni à une structure corrompue. |
| ffprobe générique | La tentative sur `VIDEO_TS.IFO` a renvoyé `Invalid data found when processing input`; l'IFO seul n'est pas un média linéaire et ce build ne possède pas le démultiplexeur DVD requis. |

L'inspection réelle via `DvdInspector.inspect("D:\\")` renvoie `backend_unavailable`, conserve le chemin `VIDEO_TS`, annonce les jeux de titres 1–4 à partir des noms IFO et retourne **zéro titre inspecté**. Les durées, chapitres, angles, codecs, langues, sous-titres et flux sont donc inconnus; aucune valeur n'est inventée. Le statut ne déclare pas le disque « protégé ».

## 4. Implémentation

- `audio_video_manager/metadata/video.py` ajoute des résultats typés distincts du modèle CD : capacité backend, statut d'inspection, flux vidéo/audio/sous-titres, chapitres, titre inspecté et résultat global. Les indices/langues/canaux/durées absents restent `None`.
- `audio_video_manager/extraction/dvd.py` remplace le placeholder par `DvdInspector`. Il détecte `VIDEO_TS.IFO`/signature VMG et les noms VTS, sonde le binaire pour le démultiplexeur `dvdvideo`, et exige une sélection explicite de titre/angle. Si le backend manque, il s'arrête avant toute lecture de contenu VOB. S'il est disponible, il appelle uniquement `ffprobe` avec `-show_format/-show_streams/-show_chapters`; aucune option de sortie média n'est construite. Timeout, erreur de lecture, protection explicitement signalée, structure invalide et backend absent ont des statuts séparés.
- `audio_video_manager/extraction/__init__.py` exporte `DvdInspector`; aucune fonction d'extraction DVD n'est ajoutée.
- Tests synthétiques sous `tests/test_dvd_inspector_11b.py` couvrent un DVD-Video valide, disque inconnu, structure invalide, backend absent, sélection de titre, erreur/timeout, protection signalée et métadonnées incomplètes. Le runner CI ajoute ce fichier au groupe domaine.
- D-010 ne modifie aucun comportement CD; le module `cd_ripper.py`, les modèles audio et le pipeline CD n'ont pas été changés dans ce mandat.

## 5. Contrats préparés pour MKV et MP4

La cible décidée est un **MKV maître sans réencodage**. Un futur backend devra sélectionner explicitement le titre, l'angle, les flux audio/sous-titres et les chapitres; il devra conserver le codec, la résolution, la cadence et l'ordre des flux vérifiés. Il devra enregistrer versions, arguments, titres et hashes dans les checkpoints du job. L'inspecteur présent ne crée pas de MKV.

Un futur MP4 H.264/AAC sera un **dérivé facultatif** dans un profil séparé, jamais un remplacement du maître. Toute conversion devra être opt-in, marquée comme avec perte, documenter codecs/qualité/paramètres, utiliser une destination distincte et ne jamais écraser le MKV maître.

## 6. Tests, intégrité et limites

| Contrôle | Résultat |
|---|---|
| Tests ciblés `test_dvd_inspector_11b.py`, `test_disc_metadata.py`, `test_cd_ripper.py` | PASS : 30 tests; le contrat CD demeure inchangé. |
| Tests DVD dans le JUnit de la CI | 9 cas présents dans le groupe `domain`, tous réussis (8 nouveaux + le test existant du placeholder D-010). |
| Diagnostics Pylance | PASS : aucune erreur sur le modèle vidéo, l'inspecteur, son export, les tests et le runner CI. |
| CI complète | PASS : 14 groupes, 294 tests, 0 échec, 0 erreur, 0 skip, aucun crash natif. Résultats `.ci/avm10e-11b-final-results.json`; JUnit `.ci/avm10e-11b-final-junit/`. |
| Données / processus | Aucun freaccmd, ffprobe ou ffmpeg actif après le probe; aucun fichier média créé. La base 10E conserve son hash antérieur `819186612119336244b6cf4aa37b4cf9bdf5479ff5f705e2dea560601ae0eabc`; le job D6 reste `CompletedWithWarnings`. Les 144 fichiers protégés conservent les deux différences antérieures cache/log, sans différence supplémentaire observée. |

Le DVD n'a pas pu fournir de titres/flux physiques par FFmpeg. Les fixtures ne sont pas une validation matérielle et n'établissent ni le nombre réel de titres ni l'état anticopie. Une validation physique complète nécessite un build FFmpeg qui expose `dvdvideo` (avec `libdvdread`/`libdvdnav`) ou un backend inspecteur open source compatible, puis une nouvelle inspection autorisée en lecture seule. La politique de sécurité Windows est restée inchangée.

## 7. Verdict

**NON VALIDÉ pour l'inspection physique des titres, chapitres et flux; fondation logicielle et tests validés.** Le DVD est structurellement reconnu au niveau du volume/IFO, mais le backend de la machine ne peut pas inspecter son contenu. La différence entre absence de démultiplexeur, erreur d'accès VOB et protection du disque reste non résolue; aucun de ces états n'est assimilé à une preuve d'un autre.

Aucun rip, remux, transcodage, publication, installation ou changement de données de production n'a eu lieu. AVM-11B s'arrête ici; aucune suite d'archivage n'est lancée automatiquement.