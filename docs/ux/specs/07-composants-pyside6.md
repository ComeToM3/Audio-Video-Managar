# 07 — Composants PySide6 recommandés

## 1. Structure modules UI (cible implémentation — pas encore code)

```text
ui/
  main_window.py          → shell + stacked sections
  sections/
    archive_wizard.py     → stepper + pages
    library_page.py
    history_page.py
    settings_page.py
  widgets/
    step_header.py
    cover_thumb.py
    warning_list.py
    path_preview.py
  workers/                → archive_worker, rip_worker, identify_worker
```

Refactor organisationnel autorisé à l’implémentation ; **pas** de changement métier.

## 2. Mapping composant → widget

| Composant design | PySide6 |
|------------------|---------|
| Shell nav | `QListWidget` + `QStackedWidget` ou `QTabWidget` |
| Stepper | `QWidget` custom (boutons labels) ou `QProgressBar` set + labels |
| CoverThumb | `QLabel` pixmap, scaled `KeepAspectRatio` |
| Warning/Error lists | `QLabel` rich text ou `QListWidget` read-only |
| Pistes | `QTableWidget` / `QTableView` |
| Path preview | `QPlainTextEdit` read-only mono |
| Doublons | `QButtonGroup` + `QRadioButton` |
| Progress | `QProgressBar` + `QLabel` étape |
| Dialogs | `QMessageBox` (confirmations courtes) |
| Bibliothèque liste | `QListWidget` icons ou `QTableView` |
| Historique | `QTableView` + model simple |
| Paramètres | `QFormLayout` + `QGroupBox` ; Avancé = `QToolBox` ou collapsible |

## 3. Accessibilité

- `setAccessibleName` / `setAccessibleDescription` sur CTA.
- Raccourcis : Enter = CTA primaire de l’étape si focus formulaire OK.
- Contraste tokens [../05-systeme-visuel.md](../05-systeme-visuel.md).
- Ne pas désactiver le focus pendant loading sans alternative Escape/Annuler.

## 4. Redimensionnement

- `QScrollArea` autour du corps d’étape si hauteur &lt; contenu.
- Table pistes : `setStretchLastSection(True)`.
- Cover : taille fixe ; ne pas déformer.

## 5. QSS (orientation)

Sélecteurs stables : `#navArchive`, `QPushButton[primary="true"]`, `QLabel[role="warning"]`.  
Éviter styles inline épars sauf états ponctuels.
