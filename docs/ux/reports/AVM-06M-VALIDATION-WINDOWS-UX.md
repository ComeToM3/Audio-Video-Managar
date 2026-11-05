# Rapport AVM-06M — Validation UX/UI réelle sur Windows

**Date :** 2026-11-03  
**Version :** 0.5.0  
**Plateforme de preuve :** `QApplication.platformName() = windows` (pas offscreen)  
**Suite automatisée (contexte) :** 167 tests PASS — **non substituée** à cette validation manuelle  
**Arrêt :** validation explicite requise avant toute correction ou mandat suivant

---

## Verdict

| Question | Réponse |
|----------|---------|
| L’app est-elle utilisable sur Windows réel ? | **Oui** |
| Design system 06L perceptible (crème / accent forêt / cartes) ? | **Oui** |
| Parcours critique Archivage / Biblio / 06K gate 1 ? | **OK observé** (CD réel Queen GH) |
| Historique conforme à l’intention 06J ? | **Écart majeur** (sélection cartes + actions) |
| Bloquant pour archivage / intégrité / D-011…D-015 ? | **Non** |
| **Verdict global** | **GO avec réserves** |

**Recommandation :** valider ce rapport, puis corriger en priorité les anomalies **P1 Historique** avant tout nouveau mandat UX. Ne pas lancer de rip ni de refonte large sans GO utilisateur.

---

## 1. Méthode et preuves

### 1.1 Ce qui a été fait (Windows réel)

| Preuve | Détail |
|--------|--------|
| Captures Qt `platform=windows` | `scripts/capture_avm06m_windows.py` → `docs/ux/reports/assets/avm06m-*.png` |
| Meta | `docs/ux/reports/avm06m-capture-meta.txt` (`platform=windows`, `style=QCommonStyle`) |
| Session interactive | `python -m audio_video_manager` (sans `QT_QPA_PLATFORM=offscreen`) + pilotage bureau |
| CD optique réel | Queen *Greatest Hits* — **17 pistes · ~59 min**, Disc ID détecté |
| Gate 06K live | Bandeau doublon W1 affiché (Disc ID déjà en bibliothèque) |
| Inventaire a11y | `docs/ux/reports/avm06m-accessible-names.txt` (40 noms) |

### 1.2 Dimensions testées

| Mode | Taille approximative | Captures |
|------|----------------------|----------|
| Large | 1120 × 740 | archive / library / history / settings |
| Intermédiaire | 980 × 680 | library-980 |
| Étroit | 820 × 640 (&lt; 900 → onglets) | archive / library / history narrow |
| Maximisé | ~1707 × 889 | library-maximized |
| Live desktop | fenêtre utilisateur ~1100×720 | `avm06m-live-*.png` |

### 1.3 Limites explicites (non testé / interdit)

| Limite | Raison |
|--------|--------|
| **Aucun rip physique** | Contrainte mandat |
| Gate 3 dialog « Ouvrir / Réarchiver » | Non cliqué jusqu’au lancement d’extraction |
| Approbation W3 bout-en-bout manuelle | Couvert par tests auto ; session focusée gate 1 + shell |
| Navigation clavier exhaustive | Inventaire AccessibleName + smoke focus ; pas de parcours NVDA |
| FLAC Queen / jobs historiques | Lecture seule — non modifiés |
| Offscreen | **Non utilisé comme preuve unique** (captures windows + live) |

---

## 2. Synthèse par section

### 2.1 Archivage (wizard)

**Positif**
- Stepper pastilles lisible ; hiérarchie Disque → Continuer claire.
- Libellé lecteur humanisé `Lecteur CD/DVD (D:)` (06I).
- Mode étroit : bascule onglets OK, contenu utilisable.
- **06K gate 1 live** : bandeau jaune contextualisé Queen GH, conseil « ouvrir l’album », pas de modal bloquant au démarrage.

**Écarts**
- `Référence technique du disque (Disc ID)` toujours visible dans le parcours normal (diagnostic utile, encore technique).
- Bouton « Relire le disque » très large + beaucoup de vide sous le contenu (hiérarchie diluée vs prototype 06J).
- Statut header « CD 17 pistes » reste affiché en changeant de section (fuite de contexte).

