# AVM-11F — Préparation Windows autonome

Date : 2026-11-06 · AVM 0.5.0 · Windows 11 x64 · Python 3.12.10 · PySide6 6.12.0.

## 1. Verdict

**PRÊT SOUS CONDITIONS pour préparer un premier packaging expérimental Windows; pas prêt à redistribuer un paquet autonome CD/DVD en l’état.** La configuration DVD persistante est maintenant prouvée depuis PySide6, les erreurs de dépendances sont contenues, le backend DVD peut fonctionner depuis des dossiers locaux sans PATH global, et la CI complète passe. Une anomalie reproductible a été corrigée sans refonte.

Deux conditions indispensables restent ouvertes : adapter le lancement du worker DVD au runtime retenu et constituer le dossier de redistribution des binaires effectivement embarqués. Le premier est un obstacle technique au gel naïf de l’application; le second est un préalable à toute livraison extérieure, pas une incompatibilité juridique démontrée. La validation sur Windows propre et sur support optique autorisé reste à réaliser. Aucun installateur ni exécutable AVM n’a été produit dans ce mandat.

## 2. Preuve de configuration persistante

Script reproductible : [validate_windows.py](../../../scripts/diag11f/validate_windows.py). Depuis la racine du dépôt :

```powershell
.\.venv\Scripts\python.exe scripts/diag11f/validate_windows.py
```

Le script crée un profil Temp unique et fournit `AVM_DATA_DIR` et `AVM_LIBRARY_ROOT` avant l’import de l’application. Il utilise le véritable `SettingsPage`, le bouton **Enregistrer**, `save_config` et `load_config`, sans détourner la sauvegarde. Les deux processus Qt utilisent `platformName=windows`; la session Windows n’est pas élevée.

1. Premier processus : remplacement des champs par Ctrl+A puis saisie QtTest, clic **Enregistrer**, confirmation du message et lecture du JSON réellement écrit.
2. Second processus : rechargement du JSON depuis le même profil, réaffichage des chemins dans Paramètres, résolution de ffprobe puis inspection réelle du titre 2 de la source synthétique AVM-11C.

Profil de la preuve : `%LOCALAPPDATA%\Temp\AVM-11F-yafam1m1`; configuration : `data\config.json`; bibliothèque : `library`; jobs et logs : `data\jobs` et `data\logs`. Aucun de ces chemins ne pointe vers la bibliothèque personnelle.

| Élément | Valeur sauvegardée/rechargée et résultat |
|---|---|
| FFmpeg | `%LOCALAPPDATA%\Temp\AVM-11B2\ffmpeg\unpacked\ffmpeg-9.0.2-full_build\bin\ffmpeg.exe`, strictement identique sur disque et dans le second formulaire. |
| ffprobe | Il n’existe pas de champ indépendant : le worker dérive `ffprobe.exe` voisin du FFmpeg configuré. Ce chemin exact a été vérifié après rechargement, puis utilisé pour sonder le titre. |
| libdvdnav/libdvdread | `%LOCALAPPDATA%\Temp\AVM-11B2\msys64\ucrt64\bin`, strictement identique sur disque et dans le formulaire. Les deux DLL sont chargées depuis ce dossier. |
| Inspection après rechargement | Statut `inspected`, deux titres candidats, deux flux pour le titre 2. La configuration sauvegardée est réellement utilisable pour l’inspection; ce n’est pas seulement une comparaison de chaînes. |
| Configuration personnelle | SHA-256 avant/après : `b37a325e1835e5e1c7a943c933c0d54fa103d90c597ee5ac26dcdcea76797c50`, inchangé. |

Preuves conservées : [résultats natifs](AVM-11F-evidence/native-settings.json), [paramètres après sauvegarde](AVM-11F-evidence/save-settings.png), [paramètres après rechargement](AVM-11F-evidence/reload-settings.png).

La limite de persistance AVM-11E est levée pour ce parcours isolé. Le script AVM-11F ne répète pas les extractions MKV/MKA réussies en AVM-11E et ne revendique pas un essai manuel non automatisé ni un redémarrage de Windows. Les chemins avec espaces sont exercés par les chemins réels; les chemins UNC, très longs et contenant des caractères non ASCII ne sont pas certifiés ici.

## 3. Détection des dépendances et messages

### Démarrage

