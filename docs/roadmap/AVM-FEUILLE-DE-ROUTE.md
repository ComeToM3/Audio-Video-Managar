# Feuille de route — AudioVideoManager

**Statut :** séquencement indicatif, sans dates calendaires. Les travaux et ambitions ci-dessous ne valent pas approbation de mandat ni promesse de livraison, sauf l'engagement d'ouverture décrit dans la [vision stratégique](../vision/AVM-VISION-STRATEGIQUE.md).

## Lecture des statuts

- **Immédiat :** travaux requis avant de revendiquer une validation réelle ou une distribution; leur exécution demeure soumise aux prérequis et autorisations indiqués.
- **Étape suivante :** piste de travail proposée après les validations immédiates; portée et ordre interne à confirmer.
- **Horizon de trois ans :** ambition à explorer; les éléments ne sont pas des capacités acquises. L'ouverture officielle constitue l'exception : c'est un engagement ferme lié au lancement commercial, non aux ventes.

## 1. Travaux immédiats

| Travail | Dépendances | Risques / limites | Critère de validation |
|---|---|---|---|
| Valider un parcours réel CD de bout en bout | Lecteur et CD autorisés; lancement en environnement isolé; chemins de données, jobs et bibliothèque vérifiés; fiche complète, corrigée et approuvée par une personne; protocole et autorisation explicite pour l'extraction | Risque d'écrire dans les données de production; fiche ambiguë ou année inconnue; confusion entre validation logicielle et rip physique; écart entre Disc ID, TOC et édition | Un rapport reproductible associe le média à la fiche approuvée et au job; trace les chemins et le code retour; contrôle les pistes FLAC, F-08a/F-08b, métadonnées, publication et cohérence SQLite; aucun résultat manquant n'est interprété comme un succès |
| Auditer les licences et droits avant distribution | Inventaire réel des composants et contenus livrés; version et modalités d'inclusion de chaque dépendance; examen juridique des licences et conditions d'API | Avis incomplets signalés par AVM-10A; fre:ac séparé sous GPL-2.0; obligations des composants, polices, outils, données et images; évolution des conditions d'API; tension entre GPL-3.0-or-later déclarée et qualification juridique encore à auditer | Matrice complète des dépendances directes/transitives et composants externes, versions, licences, mode d'inclusion, avis requis et conclusion de compatibilité commerciale; décisions ou blocages juridiques consignés avant de produire un bundle |

### État connu de la validation CD

Les résultats les plus récents consultés empêchent de déclarer ce travail terminé :

- AVM-10E-D rapporte un arrêt avant approbation humaine et avant extraction; aucun rip n'a été lancé.
- AVM-10E-VALIDATION-FINALE conclut que le parcours physique complet de 22 pistes n'est pas démontré et que les étapes suivantes dépendantes sont bloquées.
- AVM-10E-D1 valide des corrections et tests de métadonnées sous réserves, mais ne reprend pas l'extraction physique.
- AVM-10A mentionne un album Queen archivé en laboratoire; ce cas antérieur ne remplace pas la preuve du parcours CD candidat exigée par AVM-10E.

La reprise doit donc respecter l'approbation de métadonnées et l'isolation documentées dans les rapports, sans conclure que les validations existantes sont nulles ni qu'elles prouvent un parcours différent.

## 2. Étapes suivantes envisagées

Les points ci-dessous ne sont pas des décisions de livraison. Leur ordre précis, leur périmètre et leur autorisation restent à confirmer après les travaux immédiats.

| Piste | Dépendances | Risques / limites | Critère de validation avant de la déclarer prête |
|---|---|---|---|
| Distribution Windows autonome | Validation produit et tests fiables; packaging et installateur; reprise des jobs; validation UX; audit des licences; prérequis fre:ac clairement communiqués | AVM-10A conclut NO-GO V1 : absence d'installateur, reprise F-13 absente, CI et validation visuelle à consolider, couverture matérielle limitée; avis de licences incomplets | Installation et lancement sur machine Windows propre sans dépôt ni environnement de développement; parcours d'installation/mise à niveau/désinstallation testé; licences et prérequis présentés; tests et codes de sortie vérifiés; aucun accès ou écrasement non prévu |
| Extraction DVD | D-010 la reporte; étude de formats, matériel, parcours d'identification, métadonnées, intégrité, droits et conditions d'usage; audit juridique | Variabilité des supports et lecteurs; protection anticopie; complexité de vérification; risque de présenter une conception documentaire comme une extraction implémentée | Portée et droits validés, prototype isolé puis tests reproductibles sur supports autorisés; règles de conservation et de non-contournement vérifiées; résultats clairement séparés des garanties non mesurées |
| Piste YouTube / contenus en ligne | Aucun choix de périmètre trouvé dans les décisions examinées; définir le besoin, les sources et les droits; examiner les interfaces officielles et conditions en vigueur avant toute implémentation | Nouvelle surface juridique et produit; droits d'auteur, conditions de plateforme, pérennité des API, provenance et qualité; ne pas contourner DRM ou contrôles d'accès | Étude de faisabilité et d'usage licite documentée, conditions et droits vérifiés, provenance traçable et périmètre explicitement approuvé avant tout développement ou distribution |
| Inventaire de collection | Préciser s'il s'agit d'inventorier les médias physiques, la bibliothèque numérique ou les deux; s'appuyer sur le modèle de bibliothèque existant; définir import, dédoublonnage et éventuelles migrations | Ambiguïté du terme; données incomplètes; faux doublons et divergence entre supports et fichiers; coût d'une migration | Périmètre accepté, sources inventoriées sans perte, résultats rapprochables aux fichiers et métadonnées, gestion des incertitudes et doublons testée sur des données isolées |

