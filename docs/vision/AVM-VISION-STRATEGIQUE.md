# Vision stratégique — AudioVideoManager

**Statut :** document de vision, aligné sur les décisions et rapports existants au 4 novembre 2026. Il formalise l'orientation demandée sans remplacer les décisions produit acceptées ni résoudre les questions signalées comme ouvertes.

## 1. Mission

AudioVideoManager (AVM) vise à simplifier la numérisation, l'identification et l'organisation des collections personnelles de CD, DVD et médias numériques. Le produit doit aider les personnes à préserver leurs supports et à constituer une bibliothèque numérique fiable, traçable et facile à parcourir.

AVM est un outil d'importation, d'archivage, de métadonnées et d'organisation. **AVM ne développera pas de lecteur multimédia** : la lecture des fichiers relève d'applications spécialisées existantes.

La priorité produit déjà documentée est l'archivage local des CD audio en FLAC, avec identification du disque, métadonnées vérifiables, contrôles et publication non destructive. L'extraction DVD est reportée par D-010; l'extension aux autres médias reste une évolution à valider, et non une capacité actuelle.

## 2. Modèle économique envisagé

Le modèle envisagé repose principalement sur la vente de lecteurs CD/DVD compatibles, accompagnés d'AVM et de l'information nécessaire pour les utiliser. **Aucun abonnement n'est prévu dans cette vision.** La vente de matériel compatible constitue le moteur économique privilégié; la stratégie ne présume ni le prix, ni les marges, ni les canaux de vente, ni la forme contractuelle du bundle.

Cette orientation ne change pas les exigences de compatibilité, de transparence et de conservation des données. Elle ne constitue pas une décision sur un fabricant ou un modèle de lecteur.

## 3. Évolution des plateformes

La base de travail et les validations actuelles sont centrées sur Windows. L'évolution envisagée est graduelle :

1. établir une distribution Windows fiable et utilisable sans environnement de développement;
2. étudier les adaptations nécessaires à une application multiplateforme;
3. explorer le mobile comme piste de recherche produit et technique.

Le multiplateforme est une direction envisagée, pas une capacité acquise ni une date de livraison. L'exploration mobile ne vaut pas engagement de construire ou de publier une application mobile.

## 4. Engagement d'ouverture du code

AVM s'engage fermement à publier officiellement son code source en open source **au plus tard trois ans après le lancement commercial**, indépendamment du volume des ventes. La date de lancement commercial n'étant pas établie dans les documents examinés, aucune date calendaire n'est déduite ici.

La licence cible est **GPL-3.0-or-later**, sous réserve d'un audit juridique préalable de la licence du projet, des dépendances, des outils distribués avec AVM, des contenus et des obligations de redistribution. Cette réserve décrit une vérification encore à mener; elle n'efface pas la décision D-001 déjà enregistrée comme acceptée dans le dépôt.

## 5. Écarts et questions à conserver visibles

- **Ouverture actuelle et ouverture officielle :** le README présente déjà AVM comme gratuit et open source sous GPL-3.0-or-later; D-001 et `pyproject.toml` déclarent également cette licence. Cela ne correspond pas sans explication à une « ouverture officielle » qui interviendrait après le lancement commercial. Les documents existants ne précisent pas si le dépôt actuel est un prototype, une publication préliminaire ou déjà la publication officielle. Cette distinction reste à clarifier; le présent document ne tranche pas.
- **Modèle gratuit et modèle matériel :** le README décrit actuellement une application gratuite, tandis que la présente vision privilégie la vente de lecteurs compatibles accompagnés d'AVM. Le modèle commercial et le statut des versions n'étaient pas définis dans les décisions produit examinées.
- **Licence et audit :** D-001 est marqué `ACCEPTÉ`, mais les rapports de préparation V1 signalent que les notices de licences sont incomplètes pour la distribution. Le choix cible demeure GPL-3.0-or-later; sa conformité pratique et juridique doit être auditée avant toute distribution commerciale.
- **Calendrier :** aucun lancement commercial ni échéancier de plateforme n'est consigné; seul le délai maximal de trois ans après le lancement commercial s'applique à l'engagement de publication officielle.
- **Périmètre élargi :** les DVD restent reportés (D-010). Les médias numériques, le mobile et l'élargissement au-delà du CD ne sont pas des capacités validées du produit actuel.

## 6. Références

- [Principes de développement](../architecture/AVM-PRINCIPES-DE-DEVELOPPEMENT.md)
- [Feuille de route](../roadmap/AVM-FEUILLE-DE-ROUTE.md)
- [Décisions produit existantes](../product/decisions.md)
- [Exigences produit actuelles](../product/requirements.md)
- [Audit de préparation V1 — AVM-10A](../architecture/reports/AVM-10A-PRODUCTION-READINESS-V1.md)
- [Validation finale CD — AVM-10E](../architecture/reports/AVM-10E-VALIDATION-FINALE.md)
