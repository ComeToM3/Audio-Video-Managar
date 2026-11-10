# AVM-18 — Revue transversale de maturité production CD

Date : 2026-11-07 · Windows local · Python 3.12 · branche `main` · commit de départ `b4c0007` (arbre de travail non commité : modifications DVD/bibliothèque en cours sur `catalog.py`, `database.py`, `schema.py`, `main_window.py`, `archive_wizard.py`, etc. — non touchées par cette revue).

Mandat : diagnostic uniquement, aucune modification de code, migration, test ni refonte. Revue du parcours CD→FLAC réel (détection → identification → confirmation → extraction → vérification → archivage → bibliothèque) pour déterminer ce qui bloque une qualité de production pour un usage personnel (numériser des CD, écouter sur Android/iPhone).

## Méthode

Lecture directe de `.github/copilot-instructions.md`, de l'arborescence et du rapport `AVM-15` existant, puis quatre explorations ciblées en lecture seule couvrant : (1) extraction/orchestration CD, (2) bibliothèque/SQLite/transfert, (3) métadonnées/MusicBrainz/TOC, (4) UI/UX et couverture des tests. Chaque constat ci-dessous est appuyé par une citation fichier:ligne vérifiée par l'agent correspondant.

## Architecture observée (parcours CD)

`extraction/drives.py` (détection lecteurs) → `metadata/toc_reader.py` + `musicbrainz_client.py`/`enrichment.py` (identification) → `ui/wizard/archive_wizard.py` + `ui/metadata_dialog.py` (confirmation) → `extraction/cd_ripper.py` via `orchestration/rip_job.py`/`archive_job.py` (extraction fre:ac + verrouillage) → `verification`/intégrité FLAC → `library/publish.py`, `tags.py`, `transfer.py` (archivage) → `storage/database.py`/`catalog.py` (bibliothèque SQLite) → consultation Widgets/QML.

Le backend d'extraction est **fre:ac/freaccmd** exclusivement (pas de cdparanoia/FFmpeg pour l'audio CD). Le verrouillage anti-concurrence (`rip_lock.py`) et la réconciliation après interruption (`reconciliation.py`) existent et sont partiellement testés.

## Constats déjà satisfaisants (à préserver intacts)

- Intégrité FLAC contrôlée après rip (`rip_job.py:164-166`, `cd_ripper.py:281-310`) : un `returncode == 0` sans FLAC ou sans contenu valide est refusé — pas d'assimilation code-retour-nul = succès.
- Verrou de récupération correctement exclusif (`rip_lock.py:240-268`, `O_CREAT|O_EXCL`).
- Migrations SQLite majoritairement non destructives (`CREATE IF NOT EXISTS`, `ALTER TABLE ADD COLUMN`), pas d'écrasement des données existantes constaté.
- Validation des métadonnées utilisateur globalement stricte : TOC obligatoire/cohérente, durées comparées, pistes confirmées (`metadata/validation.py:46-190`).
- Sanitisation Windows des noms de fichiers (caractères interdits, noms réservés) dans `metadata/path_preview.py`.
- Wizard CD : étapes explicites et traçables (Disque → Identification → Vérifier/approuver → Extraire/publier → Terminé), extraction et identification du wizard workerisées (`identify_worker.py`, `rip_worker.py`), navigation verrouillée pendant une opération.
- Publication conditionnée à une confirmation explicite de l'utilisateur à chaque étape sensible (collision, édition, publication finale).

Ces mécanismes ne doivent pas être modifiés sans nécessité démontrée.

## Constats classés par sévérité

### P0 — Bloquants pour un usage quotidien fiable

1. **Identification CD synchrone dans le thread UI (second parcours, hors worker).**
   `audio_video_manager/ui/metadata_dialog.py:505-508` appelle directement `identify_disc(...)` (réseau MusicBrainz/Discogs + lecture disque) sans passer par un worker Qt, contrairement au wizard qui dispose d'un `IdentifyWorker` (`identify_worker.py:33-39`).
   **Impact :** ce second chemin d'identification peut geler l'interface pendant un appel réseau lent ou un timeout MusicBrainz non configuré (voir P1 ci-dessous). Un usage quotidien sur un réseau instable rendra l'application visiblement non responsive.
   **Correction minimale recommandée :** déporter l'appel `identify_disc(...)` de `metadata_dialog.py` dans un worker Qt existant (réutiliser `IdentifyWorker`), sans changer le contenu métier.

