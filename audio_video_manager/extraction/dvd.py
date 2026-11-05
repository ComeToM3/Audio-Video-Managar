"""Extraction DVD — reportée (D-010). Placeholder de module uniquement."""

from __future__ import annotations


class DvdExtractionNotAvailableError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("L'extraction DVD est reportée (décision D-010).")
