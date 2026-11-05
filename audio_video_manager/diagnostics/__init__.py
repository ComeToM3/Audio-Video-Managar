"""Diagnostics utilisateur et classification d'erreurs."""

from audio_video_manager.diagnostics.failure_kinds import (
    FailureKind,
    classify_freac_returncode,
    format_user_error,
    freac_signed_code,
)
from audio_video_manager.diagnostics.freac_logs import persist_freac_logs

__all__ = [
    "FailureKind",
    "classify_freac_returncode",
    "format_user_error",
    "freac_signed_code",
    "persist_freac_logs",
]
