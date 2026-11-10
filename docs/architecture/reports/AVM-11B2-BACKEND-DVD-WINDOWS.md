# AVM-11B2 — Backend d'inspection DVD physique sous Windows

Date : 2026-11-06 · AudioVideoManager 0.5.0 · Windows 11 · DVD `LED ZEPPELIN I`, lecteur `D:`.

**Verdict : NON VALIDÉ sur le DVD physique; implémentation et backend local CSS-off prêts, mais accès bloqué/non concluant.** `DvdInspector` sait maintenant énumérer les titres/parties/angles/chapitres via libdvdnav et inspecter un titre sélectionné via ffprobe. Les fixtures et la CI passent. L’appel natif sur `\\.\D:` et le probe ffprobe sur le lecteur `D:` ont dépassé leurs délais; aucun titre/flux physique n’a été obtenu. Cela ne prouve pas une protection CSS. Aucun VOB n’a été extrait, converti, publié ou archivé.

## 1. Reprise et état du dépôt

- Les changements AVM-11B déjà présents ont été conservés : `DvdInspector`, modèles vidéo séparés, tests synthétiques, enregistrement CI et D-010 mis à jour. Aucun fichier CD, base ou bibliothèque n'a été remplacé par ce mandat.
- D-010 est désormais `ACCEPTÉ SOUS RÉSERVE` pour le développement et l'inspection en lecture seule de DVD-Video non protégés; archivage opérationnel, DVD-Audio et contournement de protections restent hors périmètre.
- Le rapport `AVM-11A-INTEGRATION-DVD-VIDEO.md` référencé dans l'historique de conversation n'est pas présent dans le checkout courant. Son cadrage est déjà résumé dans ce rapport et D-010 est inscrite dans `docs/product/decisions.md`.

## 2. Backend retenu et blocage documentaire

Le backend cible est **libdvdnav + libdvdread pour la navigation/l'énumération, puis FFmpeg `dvdvideo`/ffprobe pour les flux**. Ce sont deux rôles distincts : libdvdnav sait compter les titres/parties et décrire les temps des chapitres; FFmpeg `dvdvideo` inspecte un titre sélectionné, mais ne fournit pas une commande fiable de liste des titres.

