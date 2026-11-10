# AVM-28B — Validation du parcours d’import CD

**Verdict : PARTIEL — le crash au démarrage a reçu un correctif ciblé et les validations synthétiques passent; le redémarrage Windows et le parcours avec CD physique restent à observer. Aucun rip physique n’a été lancé.**

## Incident et correction

L’utilisateur a fourni l’observation suivante lors du lancement Windows :

```text
freaccmd trouvé : C:\Program Files\freac\freaccmd.exe
Réconciliation : scanned=0 changed=0
code de sortie : -1073740771 (0xC000041D)
```

Le code `0xC000041D` indique une exception non gérée dans un callback utilisateur Windows. Le chemin nouvellement ajouté était `MainWindow.nativeEvent`. Il interprétait `lParam` comme un pointeur `DEV_BROADCAST_HDR` pour tout message Windows dès que `lParam` était non nul, alors que la plupart des messages portent une valeur qui n’est pas un pointeur. Le déréférencement pouvait provoquer l’exception native.

`nativeEvent` filtre maintenant la famille de messages Qt et le couple `WM_DEVICECHANGE` + arrivée/retrait avant d’accéder à `lParam`; il vérifie la taille de l’en-tête, capture ses exceptions et retourne le couple PySide `(False, 0)` pour laisser Qt traiter le message. Un test construit en mémoire des messages Win32 synthétiques et vérifie l’ignorance d’un type non-Windows, l’acceptation d’événements volume et l’absence de scan hors de la section Archiver. Cette preuve est synthétique et ne reproduit pas encore le démarrage Windows de l’utilisateur.

## Résultat logiciel

- La détection utilise un worker Qt pour l’énumération freaccmd et les lectures TOC; le thread UI ne fait pas les probes optiques. Windows `WM_DEVICECHANGE` planifie un scan debouncé; le bouton d’actualisation/relecture reste disponible.
- Les lecteurs Windows pour TOC et freaccmd pour rip sont distincts. Si plusieurs lecteurs rendent l’association incertaine, W4 exige une confirmation avant extraction. Un changement de Disc ID invalide l’ancienne fiche; retrait ou absence de CD invalide la TOC et empêche le rip normal.
- Identification, choix/correction et approbation restent dans le wizard existant. En cas d’identification en échec, la fiche issue de la TOC peut être complétée manuellement. Le pipeline d’archivage, doublons, vérification FLAC, publication SQLite et `technical_test` n’ont pas été modifiés.
- Les parcours DVD et le schéma SQLite ne sont pas modifiés par AVM-28B.

## Fichiers AVM-28B modifiés

- `audio_video_manager/ui/main_window.py` — filtrage défensif du callback natif et planification du scan.
- `audio_video_manager/ui/wizard/archive_wizard.py` — état du scan, sélection des lecteurs, réaction aux changements de disque et arrêt du worker.
- `audio_video_manager/ui/identify_worker.py` — worker d’énumération/lecture TOC.
- `tests/test_drives.py` et `tests/test_ui_shell.py` — scénarios synthétiques de détection, retrait, mode hors ligne, confirmation multi-lecteur et callback natif.
- `docs/architecture/reports/AVM-28B-VALIDATION-PARCOURS-CD.md` — présent rapport.

## Vérifications

- Tests ciblés UI/CD/DVD : `test_ui_shell.py` **34**, `test_drives.py` **4**, `test_ui_w3_prefill.py` **8**, `test_ux_06o.py` **10**, `test_library_qml_08b.py` **5**, `test_musicbrainz_identify.py` **19**, `test_edition_ranker.py` **8**, `test_cd_ripper.py` **7**, `test_rip_job.py` **1**, `test_archive_pipeline.py` **10**; tous réussis, exécutés par fichier pour Qt.
- CI Windows : `.venv/Scripts/python.exe scripts/run_tests_ci.py --report .ci/avm28b-ci-results.json --junit-dir .ci/junit/avm28b` — **379 tests, 13 groupes, 0 échec, 0 erreur, 0 skip, 0 crash natif; GO**.
- Diagnostics éditeur : aucune erreur sur les fichiers Python modifiés; `git diff --check` : réussi.
- Ni lecture TOC physique, ni identification réseau réelle, ni commande de rip freaccmd sur disque n’ont été exécutées. Les tests injectent les résultats optiques.

## Prochaine étape interactive

1. Retirer tout CD du lecteur et relancer **`Lancer-AudioVideoManager.bat`** depuis le dépôt local.
2. Observer uniquement si la fenêtre reste ouverte, si elle affiche un état d’absence de CD/lecteur, et si le code `-1073740771` réapparaît. Ne pas insérer le CD à cette étape.
3. Me transmettre le message affiché et, si l’application se ferme, les dernières lignes du journal/cadre de console. La détection de CD et tout rip restent suspendus jusqu’à cette observation.

Après démarrage stable, la validation physique suivra la procédure AVM-24 : vérifier la destination permanente, observer l’insertion/détection, confirmer explicitement le bon lecteur et les métadonnées, puis demander votre accord avant le lancement du rip. La publication ne sera déclarée réussie qu’après W5, présence du dossier et album visible dans Widgets. Aucune écoute ni export d’appareil n’est entrepris.

**Arrêt AVM-28B en attente du résultat de relance. Aucun commit n’a été créé.**