# Principes permanents de développement — AudioVideoManager

**Statut :** principes directeurs. Ils consolident les décisions et exigences documentées; ils ne constituent pas une preuve que chaque objectif est déjà atteint.

## 1. Principes produit et d'architecture

### Architecture modulaire

- Séparer l'interface, l'orchestration, l'extraction, les métadonnées, la bibliothèque, le stockage, la journalisation et la vérification.
- Garder les tâches métier appelables sans interface lorsque cela est possible; isoler les outils externes derrière des frontières explicites.
- Ne pas coupler la lecture ou la présentation des médias à AVM : AVM n'est pas et ne devient pas un lecteur multimédia.
- Préserver des contrats de service testables et des points d'extension; éviter les dépendances croisées qui rendent une plateforme ou un fournisseur obligatoire.

L'architecture documentée décrit déjà ces frontières et des interfaces telles que `CdRipper`, `MetadataProvider` et `LibraryOrganizer`. L'existence de ces frontières ne certifie pas à elle seule une portabilité multiplateforme.

### Extensibilité maîtrisée

- Permettre l'ajout de types de supports, de fournisseurs de métadonnées et de backends sans fragiliser le chemin d'archivage existant.
- Marquer explicitement les capacités différées ou expérimentales. En particulier, l'extraction DVD est reportée par D-010; un module réservé n'est pas une fonction livrée.
- Ne pas élargir le périmètre, par exemple à des flux ou plateformes en ligne, sans analyse des besoins, des droits, des conditions d'accès et une validation produit.

### Qualité d'extraction vérifiable

- Viser la meilleure qualité réalisable pour le support et le matériel, sans transformation audio injustifiée; pour les CD, la référence existante est FLAC 16 bits / 44,1 kHz sans rééchantillonnage artificiel.
- Distinguer l'intégrité structurelle d'un fichier (F-08a), le contrôle de rip (F-08b) et une preuve de correspondance bit à bit ou de qualité supérieure. Ne jamais présenter l'un comme l'autre.
- Enregistrer les résultats et limites observés; un contrôle non exécuté, un outil absent ou une validation simulée ne doit pas produire un succès implicite.
- Ne déclarer une capacité de qualité avancée, telle qu'AccurateRip, que lorsqu'elle est effectivement implémentée et validée.

### Conservation des originaux et publication prudente

- Traiter les sources, les fichiers de travail et la bibliothèque publiée comme des zones distinctes.
- Ne jamais écraser silencieusement ni supprimer automatiquement les originaux ou les fichiers récupérables. Le remplacement reste explicite et protégé conformément à D-009.
- Préserver les données de travail utiles à la reprise et rendre les opérations de publication contrôlables et récupérables.
- Ne pas contourner les protections anticopie; l'usage doit rester dans le cadre des droits applicables aux supports et contenus concernés.

### Métadonnées traçables

- Conserver la provenance des valeurs, les corrections de l'utilisateur et les niveaux de confiance.
- Distinguer les faits mesurés sur le support des propositions de catalogues et des choix de l'utilisateur. Une préférence de pays ne prouve pas l'édition physique.
- Ne jamais inventer un champ manquant. Les états `confirmed`, `ambiguous`, `missing` et `unavailable` doivent garder leur sens; une indisponibilité exige une justification lorsque le modèle le prévoit.
- Garder le gate d'approbation humaine avant l'archivage normal et ne pas confondre préremplissage ou auto-sélection avec approbation.

## 2. Principes d'expérience utilisateur

- Concevoir le parcours principal pour les personnes non techniques : terminologie claire, étapes explicites, aperçu du résultat et erreurs actionnables.
- Rendre visibles les décisions irréversibles, les chemins effectifs, les collisions et les limites de validation; demander une confirmation proportionnée au risque.
- Favoriser l'automatisation des étapes répétitives (détection, identification, organisation et contrôles) sans retirer à l'utilisateur le contrôle des métadonnées ou de la publication.
- Prévoir le fonctionnement hors ligne lorsque les informations nécessaires peuvent être fournies ou confirmées manuellement; les services réseau ne doivent pas être présentés comme une certitude.
- Ne pas supposer qu'un succès de test technique équivaut à un parcours d'archivage compréhensible et validé par un utilisateur.

## 3. Sécurité et protection des données

- Privilégier un fonctionnement local, des permissions minimales et des chemins isolés; vérifier les destinations effectives avant toute opération sur un média ou une bibliothèque.
- Valider les entrées, normaliser les chemins selon la plateforme et protéger les frontières avec les processus externes.
- Ne pas ajouter de télémétrie, d'installation silencieuse d'outils système ou d'accès réseau non documenté comme comportement implicite.
- Journaliser les opérations et erreurs utiles sans exposer de secrets ni transformer une absence de preuve en état de succès.
- Examiner les risques de traversée de chemin, collision, liens physiques et interruption; maintenir les contrôles de sécurité des données à travers chaque évolution.

