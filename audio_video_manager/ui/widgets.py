"""Widgets réutilisables du design system (cartes, chips)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QSizePolicy, QVBoxLayout


def make_card(*, object_name: str = "card") -> QFrame:
    frame = QFrame()
    frame.setObjectName(object_name)
    frame.setProperty("card", True)
    frame.setFrameShape(QFrame.Shape.NoFrame)
    frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
    return frame


def make_chip(text: str, role: str = "ok") -> QLabel:
    """role: ok | warn | err"""
    lbl = QLabel(text)
    names = {"ok": "chip", "warn": "chipWarn", "err": "chipErr"}
    lbl.setObjectName(names.get(role, "chip"))
    lbl.setProperty("chip", role if role in names else "ok")
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setAccessibleName(f"Statut : {text}")
    return lbl


def empty_state_card(title: str, body: str) -> QFrame:
    card = make_card()
    lay = QVBoxLayout(card)
    lay.setContentsMargins(32, 40, 32, 40)
    lay.setSpacing(8)
    t = QLabel(title)
    t.setObjectName("cardTitle")
    t.setAlignment(Qt.AlignmentFlag.AlignCenter)
    b = QLabel(body)
    b.setObjectName("muted")
    b.setWordWrap(True)
    b.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lay.addWidget(t)
    lay.addWidget(b)
    return card