La documentation FFmpeg officielle de remplacement, [`doc/demuxers.texi`](https://raw.githubusercontent.com/FFmpeg/FFmpeg/master/doc/demuxers.texi), confirme :

- `dvdvideo` requiert une compilation FFmpeg GPL avec `--enable-libdvdread` et `--enable-libdvdnav`;
- les entrées prises en charge sont un lecteur, une image ISO ou une structure DVD;
- FFmpeg n'embarque aucun code de déchiffrement; un numéro de titre ou PGC/PG doit être choisi. Le défaut ne sonde pas la liste et prend seulement le titre 1;
- `preindex` peut améliorer les marqueurs/durées, au prix d'une seconde passe lente sur le lecteur optique.

Les API upstream libdvdnav consultées dans le miroir de ses en-têtes exposent `dvdnav_get_number_of_titles`, `dvdnav_get_number_of_parts` et `dvdnav_describe_title_chapters`. Les en-têtes consultés — [dvdnav.h (miroir XBMC)](https://raw.githubusercontent.com/xbmc/libdvdnav/master/src/dvdnav/dvdnav.h) et [dvd_reader.h (miroir XBMC)](https://raw.githubusercontent.com/xbmc/libdvdread/master/src/dvdread/dvd_reader.h) — déclarent GPL-2.0-or-later. Les pages VideoLAN GitLab `COPYING` étaient protégées par Anubis lors de cette reprise; ces miroirs ne remplacent pas un audit des révisions/binaires exacts avant redistribution.

**Capacités locales mesurées :**

| Composant | Observation |
|---|---|
| FFmpeg système et fre:ac | Les builds déjà présents n'exposent pas `dvdvideo`; ils restent inchangés. |
| FFmpeg Gyan 9.0.2 full | Archive officielle vérifiée, build Win64 x64 GPLv3; `ffprobe -demuxers` expose `dvdvideo`. SHA-256 archive `F0E46253C70DFE902BAC915DFB4224F0CF1B7C6EEAB9DA2CCC9A5581F9A71B13`; ffprobe `02264DFA4F56BAAA31E443ECE8AA16D397F6B008200E7FD184D22B9009E75FD3`. Le binaire contient un chargeur dynamique générique, mais aucune DLL/symbole CSS embarqué. Aucun `libdvdcss-2.dll` n’a été trouvé dans les 29 répertoires PATH inspectés, les dossiers FFmpeg locaux ou les paquets MSYS2. Le probe physique borné a échoué par timeout; ce binaire n’est pas utilisé par AVM comme backend local permanent. |
| MSYS2/MinGW UCRT64 | Installé dans `%LOCALAPPDATA%\Temp\AVM-11B2\msys64` avec l’installateur `msys2-installer.exe` SHA-256 `416D506C839A2DA4BC184EEEC8CBAAF1055EE698618228C62DFC4232A6970F0E`; GCC 16.2.0, Meson 1.12.1, Ninja 1.13.2, pkgconf 1~3.0.10. Aucun paquet `libdvd*` n’a été installé. Le PATH système n’a pas été modifié. L’installateur a créé des raccourcis Menu Démarrer et initialisé `.bashrc`, `.bash_profile` et `.profile` dans le profil utilisateur; ces effets secondaires sont conservés et signalés. |
| Sources et DLL natifs | libdvdread 7.1.1 (`01A690D1B442DFBBF66E5BBE58604DDC42D5ABA4334B7C9680D9D4DBD116C74D`) et libdvdnav 7.0.0 (`15D28086937647A95C3D6B083F0A86678CD4DD428914E319C64ADF52CADEC786`), licences GPL-2.0-or-later. DLL UCRT64 : libdvdread `2066E90E736C3DF2AEA66A29FD43FA876AFDF681918EE70BAB23F351C0D84F3E`, libdvdnav `33B0C2131D6447C0FF5B66F3AACD8614B7FF42C2403BF3B2BD56CA195244C542`. |

Le build libdvdread a été configuré avec `-Dlibdvdcss=disabled` et recompilé avec `-DAVM_DISABLE_DVDCSS`. Cette macro exclut du code généré la branche upstream `LoadLibraryExA("libdvdcss-2.dll")`; le DLL final ne contient ni ce nom, ni les symboles `dvdcss_*`, ni l’import `LoadLibraryExA`. libdvdnav est compilé depuis sa source amont hash-vérifiée et dépend de ce libdvdread CSS-off. Le patch MR64 de la recette MSYS2 n’a pas été appliqué : l’endpoint VideoLAN a renvoyé une page anti-bot HTML (SHA-256 `70A5CB8664C18E675A26D06E64281BB8705BD2C0E0D55AA8D0265BB66C6AC670` au lieu du hash attendu `9EB8A19C4B0097F28BE923026C9AF05416E7AC43129CAE853555607C6306E08`). libdvdnav amont non patché compile, avec avertissements GCC upstream; aucune redistribution n’est entreprise.

## 3. Inspection physique en lecture seule

| Vérification | Résultat observé |
|---|---|
| Lecteur/volume | `D:`, lecteur optique Windows, UDF `LED ZEPPELIN I`, taille déclarée 8 201 007 104 octets. |
| Structure | `AUDIO_TS/` et `VIDEO_TS/` présents. `VIDEO_TS.IFO` (14 336 octets) commence par `DVDVIDEO-VMG`; `VTS_01_0.IFO` (51 200 octets) commence par `DVDVIDEO-VTS`. Des noms IFO VTS `01` à `04` sont présents. Les noms VTS ne prouvent pas le nombre de titres/PGC. |
| Énumération native | Les DLL CSS-off se chargent localement et les symboles d’énumération sont présents. `D:\\` a d’abord été interprété comme entrée fichier/image et a échoué en moins d’une seconde (« No such file or directory »). L’unique essai avec le chemin périphérique `\\.\D:` a dépassé 35 s sans sortie; le worker a été arrêté. |
| Inspection ffprobe | Build Gyan 9.0.2, titre 1/angle 1, mode `dvdvideo`, JSON, sans `preindex` ni fichier de sortie : timeout externe de 30 s sur `\\.\D:`. Une sonde antérieure sur `D:\\` avait également échoué à ouvrir le lecteur après environ 69 s. Aucune autre lecture physique n’a été tentée. |
| Résultat AVM | L’inspecteur ne peut pas produire de liste validée de titres/chapitres ou de flux pour ce DVD : libdvdnav bloque sur le lecteur et ffprobe ne renvoie aucune donnée. Une erreur/expiration d’accès n’est pas assimilée à CSS ou à une protection. |
| Lecture VOB antérieure | Les essais directs ont renvoyé `OSError: [Errno 22] Invalid argument` et `PermissionError: [Errno 13] Permission denied`. Ces erreurs d'accès ne distinguent pas protection CSS, pilote, lecture UDF ou erreur matérielle. |
| ffprobe générique antérieur | `VIDEO_TS.IFO` seul renvoie `Invalid data found when processing input`; l'IFO n'est pas un flux média linéaire et le binaire ne possède pas `dvdvideo`. |

**Conclusion matérielle :** la présence d'une structure DVD-Video est confirmée par le volume et les signatures IFO; le contenu des titres n'est pas validé. Aucun résultat ne permet d'affirmer que le DVD est protégé ou non protégé. Aucun essai de déchiffrement ou de contournement n'a été fait.

## 4. Implémentation

- `audio_video_manager/metadata/video.py` fournit des modèles séparés du CD pour candidat de titre, titre inspecté, parties, angles, chapitres, flux et résultat; les métadonnées manquantes restent `None`.
- `audio_video_manager/extraction/dvd_navigation.py` charge uniquement les DLL du répertoire explicitement configuré (`AVM_DVDNAV_DIR`), refuse un libdvdread contenant les marqueurs CSS vérifiés et exécute les appels C dans un worker isolé timeoutable. Il énumère titres, parties, angles, durée et chapitres; les temps DVD à 90 kHz sont convertis en secondes.
- `audio_video_manager/extraction/dvd.py` garde la structure VIDEO_TS, ajoute les candidats libdvdnav, puis exige une sélection explicite avant un probe ffprobe de flux. Le chemin de lecteur Windows est normalisé en `\\.\X:`. Aucune commande de sortie média n’est construite.
- Limite de validation : les tests synthétiques et le worker local passent, mais l’énumération et les flux de ce disque réel ne sont pas validés en raison des timeouts physiques. Aucun candidat principal n’est affirmé sans résultat.
- Le contrat MKV maître sans réencodage et la future MP4 H.264/AAC dérivée restent séparés; aucun mux/transcode n'est implémenté par AVM-11B2.

## 5. Couverture CI : D8 contre 11B

| Instantané | Groupes | Cas | Résultat |
|---|---:|---:|---|
| `.ci/avm10e-d8-final3-results.json` | 17 | 353 | GO, zéro échec/skip/crash. |
| `.ci/avm10e-11b-final-results.json` | 14 | 294 | GO, zéro échec/skip/crash; 8 tests DVD ajoutés et une assertion DiscMetadata remplacée. |
| `.ci/avm11b2-ci-results.json` | 14 | 299 | GO, zéro échec/erreur/skip/crash; 13 tests DVD, dont 5 ajoutés depuis 11B. |

Comparaison directe des identifiants JUnit D8/11B2 : **285 cas communs**, **68 cas D8 uniquement** et **14 cas 11B2 uniquement**. Les 68 cas absents se répartissent en 18 `test_rip_integration_10e_d3`, 13 `test_consolidation_10e_d5`, 20 UI D4, 9 UI D5, 3 UI D8, 3 tests de progression, 1 test d'humanisation et l'ancienne assertion d'année. Les 14 cas propres à 11B2 sont les 13 tests `test_dvd_inspector_11b.py` et le nouveau test `test_year_unavailable_requires_justification`; l’ancienne assertion D8 `test_year_unknown_is_accepted_without_justification` n’est plus le contrat courant. Les anciennes suites D3–D8 non présentes au checkout n'ont pas été recréées.

La CI 11B conserve les tests CD de base présents : `test_archive_pipeline` (10), `test_cd_ripper` (7), `test_freaccmd` (5), `test_flac_integrity` (2), `test_rip_check` (2), `test_rip_job` (1) et les tests DiscMetadata (15). Cela confirme le passage de ces tests, mais **ne compense pas** l'absence de la suite d'intégration rip D3 (18 cas) ni des suites UX CD D4–D8 du snapshot D8. Aucune modification du code CD n'a été faite par AVM-11B2.

## 6. Tests et données


## 7. Autorisation nécessaire et verdict
## 7. Verdict de clôture

**AVM-11B2 : NON VALIDÉ pour ce DVD physique; implémentation et CI VALIDÉES.** Le backend local CSS-off compile, expose les API d’énumération et se charge depuis le chemin temporaire isolé. L’énumération du disque via `\\.\D:` et le probe ffprobe du titre 1 ont dépassé leurs délais; aucun titre, chapitre ou flux réel n’a été confirmé. Les échecs n’établissent pas la présence d’une protection. Le disque n’a pas été relu après ces essais bornés.

Aucun paquet ou DLL libdvdcss n’a été installé ou trouvé dans les emplacements vérifiés. Le libdvdread utilisé par AVM a été compilé avec la fonctionnalité CSS désactivée et son chargeur dynamique neutralisé; un test vérifie que le worker refuse tout DLL portant les marqueurs interdits. L’installateur MSYS2 a créé des raccourcis Menu Démarrer et initialisé trois fichiers de profil utilisateur; le PATH système est resté inchangé. Les artefacts restent dans `%LOCALAPPDATA%\Temp\AVM-11B2`.

Aucune extraction, conversion, publication, rip ou écriture dans la bibliothèque/base n’a été lancée. Le pipeline CD D6–D8 est laissé intact. Le mandat AVM-11B2 s’arrête ici; aucune action DVD ou archivage ultérieur n’est programmée.