Le terme « YouTube » n'est pas établi par les décisions produit consultées. Il figure donc ici comme **question à instruire**, non comme approbation d'une fonction d'extraction ou de téléchargement.

## 3. Ambitions à l'horizon de trois ans

L'horizon est relatif au lancement commercial et ne correspond pas à une date calendaire fixée.

| Ambition | Dépendances | Risques / limites | Critère de validation / état |
|---|---|---|---|
| Faire évoluer AVM vers le multiplateforme | Cœur métier réellement indépendant de Windows; choix des plateformes et priorités; CI et tests sur chaque cible; distribution et dépendances compatibles | Dépendances ou périphériques spécifiques Windows; coût de maintenance et écart d'expérience; l'architecture modulaire actuelle n'est pas une preuve de portabilité | Plateformes ciblées, parcours et matériel validés sur chacune; installation, tests et support documentés. **Direction envisagée, non acquise.** |
| Explorer l'usage mobile | Recherche utilisateur, cas d'usage, compatibilité matérielle et connectivité, sécurité et modèle de synchronisation éventuel | Faisabilité de la lecture/commande de lecteurs optiques sur mobile; permissions, stockage, réseau et maintenance; le périmètre n'est pas défini | Étude documentée permettant une décision ultérieure de poursuivre ou non. **Exploration seulement; aucune publication mobile promise.** |
| Publication officielle open source au plus tard trois ans après le lancement commercial | Date de lancement à établir; audit juridique et licences; cohérence du statut open source déjà déclaré; préparation des sources, notices et processus de publication | Contradiction de statut entre l'ouverture déjà déclarée par le dépôt et l'ouverture « officielle » différée; obligations de redistribution et contributions; ne pas conditionner à la performance commerciale | Publication officielle du code source sous la licence cible GPL-3.0-or-later, sous réserve d'audit juridique, au plus tard à cette échéance et **indépendamment des ventes**. C'est l'engagement ferme de la vision, non une prévision de ventes ou une date calendaire. |

## 4. Décisions existantes à préserver

- Le MVP archivé est centré sur les CD audio et l'extraction fre:ac; D-010 reporte l'extraction DVD.
- Le flux normal exige une fiche de métadonnées approuvée; le mode test technique reste isolé.
- MusicBrainz est la source primaire documentée, avec mode manuel/hors ligne; la sélection automatique ne remplace pas l'approbation humaine.
- Le format FLAC et l'organisation de bibliothèque existants restent les références actuelles.
- D-009 interdit l'écrasement silencieux; la conservation et la récupération priment sur un succès apparent.
- D-001 indique GPL-3.0-or-later comme acceptée; l'audit demandé ici est une vérification de conformité et de compatibilité de distribution, pas une nouvelle sélection de licence.

## 5. Contradictions et arbitrages non résolus

1. **Ouverture du code :** le README et les métadonnées du projet présentent déjà AVM comme gratuit et open source sous GPL-3.0-or-later; l'engagement demandé vise une publication « officielle » future après le lancement commercial. Les documents existants ne définissent pas cette distinction. La clarification est requise, mais la présente feuille de route n'invente pas de statut intermédiaire.
2. **Distribution :** le lanceur `.bat` est validé pour un dépôt installé avec environnement virtuel; cela ne contredit pas l'audit AVM-10A qui conclut que la distribution autonome V1 n'est pas prête.
3. **Validation réelle :** un rip Queen antérieur rapporté par AVM-10A coexiste avec le parcours 22 pistes AVM-10E non validé. Ces observations ont des périmètres différents; aucune ne doit être substituée silencieusement à l'autre.
4. **Licence commerciale :** la licence cible est énoncée dans les décisions, mais la compatibilité de l'ensemble des dépendances et contenus avec une distribution commerciale reste à vérifier.
5. **Nouveaux périmètres :** YouTube, inventaire élargi, mobile et le support de médias numériques au-delà des CD ne sont pas confirmés comme décisions dans les documents examinés.

## 6. Références

- [Vision stratégique](../vision/AVM-VISION-STRATEGIQUE.md)
- [Principes de développement](../architecture/AVM-PRINCIPES-DE-DEVELOPPEMENT.md)
- [Décisions produit](../product/decisions.md)
- [Roadmap produit existante](../product/roadmap.md)
- [Audit de préparation V1 — AVM-10A](../architecture/reports/AVM-10A-PRODUCTION-READINESS-V1.md)
- [Validation CD Windows — AVM-10E](../architecture/reports/AVM-10E-VALIDATION-CD-WINDOWS.md)
- [Extraction réelle candidate — AVM-10E-D](../architecture/reports/AVM-10E-D-EXTRACTION-REELLE.md)
- [Validation finale — AVM-10E](../architecture/reports/AVM-10E-VALIDATION-FINALE.md)
- [Enrichissement métadonnées — AVM-10E-D1](../architecture/reports/AVM-10E-D1-ENRICHISSEMENT-METADONNEES.md)
