# Rapport AVM-08D.2 — Atelier chromatique (prototypes)

**Date :** 2026-11-03  
**Version :** 0.5.0  
**Nature :** **Design only** — aucune modification de `audio_video_manager/`  
**Prérequis :** AVM-08D.1 GO technique ; rendu **refusé** (noir dominant)  
**Choix DA (utilisateur) :** **A · Brume pastel** — validé 2026-11-03  
**Arrêt :** attendre mandat d’**intégration** explicite avant production

---

## Verdict

| Question | Réponse |
|----------|---------|
| Prototypes HF shell + Bibliothèque | **Livrés** (2 intensités) |
| Production touchée ? | **Non** |
| Recommandation initiale | A · Brume pastel |
| **Choix utilisateur** | **A · Brume pastel** |
| Intégration code | **EN ATTENTE** mandat explicite |
| AVM-09 | **Suspendu** |

---

## 1. Intention

Remplacer le mur anthracite de 08D.1 par une expérience **enveloppante et colorée** : peinture renversée pastel, surfaces teintées translucides, grands arrondis, navigation latérale conservée. Anthracite `#17191F` réservé au texte / contraste — jamais comme fond dominant.

### Palette (inchangée)

| Ambre | Iris | Rose | Jade | Anthracite |
|-------|------|------|------|------------|
| `#F1B65C` | `#7D8FE8` | `#D782A6` | `#58B9AA` | `#17191F` (contrastes) |

Typo : **Fraunces** / **Outfit**. Rayons : **28–32 px** scènes, **16–22 px** cartes/pochettes, capsules nav/CTA.

---

## 2. Deux variantes

| | **A · Brume pastel** | **B · Flux chromatique** |
|--|----------------------|--------------------------|
| Fond | `paint-soft.jpg` — nappes douces | `paint-vivid.jpg` — saturation + vive |
| Surfaces | Blanc cassé ~55 % opaque | Voile lilas/crème ~48 % |
| Accent nav | Ambre soft | Ambre→iris |
| Marque | Manager ambre | Manager iris |
| Risque | Moins « wow » | Fatigue visuelle longue session |
| Prototype | `prototypes/avm_08d2/variantes/a-brume-pastel/` | `.../b-flux-chromatique/` |

Hub : [`prototypes/avm_08d2/index.html`](../../../prototypes/avm_08d2/index.html)

---

## 3. Captures comparatives

| Fichier | Contenu |
|---------|---------|
| `assets/avm08d2-paint-soft.jpg` / `paint-vivid.jpg` | Toiles sources |
| `assets/avm08d2-a-brume-1120.png` | Variante A large |
| `assets/avm08d2-a-brume-820.png` | Variante A étroite |
| `assets/avm08d2-b-flux-1120.png` | Variante B large |
| `assets/avm08d2-b-flux-820.png` | Variante B étroite |
| `assets/avm08d1-library-1120.png` | **Avant** production 08D.1 (référence refusée) |

---

## 4. Recommandation initiale → **choix validé : A · Brume pastel**

**Décision utilisateur (2026-11-03).**

**Pourquoi (rappel) :**
- Respecte la demande « caresse l’œil » sans agressivité.
- Meilleure lisibilité jour (texte anthracite sur surface laiteuse).
- Même identité chromatique que B, plus durable en usage CD/archivage.
- Transition réaliste depuis 08D.1 (rail gauche + pochettes) sans retour au noir.

Référence figée : `prototypes/avm_08d2/variantes/a-brume-pastel/app.html` + `assets/paint-soft.jpg`.

---

## 5. Stratégie d’implémentation (après validation — mandat futur)

| Couche | Approche | Perf / a11y |
|--------|----------|-------------|
| Fond | JPG unique (1920×1080, ~250–350 Ko) peint dans `AtelierRoot` + `Image` QML ; **pas** d’animations | 1 texture, scale expanding |
| Surfaces | QSS `rgba(..., 0.45–0.72)` + `border-radius: 28px` ; Widgets : fond semi-opaque teinté (ambre/iris très dilué), **pas** blanc `#FFF` ni `#17191F` plein | Contraste texte ≥ 4.5:1 sur voile |
| Nav | Conserver rail gauche 08D.1 ; styles capsule ambre soft | Focus iris 2 px |
| Bibliothèque QML | Restyle Theme + voile ; bridge **inchangé** | Repli Widgets peints pareil |
| Wizard / Historique | Skin Widgets seulement (pas de migration QML) | États 06K inchangés |
| Tailles Win | 820 : rail 76 + abréviations ; 980 / 1120 / max : rail 200 | Captures réelles au mandat d’intégration |
| Hors scope | SQLite, fre:ac, FLAC, QThread, 06K, packaging AVM-09 | — |

**Ordre d’intégration proposé (futur mandat) :** tokens → fond JPG → QSS surfaces/radius → restyle QML → skin wizard/historique → captures + tests.

---

## 6. GO / NO-GO

| Décision | Verdict |
|----------|---------|
| Prototypes + recommandation | **GO livré** |
| Choix DA | **A · Brume pastel** |
| Intégration production | **NO-GO** — mandat d’intégration requis |
| AVM-09 | **NO-GO** |

---

## Arrêt

Variante **A · Brume pastel** enregistrée.  
**Ne pas modifier la production** tant que le mandat d’intégration (ex. AVM-08D.3) n’est pas donné.
