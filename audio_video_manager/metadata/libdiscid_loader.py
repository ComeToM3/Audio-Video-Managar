"""Localisation de la DLL native libdiscid (Windows) — pas d'install système."""

from __future__ import annotations

import os
import sys
from pathlib import Path


class LibdiscidMissingError(RuntimeError):
    """DLL / bibliothèque native introuvable ou non chargeable."""


def _project_roots() -> list[Path | None]:
    here = Path(__file__).resolve()
    repo = here.parents[2]
    return [
        repo / "vendor" / "libdiscid",
        Path(os.environ["AVM_LIBDISCID_DIR"]) if os.environ.get("AVM_LIBDISCID_DIR") else None,
        Path.cwd() / "vendor" / "libdiscid",
    ]


def candidate_dll_dirs() -> list[Path]:
    arch = "x64" if sys.maxsize > 2**32 else "Win32"
    dirs: list[Path] = []
    for root in _project_roots():
        if root is None:
            continue
        dirs.append(root / "libdiscid-0.6.4-win" / arch)
        dirs.append(root / arch)
        dirs.append(root)
    seen: set[str] = set()
    out: list[Path] = []
    for d in dirs:
        key = str(d.resolve()) if d.exists() else str(d)
        if key in seen:
            continue
        seen.add(key)
        out.append(d)
    return out


def find_discid_dll() -> Path | None:
    name = "discid.dll" if os.name == "nt" else "libdiscid.so"
    for d in candidate_dll_dirs():
        candidate = d / ("discid.dll" if os.name == "nt" else name)
        if os.name != "nt":
            # Linux/mac: leave to system loader mostly
            for pattern in ("libdiscid.so", "libdiscid.dylib"):
                c = d / pattern
                if c.is_file():
                    return c
            continue
        if candidate.is_file():
            return candidate
    return None


def prepare_libdiscid_search_path() -> Path | None:
    """Ajoute le dossier DLL au PATH / add_dll_directory avant ``import discid``."""
    dll = find_discid_dll()
    if dll is None:
        return None
    directory = str(dll.parent.resolve())
    if hasattr(os, "add_dll_directory"):
        try:
            os.add_dll_directory(directory)
        except OSError:
            pass
    path = os.environ.get("PATH", "")
    if directory.lower() not in path.lower():
        os.environ["PATH"] = directory + os.pathsep + path
    return dll


def import_discid():
    """Import ``discid`` après préparation du chemin native."""
    prepare_libdiscid_search_path()
    try:
        import discid  # type: ignore
    except OSError as exc:
        raise LibdiscidMissingError(
            "Impossible de charger libdiscid (DLL native). "
            "Placez discid.dll (x64) sous vendor/libdiscid/libdiscid-*-win/x64/ "
            "ou définissez AVM_LIBDISCID_DIR. "
            f"Détail: {exc}"
        ) from exc
    except ImportError as exc:
        raise LibdiscidMissingError(
            "Le paquet Python « discid » n'est pas installé (pip install discid)."
        ) from exc
    return discid
