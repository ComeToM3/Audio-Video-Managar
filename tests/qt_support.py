"""Support Qt pour tests — teardown ordonné (AVM-10C / 10C.1 / 10C.2).

Règles dures :
- jamais ``gc.collect()`` / ``gc_collect_harder`` côté harness ;
- ``deleteLater`` + drain ``DeferredDelete`` seulement ;
- ``os._exit`` = contournement CI optionnel (``AVM_QT_SAFE_EXIT=1``), jamais une preuve GO.
"""

from __future__ import annotations

import os
from typing import Any

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_tracked: list[Any] = []


def ensure_qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def track_widget(widget: Any) -> Any:
    if widget is not None and widget not in _tracked:
        _tracked.append(widget)
    return widget


def clear_tracked() -> None:
    _tracked.clear()


def drain_deferred_deletes(*, rounds: int = 12) -> None:
    """Traite les ``deleteLater`` sans forcer le GC Python."""
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        return
    for _ in range(max(1, rounds)):
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.processEvents()


def _call_shutdown_ui(obj: Any) -> None:
    shutdown = getattr(obj, "shutdown_ui", None)
    if callable(shutdown):
        try:
            shutdown()
        except RuntimeError:
            pass
    lib = getattr(obj, "page_library", None)
    if lib is not None:
        nested = getattr(lib, "shutdown_ui", None)
        if callable(nested):
            try:
                nested()
            except RuntimeError:
                pass


def _shutdown_background(obj: Any) -> None:
    """Arrêt best-effort des workers exposés (MainWindow / pages)."""
    for name in ("shutdown_background_work", "wizard", "page_history"):
        attr = getattr(obj, name, None)
        if name in {"wizard", "page_history"} and attr is not None:
            fn = getattr(attr, "shutdown_background_work", None)
            if callable(fn):
                try:
                    fn()
                except RuntimeError:
                    pass
        elif callable(attr) and name == "shutdown_background_work":
            try:
                attr()
            except RuntimeError:
                pass
    tech = getattr(obj, "_tech_thread", None)
    worker = getattr(obj, "_tech_worker", None)
    if tech is not None:
        try:
            from audio_video_manager.ui.thread_lifecycle import shutdown_worker_thread

            shutdown_worker_thread(tech, worker)
        except Exception:  # noqa: BLE001
            pass
        try:
            obj._tech_thread = None
            obj._tech_worker = None
        except Exception:  # noqa: BLE001
            pass


def dispose_widget(widget: Any) -> None:
    """Fermeture ordonnée d’un widget (idempotent)."""
    if widget is None:
        return
    try:
        from shiboken6 import isValid

        if not isValid(widget):
            return
    except Exception:  # noqa: BLE001
        pass
    _call_shutdown_ui(widget)
    _shutdown_background(widget)
    try:
        if hasattr(widget, "hide"):
            widget.hide()
    except RuntimeError:
        pass
    try:
        if hasattr(widget, "close"):
            widget.close()
    except RuntimeError:
        pass
    # Pas de setParent(None) ici : deleteLater sur le top-level détruit l’arbre
    # une seule fois (évite double destruction parent/enfant).
    try:
        if hasattr(widget, "deleteLater"):
            widget.deleteLater()
    except RuntimeError:
        pass


def shutdown_tracked_widgets(**_kwargs: object) -> None:
    while _tracked:
        dispose_widget(_tracked.pop())
    clear_tracked()
    drain_deferred_deletes()


def shutdown_all_widgets(**_kwargs: object) -> None:
    """Teardown central : tracked + tous les top-level encore vivants."""
    from PySide6.QtWidgets import QApplication, QWidget

    shutdown_tracked_widgets()
    app = QApplication.instance()
    if app is None:
        return
    # Plusieurs passes : deleteLater peut en révéler d’autres
    for _ in range(4):
        tops = list(app.topLevelWidgets())
        if not tops:
            break
        for w in tops:
            if isinstance(w, QWidget):
                dispose_widget(w)
        drain_deferred_deletes(rounds=6)
    drain_deferred_deletes(rounds=8)


def qt_session_cleanup() -> None:
    """Cleanup de fin de session / fin de test — chemin *naturel* (sans os._exit)."""
    shutdown_all_widgets()


def pytest_safe_exit(code: int) -> None:
    """Contournement CI uniquement — ne constitue pas un PASS réel 10C.2."""
    clear_tracked()
    try:
        import faulthandler

        faulthandler.disable()
    except Exception:  # noqa: BLE001
        pass
    os._exit(int(code))
