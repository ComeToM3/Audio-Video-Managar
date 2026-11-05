"""Trois écrans prototype — Archivage, Bibliothèque, Historique."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from prototypes.avm_06j import mock_data as data


def _card() -> QFrame:
    f = QFrame()
    f.setObjectName("card")
    f.setFrameShape(QFrame.Shape.NoFrame)
    return f


def _chip(text: str, role: str = "ok") -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName({"ok": "chip", "warn": "chipWarn", "err": "chipErr"}[role])
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return lbl


def build_archive_page(*, narrow: bool = False) -> QWidget:
    root = QWidget()
    lay = QVBoxLayout(root)
    lay.setContentsMargins(28 if not narrow else 16, 24, 28 if not narrow else 16, 24)
    lay.setSpacing(16)

    title = QLabel("Archiver un disque")
    title.setObjectName("heroTitle")
    title.setAccessibleName("Archiver un disque")
    sub = QLabel("Cinq étapes claires — du CD à votre bibliothèque locale.")
    sub.setObjectName("heroSub")
    lay.addWidget(title)
    lay.addWidget(sub)

    # Stepper
    step_row = QHBoxLayout()
    step_row.setSpacing(8)
    for i, name in enumerate(data.ARCHIVE_STEPS):
        chip = QLabel(f"{i + 1}  {name}")
        chip.setObjectName("chip" if i <= 3 else "muted")
        if i == 3:
            chip.setObjectName("chip")
        elif i < 3:
            chip.setStyleSheet(
                "background:#E8F3EE;color:#0A3D32;border-radius:999px;"
                "padding:6px 12px;font-size:12px;font-weight:600;"
            )
        else:
            chip.setStyleSheet(
                "background:#EDE8DC;color:#5A635C;border-radius:999px;"
                "padding:6px 12px;font-size:12px;"
            )
        if i == 3:
            chip.setStyleSheet(
                "background:#1B7A5C;color:white;border-radius:999px;"
                "padding:6px 12px;font-size:12px;font-weight:600;"
            )
        step_row.addWidget(chip)
        if i < len(data.ARCHIVE_STEPS) - 1:
            sep = QLabel("→")
            sep.setObjectName("muted")
            step_row.addWidget(sep)
    step_row.addStretch(1)
    lay.addLayout(step_row)

    # Left: recap + progress
    left = _card()
    left.setMinimumWidth(280)
    ll = QVBoxLayout(left)
    ll.setContentsMargins(20, 18, 20, 18)
    ll.setSpacing(12)
    h = QLabel("Extraction en cours")
    h.setObjectName("cardTitle")
    ll.addWidget(h)
    ll.addWidget(QLabel("Queen — Greatest Hits (1992, CA)"))
    active = QLabel("Piste 4/17 — Killer Queen")
    active.setStyleSheet("font-size:15px;font-weight:600;color:#0A3D32;")
    active.setAccessibleName("Progression piste en cours")
    ll.addWidget(active)
    bar = QProgressBar()
    bar.setRange(0, 100)
    bar.setValue(42)  # démo : en prod = fraction fre:ac réelle uniquement
    bar.setTextVisible(False)
    bar.setAccessibleName("Barre de progression")
    ll.addWidget(bar)
    note = QLabel("La barre suit les événements réels — aucun pourcentage inventé.")
    note.setObjectName("muted")
    note.setWordWrap(True)
    ll.addWidget(note)
    steps = QListWidget()
    steps.setObjectName("stepList")
    steps.setAccessibleName("Sous-étapes")
    steps.setMaximumHeight(180)
    for i, name in enumerate(data.PIPELINE):
        item = QListWidgetItem(name)
        steps.addItem(item)
        if i == 1:
            steps.setCurrentRow(i)
    ll.addWidget(steps)
    cancel = QPushButton("Annuler")
    cancel.setObjectName("ghost")
    cancel.setAccessibleName("Annuler l’archivage")
    ll.addWidget(cancel, alignment=Qt.AlignmentFlag.AlignLeft)
    ll.addStretch(1)

    # Right: cover + edition card
    right = _card()
    right.setMinimumWidth(220)
    right.setMaximumWidth(360 if not narrow else 16777215)
    rl = QVBoxLayout(right)
    rl.setContentsMargins(20, 18, 20, 18)
    cover = QLabel("Greatest Hits")
    cover.setObjectName("coverPlaceholder")
    cover.setAlignment(Qt.AlignmentFlag.AlignCenter)
    cover.setFixedHeight(200 if not narrow else 160)
    cover.setAccessibleName("Pochette album")
    rl.addWidget(cover)
    ed = QLabel("Édition proposée")
    ed.setObjectName("cardTitle")
    rl.addWidget(ed)
    meta = QLabel("Canada · 1992 · Hollywood Records\n17 pistes · approbation requise")
    meta.setObjectName("muted")
    meta.setWordWrap(True)
    rl.addWidget(meta)
    approve = QPushButton("Voir la fiche à approuver")
    approve.setObjectName("primary")
    rl.addWidget(approve)
    rl.addStretch(1)

    if narrow:
        body_col = QVBoxLayout()
        body_col.setSpacing(12)
        body_col.addWidget(left)
        body_col.addWidget(right)
        lay.addLayout(body_col, 1)
    else:
        body = QHBoxLayout()
        body.setSpacing(16)
        body.addWidget(left, 3)
        body.addWidget(right, 2)
        lay.addLayout(body, 1)

    return root


def build_library_page(*, narrow: bool = False, empty: bool = False) -> QWidget:
    root = QWidget()
    lay = QVBoxLayout(root)
    lay.setContentsMargins(28 if not narrow else 16, 24, 28 if not narrow else 16, 24)
    lay.setSpacing(16)

    head = QHBoxLayout()
    titles = QVBoxLayout()
    t = QLabel("Ma bibliothèque")
    t.setObjectName("heroTitle")
    s = QLabel("Vos albums FLAC locaux — pochettes d’abord, détails ensuite.")
    s.setObjectName("heroSub")
    titles.addWidget(t)
    titles.addWidget(s)
    head.addLayout(titles, 1)
    lay.addLayout(head)

    search = QLineEdit()
    search.setObjectName("search")
    search.setPlaceholderText("Rechercher un artiste ou un album…")
    search.setAccessibleName("Recherche bibliothèque")
    lay.addWidget(search)

    if empty:
        empty_card = _card()
        el = QVBoxLayout(empty_card)
        el.setContentsMargins(32, 40, 32, 40)
        el.addWidget(QLabel("Aucun album pour l’instant"), alignment=Qt.AlignmentFlag.AlignCenter)
        msg = QLabel("Insérez un CD et lancez Archiver un disque.")
        msg.setObjectName("muted")
        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        el.addWidget(msg)
        cta = QPushButton("Archiver un disque")
        cta.setObjectName("primary")
        el.addWidget(cta, alignment=Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(empty_card)
        lay.addStretch(1)
        return root

    grid = QGridLayout()
    grid.setSpacing(14)
    cols = 1 if narrow else 3
    for i, album in enumerate(data.ALBUMS):
        card = _card()
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        card.setMinimumWidth(160)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(12, 12, 12, 14)
        cover = QLabel(album["artist"][:1])
        cover.setObjectName("coverPlaceholder")
        cover.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cover.setFixedHeight(130 if narrow else 150)
        cover.setStyleSheet(
            f"background:{album['color']};border-radius:12px;color:#F3F0E8;"
            "font-size:28px;font-weight:700;"
        )
        cl.addWidget(cover)
        name = QLabel(f"{album['artist']}\n{album['title']}")
        name.setObjectName("cardTitle")
        name.setWordWrap(True)
        cl.addWidget(name)
        meta = QLabel(f"{album['year']} · {album['tracks']} pistes")
        meta.setObjectName("muted")
        cl.addWidget(meta)
        if album["missing"]:
            cl.addWidget(_chip("Fichiers manquants", "warn"))
        else:
            cl.addWidget(_chip("Prêt", "ok"))
        r, c = divmod(i, cols)
        grid.addWidget(card, r, c)
        if cols > 1:
            grid.setColumnStretch(c, 1)

    wrap = QWidget()
    wrap.setLayout(grid)
    lay.addWidget(wrap, 1)

    # Detail strip
    detail = _card()
    dl = QHBoxLayout(detail)
    dl.setContentsMargins(16, 14, 16, 14)
    thumb = QLabel("QH")
    thumb.setFixedSize(64, 64)
    thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
    thumb.setStyleSheet("background:#5C1A2E;border-radius:10px;color:white;font-weight:700;")
    dl.addWidget(thumb)
    info = QVBoxLayout()
    info.addWidget(QLabel("Queen — Greatest Hits"))
    tracks = QLabel("01 We Will Rock You · 02 We Are the Champions · 03 Another One Bites…")
    tracks.setObjectName("muted")
    tracks.setWordWrap(True)
    info.addWidget(tracks)
    dl.addLayout(info, 1)
    open_btn = QPushButton("Ouvrir le dossier")
    open_btn.setObjectName("primary")
    dl.addWidget(open_btn)
    lay.addWidget(detail)

    return root


def build_history_page(*, narrow: bool = False) -> QWidget:
    root = QWidget()
    lay = QVBoxLayout(root)
    lay.setContentsMargins(28 if not narrow else 16, 24, 28 if not narrow else 16, 24)
    lay.setSpacing(16)

    t = QLabel("Historique")
    t.setObjectName("heroTitle")
    s = QLabel("Ce qui s’est passé — en langage clair, actions vraiment disponibles.")
    s.setObjectName("heroSub")
    lay.addWidget(t)
    lay.addWidget(s)

    for job in data.JOBS:
        card = _card()
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(18, 14, 18, 14)
        row = QHBoxLayout()
        left = QVBoxLayout()
        when = QLabel(job["when"])
        when.setObjectName("muted")
        left.addWidget(when)
        title = QLabel(job["title"])
        title.setObjectName("cardTitle")
        left.addWidget(title)
        detail = QLabel(job["detail"])
        detail.setObjectName("muted")
        detail.setWordWrap(True)
        left.addWidget(detail)
        row.addLayout(left, 1)
        row.addWidget(_chip(job["state"], job["kind"]), 0, Qt.AlignmentFlag.AlignTop)
        cl.addLayout(row)
        actions = QHBoxLayout()
        if job["kind"] == "ok":
            b = QPushButton("Ouvrir l’album")
            b.setObjectName("primary")
            actions.addWidget(b)
        elif job["kind"] == "warn":
            b = QPushButton("Ouvrir les fichiers temporaires")
            b.setObjectName("primary")
            actions.addWidget(b)
            g = QPushButton("Abandonner (sans supprimer)")
            g.setObjectName("ghost")
            actions.addWidget(g)
        else:
            b = QPushButton("Réessayer plus tard")
            b.setObjectName("ghost")
            actions.addWidget(b)
        actions.addStretch(1)
        cl.addLayout(actions)
        lay.addWidget(card)

    lay.addStretch(1)
    return root