Ces principes prolongent notamment les exigences de non-écrasement, le gate de métadonnées et les protections testées dans les rapports AVM-10D et AVM-10E. Ils n'affirment pas qu'un audit de sécurité exhaustif a été réalisé.

## 4. Tests reproductibles et niveau de preuve

- Automatiser les tests des règles métier, des erreurs, de la récupération et des frontières externes; isoler les données utilisateur et les destinations réelles.
- Pour chaque validation, consigner le périmètre, les prérequis, l'environnement, la commande, le code de sortie et les résultats.
- Distinguer les fixtures et simulations, les tests logiciels, les probes en lecture seule et les validations physiques. Les tests automatisés réussis ne remplacent pas un rip matériel requis.
- Répéter les tests dans un environnement propre et selon les versions de plateforme revendiquées; un résultat sous une version de Python ou de Windows ne certifie pas automatiquement les autres.
- Reproduire les anomalies sans utiliser comme cible une bibliothèque personnelle ou un chemin ambigu. Toute action de rip réelle doit respecter le protocole et les autorisations applicables.

## 5. Distribution autonome

- Viser une installation et une exécution accessibles sans dépôt cloné, environnement de développement ni configuration technique manuelle.
- Rendre explicites les prérequis externes, les composants fournis et les composants que l'utilisateur doit obtenir séparément.
- Vérifier les licences et la compatibilité commerciale de **toutes** les dépendances directes, transitives, outils externes et ressources distribuées ou recommandées avant leur inclusion dans une distribution.
- Fournir les avis, textes de licence, attributions et informations de source requis avec les composants concernés; ne pas présumer que l'absence de coût d'une dépendance autorise sa redistribution commerciale.
- Tester l'installation, le lancement, la mise à niveau et la désinstallation sur une machine propre, sans altérer les bibliothèques ni installer silencieusement des outils système.

L'audit AVM-10A conclut que la V1 n'est pas distribuable, entre autres en raison de l'absence de packaging/installateur et de notices de licences complètes. Le format de distribution final n'est pas fixé par ce document.

## 6. Obligations établies et questions juridiques ouvertes

### Obligations et décisions déjà établies

- D-001 enregistre **GPL-3.0-or-later** comme licence acceptée pour AVM; `pyproject.toml` et le README portent aussi cette déclaration.
- D-002 désigne fre:ac / `freaccmd` comme backend CD du MVP; l'architecture existante indique fre:ac sous GPL-2.0 et comme dépendance d'exécution séparée.
- Les données de métadonnées doivent respecter leur provenance et leurs conditions d'usage; le rapport AVM-10E-D1 documente, entre autres, les limites et obligations associées aux API de MusicBrainz et Discogs.
- L'archivage doit respecter les droits d'usage des médias; le README interdit le contournement anticopie.
- Les licences et avis des composants distribués doivent être vérifiés avant une distribution commerciale autonome.

### Questions non résolues — ne pas traiter comme des autorisations

- Compatibilité juridique de la composition exacte d'AVM avec la licence cible, et obligations de publication ou de redistribution des composants effectivement livrés.
- Licences, notices, attribution et compatibilité commerciale de Qt/PySide6, Python et ses dépendances, polices, libdiscid, fre:ac/freaccmd, FFmpeg si distribué, ainsi que tout autre outil ou ressource embarqué.
- Conditions applicables aux API, métadonnées et images selon les données effectivement stockées, affichées, redistribuées ou conservées; l'API Discogs et les conditions d'accès peuvent évoluer.
- Droits applicables à l'extraction de DVD, aux contenus en ligne, à une éventuelle intégration YouTube et aux marchés de commercialisation visés.
- Articulation entre la licence déjà déclarée dans le dépôt, son statut open source actuel et l'engagement de publication « officielle » au plus tard trois ans après le lancement commercial.

Ces questions requièrent un audit juridique et produit; ce document ne donne pas d'avis juridique et ne change pas D-001.

## 7. Références

- [Vision stratégique](../vision/AVM-VISION-STRATEGIQUE.md)
- [Feuille de route](../roadmap/AVM-FEUILLE-DE-ROUTE.md)
- [Décisions produit](../product/decisions.md)
- [Architecture produit](../product/architecture.md)
- [Audit de préparation V1 — AVM-10A](reports/AVM-10A-PRODUCTION-READINESS-V1.md)
- [Rapport intégrité et sécurité — AVM-10D](reports/AVM-10D-INTEGRITE-SECURITE.md)
- [Rapport métadonnées — AVM-10E-D1](reports/AVM-10E-D1-ENRICHISSEMENT-METADONNEES.md)
