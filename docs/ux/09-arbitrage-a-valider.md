# 09 — Arbitrages A1–A10

**Statut : VALIDÉ** (entrée AVM-06B). Version figée pour l’implémentation : [specs/00-arbitrages-figes.md](specs/00-arbitrages-figes.md)  
**Note A3 :** nuance produit — conserver l’approbation à la navigation simple ; invalider si identité disque ou données approuvées changent (pas la révocation systématique au retour d’étape).

~~Ancien arrêt 06A~~ — la conception détaillée est dans `specs/` ; l’arrêt courant est [specs/09-risques-residuels.md](specs/09-risques-residuels.md).

---

## Recommandation globale

Adopter une **navigation à 4 sections** et un **wizard d’archivage en 5 étapes**, en réutilisant intégralement le backend AVM-05 et les gates D-011…D-015.  
Objectif : rendre le **premier archivage réel** guidé et sûr, sans ajouter de fonctionnalités métier nouvelles.

---

## Décisions à trancher (cochez)

### A1 — Structure de navigation

- [ ] **Recommandé :** barre latérale (ou onglets) : Archiver · Bibliothèque · Historique · Paramètres
- [ ] Alternative : wizard plein écran uniquement + menu Paramètres

### A2 — Ordre d’implémentation

- [ ] **Recommandé :** UI-0 coquille → UI-1 wizard → UI-2 historique → UI-3 bibliothèque → UI-4 polish
- [ ] Alternative : bibliothèque avant historique

### A3 — Retour arrière après Approuver

- [ ] **Recommandé :** revenir à l’étape 3 **révoque** l’approbation (`Pending`) avec confirmation
- [ ] Alternative : garder `Approved` jusqu’à modification de champ

### A4 — Emplacement du mode test technique

- [ ] **Recommandé :** uniquement Paramètres → Avancé (hors parcours principal)
- [ ] Alternative : lien discret « Diagnostic » dans Archiver

### A5 — Mention DVD dans l’UI

- [ ] **Recommandé :** aucune mention dans le wizard ; éventuel texte « DVD : prévu » dans À propos / Avancé
- [ ] Alternative : sélecteur CD/DVD grisé « Bientôt » sur Archiver

### A6 — Ma bibliothèque : source de données

- [ ] **Recommandé :** SQLite `releases` + vérification existence dossier ; scan FS en complément si besoin
- [ ] Alternative : scan FS pur à chaque ouverture

### A7 — Affichage pochette

- [ ] **Recommandé :** miniature téléchargée (cache local job) dès l’identification
- [ ] Alternative : URL texte seulement (statut actuel) jusqu’à plus tard

### A8 — Premier rip réel

- [ ] **Recommandé :** mandat **AVM-06C** après UI-1 minimum (wizard), avec checklist utilisateur
- [ ] Alternative : rip réel immédiat sur UI actuelle (v0.5.0) avant refonte

### A9 — Périmètre « non-objectifs » confirmé

Confirmer l’exclusion MVP UI de :

- [ ] Lecteur multimédia intégré riche
- [ ] Cloud / comptes
- [ ] Auto-approbation (reste OFF)
- [ ] Extraction DVD

### A10 — Langue UI

- [ ] **Recommandé :** français uniquement (NF-07)
- [ ] Alternative : i18n EN dès 06B (coût)

---

## Risques produit (conception)

| Risque | Sévérité | Réponse conception |
|--------|----------|-------------------|
| Utilisateur archive le mauvais mode (test vs archive) | Haute | Test en Avancé seulement (A4) |
| Confusion préférence pays CA = provenance | Moyenne | Texte explicite étape 2 |
| Replace destructif perçu | Haute | Libellé « corbeille locale » + confirm |
| Scope UI trop large avant 1er rip réel | Haute | A8 : rip après wizard minimal |
| Contournement gate via UI | Haute | Interdit — mêmes appels `approve_sheet` / `assert_*` |

---

## Hors scope explicite de ce dossier

- Modification du code, de la DB, des règles D-001…D-015.
- Choix fin de widgets Qt (à trancher en 06B : `QStackedWidget` vs pages).
- Design pixels haute fidélité (wireframes textuels suffisent pour GO).

---

## Validation

| Rôle | Nom | Date | Décisions A1–A10 |
|------|-----|------|------------------|
| Product owner | | | |
| | | | **GO AVM-06B** / **NO-GO** / **GO avec réserves** |

Commentaires :

```
…


```

Dès **GO**, le mandat suivant pourra implémenter selon [08-plan-implementation.md](08-plan-implementation.md) sans élargir le métier.
