# AVM-29 — Limitation de vitesse du lecteur CD

**Verdict : NON DÉMONTRÉ.** Une demande de vitesse est prévue par Windows/MMC, mais l’acceptation d’une limite 8× par le lecteur `ATAPI iHAS324 C` de `D:` n’a pas été vérifiée. Aucune commande matérielle n’a été envoyée.

## Capacités observées

- `freaccmd.exe` installé : fre:ac **1.1.7**, fichier **1.1.7.5891**, x86-64.
- L’aide CLI réelle ne propose aucun argument de vitesse. Elle propose lecteur, pistes, délai d’attente, éjection et `--superfast`; le code fre:ac rattache `--superfast` au traitement/conversion, pas à une consigne de vitesse CD.
- `freaccmd --list-configs` retourne seulement « Configuration par défaut ». `%APPDATA%\freac\freac.xml` ne contient pas de clé vitesse; le réglage de lecteur observé est `ActiveDrive=0`.
- Les ressources fre:ac incluent le libellé GUI « Set drive speed limit » et `CDRip.dll` contient des messages `Current read speed`/`Max read speed`; le GUI/composant possède donc des indices de contrôle et de télémétrie. Le call site n’est pas présent dans les sources C/C++ livrées et l’interface n’a pas été ouverte; présence, choix 8× et acceptation par cette unité restent à confirmer. Ce contrôle n’existe pas comme option de `freaccmd` et aucune vitesse n’est persistée dans `freac.xml`.
- Windows identifie le périphérique chargé comme `ATAPI iHAS324 C`, `D:`, état `OK`. Les spécifications publiques du modèle iHAS324 indiquent une lecture CD maximale pouvant atteindre **48×**. C’est une capacité maximale, pas une preuve d’acceptation d’une limite 8×; la révision/firmware exacte n’est pas exposée par le contrôle effectué.

## Contrôle Windows documenté

Windows expose `IOCTL_CDROM_SET_SPEED` avec une structure contenant une vitesse de lecture en ko/s et deux requêtes MMC possibles : `SET CD SPEED` et `SET STREAMING`. Microsoft indique explicitement que l’IOCTL peut échouer si le lecteur ne supporte pas la demande. Le standard décrit donc un mécanisme; il ne prouve ni le support de l’iHAS324 C, ni que freaccmd conserve ce réglage pendant le rip. La réponse matérielle et la restauration n’ont pas été testées.

## Options

1. **fre:ac GUI — voie à vérifier en premier.** Le contrôle est suggéré par les ressources GUI/DLL; s’il apparaît dans le menu du lecteur, il pourrait limiter la vitesse pour ce composant. Aucun réglage 8× ni acceptation sur `D:` n’a été observé. L’héritage par `freaccmd` n’est pas établi.
2. **Windows `IOCTL_CDROM_SET_SPEED` / MMC — possible en principe, mais non démontré.** L’API accepte une vitesse de lecture en ko/s et le pilote peut refuser la requête. Pas d’outil déjà installé ou de vérification de restauration sûre identifiés; aucune commande n’a été envoyée.
3. **Utilitaire tiers de contrôle optique.** Des outils existent, mais aucun n’est installé ni validé ici; leur installation est hors contraintes et leur réussite sur cette révision resterait à vérifier.

À 8×, la limite concerne le débit de lecture, pas l’encodeur FLAC. La durée peut augmenter sensiblement par rapport au maximum 48× annoncé; le profil réel dépend du disque et de la stratégie CAV/CLV. Le bruit de rotation pourrait baisser si le lecteur honore la consigne, mais seek/vibrations subsisteraient. Une vitesse plus faible ne garantit ni meilleure fidélité ni fiabilité : conserver les vérifications FLAC et de contenu existantes.

## État et limite

Pas de modification de fre:ac, configuration, lecteur ou AVM; les processus d’aide/inspection CLI uniquement ont été lancés. Aucun rip, éjection, changement de vitesse, logiciel installé, test automatisé ou commit. Pour vérifier le chemin GUI sans changer la vitesse, l’utilisateur peut ouvrir le menu du lecteur `D:` dans fre:ac et rapporter si « Définir la vitesse limite du lecteur » et 8× sont proposés, sans sélectionner de vitesse. Pour prouver l’acceptation matérielle, un test `IOCTL_CDROM_SET_SPEED` est nécessaire, mais aucune commande sûre de retour par défaut n’a été établie; il n’est pas recommandé sans procédure de restauration confirmée et autorisation explicite.

## Références

- [fre:ac User Guide](https://freac.org/manual/index_en.html)
- [Microsoft `IOCTL_CDROM_SET_SPEED`](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntddcdrm/ni-ntddcdrm-ioctl_cdrom_set_speed) et [CD-ROM Set Speed](https://learn.microsoft.com/en-us/windows-hardware/drivers/storage/cd-rom-set-speed)
- [Lite-On iHAS324 — CDRInfo](https://www.cdrinfo.com/d7/content/lite-ihas324) (revue du modèle; ne démontre pas la commande 8× sur l’unité `iHAS324 C`)

**Verdict final : NON DÉMONTRÉ pour l’iHAS324 C; support standard Windows/MMC disponible, support de cette unité et de freaccmd non vérifié.**