Le démarrage `run_app` charge la configuration, crée les dossiers applicatifs, ouvre SQLite et affiche la fenêtre. Il ne lance pas de vérification DVD globale ni de probe fre:ac automatique. Les tests shell conservent ce contrat. Une dépendance multimédia absente ne bloque donc pas l’accès à la bibliothèque et aux paramètres; sa détection intervient à la demande.

L’import de PySide6 est requis pour démarrer : s’il manque ou ne se charge pas, le chemin d’entrée actuel n’offre pas de dialogue graphique de récupération. Le packaging doit l’inclure avec ses DLL/plugins; cette situation n’a pas été simulée en désinstallant une dépendance du poste. Les imports Pylance `PySide6`, `shiboken6`, `discid`, `musicbrainzngs` et `mutagen` sont résolus dans l’environnement vérifié.

### Diagnostics DVD réellement observés dans le dialogue Windows

Chaque cas utilise la source synthétique autorisée. Le worker a terminé, l’inspection n’a pas été déclarée réussie et **Démarrer** est resté désactivé.

| Cas | Message affiché après stabilisation |
|---|---|
| Chemins vides, PATH enfant limité à Windows | `Opération non terminée : ffprobe introuvable; aucun backend DVD-Video disponible.` |
| Chemin configuré inexistant | Même message `ffprobe introuvable`. |
| Build présent sans dvdvideo | `Opération non terminée : Ce build ffprobe n'expose pas dvdvideo; il peut manquer libdvdread/libdvdnav.` |
| Exécutable invalide, fixture non PE | `Opération non terminée : Sonde ffprobe impossible : OSError.` |
| Dossier DLL manquant | `Opération non terminée : libdvdnav n'a pas pu énumérer les titres; aucune protection n'est déduite.` |
| DLL présentes mais invalides, fixtures non PE | Même message générique libdvdnav, sans crash du processus UI. |

[Capture backend absent](AVM-11F-evidence/absent.png), [build incompatible](AVM-11F-evidence/incompatible_demuxer.png), [DLL invalides](AVM-11F-evidence/invalid_dll.png). Les fixtures invalides ne prouvent pas la compatibilité de toutes les architectures/ABI; aucun test réel x86/ARM64 n’est revendiqué.

Les préflights du service FFmpeg ont aussi été exécutés, indépendamment du dialogue : `ffmpeg introuvable; extraction DVD indisponible.`, `Sonde ffmpeg impossible : OSError.` et `Le build ffmpeg ne fournit pas le démultiplexeur dvdvideo.` pour les trois cas absence/fichier invalide/build incompatible. Preuve : [backend minimal et préflights](AVM-11F-evidence/minimal-backend.json).

Pour le CD, le bouton diagnostic de Paramètres vérifie la présence de freaccmd (`run_probes=False`) et affiche `OK` ou `Introuvable — vérifiez le chemin.` Cela n’est pas un test de codec, de lecteur ni d’extraction. La recherche peut retomber sur une installation fre:ac existante; un chemin vide n’équivaut pas à l’absence du programme. Les tests CD existants restent inchangés.

Les messages de DLL et d’exécutable invalide sont suffisants pour refuser l’opération, mais peu précis pour un utilisateur autonome. Les améliorer est facultatif pour un premier paquet de validation; ce n’est pas la cause d’un succès erroné.

## 4. Dépendances et faisabilité sans installation système

