"""Persistance stdout/stderr fre:ac par job (ne masque pas les erreurs)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def freac_log_dir(rip_workdir: Path) -> Path:
    """Dossier job parent si workdir = …/rip, sinon workdir lui-même."""
    wd = Path(rip_workdir)
    return wd.parent if wd.name.lower() == "rip" else wd


def persist_freac_logs(
    rip_workdir: Path,
    *,
    argv: tuple[str, ...] | list[str],
    returncode: int | None,
    stdout: str,
    stderr: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Path]:
    """
    Écrit freac_stdout.txt, freac_stderr.txt, freac_meta.json.

    Retourne les chemins créés. N’efface jamais d’autres fichiers du job.
    """
    root = freac_log_dir(rip_workdir)
    root.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    out = root / "freac_stdout.txt"
    err = root / "freac_stderr.txt"
    meta = root / "freac_meta.json"
    out.write_text(stdout or "", encoding="utf-8")
    err.write_text(stderr or "", encoding="utf-8")
    payload = {
        "argv": list(argv),
        "returncode": returncode,
        "stdout_chars": len(stdout or ""),
        "stderr_chars": len(stderr or ""),
        **(extra or {}),
    }
    meta.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    paths["stdout"] = out
    paths["stderr"] = err
    paths["meta"] = meta
    return paths