2. **Écrasement silencieux possible lors de la publication en mode copie (TOCTOU).**
   `library/publish.py:156-160` vérifie `dest.exists()` puis `library/transfer.py:79-92` exécute `shutil.copy2(src, dest)` sans création exclusive atomique.
   **Impact :** fenêtre de concurrence où un fichier peut être silencieusement écrasé — violation directe de la priorité « intégrité des données » du dépôt, en particulier si deux archivages visent la même destination (ex. collision après resanitisation de titres, voir P1-9 ci-dessous).
   **Correction minimale recommandée :** ouvrir la destination en création exclusive (`os.O_CREAT|O_EXCL`) avant copie, à l'image du verrou de récupération déjà correct dans `rip_lock.py:240-268`.

### P1 — Importants (fiabilité, résilience, UX)

3. **Verrouillage de rip non réellement exclusif.** `orchestration/rip_lock.py:137-151` écrit le verrou avec `path.write_text(...)` sans `O_EXCL` ni verrou OS : deux processus peuvent chacun se croire propriétaires. Contraste avec le verrou de récupération, correctement exclusif.
4. **Incohérence fichier/DB possible après interruption.** `rip_job.py:141-187` : le verrou est levé en `finally` avant la mise à jour DB ; un crash entre les deux laisse la base en état `Ripping` malgré des FLAC déjà présents. `archive_job.py:635-666` : copie + tagging sans fichier temporaire ni transaction — une interruption peut laisser un FLAC partiel/corrompu dans `tagged/`.
5. **Pas de reprise physique du rip piste par piste.** `reconciliation.py:548-588` : la reprise ne relance que depuis des FLAC déjà extraits ; une extraction interrompue en cours de piste doit repartir de zéro pour les pistes manquantes (comportement documenté dans le code lui-même, pas une découverte imprévue, mais une limite réelle pour la fiabilité quotidienne).
6. **Dépendance externe obligatoire non encapsulée / sans fallback.** `extraction/cd.py:65-96` et `cd_ripper.py:158-173` : tout le pipeline dépend de `freaccmd.exe` trouvable sur le système ; aucun mécanisme de secours.
7. **Détection des lecteurs fragile.** `drives.py:43-84` : parsing par regex de la sortie texte de fre:ac ; un `returncode` non nul du probe n'empêche pas de retourner une liste vide sans distinguer « pas de lecteur » de « échec de détection ».
8. **Blocage potentiel du thread appelant pendant le rip bas niveau.** `cd_ripper.py:174-255` : boucle synchrone (`readline`, `wait`, `sleep`) ; aucun `QThread` propre à ce module — la protection actuelle dépend entièrement de l'appelant (le wizard protège via `rip_worker.py`, mais `metadata_dialog.py` ne le fait pas pour l'identification, cf. P0-1).
9. **Collision de noms de pistes après sanitisation, non résolue individuellement.** `archive_job.py:648-655` et `library/publish.py:47-76` : la collision est gérée au niveau album (`skip`/`rename`/`replace`), mais deux titres de pistes distincts peuvent produire le même nom sanitisé ; le second `copy2()` écrase le premier silencieusement.
10. **Tags FLAC obsolètes conservés.** `library/tags.py:18-93` : les champs absents de la fiche ne sont pas effacés des tags existants, contrairement à l'intention documentée (« reflètent uniquement la fiche approuvée »).
11. **Publication `replace` non atomique**, reconnu explicitement dans le code (`publish.py:92-94` « atomicité non garantie V1 ») ; rollback incomplet si le dossier cible existe déjà après un échec partiel.
12. **MusicBrainz sans timeout configurable ni gestion HTTP 429/Retry-After.** `metadata/musicbrainz_client.py:190-222, 64-104` : dépend du comportement interne de `musicbrainzngs` ; le rate-limit est un état mono-processus sans réaction aux réponses 429.
13. **Pas de fallback hors-ligne réel.** `apply_lookup.py:226-287` : une erreur réseau MusicBrainz lève une exception ; le seul recours est la saisie manuelle, pas une récupération locale.
14. **Disc ID entièrement dépendant de `libdiscid`/DLL native**, sans calcul alternatif en cas d'absence (`toc_reader.py:76-91`, `libdiscid_loader.py:76-91`).
15. **Troncature silencieuse d'incohérence TOC.** `toc_reader.py:94-117` : une différence entre le nombre de pistes et `first/last_track_num` est tronquée sans erreur.
16. **Identifiants MusicBrainz saisis non vérifiés** par `FieldTrust` (`validation.py:151-157`), alors que les autres champs le sont.
17. **Annulation UI seulement coopérative et non garantie pendant les opérations disque longues** (copie, tagging) : `archive_wizard.py:1543-1547`, `rip_worker.py:45-46`, `archive_job.py:635-650` — le point d'annulation est testé entre pistes, pas pendant `copy2()`/tagging.
18. **Messages d'erreur peu actionnables** : affichage brut des erreurs techniques dans `metadata_dialog.py:484-486` et `archive_wizard.py:1629-1633`, malgré l'existence d'une fonction d'humanisation (`progress_labels.py`) peu systématiquement branchée.
19. **Deux parcours d'identification parallèles** (wizard workerisé vs dialogue synchrone) risquant de diverger en comportement et en affichage des candidats.

