"""Point d'entrée : ``python -m audio_video_manager``."""

from __future__ import annotations

import sys
import os

from audio_video_manager.diag10e_isolation import IsolationError, validate_10e_environment


def main(argv: list[str] | None = None) -> int:
    if "AVM_10E_MODE" in os.environ:
        try:
            validate_10e_environment()
        except IsolationError as exc:
            print(f"AVM-10E REFUS: {exc}", file=sys.stderr)
            return 2
    from audio_video_manager.ui.main_window import run_app

    return run_app(argv)


if __name__ == "__main__":
    raise SystemExit(main())
