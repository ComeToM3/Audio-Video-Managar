"""Pages Bibliothèque / Historique — stubs UI-0 (pas de fonctionnalités fictives)."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class PlaceholderPage(QWidget):
    def __init__(self, title: str, body: str, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        h = QLabel(title)
        h.setStyleSheet("font-size: 18px; font-weight: 600;")
        msg = QLabel(body)
        msg.setWordWrap(True)
        msg.setProperty("role", "muted")
        layout.addWidget(h)
        layout.addWidget(msg)
        layout.addStretch(1)
