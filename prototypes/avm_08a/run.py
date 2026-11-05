"""Lanceur prototype AVM-08A — Qt Quick Bibliothèque (isolé, lecture seule)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Prototype isolé : ne jamais forcer offscreen ici (preuves Windows)
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")

from PySide6.QtCore import QUrl
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from prototypes.avm_08a.bridge import LibraryBridge


def main() -> int:
    app = QGuiApplication(sys.argv)
    app.setApplicationName("AVM-08A Library Prototype")
    app.setOrganizationName("AudioVideoManager")
    font = QFont("Segoe UI")
    font.setStyleHint(QFont.StyleHint.SansSerif)
    app.setFont(font)

    qml_root = Path(__file__).resolve().parent / "qml"
    engine = QQmlApplicationEngine()
    # import Avm08a → qml/Avm08a/qmldir
    engine.addImportPath(str(qml_root))

    bridge = LibraryBridge()
    engine.rootContext().setContextProperty("library", bridge)

    main_qml = qml_root / "Main.qml"
    engine.load(QUrl.fromLocalFile(str(main_qml)))
    if not engine.rootObjects():
        print("Échec chargement QML:", main_qml, file=sys.stderr)
        return 1

    print("platform=", app.platformName())
    print("source=", bridge.sourceLabel)
    print("albums=", bridge.albumCount())
    return int(app.exec())


if __name__ == "__main__":
    raise SystemExit(main())