### P2 — Améliorations facultatives / dette technique démontrée

20. Duplication de la logique verrou+rip entre `rip_job.py:141-145` et `archive_job.py:386-395`.
21. Fonctions excessives : `run_archive_job()` (`archive_job.py:181-834`), `publish_album()` (`publish.py:80-238`), `assess_duplicates()` (`duplicates.py:100-318`), `validate_disc_metadata()` (`validation.py:41-199`) — cumulent plusieurs responsabilités, sans constituer en soi un bug.
22. Doublons détectés par logique applicative Python, sans contrainte unique SQLite sur `releases.disc_id`/`mbid` (`schema.py:14-23`) — fiabilise la détection mais ne garantit pas l'intégrité en cas de concurrence.
23. `cover.jpg` peut contenir des octets PNG sans conversion (`library/cover.py:146-154`).
24. Couplage `library/cover.py` → `ui/cover_cache.py` (bibliothèque dépendant de l'UI) ; chemins/sanitisation répartis entre `library/paths.py` et `metadata/path_preview.py`.
25. Deux implémentations séparées de rate-limiting (MusicBrainz, Discogs) ; `metadata/enrichment.py` volumineux (≥654 lignes) mélangeant transport HTTP, parsing et rendu.
26. Couplage UI → métier élevé : `metadata_dialog.py`, `identify_worker.py`, `rip_worker.py` importent et orchestrent directement la logique métier (acceptable à ce stade, mais limite la testabilité isolée).

## Couverture réelle des tests (vs comportement physique)

- **Pipeline CD/orchestration** (`test_cd_ripper.py`, `test_rip_job.py`, `test_archive_pipeline.py`, `test_archive_recovery_staging.py`, `test_reconciliation_10b/10c.py`, `test_drives.py`, `test_rip_check.py`) : couvrent la logique orchestrée avec `subprocess.Popen` et `FreacCdRipper.rip` **mockés**. Aucun test n'exécute un vrai `freaccmd`, ne lit un CD physique, ne vérifie le parsing réel de `--list-drives` sur une machine donnée, ni l'écriture concurrente du verrou de rip, ni l'annulation pendant tagging/copie/publication, ni une collision de noms après sanitisation.
- **Bibliothèque/SQLite** (`test_database.py`, `test_cover_cache.py`, `test_duplicates_06k.py`, `test_disc_metadata.py`, `test_hardlink_security_06gp1.py`, `test_flac_integrity.py`, `test_integrity_10d.py`) : migrations testées surtout pour idempotence et présence de colonnes, pas pour un échec en cours de migration ni une concurrence. Le contrôle d'espace disque est testé isolément mais son caractère bloquant réel avant publication n'est pas vérifié. Le cache de pochette est testé avec un hit artificiel, pas le vrai chemin réseau→cache.
- **Métadonnées/MusicBrainz** (`test_musicbrainz_identify.py`, `test_musicbrainz_identity.py`, `test_metadata_enrichment.py`, `test_edition_ranker.py`, `test_approval_fingerprint.py`, `test_metadata_dialog_sources.py`, `test_disc_metadata.py`) : entièrement mockés/injectés, aucun appel réseau réel. Non couverts : timeout réel, HTTP 429, absence réelle d'Internet, lecture TOC avec un vrai binding `discid`, DLL absente en conditions réelles.
- **UI** (`test_progress_labels.py`, `test_qthread_07b.py`, `test_qt_teardown_10c1/10c2.py`, `test_library_qml_08b.py`, `test_history_06n.py`, `test_humanisation_06i.py`) : solide sur le cycle de vie Qt (threads, teardown, bridges QML/Widgets) en environnement headless simulé. Aucun test n'exerce le parcours physique complet détection→bibliothèque ; l'accessibilité (focus, ordre de tabulation, `accessibleName`) n'est pas validée automatiquement ; la CI verte ne constitue donc pas une preuve d'expérience utilisateur réelle sur matériel physique.

**Conclusion couverture :** la CI protège la logique métier et le cycle de vie Qt, mais ne démontre ni la fiabilité du binaire fre:ac réel, ni le comportement réseau réel, ni l'expérience utilisateur physique bout-en-bout. Une CI verte ne doit pas être interprétée comme une validation de production.

## Risques pour l'usage ciblé (numériser et écouter sur Android/iPhone)

- Le format de sortie (FLAC) est correct pour Android et pour iPhone via des lecteurs tiers, mais l'app native iOS ne lit pas FLAC nativement — hors du périmètre de cette revue (export/transfert), à clarifier séparément si pertinent.
- Les risques les plus concrets pour un usage quotidien solo sont : blocage UI pendant l'identification (P0-1), écrasement silencieux en cas de republication accidentelle (P0-2), et incohérences fichier/DB après interruption d'un rip (P1-4/5) — ce sont les scénarios les plus probables en usage réel (interruption réseau, fermeture accidentelle, double archivage du même disque).
- Les dépendances externes obligatoires (fre:ac, libdiscid/DLL) doivent être présentes et fonctionnelles sur la machine Windows cible ; aucun diagnostic de disponibilité proactif n'a été vérifié dans ce périmètre au-delà de la détection de lecteur.

## Plan minimal de stabilisation (ordre recommandé, sans élargir le mandat)

1. Corriger P0-1 : déporter l'identification de `metadata_dialog.py` dans un worker existant (réutilisation directe d'`IdentifyWorker`).
2. Corriger P0-2 : rendre la copie de publication exclusive (`O_CREAT|O_EXCL`) pour éliminer la fenêtre TOCTOU, en conservant le comportement `skip`/`rename`/`replace` actuel pour les cas prévus.
3. Traiter P1-9 (collision de noms de pistes) et P1-10 (tags obsolètes conservés) : ce sont des pertes silencieuses de fidélité aux données, prioritaires avant toute nouvelle fonctionnalité.
4. Ajouter un timeout explicite et une gestion 429/Retry-After pour MusicBrainz (P1-12) afin d'éviter un blocage perçu comme un gel applicatif.
5. Documenter/exposer à l'utilisateur les limites P1-4/5 (pas de reprise piste par piste, incohérence fichier/DB possible après crash) plutôt que de les corriger immédiatement si le risque réel est jugé acceptable pour un usage personnel — décision à confirmer avec l'utilisateur avant tout développement supplémentaire.
6. Ne pas entreprendre les points P2 sans bénéfice mesurable démontré (pas de refactorisation préventive de `run_archive_job()`/`publish_album()`).

## Limites de cette revue

- Analyse statique uniquement ; aucune extraction physique de CD, aucun appel réseau réel, aucune modification de fichier n'a été effectuée.
- N'a pas examiné en détail `extraction/dvd*.py`, le flux YouTube, ni les modifications en cours non commitées sur `catalog.py`/`database.py`/`schema.py` (hors périmètre CD stabilisé demandé).
- Les sévérités P0/P1/P2 reflètent l'impact sur la fiabilité et l'intégrité des données pour un usage personnel quotidien, pas une notation de sécurité externe (l'application n'est pas exposée en réseau).

## Verdict

**STABILISATION REQUISE.**

Le parcours CD→FLAC est fonctionnellement complet et globalement bien structuré (verrouillage, réconciliation, intégrité FLAC, wizard workerisé), mais deux défauts bloquants (P0-1, P0-2) et plusieurs défauts importants de cohérence fichier/DB et de résilience réseau (P1) doivent être traités avant de considérer l'application prête pour un usage de production quotidien fiable. Aucun défaut ne remet en cause l'architecture globale ; aucune refonte n'est justifiée.
