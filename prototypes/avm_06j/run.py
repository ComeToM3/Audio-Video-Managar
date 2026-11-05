#!/usr/bin/env python3
"""Lance le prototype UX AVM-06J (isolé du pipeline métier)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from prototypes.avm_06j.app import run

if __name__ == "__main__":
    raise SystemExit(run())