| Composant | Rôle et constat |
|---|---|
| Python 3.12.10 x64 | Runtime actuel, bibliothèque standard/SQLite/ctypes. Un paquet autonome doit fournir un runtime ou utiliser un outil de gel; il ne doit pas dépendre du `.venv` du développeur. |
| PySide6/Shiboken 6.12.0 | Widgets, QML/QtQuick et rendu. Inclure les modules utilisés, le plugin Windows `qwindows`, les plugins d’images nécessaires, les imports QtQuick/Controls et le style Basic. Ne pas embarquer indistinctement tous les Addons/WebEngine installés. |
| discid 1.4.2 + libdiscid 0.6.4 x64 | Identification CD. Le loader cherche notamment sous `vendor/libdiscid/libdiscid-0.6.4-win/x64` ou `AVM_LIBDISCID_DIR`. Le fichier vendor n’est pas inclus par la règle setuptools des seuls packages Python; collecte native explicite requise. Son ajout au PATH est local au processus, pas au PATH Windows global. |
| musicbrainzngs 0.7.1 / mutagen 1.48.1 | Métadonnées réseau et fichiers audio; dépendances déclarées. Les services réseau restent requis pour les fonctions qui les utilisent. |
| fre:ac 1.1.7 / freaccmd | Backend CD existant. La notice locale décrit une archive ZIP utilisable sans installateur. `freaccmd.exe` seul n’est pas un bundle : DLL CDRip/smooth/freac et codecs utilisés doivent être identifiés et validés. La relocation de fre:ac n’a pas été exécutée ici. |
| FFmpeg/ffprobe Gyan 9.0.2 full | dvdvideo, remux/sondes et validation. Exécutables x64, chacun environ 228 Mo; total 455 444 480 octets, environ 434 Mio. Imports PE observés : Windows/UCRT, sans DLL MSYS2 dans leur table d’imports. Un build plus petit est une optimisation, pas un préalable fonctionnel. |
| libdvdnav 7.0.0 / libdvdread 7.1.1 CSS-off | Navigation DVD native. Les deux DLL copiées seules dans un dossier Temp ont inspecté les deux titres avec `PATH=C:\WINDOWS\System32`. libdvdnav importe libdvdread et Windows/UCRT; libdvdread importe Windows/UCRT. Aucun runtime MSYS2 supplémentaire n’apparaît dans ces tables d’imports. |
| QML, images et polices AVM | Les règles `package-data` les déclarent déjà. Leur collecte réelle et leur résolution après gel restent à tester; les notices OFL doivent accompagner les polices. |

Le backend minimal testé contient seulement :

| DLL | Taille | SHA-256 |
|---|---:|---|
| libdvdnav-4.dll | 150 493 octets | `33b0c2131d6447c0ff5b66f3aacd8614b7ff42c2403bf3b2bd56ca195244c542` |
| libdvdread-8.dll | 196 882 octets | `2066e90e736c3df2aea66a29fd43fa876afdf681918ee70bab23f351c0d84f3e` |

**Faisabilité : oui pour des outils placés à côté du futur paquet et configurés par leurs chemins explicites.** Aucun privilège administrateur ni modification du PATH global n’a été nécessaire dans les essais. Cela ne démontre pas une découverte automatique de dépendances embarquées, qui n’existe pas actuellement. Ne pas redistribuer tout l’environnement MSYS2 ni des fichiers Windows système. La gestion des DLL d’un runtime gelé et de ses sous-processus externes devra être vérifiée sur une machine propre.

## 5. Licences et obligations de redistribution

Cette section est un examen technique des preuves disponibles, pas un avis juridique ni une approbation du futur bundle. Une licence du projet ne suffit pas à établir celle de chaque binaire/plugin ni à remplir ses obligations.

| Composant réellement présent/utilisé | Licence établie et obligations principales |
|---|---|
| AVM | `GPL-3.0-or-later` dans pyproject et texte GPLv3 du dépôt. Livrer licence/notices et source correspondant à la version distribuée, avec scripts nécessaires de compilation/installation. |
| Python | Licence PSF/Python et notices tierces du runtime exact à conserver. Examiner aussi les bibliothèques natives effectivement collectées; le caractère standard d’un module ne dispense pas de notices. |
| PySide6/Essentials/Addons/Shiboken | Métadonnées locales : `LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only`. Pour AVM GPLv3, retenir explicitement une voie compatible et vérifier les modules Qt et leurs tiers effectivement embarqués. En voie LGPLv3 : textes LGPL/GPL, notices, sources correspondantes des bibliothèques livrées et possibilité de modification/remplacement conformément aux termes. Ne pas supposer une licence commerciale acquise parce qu’un fichier `LicenseRef-Qt-Commercial.txt` est présent. |
| python-discid 1.4.2 | `LGPL-3.0-or-later` dans les métadonnées; texte `COPYING.LESSER` local. Conserver notices et satisfaire la fourniture des sources de la bibliothèque distribuée. |
| libdiscid 0.6.4 | En-tête `discid.h` : `LGPL-2.1-or-later`; `COPYING` contient LGPLv2.1. Licence/notices et sources de la version native livrée; distinguer cette bibliothèque du binding Python. |
| musicbrainzngs 0.7.1 | `COPYING` : BSD 2 clauses, avec `compat.py` sous ISC. Conserver les deux notices et disclaimers dans la distribution. |
| mutagen 1.48.1 | `GPL-2.0-or-later`, pas GPLv2-only. La variante « or later » permet la combinaison GPLv3; conserver licence/notices et sources correspondantes. |
| FFmpeg/ffprobe exacts | `ffmpeg -L` annonce `GPL-3.0-or-later`; options `--enable-gpl --enable-version3 --enable-static`, sans `--enable-nonfree` dans la ligne observée. Le full build contient de nombreuses bibliothèques tierces statiques : fournir leurs notices et les sources correspondantes, configurations et modifications. La seule archive binaire et son fichier LICENSE ne constituent pas un dossier de conformité complet. |
| libdvdnav/libdvdread | Les en-têtes des sources locales annoncent `GPL-2.0-or-later`. Conserver licences/notices, sources correspondant aux DLL, recette de compilation et modifications CSS-off effectivement utilisées; les arbres de sources Temp ne sont pas un manifeste de redistribution vérifié. |
| fre:ac et plugins | Le `COPYING` installé contient GPLv2. La portée/variante exacte des composants et les licences CDRip, smooth, codecs et autres DLL doivent être établies individuellement avant de redistribuer l’ensemble. Ne pas conclure GPLv2-only ou GPLv2-or-later pour tous les plugins à partir de ce seul texte. La notice mentionne aussi des sons CC BY 3.0, à prendre en compte seulement s’ils sont livrés. |
| Fraunces/Outfit | Notices locales `OFL-Fraunces.txt` et `OFL-Outfit.txt`, SIL OFL 1.1. Inclure copyright et licence; respecter les conditions de modification et noms réservés éventuels, et ne pas vendre les polices seules. |