### 2.2 Bibliothèque

**Positif**
- Grille pochettes réelle (cover Queen GH) + badge **Prêt** / **Fichiers manquants**.
- Recherche, détail, table pistes, CTA « Ouvrir le dossier album ».
- Maximisé : lisible ; étroit : onglets + grille encore compréhensible.

**Écarts**
- Chemins absolus complets sous le titre / dans le détail (jargon filesystem).
- Maximisé : espace mort à droite de la grille (pas de reflow dense type 06J 3 colonnes).
- Étroit : zone grille basse → détail écrase la hiérarchie « pochettes d’abord ».

### 2.3 Historique — zone critique

**Positif**
- Intention cartes + chips (Terminé / Annulé / Échec · récupérable).
- Panneau détail riche ; CTA « Ouvrir l’album » / temporaires / Abandonner.
- Langage d’intro clair (« Aucune suppression automatique »).

**Écarts majeurs vs 06J et vs usages**
- Prototype 06J : **actions sur chaque carte**. Implémentation 06L : liste + panneau détail.
- **Clic sur le contenu d’une carte ne sélectionne souvent pas** l’item (`QListWidget` + `setItemWidget`) → panneau reste sur « Sélectionnez une opération. »
- Scrollbar **horizontale** sur la liste de cartes (overflow largeur).
- Chips tronqués (`Annulé · ré…`, `Échec · ré…`).
- Messages encore techniques sur cartes (`code d’extraction = 4294967293`).
- Affordance « Reprendre » active alors que seule une info « non disponible » s’affiche.

### 2.4 Paramètres

**Positif**
- Groupes Bibliothèque / Identification / Extraction / Avancé cohérents avec le design system.
- Auto-approve désactivé ; DVD annoncé non disponible.
- CTA Enregistrer primaire clair.

**Écarts**
- Chemins longs coupés ; section Avancé peut paraître serrée / besoin de scroll selon hauteur.
- Libellé « fre:ac » encore exposé (acceptable en Avancé, un peu technique).

---

## 3. Scénarios 06K / wizard / a11y

| Scénario | Résultat | Preuve |
|----------|----------|--------|
| CD déjà archivé inséré → app démarre | **OK** (pas de freeze) | Live W1 |
| Avertissement doublon Disc ID | **OK** bandeau FR + Queen GH | Live |
| Éditions différentes (titre seul) | Non rejoué live (seed capture + tests 06K) | Auto / seed |
| Fichiers manquants bibliothèque | **OK** chip « Fichiers manquants » | Capture library |
| Réarchivage volontaire (dialog gate 3) | **Non exercé** (pas de rip) | Limite |
| Ouvrir album existant (priorité UX) | Libellé présent en dialog code ; non cliqué live | Code 06L |
| Conservation approbation (nav) | **OK tests auto** | `test_navigate_preserves_wizard_approval` |
| Progression réelle / pas de % inventé | Non observé (pas d’extraction) | Limite + code W4 |
| Focus / AccessibleName | ~40 noms ; focus ring partiel selon widget | Inventaire + capture focus |
| Tab order | Smoke seulement — **pas d’audit exhaustif** | Limite |

---

## 4. Matrice d’anomalies priorisées

