"""Historique — cartes sélectionnables, badges courts, reprise contrôlée (AVM-06N / 10B)."""

from __future__ import annotations

from pathlib import Path

from collections.abc import Callable

from PySide6.QtCore import Qt, QThread, QUrl
from PySide6.QtGui import QDesktopServices, QMouseEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from audio_video_manager.config import AppConfig
from audio_video_manager.library.publish import CollisionPolicy
from audio_video_manager.orchestration.reconciliation import (
    RecoveryVerdict,
    assess_recovery_from_files,
    list_job_flac_files,
    mark_job_abandoned,
    recovery_in_progress,
)
from audio_video_manager.storage.catalog import (
    JobRow,
    list_jobs,
    state_label_fr,
)
from audio_video_manager.storage.database import Database
from audio_video_manager.ui.path_labels import friendly_path_label
from audio_video_manager.ui.progress_labels import humanize_error_for_user
from audio_video_manager.ui.recovery_worker import RecoveryWorker
from audio_video_manager.ui.thread_lifecycle import (
    attach_worker_thread,
    shutdown_worker_thread,
)
from audio_video_manager.ui.widgets import make_chip


def _chip_role(state: str) -> str:
    if state in {"Completed", "CompletedWithWarnings", "SkippedDuplicate"}:
        return "ok"
    if state in {"Failed", "Interrupted"}:
        return "err"
    if state in {"Cancelled", "Abandoned"}:
        return "warn"
    return "warn"


def _chip_state_text(state: str) -> str:
    """Badge court — jamais « · récupérable » (séparé)."""
    short = {
        "Completed": "Terminé",
        "CompletedWithWarnings": "Terminé",
        "Failed": "Échec",
        "Cancelled": "Annulé",
        "Interrupted": "Interrompu",
        "Abandoned": "Abandonné",
        "SkippedDuplicate": "Doublon",
        "Ripping": "En cours",
        "Tagging": "En cours",
        "Staging": "En cours",
        "FlacIntegrity": "En cours",
        "Organizing": "En cours",
        "ReadyToPublish": "Prêt",
        "AwaitingPublishConfirmation": "En attente",
    }
    return short.get(state, state_label_fr(state)[:12])


