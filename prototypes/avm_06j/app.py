"""Coquille prototype — navigation Archivage / Bibliothèque / Historique."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from prototypes.avm_06j.pages import (
    build_archive_page,
    build_history_page,
    build_library_page,
)

NARROW = 900
_STYLE = (Path(__file__).parent / "style.qss").read_text(encoding="utf-8")


class PrototypeShell(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("AVM-06J · Prototypes UX (hors métier)")
        self.resize(1120, 740)
        self.setMinimumSize(640, 520)
        self._narrow = False
        self._page = 0

        shell = QWidget()
        shell.setObjectName("shell")
        self.setCentralWidget(shell)
        root = QHBoxLayout(shell)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.nav = QWidget()
        self.nav.setObjectName("navRail")
        self.nav.setFixedWidth(200)
        nv = QVBoxLayout(self.nav)
        nv.setContentsMargins(8, 20, 8, 20)
        brand = QLabel("AudioVideo\nManager")
        brand.setStyleSheet(
            "font-size:15px;font-weight:700;color:#0A3D32;padding:8px 12px;"
        )
        nv.addWidget(brand)
        hint = QLabel("Prototype 06J")
        hint.setObjectName("muted")
        hint.setStyleSheet("padding:0 12px 12px 12px;color:#5A635C;font-size:12px;")
        nv.addWidget(hint)

        self._nav_btns: list[QPushButton] = []
        for i, label in enumerate(("Archivage", "Bibliothèque", "Historique")):
            btn = QPushButton(label)
            btn.setObjectName("navBtn")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setAccessibleName(label)
            btn.clicked.connect(lambda _=False, idx=i: self._go(idx))
            self._nav_btns.append(btn)
            nv.addWidget(btn)
        nv.addStretch(1)
        width_hint = QLabel("Redimensionnez pour\nvoir le mode étroit.")
        width_hint.setObjectName("muted")
        width_hint.setStyleSheet("padding:8px 12px;color:#5A635C;font-size:11px;")
        width_hint.setWordWrap(True)
        nv.addWidget(width_hint)
        root.addWidget(self.nav)

        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)
        self._rebuild_pages()
        self._go(0)

    def _rebuild_pages(self) -> None:
        while self.stack.count():
            w = self.stack.widget(0)
            self.stack.removeWidget(w)
            w.deleteLater()
        self.stack.addWidget(build_archive_page(narrow=self._narrow))
        self.stack.addWidget(build_library_page(narrow=self._narrow))
        self.stack.addWidget(build_history_page(narrow=self._narrow))
        self.stack.setCurrentIndex(self._page)

    def _go(self, index: int) -> None:
        self._page = index
        self.stack.setCurrentIndex(index)
        for i, btn in enumerate(self._nav_btns):
            btn.setProperty("active", "true" if i == index else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        narrow = self.width() < NARROW
        if narrow == self._narrow:
            return
        self._narrow = narrow
        self.nav.setVisible(not narrow)
        # En étroit : barre haute simple
        self._rebuild_pages()


def run() -> int:
    import sys

    app = QApplication(sys.argv)
    # Fusion : QSS prévisible (évite le style native Windows qui ignore trop de règles).
    app.setStyle("Fusion")
    app.setStyleSheet(_STYLE)
    win = PrototypeShell()
    win.show()
    return int(app.exec())
