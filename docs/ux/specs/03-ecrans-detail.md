# 03 — Spécification détaillée des écrans

Format par écran : **ID** · composants · données · actions · validations · états · messages FR.

---

## S-ARCH — Section Archiver (conteneur)

| | |
|--|--|
| Composants | `StepHeader` (stepper) + `QStackedWidget` pages W1…W5 |
| État session | `WizardSession` : disc_read, lookup, decision, sheet, step_index, approved_snapshot_hash |

---

## W1 — Disque (`wizard.disc`)

**Composants :** `QComboBox` lecteur · `QLabel` résumé · `QPushButton` Relire / Continuer · `QToolButton` Détails techniques · éventuel `QProgressIndicator`.

**Visible :** nom lecteur grand public ; « N pistes · durée ≈ Hh Mm » ; pastille état.

**Actions :** Relire → TOC ; Continuer → W2 si OK.

**Validations :** au moins 1 piste audio ; Disc ID non vide si libdiscid OK.

| État | UI |
|------|-----|
| empty | Illustration/texte insert CD ; Continuer disabled |
| loading | Spinner ; boutons disabled |
| ready | Continuer enabled |
| error | Bannière rouge + Relire |

**Messages :**
- empty : « Insérez un CD audio, puis cliquez sur Relire le disque. »
- error no disc : « Aucun CD lisible dans ce lecteur. »
- error dll : « Composant de lecture de disque indisponible. Vérifiez l’installation (libdiscid). »

---

## W2 — Identification (`wizard.identify`)

**Composants :** `CoverThumb` · labels meta · `WarningList` · `QToolButton` « Autres éditions » → `QListWidget` · boutons Continuer / Manuel.

**Visible :** pochette (A7), titre, artiste, année, pays, label, catalogue ; badge « Proposition automatique » si smart select.

**Actions :** choisir alternative ; Continuer ; saisie manuelle (passe W3 avec champs vides/partiels).

**Validations :** aucune approbation ici.

| État | UI |
|------|-----|
| loading | Skeleton cover + « Recherche des informations… » |
| multi_auto | Édition CA (ou pref) préremplie + warnings |
| multi_manual | Liste obligatoire si non équivalentes |
| zero | « Aucune correspondance en ligne » → manuel |
| error_net | « Réseau indisponible » + Réessayer + Manuel |

**Messages :**
- pref pays : « Le pays préféré (ex. Canada) sert seulement à trancher entre éditions semblables. »
- toc partial : « Une durée de piste diffère légèrement de la base MusicBrainz. L’écart est conservé pour information. »

---

## W3 — Approbation (`wizard.approve`)

**Composants :** formulaire (`QLineEdit`/`QSpinBox`/`QCheckBox` compilation) · `QTableWidget` pistes · `PathPreviewList` · `ErrorList` / `WarningList` · Brouillon / Approuver / Retour · badge approval.

**Visible en premier :** champs bloquants manquants ; puis pistes ; puis chemins.

**Actions :**
- Valider en continu (debounce) via `apply_validation` / équivalent
- Enregistrer brouillon → `DiscMetadataRepository.save`
- Approuver → `approve_sheet` puis save
- Édition champ si Approved → dirty → Pending (A3)

**Validations :** règles existantes (placeholders, TOC, cover, year, compilation…).

| État | UI |
|------|-----|
| incomplete | Approuver disabled ; ErrorList |
| ready_to_approve | Approuver enabled |
| approved | Badge vert ; « Continuer » vers W4 |
| dirty_after_approve | Badge ambre ; Approuver à nouveau |

**Messages :**
- compilation : « Indiquez si l’album est une compilation (artistes variés). »
- approve ok : « Fiche approuvée. Vous pouvez lancer l’extraction. »
- dirty : « Vous avez modifié la fiche. Approuvez à nouveau avant d’extraire. »

---

## W4 — Extraction / publication (`wizard.extract`)

**Composants :** récap édition · `QButtonGroup` doublons · case/dialog publish · `QProgressBar` + liste sous-étapes · Lancer / Annuler.

**Libellés doublons (FR) :**
- Renommer : « Créer un nouveau dossier (import-2, …) »
- Ignorer : « Ne pas publier si l’album existe déjà »
- Remplacer : « Remplacer — l’ancien dossier ira dans une corbeille locale de l’application »

**Actions :** Lancer → `ArchiveWorker` / `run_archive_job` ; Annuler → cancel_event.

| État | UI |
|------|-----|
| idle_ready | Lancer enabled si Approved + confirm publish |
| running | Nav lock ; sous-étape active |
| mismatch | Stop avant rip ; message disc |
| cancelling | « Annulation… » |

**Sous-étapes nommées :** Vérification du disque → Extraction audio → Contrôle des fichiers → Mise en tags et pochette → Organisation → Publication.

**Messages :**
- mismatch : « Le CD dans le lecteur n’est plus le même que celui de la fiche approuvée. Réinsérez le bon disque ou recommencez l’identification. »
- confirm : « Confirmez la publication dans votre bibliothèque. Sans confirmation, les fichiers restent en zone temporaire. »

---

## W5 — Terminé (`wizard.done`)

**Composants :** icône résultat · résumé · warnings · `QPushButton` Ouvrir dossier / Historique / Autre CD.

| État | UI |
|------|-----|
| completed | Vert + chemin |
| completed_warnings | Ambre + liste |
| failed / cancelled | Rouge + cause |

**Messages :**
- success : « Album ajouté à votre bibliothèque. Les fichiers FLAC s’ouvrent dans n’importe quel lecteur compatible. »
- open folder fail : « Impossible d’ouvrir le dossier. Vérifiez qu’il existe encore. »

---

## S-LIB — Ma bibliothèque

**Composants :** chemin root (lecture) · recherche · liste/grille albums · panneau détail · Ouvrir dossier · Rafraîchir.

**Données (A6) :** requêtes `releases` ; pour chaque ligne, `Path.exists()` sur `path` ; si absent → badge « Dossier manquant ».  
Jobs `AwaitingPublishConfirmation` → section « En attente de publication » (inbox).

| État | UI |
|------|-----|
| empty | « Aucun album importé pour l’instant. Utilisez Archiver un disque. » |
| loading | Spinner liste |
| ready | Liste |
| path_missing | Badge sur item |

**Pas de lecteur audio.**

---

## S-HIST — Historique

**Composants :** `QTableView` jobs · panneau détail (warnings_json, library_path, workdir, state) · Reprendre / Abandonner / Ouvrir…

| Actions | Règles |
|---------|--------|
| Ouvrir album C | Si `library_path` existe |
| Ouvrir workdir | Si dossier A existe |
| Abandonner | Marque job ; **ne supprime pas** C |
| Reprendre | Seulement états prévus architecture ; sinon message « Reprise non disponible pour cet état » |

| empty | « Aucune opération enregistrée. » |

---

## S-SET — Paramètres

**Groupes :** Bibliothèque · Identification · Extraction · ▸ Avancé.

| Avancé contient | |
|-----------------|--|
| Test technique zone A | Bouton + confirm forte (A4) |
| jobs_dir, log_dir | Chemins |
| Probes fre:ac | Texte replié |
| Schéma SQLite | Info |
| Auto-approve | Checkbox disabled + « Non disponible » |
| DVD | « Prévu ultérieurement » (A5) une ligne max |

**Messages save :** « Paramètres enregistrés. »
