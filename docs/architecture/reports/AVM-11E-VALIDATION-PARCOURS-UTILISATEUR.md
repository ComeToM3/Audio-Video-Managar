# AVM-11E — Validation du parcours utilisateur DVD-Video

Date : 2026-11-06 · AudioVideoManager 0.5.0 · Windows 11 · PySide6.

**Verdict : VALIDÉ pour les parcours MKV maître et MKA audio seul depuis l’interface Windows, avec le DVD-Video synthétique autorisé AVM-11C. PARTIEL pour la configuration initiale des chemins depuis Paramètres; aucune validation sur disque optique physique n’est revendiquée.** Les deux extractions ont été lancées depuis le dialogue DVD, leurs sorties ont été validées indépendamment par ffprobe et le dossier de résultat a été ouvert par l’action de l’interface. Les erreurs de source, de backend, de destination existante et l’annulation ont également été vérifiées, avec les réserves détaillées ci-dessous.

## 1. Conditions et périmètre

- Application lancée sous Windows avec le backend Qt natif (`platformName=windows`). Le rail conserve les quatre sections existantes et expose le bouton **DVD**.
- Source utilisée : `%LOCALAPPDATA%\Temp\AVM-11C\reference-dvd`, une structure `VIDEO_TS` synthétique générée localement, pas un disque gravé. Elle contient deux titres; le titre 2 (10 s) est suggéré. Son inspection UI affiche une piste AC-3 et trois chapitres.
- FFmpeg/ffprobe 9.0.2 et les DLL libdvdnav/libdvdread CSS-off proviennent de l’environnement temporaire AVM-11B2. Aucun déchiffrement ou contournement CSS n’a été utilisé.
- Pour les extractions réussies, les chemins outils et les dossiers de travail ont été fournis à la configuration en mémoire; aucun `save_config` vers la configuration personnelle n’a été appelé. Le lecteur `D:` n’a pas été consulté.

## 2. Parcours réussis depuis l’interface

### MKV maître

Le dialogue a inspecté les titres, présenté la suggestion du titre 2 et les détails du titre sélectionné, puis a demandé l’attestation de droits et la confirmation explicite avant l’extraction. AVM a affiché le résultat comme validé.

- Sortie : `%LOCALAPPDATA%\Temp\AVM-11E\mkv-ui-debug\library\ui-master.mkv`.
- Taille : 4 055 998 octets; SHA-256 : `c500bac4def1c20058a40009d35f77506dacf605a6223de93ef36b6ef0ea7215`.
- ffprobe, code retour 0 : conteneur Matroska, durée 10,011 s, vidéo MPEG-2, audio AC-3 stéréo 48 kHz, trois chapitres.

### MKA audio seul

Le mode audio seul a permis de cocher la piste AC-3, d’indiquer une destination `.mka`, puis de confirmer les droits et l’opération. Le dialogue a validé le résultat et activé l’ouverture du dossier.

- Sortie : `%LOCALAPPDATA%\Temp\AVM-11E\mka-ui-actual\library\ui-audio.mka`.
- Taille : 240 886 octets; SHA-256 : `e3a1321fe7d2e3a954aa62e5454009c9350cf55240d7d43e8e0a66eb57bdab0a`.
- ffprobe, code retour 0 : conteneur Matroska, durée 9,920 s, un flux audio AC-3 stéréo 48 kHz, aucun flux vidéo, trois chapitres.

### Ouverture du dossier résultat

Une seconde sortie MKV a été produite depuis l’UI dans `%LOCALAPPDATA%\Temp\AVM-11E\mkv-open-ui\library\open-result.mkv`. Après le clic **Ouvrir le dossier**, l’interface Shell Windows a rapporté cette même destination comme emplacement de la fenêtre Explorer. Le fichier passe aussi ffprobe : 4 055 998 octets, 10,011 s, vidéo MPEG-2, audio AC-3 et trois chapitres.

## 3. Erreurs, annulation et garde-fous

| Parcours | Résultat observé |
|---|---|
| Source invalide | Le dialogue affiche l’absence de `VIDEO_TS/VIDEO_TS.IFO`; aucune extraction n’est publiée. Capture : [source invalide](AVM-11E-evidence-203d6ec2/error-invalid-source.png). |
| Backend manquant | Le dialogue indique `ffprobe introuvable; aucun backend DVD-Video disponible.` |
| Destination existante | Le fichier sentinelle `preserve-me` (11 octets) reste inchangé; aucun résultat ne le remplace. La capture montre la destination existante : [destination existante](AVM-11E-evidence-203d6ec2/error-existing-destination.png). Le message final du worker n’a pas été capturé après stabilisation; le refus d’écrasement est également couvert par les tests du service. |
| Annulation | Annulation cliquée pendant « Copie de flux »; le dialogue affiche `Extraction DVD annulée par l’utilisateur`, le worker s’arrête, aucun MKV final n’existe et aucun staging ne reste. |
| Aucune piste audio cochée | Le test Qt confirme que **Démarrer** reste désactivé. Ce cas est validé par le test automatisé, pas par une session native distincte. |

## 4. Paramètres et portée de la preuve

Les parcours d’extraction ci-dessus ont utilisé des chemins de backend temporaires injectés en mémoire. Un essai complémentaire de saisie dans Paramètres a redirigé la sauvegarde vers `%LOCALAPPDATA%\Temp\AVM-11E\settings-e2e\config.json`, jamais vers le fichier personnel. L’automatisation a ajouté les caractères aux valeurs déjà présentes au lieu de remplacer le texte; le JSON Temp contient donc des chemins doublés et aucun média n’a été extrait dans cet essai. Cette tentative ne constitue ni une validation de la configuration utilisateur persistante ni un défaut produit démontré.

Les captures de l’interface et des étapes MKA sont conservées ici :

- [Fenêtre principale](AVM-11E-evidence-203d6ec2/01-main-window.png)
- [Paramètres DVD](AVM-11E-evidence-203d6ec2/02-settings-dvd-tools.png)
- [Sélection MKA](AVM-11E-evidence/AVM-11E-mka-selection.png)
- [Confirmation MKA](AVM-11E-evidence/AVM-11E-mka-confirm.png)
- [Résultat MKA](AVM-11E-evidence/AVM-11E-mka-result.png)

## 5. Vérifications et limites

- ffprobe indépendant a retourné le code 0 pour les MKV et MKA issus de l’interface. Les propriétés observées concordent avec la structure synthétique AVM-11C.
- La CI complète la plus récente, exécutée pour AVM-11D, compte 14 groupes, 317 tests (242 domaine et 75 UI), 0 échec, 0 erreur et 0 skip : `.ci/avm11d-final-ci-results.json`. AVM-11E n’a modifié que ce rapport; la CI n’a pas été relancée.
- La vérification ne porte pas sur un disque optique gravé ni sur le lecteur `D:`. Elle ne démontre ni la compatibilité avec tous les DVD-Video ni l’application d’un droit de reproduction. L’attestation affichée par AVM est une déclaration utilisateur.
- La configuration persistante des chemins outils doit faire l’objet d’une vérification manuelle/automatisée distincte avant de considérer l’installation initiale comme validée de bout en bout.

**Conclusion :** un utilisateur peut lancer depuis l’interface Windows les deux opérations d’archivage sur le DVD-Video synthétique autorisé, suivre leur résultat, annuler une extraction et ouvrir le dossier généré. La preuve est concluante pour le parcours opérationnel une fois le backend configuré; elle reste partielle pour la saisie/persistance de cette configuration et ne couvre aucun support optique physique.