| ID | Gravité | Repro | Écran | Anomalie | Correction recommandée |
|----|---------|-------|-------|----------|------------------------|
| A-01 | **P1** | Toujours | Historique | Clic sur carte (`setItemWidget`) ne sélectionne pas → détail vide | Event filter / `itemPressed` sur carte ; ou actions inline comme 06J |
| A-02 | **P1** | Large & étroit | Historique | Scrollbar horizontale / overflow cartes | Largeur contrainte, `wordWrap`, pas de chip trop large |
| A-03 | **P1** | Fréquent | Historique | Chips statut tronqués | Texte court (`Échec`, `Annulé`) + tooltip complet |
| A-04 | **P2** | Live jobs | Historique | Codes fre:ac numériques dans le résumé carte | Humaniser via `humanize_error` sans exposer le code en titre |
| A-05 | **P2** | W1 | Archivage | Disc ID visible parcours normal | Plier sous « Détails techniques » / tooltip |
| A-06 | **P2** | Biblio / Settings | Plusieurs | Chemins absolus dominants | Elision + tooltip ; libellé « Dossier bibliothèque » |
| A-07 | **P2** | Windows | Global | `apply_app_style` demande Fusion mais `QCommonStyle` constaté | Vérifier `setStyle("Fusion")` après QApplication ; documenter fallback |
| A-08 | **P2** | Historique | Historique | « Reprendre » toujours cliquable sans reprise réelle | Désactiver ou renommer « Que faire ? » |
| A-09 | **P2** | Étroit | Bibliothèque | Grille trop basse vs panneau détail | Splitter vertical ou détail en tiroir |
| A-10 | **P2** | Maximisé | Bibliothèque | Espace mort à droite | Augmenter colonnes grille / `flow` |
| A-11 | **P3** | Header | Shell | « CD N pistes » persiste hors Archivage | Clear status en changeant de section |
| A-12 | **P3** | a11y | Historique | Table masquée encore dans l’arbre (« Liste des opérations ») | `WA_Accessible` off ou retirer table une fois tests migrés |
| A-13 | **P3** | W1 | Archivage | Gros vide sous « Relire le disque » | Reserrer layout / carte contenu |
| A-14 | **P3** | vs 06J | Historique | Actions pas sur la carte (écart intention) | Réaligner sur prototype (CTA par carte) |

**Aucune P0** (crash, rip silencieux, écrasement, perte d’approbation observée).

---

## 5. Comparaison intentions AVM-06J

| Intention 06J | Constat 06M Windows |
|---------------|---------------------|
| Widgets + Fusion/QSS crème / accent forêt | **Aligné** visuellement (QSS) ; style moteur = CommonStyle |
| Historique : cartes + actions disponibles | Cartes **oui** ; actions **panneau** + sélection défaillante |
| Bibliothèque : grille pochettes d’abord | **Oui** ; densités maximisé/étroit à peaufiner |
| Archivage : stepper + progression + pochette | Stepper OK ; W4 non rejoué live ; W1 encore technique (Disc ID) |
| Peu de modales | Gate 1 **inline** (bien) ; Historique détail ressemble à une « modale » persistante |

---

## 6. Captures livrées

| Fichier | Contenu |
|---------|---------|
| `assets/avm06m-archive-1120.png` | Wizard W1 large |
| `assets/avm06m-library-1120.png` | Grille + manquants |
| `assets/avm06m-history-1120.png` | Cartes + panneau |
| `assets/avm06m-settings-1120.png` | Paramètres |
| `assets/avm06m-*-narrow.png` | Mode &lt; 900 px |
| `assets/avm06m-library-980.png` | Intermédiaire |
| `assets/avm06m-library-maximized.png` | Maximisé |
| `assets/avm06m-archive-focus-tab.png` | Smoke focus |
| `assets/avm06m-live-*.png` | Session interactive bureau (biblio réelle Queen, etc.) |
| `avm06m-accessible-names.txt` | Noms accessibles |
| `avm06m-capture-meta.txt` | platform=windows |

Références concept 06J : `assets/avm06j-*.png`.

---

## 7. Risques résiduels

| Risque | Niveau |
|--------|--------|
| Utilisateur Historique croit l’écran « cassé » (pas de sélection) | **Élevé** (P1) |
| Confusion codes d’erreur techniques | Moyen |
| Gate 3 / rip non validés manuellement cette session | Moyen (mitigé par 06K tests + code) |
| Perf grille &gt; centaines d’albums | Non mesuré live (hors scope volume) |

---

## 8. Arrêt

**AVM-06M terminé.**  
Verdict : **GO avec réserves** — produit Windows réel cohérent avec 06L/06K sur Archivage/Bibliothèque ; **Historique à corriger (P1)** avant d’empiler de nouvelles évolutions UX.

**Attendre validation explicite** avant toute correction ciblée ou mandat suivant.
