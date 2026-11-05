"""Décodage intégral FLAC (CRC trames) via ffmpeg si disponible."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FlacDecodeResult:
    path: Path
    attempted: bool
    ok: bool
    tool: str | None
    message: str


def find_flac_decode_tool() -> Path | None:
    """
    Cherche un décodeur en lecture seule.

    Ordre : ``AVM_FFMPEG`` → PATH ``ffmpeg`` → fre:ac ``codecs/cmdline/ffmpeg.exe``.
    """
    env = (os.environ.get("AVM_FFMPEG") or "").strip()
    if env:
        p = Path(env)
        if p.is_file():
            return p
    which = shutil.which("ffmpeg")
    if which:
        return Path(which)
    freac = Path(r"C:\Program Files\freac\codecs\cmdline\ffmpeg.exe")
    if freac.is_file():
        return freac
    return None


def require_flac_decode() -> bool:
    """Politique stricte optionnelle : ``AVM_REQUIRE_FLAC_DECODE=1`` bloque sans ffmpeg."""
    return (os.environ.get("AVM_REQUIRE_FLAC_DECODE") or "").strip() in {
        "1",
        "true",
        "yes",
        "on",
    }


def decode_flac_full(
    path: Path,
    *,
    tool: Path | None = None,
    timeout_sec: float = 120.0,
) -> FlacDecodeResult:
    """
    Décode entièrement le fichier vers null (vérifie les trames / CRC côté décodeur).

    Si aucun outil : ``attempted=False``, ``ok=False`` — **pas** un succès fictif.
    Le pipeline décide (avertissement V1 vs blocage si ``AVM_REQUIRE_FLAC_DECODE``).
    """
    p = Path(path)
    decoder = tool or find_flac_decode_tool()
    if decoder is None:
        return FlacDecodeResult(
            p,
            attempted=False,
            ok=False,
            tool=None,
            message=(
                "Décodage intégral non exécuté — ffmpeg introuvable "
                "(installez ffmpeg ou définissez AVM_FFMPEG). "
                "Contrôle structurel F-08a seul ; ce n’est pas une validation CRC."
            ),
        )
    if not p.is_file():
        return FlacDecodeResult(
            p, True, False, str(decoder), "fichier absent pour décodage"
        )
    try:
        proc = subprocess.run(
            [str(decoder), "-v", "error", "-i", str(p), "-f", "null", "-"],
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0,
        )
    except subprocess.TimeoutExpired:
        return FlacDecodeResult(
            p, True, False, str(decoder), f"timeout décodage ({timeout_sec}s)"
        )
    except OSError as exc:
        return FlacDecodeResult(
            p, True, False, str(decoder), f"échec lancement décodeur : {exc}"
        )
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()[:300]
        return FlacDecodeResult(
            p,
            True,
            False,
            str(decoder),
            f"décodage échoué rc={proc.returncode}" + (f" — {err}" if err else ""),
        )
    return FlacDecodeResult(
        p, True, True, str(decoder), "décodage intégral OK (ffmpeg null)"
    )


def decode_many(
    paths: list[Path],
    *,
    tool: Path | None = None,
) -> list[FlacDecodeResult]:
    resolved = tool or find_flac_decode_tool()
    return [decode_flac_full(p, tool=resolved) for p in paths]
