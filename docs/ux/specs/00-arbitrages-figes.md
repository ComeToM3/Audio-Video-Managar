# 00 — Arbitrages A1–A10 figés (entrée AVM-06B)

Source : validation produit sur [../09-arbitrage-a-valider.md](../09-arbitrage-a-valider.md).  
Ce document **fige** les choix pour les spécifications ; toute modification exige un nouvel arbitrage.

| ID | Décision figée |
|----|----------------|
| **A1** | Navigation **4 sections** : Archiver · Bibliothèque · Historique · Paramètres (latérale ; onglets si étroit) |
| **A2** | Ordre d’implémentation : **UI-0 coquille → UI-1 wizard → UI-2 historique → UI-3 bibliothèque → UI-4 polish** |
| **A3** | Voir § nuance ci-dessous (hybride navigation / invalidation) |
| **A4** | Test technique **uniquement** Paramètres → Avancé |
| **A5** | **Aucune** mention DVD dans le wizard ; éventuel « DVD : prévu » dans Avancé / À propos seulement |
| **A6** | Bibliothèque = **SQLite `releases`** + **vérification existence** des dossiers/fichiers ; scan FS complémentaire si besoin |
| **A7** | **Pochettes visibles** (miniature, cache local) dès l’identification |
| **A8** | Premier rip réel = mandat **AVM-06C** après wizard minimal fonctionnel (UI-1) |
| **A9** | Exclus MVP : lecteur multimédia riche, cloud, auto-approve (OFF), extraction DVD |
| **A10** | UI **français uniquement** |

## Nuance A3 (figée par le mandat AVM-06B)

> Conserver l’approbation lors d’une **simple navigation**, mais l’**invalider** lorsque l’**identité du disque** ou les **données approuvées** changent.

| Action utilisateur | Effet sur `approval` |
|--------------------|----------------------|
| Changer de section (Bibliothèque, Historique, Paramètres) puis revenir à Archiver | **Conserve** `Approved` |
| Naviguer stepper 4 → 3 (retour) **sans** modifier de champ | **Conserve** `Approved` |
| Modifier un champ de la fiche après Approuver (titre, piste, compilation, etc.) | → `Pending` (ré-approbation requise) |
| Relire TOC / Disc ID différent du disque de la fiche | → `Pending` + message « Le disque a changé » |
| Appliquer une autre édition MB | → `Pending` |
| Nouvel `identify_disc` qui remplace l’identité | → `Pending` |

### Compatibilité technique (à respecter sans changer D-011)

- Aujourd’hui `approve_sheet` / modèle n’ont pas de « dirty flag » UI : l’implémentation devra **détecter le dirty** côté UI et appeler une révocation explicite (ex. remettre `ApprovalState.PENDING`, `approved_at=None`) **sans** inventer de nouvelle règle métier autre que « Approuvé implique données figées ».
- **Incompatibilité signalée :** l’option A3 « recommandé » du doc 06A (révocation systématique au retour étape 3) est **écartée** au profit de cette nuance. Les specs wizard suivent la nuance, pas le 03-navigation ancien § transitions.
- D-011 reste : pas de rip archive sans `Approved` au moment du lancement.

## Non-objectifs rappelés

Pas de duplication de logique métier dans l’UI : uniquement orchestration d’appels vers modules existants ([05-contrats-services.md](05-contrats-services.md)).
