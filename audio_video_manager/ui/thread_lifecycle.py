"""Cycle de vie QThread / workers — éviter « Destroyed while thread is still running »."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QThread


# Attente bornée à la fermeture (ms) — fre:ac peut mettre quelques secondes à s'arrêter
DEFAULT_STOP_TIMEOUT_MS = 12_000


def attach_worker_thread(
    worker: QObject,
    *,
    on_finished: Callable[..., Any] | None = None,
    on_failed: Callable[..., Any] | None = None,
    on_cleared: Callable[[], Any] | None = None,
    progress_slot: Callable[..., Any] | None = None,
) -> QThread:
    """
    Crée un QThread **sans parent widget**.

    Parent widget = destruction du QThread avec la fenêtre alors que le worker
    tourne encore → QThread: Destroyed while thread is still running / 0xC0000409.
    """
    thread = QThread()  # volontairement sans parent
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    if progress_slot is not None and hasattr(worker, "progress"):
        worker.progress.connect(progress_slot)
    if hasattr(worker, "finished"):
        if on_finished is not None:
            worker.finished.connect(on_finished)
        worker.finished.connect(thread.quit)
    if hasattr(worker, "failed"):
        if on_failed is not None:
            worker.failed.connect(on_failed)
        worker.failed.connect(thread.quit)
    # Destruction seulement après terminaison réelle du thread
    thread.finished.connect(worker.deleteLater)
    thread.finished.connect(thread.deleteLater)
    if on_cleared is not None:
        thread.finished.connect(on_cleared)
    return thread


def request_stop_worker(worker: QObject | None) -> None:
    if worker is not None and hasattr(worker, "cancel"):
        worker.cancel()  # type: ignore[operator]


def wait_thread_finished(
    thread: QThread | None,
    *,
    timeout_ms: int = DEFAULT_STOP_TIMEOUT_MS,
) -> bool:
    """
    Demande ``quit()`` si encore actif, puis ``wait`` borné.
    Retourne True si le thread est arrêté (ou absent).
    Ne masque jamais un échec : False si timeout.
    """
    if thread is None:
        return True
    if not thread.isRunning():
        return True
    thread.quit()
    return bool(thread.wait(timeout_ms))


def shutdown_worker_thread(
    thread: QThread | None,
    worker: QObject | None,
    *,
    timeout_ms: int = DEFAULT_STOP_TIMEOUT_MS,
) -> bool:
    """Annulation coopérative + attente bornée. Pas de terminate() silencieux."""
    request_stop_worker(worker)
    return wait_thread_finished(thread, timeout_ms=timeout_ms)
