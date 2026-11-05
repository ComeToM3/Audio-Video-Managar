"""Captures Windows réelles du prototype QML AVM-08A (pas offscreen)."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

os.environ.pop("QT_QPA_PLATFORM", None)
os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QSize, QTimer, QUrl  # noqa: E402
from PySide6.QtGui import QFont, QGuiApplication  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402
from PySide6.QtQuick import QQuickWindow  # noqa: E402

from prototypes.avm_08a.bridge import LibraryBridge  # noqa: E402

OUT = ROOT / "docs" / "ux" / "reports" / "assets"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    app = QGuiApplication([])
    app.setFont(QFont("Segoe UI"))
    platform = app.platformName()
    print("platform=", platform)
    if platform == "offscreen":
        return 2

    qml_root = ROOT / "prototypes" / "avm_08a" / "qml"
    engine = QQmlApplicationEngine()
    engine.addImportPath(str(qml_root))
    bridge = LibraryBridge()
    engine.rootContext().setContextProperty("library", bridge)
    engine.load(QUrl.fromLocalFile(str(qml_root / "Main.qml")))
    roots = engine.rootObjects()
    if not roots:
        print("no root")
        return 1
    win = roots[0]
    assert isinstance(win, QQuickWindow)

    shots: list[tuple[str, QSize]] = [
        ("avm08a-library-1120.png", QSize(1120, 740)),
        ("avm08a-library-980.png", QSize(980, 680)),
        ("avm08a-library-820.png", QSize(820, 640)),
    ]

    def grab_all(step: list[int] | None = None) -> None:
        i = step[0] if step is not None else 0
        if i < len(shots):
            name, size = shots[i]
            win.resize(size)
            app.processEvents()
            path = OUT / name
            img = win.grabWindow()
            img.save(str(path), "PNG")
            print("wrote", path, size.width(), "x", size.height())
            if step is not None:
                step[0] = i + 1
                QTimer.singleShot(250, lambda: grab_all(step))
            return
        # maximized-ish
        win.showMaximized()
        app.processEvents()
        path = OUT / "avm08a-library-maximized.png"
        win.grabWindow().save(str(path), "PNG")
        print("wrote", path, win.width(), "x", win.height())
        meta = OUT.parent / "avm08a-capture-meta.txt"
        meta.write_text(
            f"platform={platform}\n"
            f"source={bridge.sourceLabel}\n"
            f"albums={bridge.albumCount()}\n"
            f"captured_at={datetime.now(timezone.utc).isoformat()}\n",
            encoding="utf-8",
        )
        print("meta", meta)
        app.quit()

    win.show()
    app.processEvents()
    if bridge.albumCount() > 0:
        bridge.selectRow(0)
    QTimer.singleShot(400, lambda: grab_all([0]))
    return int(app.exec())


if __name__ == "__main__":
    raise SystemExit(main())