Pillow 13.0.0 est installé (métadonnées `MIT-CMU`), mais n’apparaît pas dans les imports AVM de l’audit Pylance; il n’est pas une dépendance runtime à embarquer par défaut. Les packages de tests, l’auteur DVD/dvdauthor et les outils de compilation ne sont pas des dépendances runtime AVM.

La matrice GNU confirme que **GPLv2-or-later**, LGPLv2.1 et LGPLv3 disposent de voies compatibles avec GPLv3; **GPLv2-only** ne peut pas être supposée compatible dans une œuvre combinée. Le lancement d’un outil externe n’annule pas ses obligations propres de redistribution. Aucun conflit précis n’a été démontré dans les composants examinés; la conformité du bundle entier reste non établie.

Les images `ui/assets` sont utilisées par l’application. Les documents UX consultés donnent leurs chemins, mais pas une preuve complète de droits de redistribution pour chaque fichier; établir leur provenance/permission avant livraison extérieure. Les éventuels runtimes Microsoft, bibliothèques statiques FFmpeg et plugins Qt requièrent eux aussi une revue par artefact. Les licences libres ne déterminent ni les droits de reproduction des DVD ni les obligations éventuelles de brevets multimédia.

Références officielles consultées : [FFmpeg, licence et considérations légales](https://ffmpeg.org/legal.html), [Qt for Python, licences tierces](https://doc.qt.io/qtforpython-6/licenses.html), [matrice de compatibilité GNU](https://www.gnu.org/licenses/gpl-faq.html#AllCompatibility), [PyInstaller, sens de sys.executable en mode gelé](https://pyinstaller.org/en/stable/runtime-information.html#using-sys-executable-and-sys-argv-0). Les obligations du FFmpeg GPLv3 testé ne doivent pas être remplacées par la checklist LGPL générique de son site.

## 6. Tests, correction et limites matérielles

Anomalie démontrée avant correction : avec `ffmpeg_path=""`, `DvdTaskWorker.run()` émettait `name 'os' is not defined` au lieu du diagnostic prévu. [dvd_worker.py](../../../audio_video_manager/ui/dvd_worker.py) utilisait `os.environ` sans import. Seul l’import manquant a été ajouté; [test_ui_shell.py](../../../tests/test_ui_shell.py) couvre désormais les chemins vide et fourni via `AVM_FFMPEG`. Les deux cas ciblés passent immédiatement après correction. Aucun changement de signature, de fonctions CD ou d’architecture n’a été effectué.

CI complète exécutée :

```powershell
.\.venv\Scripts\python.exe scripts/run_tests_ci.py --report .ci/avm11f-final-ci-results.json --junit-dir .ci/junit/avm11f-final
```

Résultat : **14 groupes, 319 tests (242 domaine + 77 UI), 0 échec, 0 erreur, 0 skip, tous les codes de sortie à 0, aucun crash natif**. [Rapport CI conservé](AVM-11F-evidence/ci-results.json); JUnit locaux dans `.ci/junit/avm11f-final/`. Les tests d’inspection/extraction DVD, confirmations, sélection audio, refus d’écrasement, garde CSS, annulation/timeouts, CD, archive/recovery, métadonnées, bibliothèque et teardown Qt sont inclus dans l’orchestrateur existant. Aucun import Pylance non résolu ni diagnostic sur les fichiers Python touchés.

La CI détecte freaccmd dans `C:\Program Files\freac`, libdiscid chargeable et le FFmpeg générique de `C:\Tools`; cela ne prouve pas l’autonomie du futur paquet ni un rip CD physique. La validation DVD native utilise séparément le build Temp avec dvdvideo. L’environnement editable annonce encore une ancienne version de distribution AVM dans ses métadonnées, alors que le code et pyproject indiquent 0.5.0 : partir d’un environnement de build propre et figé, pas réutiliser aveuglément ce `.venv`.

**DVD physique autorisé : aucun n’est établi comme disponible pour ce mandat.** Aucune inspection ni extraction du lecteur `D:` n’a été lancée. Les seules lectures DVD nouvelles concernent la référence synthétique locale AVM-11C. Les extractions MKV/MKA natives déjà validées restent documentées dans [AVM-11E](AVM-11E-VALIDATION-PARCOURS-UTILISATEUR.md); aucun résultat optique ne leur est substitué.

Restent non certifiés : disque gravé/lecteur physique, autres architectures Windows, machine sans Python/outils système, paquet gelé, sous-titres VobSub/langues/angles réels au-delà des fixtures, réseau/UNC, chemins extrêmes et DPI variés. Aucun CSS, extraction commerciale non autorisée, installation globale ou changement destructif n’a été effectué.

## 7. Obstacles hiérarchisés

| Priorité | Obstacle et impact | Condition de clôture |
|---|---|---|
| **P0 technique, avant un paquet DVD fonctionnel** | [dvd_navigation.py](../../../audio_video_manager/extraction/dvd_navigation.py) démarre son worker avec `sys.executable -c <code>`. PyInstaller remplace ce chemin par le lanceur AVM gelé, qui ne traite pas `-c` comme Python. Le contrat actuel ne permet donc pas un gel direct fiable. Constat code/documentation, pas crash d’un exécutable testé. | Choisir et valider un runtime fournissant ce contrat ou un dispatch worker compatible avec le gel; préserver l’isolation native et les timeouts. Non implémenté ici : aucune nouvelle fonction de lancement/packaging ni exécutable de test. |
| **P0 conformité, avant redistribution** | Pas de dossier exhaustif pour FFmpeg full, DLL DVD modifiées, Qt/tiers, fre:ac/plugins et images. Une permission/licence générique ne remplit pas les obligations par artefact. | Manifeste versions/hashes/licences, notices, sources correspondantes et recettes/modifications; provenance des assets et revue de toute obligation non établie. |
| **P1 indispensable au packaging** | Pas de recette gel/collecte validée pour les natives, Qt/QML, assets et outils externes; aucune certification sur Windows propre. Les chemins explicites existent mais aucun auto-bundle n’est prouvé. | Collecte ciblée, profil utilisateur hors dossier programme, tests de démarrage/configuration/worker et sous-processus sur machine propre sans Python/PATH outils, avec compte non administrateur. Cette validation appartient au futur packaging, pas à ce mandat. |
| **P1 validation produit conditionnelle** | Pas d’extraction sur support optique physique autorisé. | Test d’inspection puis MKV/MKA sur DVD autorisé, avec validation des fichiers. Ne bloque pas un paquet expérimental clairement limité aux dossiers DVD; bloque la revendication d’archivage optique certifié. |
| **P2 facultatif** | Diagnostics DLL plus précis, état de dépendances au démarrage, contrôle des chemins avant sauvegarde, build FFmpeg plus petit, signature Windows et automatisation de déploiement. | Améliorations ultérieures selon audience et risque; aucune n’est une correction nécessaire à la persistance ou aux extractions synthétiques déjà prouvées. La signature peut devenir une exigence d’une politique de distribution particulière. |

**Décision finale : PRÊT SOUS CONDITIONS.** Les prérequis applicatifs permettent d’engager la préparation d’un premier paquet de validation après traitement du contrat worker; ils ne justifient pas une livraison autonome immédiate. La persistance n’est plus bloquante, et aucune incompatibilité de licence globale n’est présumée. Les conditions P0/P1 ci-dessus sont explicites et vérifiables. AVM-11F s’arrête ici, sans lancement automatique du mandat suivant.