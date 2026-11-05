# Rapport AVM-08B — Intégration hybride Bibliothèque QML

**Date :** 2026-11-03  
**Version :** 0.5.0  
**Suite :** **192 passed** (187 + 5 `test_library_qml_08b`) — 0 failed / 0 error  
**Preuve Windows :** `using_qml=True` dans MainWindow ; repli Widgets vérifié  
**Arrêt :** validation avant AVM-08C / autre migration

---

## Verdict

| Critère | Statut |
|---------|--------|
| Bibliothèque QML dans le shell Widgets | **OK** (`QQuickWidget`) |
| Wizard / Historique / Paramètres Widgets | **Inchangés** |
| Données catalogue partagées (même `Database`) | **OK** |
| Recherche, sélection, détail, pistes, ouvrir dossier | **OK** |
| Refresh post-archivage (`library_changed`) | **OK** |
| Repli Widgets explicite | **OK** (bouton + Paramètres + `AVM_LIBRARY_UI`) |
| Captures 820 / 980 / 1120 / max | **OK** |
| Crash QThread/QML runtime sur parcours hybride | **Non observé** (captures) |
| **Verdict** | **GO technique AVM-08B** |

---

## 1. Intégration

| Élément | Emplacement |
|---------|-------------|
| Hôte hybride | `ui/sections/library_host.py` |
| Bridge | `ui/qml/library_bridge.py` |
| QML | `ui/qml/LibraryPage.qml` + module `ui/qml/AvmLibrary/` |
| Config | `AppConfig.library_ui_mode` (`qml` \| `widgets`) |
| Env | `AVM_LIBRARY_UI=qml\|widgets` |
| Refresh archive | `ArchiveWizardPage.library_changed` → `MainWindow._on_library_changed` |

Navigation shell inchangée (4 sections). Seule la page index 1 est un `LibraryHost`.

### Repli

1. Bouton « Interface classique… » dans la barre Bibliothèque.  
2. Paramètres → Affichage bibliothèque (persisté JSON).  
3. Variable d’environnement `AVM_LIBRARY_UI=widgets`.  
4. Échec chargement QML → repli automatique Widgets + log.

---

## 2. Captures Windows (réelles)

| Fichier | Note |
|---------|------|
| `assets/avm08b-library-qml-1120.png` | Shell Widgets + contenu QML |
| `assets/avm08b-library-qml-980.png` | |
| `assets/avm08b-library-qml-820.png` | Mode étroit |
| `assets/avm08b-library-qml-maximized.png` | |
| `assets/avm08b-library-widgets-fallback-1120.png` | Après `force_widgets_fallback` |
| `avm08b-capture-meta.txt` | `platform=windows`, QML puis fallback |

**Comparaison visuelle :** le panneau QML conserve le design 08A (grille, chips, détail) à l’intérieur du chrome Widgets 06L — rendu **supérieur** à la seule `QListWidget` IconMode pour la zone contenu.

---

## 3. Tests

| Module | Résultat |
|--------|----------|
| `tests/test_library_qml_08b.py` | **5 PASS**, process rc=0 |
| Suite fichier-par-fichier | **192 PASS**, 0 fail, 0 error |
| Exit teardown UI (07A) | Toujours possible AV/STACK **après** PASS — documenté, hors critère runtime 08B |

Les fixtures shell/design/history forcent `library_ui_mode=widgets` pour limiter le bruit pytest GC ; la prod et `test_library_qml_08b` exercent le chemin QML.

---

## 4. Risques résiduels

| Risque | Gravité | Note |
|--------|---------|------|
| Double surface Widgets+QML | P2 | Feature flag + un seul mode visible |
| Sélection QML au premier paint | P3 | Sync Python `selectRow(0)` après refresh |
| A11y QML vs Widgets | P2 | Smoke Accessible.name ; audit NVDA → 08C |
| Teardown pytest + QML | P2 CI | Isoler tests QML / mode widgets dans fixtures |
| Ouverture dossier via `QDesktopServices` | P3 | Comportement OS standard |

---

## 5. GO / NO-GO

| Décision | Verdict |
|----------|---------|
| Intégration hybride Bibliothèque | **GO** |
| Migration Historique (08C) | **En attente** validation 08B |
| Migration wizard / shell | **NO-GO** |

**Arrêt obligatoire :** attendre validation utilisateur avant AVM-08C.
