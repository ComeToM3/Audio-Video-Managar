# AVM-11B — Inspection physique DVD

Date : 6 novembre 2026. **Verdict global : NON VALIDÉ.**

L'inspection structurelle et le traitement des métadonnées sur fixtures sont
validés par les tests ciblés. La lecture du DVD physique Led Zeppelin, le
binaire installé sur le poste Windows et la non-régression complète ne sont
**pas** validés. Aucun résultat de fixture ne constitue une preuve matérielle.

## 1. État initial et déblocage documentaire

Dans la révision reçue, le module DVD ne contenait que
`DvdExtractionNotAvailableError` ; aucun inspecteur, modèle vidéo ou rapport
AVM-11B préexistant n'a été trouvé.

L'URL officielle <https://ffmpeg.org/ffmpeg-formats.html#dvdvideo> a échoué
en résolution DNS dans cet environnement. Cela ne permet pas de diagnostiquer
la session Cursor ni le réseau du poste Windows, dont les journaux ne sont
pas disponibles. Aucun téléchargement n'a été laissé en attente indéfinie :
la recherche a utilisé les sources alternatives accessibles du projet FFmpeg.

Sources officielles consultées, figées au commit
`2f1e5761d89a31350bed3d33817508f83b2f48f9` :

- [Documentation du démultiplexeur](https://raw.githubusercontent.com/FFmpeg/FFmpeg/2f1e5761d89a31350bed3d33817508f83b2f48f9/doc/demuxers.texi).
- [Implémentation et table des options](https://github.com/FFmpeg/FFmpeg/blob/2f1e5761d89a31350bed3d33817508f83b2f48f9/libavformat/dvdvideodec.c#L1839-L1875).
- [Dépendances de compilation](https://raw.githubusercontent.com/FFmpeg/FFmpeg/2f1e5761d89a31350bed3d33817508f83b2f48f9/configure).
- [Options générales des outils](https://raw.githubusercontent.com/FFmpeg/FFmpeg/2f1e5761d89a31350bed3d33817508f83b2f48f9/doc/fftools-common-opts.texi).
- [Documentation ffprobe](https://raw.githubusercontent.com/FFmpeg/FFmpeg/2f1e5761d89a31350bed3d33817508f83b2f48f9/doc/ffprobe.texi).

Le démultiplexeur `dvdvideo` dépend de libdvdnav et libdvdread, avec activation
GPL. La configuration amont vérifie dvdnav >= 6.1.0 et dvdread >= 6.1.1.
Une version récente ou des drapeaux `--enable-libdvdnav` /
`--enable-libdvdread` ne prouvent pas à eux seuls sa disponibilité.

Les options documentées incluent `title`, `angle`, `chapter_start`,
`chapter_end`, `preindex`, `trim`, `pgc`, `pg`, `menu`, `menu_lu`, `menu_vts`,
`region`. L'inspecteur utilise seulement `title` ; il n'active ni préindexation,
ni navigation de menus, ni sélection de région. Les bornes d'options ne
garantissent pas l'existence des titres correspondants.

## 2. Capacités réellement observées

Environnement de validation : Linux, Python 3.12.3, PySide6 6.12.0.
Les dépendances Python déclarées du projet ont été installées, sans changement
de leur déclaration.

| Vérification exécutée | Observation |
|---|---|
| `command -v ffmpeg` / `command -v ffprobe` | Aucun chemin retourné |
| Découverte applicative FFmpeg et ffprobe | Les deux chemins sont `None` |
| `probe_dvd_tool` sur les outils découverts | `tool_missing` pour chacun |
| Recherche `/dev/sr*`, `/dev/cdrom` et `lsblk` | Aucun lecteur optique visible |
| `DvdInspector().inspect(Path('/dev/cdrom'))` | `source_missing`, erreur système conservée |

**Aucune version ni capacité dvdvideo d'un binaire réel ne peut donc être
certifiée ici.** Aucun outil FFmpeg n'a été installé pour faire passer
artificiellement cette validation ; aucune connexion au lecteur Windows
de l'utilisateur n'est disponible.

L'API `probe_dvd_tool` conserve argv, code de retour, stdout, stderr et erreur
des quatre interrogations documentées suivantes, sans ouvrir de média :

```text
ffmpeg -version
ffmpeg -buildconf
ffmpeg -hide_banner -demuxers
ffmpeg -hide_banner -h demuxer=dvdvideo
```

Les mêmes interrogations s'appliquent à ffprobe. Son support doit être vérifié
indépendamment de celui de FFmpeg. L'inspecteur exige une entrée `dvdvideo`
dans les démultiplexeurs **et** l'option `-title` dans l'aide. Une réponse
« Unknown format » avec code zéro n'est pas considérée comme un succès.
Chaque invocation est bornée à 15 secondes par le composant existant.

## 3. Lecture seule et protection : limites de sécurité

Une structure VIDEO_TS lisible ne prouve ni l'absence de protection, ni la
lisibilité des secteurs vidéo, ni l'intégrité de l'archive future.
Un DVD commercial n'est pas déclaré protégé sur la seule base de son origine.

FFmpeg indique ne pas embarquer de code de déchiffrement dans ce démultiplexeur.
Ce n'est cependant pas une garantie pour ses dépendances. Les sources VideoLAN
n'ont pas été accessibles en DNS. Un
[instantané du fork Kodi de libdvdread](https://github.com/xbmc/libdvdread/blob/329ec88257ecaf64a3144644a423289bb3da8ef6/src/dvd_input.c#L310-L419)
montre le chargement automatique possible de libdvdcss, notamment sous Windows.
Ce constat démontre un risque ; il ne certifie pas la pile actuelle du poste.
Aucune option runtime fiable de désactivation du déchiffrement n'a été vérifiée.
Aucune variable d'environnement prétendant le désactiver n'est inventée.

En conséquence :

- Par défaut, l'inspecteur énumère uniquement les noms de fichiers et lit les
  12 octets des signatures IFO. Aucun moteur DVD externe n'ouvre le disque.
- La sonde de métadonnées exige **deux attestations explicites** :
  `known_unprotected=True` pour une source autorisée connue non protégée,
  et `no_css_environment=True` pour une pile auditée incapable de charger CSS.
  Ces attestations ne sont pas une détection automatique ni une preuve
  technique produite par l'application ; leur absence bloque la sonde.
- Elles ne doivent pas être activées pour le DVD commercial dont la protection
  et la pile de lecture restent inconnues. Aucun essai de ce type n'a eu lieu.
- Aucun contournement, extraction, conversion, fichier média de sortie,
  éjection, modification de région ou publication n'a été effectué ou ajouté.

## 4. Implémentation livrée

- `/home/runner/work/Audio-Video-Managar/Audio-Video-Managar/audio_video_manager/extraction/dvd.py` :
  `DvdInspector`, contrôle structurel, capacités réelles et erreurs contrôlées.
  Accepte une racine montée ou un dossier VIDEO_TS, avec noms insensibles à la
  casse. Vérifie VIDEO_TS.IFO, les signatures VTS et la présence des premiers
  VOB de titre ; les BUP absents produisent des avertissements.
- `/home/runner/work/Audio-Video-Managar/Audio-Video-Managar/audio_video_manager/metadata/video.py` :
  modèles immuables pour un titre sélectionné, ses flux vidéo/audio/sous-titres
  et ses chapitres. Dimensions, cadence rationnelle, aspect, entrelacement,
  langues, canaux et fréquence audio restent des observations de la source.
  Les durées absentes restent inconnues ; valeurs non finies et chapitres
  incohérents sont refusés.
- Réutilisation de `CommandProbe`, de l'exécution bornée et de la découverte
  FFmpeg existants, sans modification de ces composants CD/FLAC.
- `/home/runner/work/Audio-Video-Managar/Audio-Video-Managar/scripts/run_tests_ci.py` :
  ajout du seul fichier de tests DVD à la liste du domaine.

Les numéros VTS ne sont **pas** assimilés à des numéros de titres. Le titre
sélectionné explicitement vaut 1 par défaut, sans prétendre identifier le
programme principal. Il n'y a pas d'inventaire exhaustif, de prise en charge
directe des ISO/périphériques bruts, de lecture de menus ni d'intégration UI.
L'API est synchrone et doit être appelée hors du thread UI.

La sonde utilise ffprobe avec `-f dvdvideo`, `-title`, `-show_streams`,
`-show_chapters`, `-show_format` et `-of json`, sans sortie média. Les journaux
bruts restent dans le résultat. Une sonde réussie n'est pas un décodage intégral ;
sans préindexation, durées et chapitrage peuvent être incomplets ou imprécis.

Le modèle décrit la **source**, pas un fichier MP4 supposé compatible.
Le futur MKV maître devra conserver les flux sans réencodage ; toute future
version MP4 compatible restera distincte. Aucune commande de fabrication
de ces versions n'est ajoutée. L'extraction reste désactivée (D-010).
Les modules CD D6–D8, bases, schémas et bibliothèques restent inchangés.

### Diagnostic rendu

| État | Sens, sans conclusion abusive |
|---|---|
| `source_missing` | Chemin/support absent |
| `invalid_structure` | Arborescence ou signature non conforme |
| `structure_only` | Structure reconnue ; protection et lecture vidéo inconnues |
| `backend_unverified` | Absence de CSS non attestée ; aucune sonde média |
| `tool_missing` / `tool_error` / `dvdvideo_unavailable` | Limitation de l'outil, pas preuve d'un défaut du disque |
| `read_error` | Accès/lecture échoué ; détails bruts conservés |
| `probe_error` | Lancement ou délai de sonde échoué |
| `invalid_metadata` | JSON ou métadonnées incohérents |
| `inspected` | Métadonnées du seul titre demandé lues |

Un refus d'accès peut relever des permissions ou du lecteur. Une erreur d'E/S
peut relever du support, du matériel, de la navigation ou d'une protection.
Même une mention CSS dans stderr reste un indice du backend, pas une preuve
indépendante. Pas de repli par concaténation VOB ou autre tentative.

## 5. Validation exécutée et preuves

Tests ciblés :

```text
python -m pytest /home/runner/work/Audio-Video-Managar/Audio-Video-Managar/tests/test_dvd_inspector.py --junitxml=/tmp/avm11b-dvd.xml
39 passed

python -m pytest /home/runner/work/Audio-Video-Managar/Audio-Video-Managar/tests/test_cd_ripper.py /home/runner/work/Audio-Video-Managar/Audio-Video-Managar/tests/test_drives.py /home/runner/work/Audio-Video-Managar/Audio-Video-Managar/tests/test_freaccmd.py /home/runner/work/Audio-Video-Managar/Audio-Video-Managar/tests/test_rip_job.py --junitxml=/tmp/avm11b-cd.xml
15 passed
```

Fixtures synthétiques uniquement : signatures et arborescences DVD, VTS
multiples, BUP manquants, JSON représentatif PAL/NTSC, MPEG-2 entrelacé,
AC-3 5.1, PCM stéréo, langues, sous-titres DVD et chapitres.
Les VOB sont des placeholders **non lisibles comme une vidéo** : aucun
échantillon commercial n'est copié. Les sous-processus sont simulés pour les
cas capacités absentes, délais dépassés, accès refusé, erreurs d'E/S/CSS,
JSON invalide et durées non finies.

Essai manuel sur une arborescence temporaire sous `/tmp` :
`structure_only`, avertissements BUP, comparaison des octets avant/après
identique ; `backend_unverified` quand seule l'origine non protégée est
attestée. Aucun fichier de bibliothèque ni base existante n'a été ouvert.

Suite complète, sans exclusion de tests :

```text
QT_QPA_PLATFORM=offscreen QT_QUICK_CONTROLS_STYLE=Basic AVM_QT_SAFE_EXIT=0 python /home/runner/work/Audio-Video-Managar/Audio-Video-Managar/scripts/run_tests_ci.py --junit-dir /tmp/avm11b-junit --report /tmp/avm11b-ci-results.json
OVERALL: NO-GO
```

Premier passage : bibliothèque native Qt `libEGL.so.1` absente et module
applicatif manquant. Après installation système de `libegl1` et `libopengl0`,
second passage : **14 processus en échec, 24 erreurs de collecte**, tous sur
`ModuleNotFoundError: No module named 'audio_video_manager.library'`.
Les assertions bloquées à la collecte ne sont pas comptées PASS.
freaccmd, libdiscid native et FFmpeg sont indisponibles pour les tests live.
Les preuves locales temporaires sont dans `/tmp/avm11b-ci.log`, les JUnit
et le JSON ci-dessus ; elles ne sont pas des artefacts versionnés.

Les outils GitHub ont aussi confirmé :

- [CI Windows antérieure](https://github.com/ComeToM3/Audio-Video-Managar/actions/runs/42031918245),
  déjà en échec de collecte sur le même module `library` absent.
- [CI Windows du commit d'implémentation](https://github.com/ComeToM3/Audio-Video-Managar/actions/runs/42274972431),
  conclusion `action_required` : autorisation requise, pas une suite réussie.

Le défaut préexistant n'a pas été corrigé hors périmètre et aucun test n'a
été supprimé, ignoré ou réécrit pour le masquer.
`git diff --check` est sans erreur ; scan de secrets sans détection ;
CodeQL Python : **0 alerte**.

## 6. Verdict et arrêt

| Périmètre | Verdict |
|---|---|
| Déblocage documentaire par sources officielles alternatives | VALIDÉ |
| Structures, erreurs contrôlées et modèle sur fixtures | VALIDÉ |
| Régression CD ciblée (15 tests, code CD inchangé) | VALIDÉ |
| Capacité d'un FFmpeg/ffprobe réel sur le poste Windows | NON VALIDÉ |
| Inspection physique du DVD Led Zeppelin / état de protection | NON VALIDÉ |
| CI complète et non-régression globale | NON VALIDÉ |

**AVM-11B : NON VALIDÉ globalement**, faute de matériel accessible et de
validation globale réussie. La lecture physique nécessiterait le poste
Windows et son lecteur ; aucune autorisation de contournement n'en découle.
Le travail s'arrête à ce rapport. Aucun mandat suivant n'est lancé.
