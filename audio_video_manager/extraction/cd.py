"""Détection et validation non destructive de freaccmd (pas de rip)."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from audio_video_manager.logging_setup import get_logger

log = get_logger("extraction.cd")

# Emplacements Windows courants (lecture seule).
_DEFAULT_CANDIDATES = (
    Path(r"C:\Program Files\freac\freaccmd.exe"),
    Path(r"C:\Program Files (x86)\freac\freaccmd.exe"),
)

_PROBE_TIMEOUT_SEC = 15


@dataclass(frozen=True)
class CommandProbe:
    """Résultat brut d'une invocation — jamais inventé."""

    argv: tuple[str, ...]
    returncode: int | None
    stdout: str
    stderr: str
    error: str | None = None


@dataclass
class FreaccmdStatus:
    """État de la CLI fre:ac pour l'UI et les tests."""

    found: bool
    path: Path | None = None
    message: str = ""
    help_probe: CommandProbe | None = None
    list_drives_probe: CommandProbe | None = None
    candidate_paths_checked: tuple[str, ...] = field(default_factory=tuple)

    @property
    def ok_for_phase1(self) -> bool:
        """Phase 0 : présence du binaire. Phase 1 exigera des probes réussis."""
        return self.found and self.path is not None


def _unique_existing(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    out: list[Path] = []
    for p in paths:
        key = str(p).lower()
        if key in seen:
            continue
        seen.add(key)
        if p.is_file():
            out.append(p)
    return out


def discover_freaccmd_candidates(
    *,
    configured_path: str | Path | None = None,
    freac_install_dir: str | Path | None = None,
    include_system_defaults: bool = True,
    include_path_lookup: bool = True,
) -> list[Path]:
    """Liste ordonnée de chemins freaccmd à tester (fichiers existants uniquement)."""
    ordered: list[Path] = []

    if configured_path:
        ordered.append(Path(configured_path))

    if freac_install_dir:
        install = Path(freac_install_dir)
        ordered.append(install / "freaccmd.exe")
        ordered.append(install / "freaccmd")

    if include_path_lookup:
        which = shutil.which("freaccmd") or shutil.which("freaccmd.exe")
        if which:
            ordered.append(Path(which))

    if include_system_defaults:
        ordered.extend(_DEFAULT_CANDIDATES)

    return _unique_existing(ordered)


def find_freac_install_hint() -> Path | None:
    """Retourne le dossier fre:ac s'il contient freac.exe (indice UI)."""
    for base in (
        Path(r"C:\Program Files\freac"),
        Path(r"C:\Program Files (x86)\freac"),
    ):
        if (base / "freac.exe").is_file():
            return base
    return None


def _run_probe(executable: Path, *args: str) -> CommandProbe:
    argv = (str(executable), *args)
    creationflags = 0
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        completed = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_PROBE_TIMEOUT_SEC,
            check=False,
            creationflags=creationflags,
        )
        return CommandProbe(
            argv=argv,
            returncode=completed.returncode,
            stdout=completed.stdout or "",
            stderr=completed.stderr or "",
        )
    except FileNotFoundError as exc:
        return CommandProbe(argv=argv, returncode=None, stdout="", stderr="", error=str(exc))
    except subprocess.TimeoutExpired as exc:
        out = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
        err = (exc.stderr or "") if isinstance(exc.stderr, str) else ""
        return CommandProbe(
            argv=argv,
            returncode=None,
            stdout=out,
            stderr=err,
            error=f"timeout after {_PROBE_TIMEOUT_SEC}s",
        )
    except OSError as exc:
        return CommandProbe(argv=argv, returncode=None, stdout="", stderr="", error=str(exc))


def validate_freaccmd(executable: Path) -> tuple[CommandProbe, CommandProbe]:
    """
    Validations non destructives uniquement.

    - Aide : exécutable sans argument (comportement documenté fre:ac).
    - Lecteurs : ``--list-drives`` (pas de rip, pas d'éjection forcée ici).

    Les sorties sont celles du processus ; aucun texte n'est inventé.
    """
    help_probe = _run_probe(executable)
    list_drives_probe = _run_probe(executable, "--list-drives")
    return help_probe, list_drives_probe


def probe_freaccmd(
    *,
    configured_path: str | Path | None = None,
    freac_install_dir: str | Path | None = None,
    run_probes: bool = True,
    include_system_defaults: bool = True,
    include_path_lookup: bool = True,
) -> FreaccmdStatus:
    """
    Détecte freaccmd et, si trouvé, lance les probes non destructifs.

    Si absent : ``found=False`` et message explicite.
    """
    checked: list[str] = []
    for c in (
        Path(configured_path) if configured_path else None,
        Path(freac_install_dir) / "freaccmd.exe" if freac_install_dir else None,
    ):
        if c is not None:
            checked.append(str(c))
    if include_system_defaults:
        checked.extend(str(p) for p in _DEFAULT_CANDIDATES)

    candidates = discover_freaccmd_candidates(
        configured_path=configured_path,
        freac_install_dir=freac_install_dir,
        include_system_defaults=include_system_defaults,
        include_path_lookup=include_path_lookup,
    )

    if not candidates:
        hint = find_freac_install_hint()
        if hint is not None:
            message = (
                f"freaccmd.exe introuvable. fre:ac GUI détecté dans {hint} "
                "mais la CLI est absente. Réinstallez le paquet ZIP/installeur "
                "officiel (pas Microsoft Store), puis indiquez le chemin dans les paramètres."
            )
        else:
            message = (
                "freaccmd.exe introuvable. Installez fre:ac depuis freac.org "
                "(installeur ou ZIP, pas Microsoft Store) et configurez le chemin."
            )
        log.warning(message)
        return FreaccmdStatus(
            found=False,
            path=None,
            message=message,
            candidate_paths_checked=tuple(checked),
        )

    exe = candidates[0]
    log.info("freaccmd trouvé : %s", exe)

    help_probe = None
    list_drives_probe = None
    if run_probes:
        help_probe, list_drives_probe = validate_freaccmd(exe)
        log.info(
            "Probe aide returncode=%s error=%s",
            help_probe.returncode,
            help_probe.error,
        )
        log.info(
            "Probe --list-drives returncode=%s error=%s",
            list_drives_probe.returncode,
            list_drives_probe.error,
        )

    return FreaccmdStatus(
        found=True,
        path=exe,
        message=f"freaccmd détecté : {exe}",
        help_probe=help_probe,
        list_drives_probe=list_drives_probe,
        candidate_paths_checked=tuple(checked),
    )