class SelectableJobCard(QFrame):
    """Carte dont tout le rectangle déclenche la sélection (A-01)."""

    def __init__(
        self,
        *,
        row: int,
        on_select: Callable[[int], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._row = row
        self._on_select = on_select
        self.setObjectName("card")
        self.setProperty("card", True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self.setMinimumWidth(0)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._on_select(self._row)
            event.accept()
            return
        super().mousePressEvent(event)


class HistoryPage(QWidget):
    def __init__(
        self,
        db: Database,
        parent=None,
        *,
        config: AppConfig | None = None,
        on_busy: Callable[[bool], None] | None = None,
        on_library_changed: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self._db = db
        self._config = config or AppConfig()
        self._on_busy = on_busy
        self._on_library_changed = on_library_changed
        self._rows: list[JobRow] = []
        self._selected: JobRow | None = None
        self._recovery_thread: QThread | None = None
        self._recovery_worker: RecoveryWorker | None = None
        self._action_guard = False

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 20, 28, 20)
        root.setSpacing(12)

        title = QLabel("Historique")
        title.setObjectName("pageTitle")
        title.setAccessibleName("Historique des opérations")
        root.addWidget(title)

        help_lbl = QLabel(
            "Ce qui s’est passé — en langage clair. Aucune suppression automatique. "
            "La reprise utilise les fichiers déjà extraits (pas une extraction à la piste)."
        )
        help_lbl.setObjectName("heroSub")
        help_lbl.setWordWrap(True)
        root.addWidget(help_lbl)

        self.lbl_reconcile = QLabel("")
        self.lbl_reconcile.setObjectName("muted")
        self.lbl_reconcile.setWordWrap(True)
        self.lbl_reconcile.hide()
        root.addWidget(self.lbl_reconcile)

        tools = QHBoxLayout()
        self.btn_refresh = QPushButton("Actualiser")
        self.btn_refresh.setProperty("ghost", True)
        self.btn_refresh.setAccessibleName("Actualiser l’historique")
        self.btn_refresh.clicked.connect(self.refresh)
        tools.addWidget(self.btn_refresh)
        tools.addStretch(1)
        root.addLayout(tools)

        # Table masquée : compatibilité tests 06H (rowCount / selectRow)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Date", "État", "Mode", "Identifiant"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAccessibleName("Liste des opérations")
        self.table.itemSelectionChanged.connect(self._on_table_select)
        self.table.hide()
        root.addWidget(self.table)

        body = QHBoxLayout()
        body.setSpacing(16)

        self.list = QListWidget()
        self.list.setObjectName("historyCards")
        self.list.setAccessibleName("Cartes des opérations")
        self.list.setSpacing(6)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.list.setUniformItemSizes(False)
        self.list.setWordWrap(True)
        self.list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.list.currentRowChanged.connect(self._on_card_row)
        body.addWidget(self.list, 3)

        detail_card = QFrame()
        detail_card.setObjectName("card")
        detail_card.setProperty("card", True)
        detail_card.setMinimumWidth(200)
        dv = QVBoxLayout(detail_card)
        dv.setContentsMargins(16, 14, 16, 14)
        dv.setSpacing(10)
        self.lbl_detail = QLabel("Sélectionnez une opération.")
        self.lbl_detail.setWordWrap(True)
        self.lbl_detail.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        dv.addWidget(self.lbl_detail)
        self.txt_detail = QTextEdit()
        self.txt_detail.setReadOnly(True)
        self.txt_detail.setAccessibleName("Détails de l’opération")
        self.txt_detail.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.txt_detail.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        dv.addWidget(self.txt_detail, 1)

        # Actions empilées : évite la troncature aux largeurs étroites (A-02)
        actions = QVBoxLayout()
        actions.setSpacing(6)
        self.btn_open_album = QPushButton("Ouvrir l’album")
        self.btn_open_album.setProperty("primary", True)
        self.btn_open_album.setEnabled(False)
        self.btn_open_album.setMinimumWidth(0)
        self.btn_open_album.setMinimumHeight(36)
        self.btn_open_album.clicked.connect(self._open_album)
        self.btn_open_work = QPushButton("Ouvrir le dossier temporaire")
        self.btn_open_work.setProperty("ghost", True)
        self.btn_open_work.setEnabled(False)
        self.btn_open_work.setMinimumWidth(0)
        self.btn_open_work.setMinimumHeight(36)
        self.btn_open_work.setToolTip(
            "Fichiers encore présents après un échec ou une annulation (non publiés)."
        )
        self.btn_open_work.clicked.connect(self._open_workdir)
        self.btn_resume = QPushButton("Reprendre depuis les fichiers")
        self.btn_resume.setProperty("primary", True)
        self.btn_resume.setEnabled(False)
        self.btn_resume.setMinimumWidth(0)
        self.btn_resume.setMinimumHeight(36)
        self.btn_resume.setAccessibleName(
            "Reprendre l’archivage depuis les fichiers FLAC existants"
        )
        self.btn_resume.setToolTip(
            "Crée une nouvelle opération à partir des FLAC déjà présents. "
            "Ne reprend pas une extraction CD à la piste interrompue."
        )
        self.btn_resume.clicked.connect(self._resume_from_files)
        self.btn_abandon = QPushButton("Abandonner")
        self.btn_abandon.setProperty("ghost", True)
        self.btn_abandon.setEnabled(False)
        self.btn_abandon.setMinimumWidth(0)
        self.btn_abandon.setMinimumHeight(36)
        self.btn_abandon.setAccessibleName("Abandonner l’opération sans supprimer les fichiers")
        self.btn_abandon.clicked.connect(self._abandon)
        actions.addWidget(self.btn_open_album)
        actions.addWidget(self.btn_open_work)
        actions.addWidget(self.btn_resume)
        actions.addWidget(self.btn_abandon)
        dv.addLayout(actions)
        body.addWidget(detail_card, 2)
        root.addLayout(body, 1)

        self.lbl_empty = QLabel("Aucune opération enregistrée.")
        self.lbl_empty.setProperty("role", "muted")
        root.addWidget(self.lbl_empty)

    def refresh(self) -> None:
        prev_id = self._selected.id if self._selected else None
        self._rows = list_jobs(self._db)
        self.table.setRowCount(len(self._rows))
        self.list.blockSignals(True)
        # Couper les callbacks avant destruction des cartes (évite crash teardown Qt)
        for i in range(self.list.count()):
            w = self.list.itemWidget(self.list.item(i))
            if isinstance(w, SelectableJobCard):
                w._on_select = lambda _row: None
        self.list.clear()
        for i, job in enumerate(self._rows):
            date = (job.finished_at or job.started_at or "—")[:19]
            state = state_label_fr(job.state)
            if job.files_recoverable:
                state += " · fichiers récupérables"
            mode = {
                "normal": "Archivage",
                "technical_test": "Test technique",
            }.get(job.mode or "", job.mode or "—")
            self.table.setItem(i, 0, QTableWidgetItem(date))
            self.table.setItem(i, 1, QTableWidgetItem(state))
            self.table.setItem(i, 2, QTableWidgetItem(mode))
            self.table.setItem(i, 3, QTableWidgetItem(job.id[:8] + "…"))
            self.table.item(i, 0).setData(Qt.ItemDataRole.UserRole, job.id)

            card = self._build_job_card(job, row=i)
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, job.id)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            # Largeur flexible : éviter hint trop large (A-02)
            hint = card.sizeHint()
            hint.setWidth(120)
            item.setSizeHint(hint)
            self.list.addItem(item)
            self.list.setItemWidget(item, card)
            # Recalcul après placement dans la liste
            self._relayout_card(item, card)

        self.list.blockSignals(False)
        empty = len(self._rows) == 0
        self.lbl_empty.setVisible(empty)
        self.list.setVisible(not empty)
        if empty:
            self._selected = None
            self.lbl_detail.setText("Aucune opération.")
            self.txt_detail.clear()
            self._update_actions()
            return

        # Restaurer sélection si possible
        restore = 0
        if prev_id:
            for i, job in enumerate(self._rows):
                if job.id == prev_id:
                    restore = i
                    break
        self.select_row(restore)

    def select_row(self, row: int) -> None:
        """API test / clavier / clic carte — synchronise liste + table + détail."""
        if row < 0 or row >= len(self._rows):
            return
        self.list.blockSignals(True)
        self.table.blockSignals(True)
        self.list.setCurrentRow(row)
        self.table.selectRow(row)
        self.list.blockSignals(False)
        self.table.blockSignals(False)
        self._show_job_at(row)

    def _relayout_card(self, item: QListWidgetItem, card: QWidget) -> None:
        viewport_w = max(160, self.list.viewport().width() - 16)
        card.setMaximumWidth(viewport_w)
        card.adjustSize()
        hint = card.sizeHint()
        hint.setWidth(min(hint.width(), viewport_w))
        item.setSizeHint(hint)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        for i in range(self.list.count()):
            item = self.list.item(i)
            card = self.list.itemWidget(item)
            if item and card:
                self._relayout_card(item, card)

    def _build_job_card(self, job: JobRow, *, row: int) -> SelectableJobCard:
        card = SelectableJobCard(row=row, on_select=self.select_row)
        card.setAccessibleName(
            f"Opération {state_label_fr(job.state)} du "
            f"{(job.finished_at or job.started_at or '')[:19]}"
        )
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(6)

        top = QHBoxLayout()
        top.setSpacing(8)
        left = QVBoxLayout()
        left.setSpacing(2)
        when = QLabel((job.finished_at or job.started_at or "—")[:19].replace("T", " "))
        when.setObjectName("muted")
        when.setWordWrap(True)
        left.addWidget(when)
        title = QLabel(
            {
                "normal": "Archivage CD → FLAC",
                "technical_test": "Test technique",
            }.get(job.mode or "", "Opération")
        )
        title.setObjectName("cardTitle")
        title.setWordWrap(True)
        left.addWidget(title)
        summary, _ = humanize_error_for_user(job.error_summary)
        if job.state in {"Completed", "CompletedWithWarnings"} and (
            not job.error_summary or summary == "Une erreur est survenue."
        ):
            detail_txt = "Opération terminée."
        else:
            detail_txt = summary if summary else "Sans message particulier."
        detail = QLabel(detail_txt)
        detail.setObjectName("muted")
        detail.setWordWrap(True)
        left.addWidget(detail)
        top.addLayout(left, 1)

        badges = QVBoxLayout()
        badges.setSpacing(4)
        badges.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        state_chip = make_chip(_chip_state_text(job.state), _chip_role(job.state))
        state_chip.setToolTip(state_label_fr(job.state))
        state_chip.setMinimumWidth(0)
        badges.addWidget(state_chip)
        if job.files_recoverable:
            rec = make_chip("Récupérable", "warn")
            rec.setToolTip("Des fichiers temporaires sont encore présents.")
            badges.addWidget(rec)
        top.addLayout(badges)
        lay.addLayout(top)

        hints = []
        if job.library_exists:
            hints.append("Album publié disponible")
        if job.files_recoverable:
            hints.append("Fichiers temporaires encore présents")
        if job.state == "CompletedWithWarnings":
            hints.append("Terminé avec avertissements")
        if job.unfinished_active:
            hints.append("État actif non terminé — voir détails")
        if hints:
            h = QLabel(" · ".join(hints))
            h.setObjectName("muted")
            h.setWordWrap(True)
            lay.addWidget(h)

        # Enfants : laisser remonter le clic à la carte
        for child in card.findChildren(QWidget):
            if child is card:
                continue
            child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        return card

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.refresh()

    def closeEvent(self, event) -> None:  # noqa: N802
        for i in range(self.list.count()):
            w = self.list.itemWidget(self.list.item(i))
            if isinstance(w, SelectableJobCard):
                w._on_select = lambda _row: None
        self.list.clear()
        super().closeEvent(event)

    def _job_by_id(self, jid: str) -> JobRow | None:
        for j in self._rows:
            if j.id == jid:
                return j
        return None

    def _on_card_row(self, row: int) -> None:
        if row < 0 or row >= self.table.rowCount():
            return
        self.table.blockSignals(True)
        self.table.selectRow(row)
        self.table.blockSignals(False)
        self._show_job_at(row)

    def _on_table_select(self) -> None:
        items = self.table.selectedItems()
        if not items:
            self._selected = None
            self._update_actions()
            return
        row = items[0].row()
        if self.list.currentRow() != row:
            self.list.blockSignals(True)
            self.list.setCurrentRow(row)
            self.list.blockSignals(False)
        self._show_job_at(row)

    def _show_job_at(self, row: int) -> None:
        jid = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        job = self._job_by_id(str(jid))
        self._selected = job
        if job is None:
            return
        flac_n = len(list_job_flac_files(job.workdir)) if job.workdir_exists else 0
        if job.unfinished_active:
            recover = (
                "Opération encore marquée active (non terminée). "
                "Si l’application a planté, la réconciliation au démarrage "
                "la passera en « Interrompu » seulement si aucune extraction n’est active."
            )
        elif job.files_recoverable:
            recover = (
                f"Fichiers récupérables : {flac_n} FLAC dans le dossier temporaire "
                "(non publiés automatiquement)."
            )
        else:
            recover = ""
        self.lbl_detail.setText(
            f"{state_label_fr(job.state)}\n"
            f"Début : {(job.started_at or '—')[:19]} · Fin : {(job.finished_at or '—')[:19]}\n"
            f"{recover}"
        )
        if job.error_summary:
            summary, tech = humanize_error_for_user(job.error_summary)
        elif job.state in {"Completed", "CompletedWithWarnings", "SkippedDuplicate"}:
            summary, tech = "Opération terminée.", None
        elif job.state == "Abandoned":
            summary, tech = "Opération abandonnée (fichiers non supprimés).", None
        elif job.state == "Cancelled":
            summary, tech = "Annulé par l’utilisateur.", None
        else:
            summary, tech = humanize_error_for_user(job.error_summary)
        collision = {
            "rename": "Créer un nouveau dossier en cas de doublon",
            "skip": "Ne pas publier si l’album existe",
            "replace": "Remplacer (corbeille locale)",
        }.get(job.collision_policy or "", job.collision_policy or "—")
        album_lbl = (
            friendly_path_label(job.library_path)
            if job.library_path
            else "non"
        )
        work_lbl = (
            friendly_path_label(job.workdir) if job.workdir else "aucun"
        )
        lines = [
            f"Référence : {job.id}",
            f"En cas de doublon : {collision}",
            f"Album publié : {album_lbl}",
            f"Dossier temporaire : {work_lbl}",
            "",
            f"Message : {summary}",
        ]
        tips = []
        if job.library_path:
            tips.append(f"Album : {job.library_path}")
        if job.workdir:
            tips.append(f"Temporaire : {job.workdir}")
        self.txt_detail.setToolTip("\n".join(tips) if tips else "")
        if tech:
            lines.extend(["", "Détail technique :", tech])
        if job.files_recoverable:
            lines.extend(
                [
                    "",
                    f"Fichiers récupérables : {flac_n} FLAC — "
                    "« Ouvrir le dossier temporaire » ou "
                    "« Reprendre depuis les fichiers » (si éligible).",
                    "Important : la reprise ne continue pas un rip fre:ac à mi-piste.",
                ]
            )
        if job.metadata_id:
            lines.append(f"Fiche métadonnées : {job.metadata_id}")
        warns = job.warnings
        lines.append("")
        lines.append("Avertissements :")
        if warns:
            lines.extend(f"• {w}" for w in warns[:12])
        else:
            lines.append("• (aucun)")
        self.txt_detail.setPlainText("\n".join(lines))
        self._update_actions()

    def set_reconcile_banner(self, text: str) -> None:
        if text.strip():
            self.lbl_reconcile.setText(text)
            self.lbl_reconcile.show()
        else:
            self.lbl_reconcile.hide()

    def is_recovery_busy(self) -> bool:
        return self._recovery_thread is not None

    def shutdown_background_work(self) -> bool:
        return shutdown_worker_thread(self._recovery_thread, self._recovery_worker)

    def _update_actions(self) -> None:
        job = self._selected
        busy = self._recovery_thread is not None or self._action_guard
        if job is None:
            self.btn_open_album.setEnabled(False)
            self.btn_open_work.setEnabled(False)
            self.btn_resume.setEnabled(False)
            self.btn_resume.setVisible(True)
            self.btn_abandon.setEnabled(False)
            return
        self.btn_open_album.setEnabled(job.library_exists and not busy)
        self.btn_open_work.setEnabled(job.workdir_exists and not busy)
        terminal = job.state in {
            "Completed",
            "CompletedWithWarnings",
            "Abandoned",
            "SkippedDuplicate",
        }
        self.btn_abandon.setEnabled(not terminal and not busy)
        # Reprise visible dès qu’il y a un workdir récupérable ; éligibilité réelle au clic
        can_offer_resume = (
            job.files_recoverable
            and bool(job.metadata_id)
            and job.state in {"Failed", "Cancelled", "Interrupted", "Abandoned"}
            and not busy
            and recovery_in_progress() is None
        )
        self.btn_resume.setVisible(True)
        self.btn_resume.setEnabled(can_offer_resume)
        self.btn_open_album.setProperty("primary", job.library_exists)
        self.btn_resume.setProperty("primary", can_offer_resume and not job.library_exists)
        self.btn_open_work.setProperty(
            "primary",
            (not job.library_exists) and job.files_recoverable and not can_offer_resume,
        )
        for w in (self.btn_open_album, self.btn_open_work, self.btn_resume):
            w.style().unpolish(w)
            w.style().polish(w)

    def _open_album(self) -> None:
        job = self._selected
        if not job or not job.library_path:
            return
        path = Path(job.library_path)
        if path.is_dir():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        else:
            QMessageBox.warning(self, "Album", "Le dossier album est introuvable.")

    def _open_workdir(self) -> None:
        job = self._selected
        if not job or not job.workdir:
            return
        path = Path(job.workdir)
        if path.is_dir():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        else:
            QMessageBox.warning(
                self, "Dossier temporaire", "Le dossier temporaire n’existe plus."
            )

    def _abandon(self) -> None:
        job = self._selected
        if not job or self._action_guard:
            return
        if job.state == "Abandoned":
            QMessageBox.information(
                self,
                "Abandonner",
                "Cette opération est déjà marquée abandonnée. Aucun fichier n’a été modifié.",
            )
            return
        reply = QMessageBox.question(
            self,
            "Abandonner",
            "Marquer cette opération comme abandonnée ?\n\n"
            "• L’état du job sera mis à jour dans la base.\n"
            "• Aucun fichier ne sera supprimé, déplacé ni écrasé "
            "(bibliothèque et dossier temporaire inchangés).",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._action_guard = True
        try:
            changed = mark_job_abandoned(self._db, job.id)
            if not changed:
                QMessageBox.information(
                    self,
                    "Abandonner",
                    "Aucune modification (déjà abandonnée ou état terminal).",
                )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Abandonner", str(exc))
        finally:
            self._action_guard = False
        self.refresh()

    def _resume_from_files(self) -> None:
        job = self._selected
        if not job or self._action_guard or self._recovery_thread is not None:
            return
        if recovery_in_progress() is not None:
            QMessageBox.warning(
                self,
                "Reprise",
                "Une récupération est déjà en cours. Attendez la fin.",
            )
            return

        self._action_guard = True
        try:
            assessment = assess_recovery_from_files(
                self._db,
                job.id,
                skip_optical_probe=False,
                allow_offline=False,
            )
        finally:
            self._action_guard = False

        if assessment.verdict == RecoveryVerdict.DENY:
            QMessageBox.warning(
                self,
                "Reprise impossible",
                assessment.summary_fr
                + (
                    "\n\n" + "\n".join(assessment.detail_lines[:6])
                    if assessment.detail_lines
                    else ""
                ),
            )
            return

        allow_offline = False
        confirmed_rearchive = False

        if assessment.verdict == RecoveryVerdict.REQUIRE_CONFIRM:
            if assessment.offline_disc:
                reply = QMessageBox.question(
                    self,
                    "Reprise hors ligne",
                    assessment.summary_fr
                    + "\n\nConfirmer la reprise sans relecture du disque ?",
                )
                if reply != QMessageBox.StandardButton.Yes:
                    return
                allow_offline = True
            if assessment.requires_rearchive_confirmation:
                reply = QMessageBox.question(
                    self,
                    "Réarchivage",
                    assessment.summary_fr
                    + "\n\nConfirmer le réarchivage volontaire ?",
                )
                if reply != QMessageBox.StandardButton.Yes:
                    return
                confirmed_rearchive = True

        n_flac = len(assessment.flac_files)
        reply = QMessageBox.question(
            self,
            "Reprendre depuis les fichiers",
            f"Créer une nouvelle opération d’archivage à partir de {n_flac} fichier(s) FLAC "
            f"déjà présents ?\n\n"
            "• Ce n’est pas une reprise d’extraction CD à la piste.\n"
            "• Les fichiers source ne seront ni supprimés ni déplacés.\n"
            "• Publication : politique « nouveau dossier » en cas de collision.",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        worker = RecoveryWorker(
            source_job_id=job.id,
            library_root=Path(self._config.library_root),
            jobs_root=Path(self._config.jobs_dir),
            db_path=self._db.path,
            collision_policy=CollisionPolicy.RENAME,
            confirm_publish=True,
            confirmed_rearchive=confirmed_rearchive,
            allow_offline=allow_offline,
            skip_optical_probe=False,
        )
        thread = attach_worker_thread(
            worker,
            on_finished=self._on_recovery_finished,
            on_failed=self._on_recovery_failed,
            on_cleared=self._clear_recovery,
            progress_slot=self._on_recovery_progress,
        )
        self._recovery_worker = worker
        self._recovery_thread = thread
        if self._on_busy:
            self._on_busy(True)
        self._update_actions()
        thread.start()

    def _on_recovery_progress(self, message: str, _fraction: object) -> None:
        self.lbl_detail.setText(f"Récupération en cours…\n{message}")

    def _on_recovery_finished(self, report: object) -> None:
        state = getattr(report, "state", "")
        job_id = getattr(report, "job_id", "")
        if str(state).startswith("Completed"):
            QMessageBox.information(
                self,
                "Récupération",
                f"Nouvelle opération terminée (réf. {str(job_id)[:8]}…).\n"
                "Les fichiers du job d’origine n’ont pas été supprimés.",
            )
            if self._on_library_changed:
                self._on_library_changed()
        else:
            err = getattr(report, "error", None) or state
            QMessageBox.warning(
                self,
                "Récupération",
                f"La nouvelle opération s’est terminée avec l’état « {state} ».\n{err}",
            )
        self.refresh()

    def _on_recovery_failed(self, message: str) -> None:
        QMessageBox.critical(self, "Récupération", message)
        self.refresh()

    def _clear_recovery(self) -> None:
        self._recovery_thread = None
        self._recovery_worker = None
        if self._on_busy:
            self._on_busy(False)
        self._update_actions()
