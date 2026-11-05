"""Fail-closed preflight for the isolated AVM-10E launch path."""

from __future__ import annotations

import json
import os
import stat
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


class IsolationError(RuntimeError):
    """The AVM-10E process is not isolated from production data."""


@dataclass(frozen=True)
class IsolationPaths:
    repo_root: Path
    data_root: Path
    library_root: Path
    config_path: Path
    database_path: Path
    log_dir: Path
    jobs_dir: Path
    freaccmd_path: Path


def _is_reparse_point(info: os.stat_result) -> bool:
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0) & 0x400
    )


def _absolute_path(raw: object, label: str) -> Path:
    if not isinstance(raw, str) or not raw.strip():
        raise IsolationError(f"Chemin requis absent : {label}")
    value = raw.strip()
    path = Path(value)
    if (
        not path.is_absolute()
        or "." in path.parts
        or ".." in path.parts
        or os.path.normcase(value) != os.path.normcase(str(path))
    ):
        raise IsolationError(f"Chemin absolu non canonique : {label}={value!r}")
    return path


def _assert_no_reparse_chain(path: Path) -> None:
    chain: list[Path] = []
    current = path
    while True:
        chain.append(current)
        if current.parent == current:
            break
        current = current.parent
    for component in reversed(chain):
        try:
            info = component.lstat()
        except OSError as exc:
            raise IsolationError(f"Chemin absent ou illisible : {component}") from exc
        if _is_reparse_point(info):
            raise IsolationError(f"Lien symbolique/jonction interdit : {component}")


def _resolve_existing(raw: object, label: str, *, directory: bool) -> Path:
    path = _absolute_path(raw, label)
    try:
        _assert_no_reparse_chain(path)
    except IsolationError as exc:
        raise IsolationError(f"{label}: {exc}") from exc
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise IsolationError(f"Chemin non résoluble : {label}={path}") from exc
    if directory and not resolved.is_dir():
        raise IsolationError(f"Répertoire requis : {label}={resolved}")
    if not directory and not resolved.is_file():
        raise IsolationError(f"Fichier requis : {label}={resolved}")
    return resolved


def _same_path(actual: Path, expected: Path) -> bool:
    return os.path.normcase(str(actual)) == os.path.normcase(str(expected))


def _require_expected_path(
    raw: object,
    expected: Path,
    label: str,
    *,
    directory: bool,
) -> Path:
    actual = _resolve_existing(raw, label, directory=directory)
    expected_resolved = _resolve_existing(
        str(expected), f"allowlist:{label}", directory=directory
    )
    if not _same_path(actual, expected_resolved):
        raise IsolationError(
            f"Chemin hors allowlist : {label}={actual}; attendu {expected_resolved}"
        )
    return actual


def _walk_files_without_reparse(root: Path):
    def fail_on_walk_error(exc: OSError) -> None:
        raise IsolationError(f"Impossible de parcourir {root}: {exc}") from exc

    for current, directories, files in os.walk(
        root, followlinks=False, onerror=fail_on_walk_error
    ):
        current_path = Path(current)
        for name in [*directories, *files]:
            entry = current_path / name
            try:
                info = entry.lstat()
            except OSError as exc:
                raise IsolationError(f"Entrée illisible sous {root}: {entry}") from exc
            if _is_reparse_point(info):
                raise IsolationError(f"Lien symbolique/jonction interdit : {entry}")
            if stat.S_ISREG(info.st_mode):
                yield entry, (info.st_dev, info.st_ino)


def _protected_file_identities(paths: list[Path]) -> set[tuple[int, int]]:
    identities: set[tuple[int, int]] = set()
    for root in paths:
        _assert_no_reparse_chain(root)
        if root.is_file():
            info = root.stat()
            if stat.S_ISREG(info.st_mode):
                identities.add((info.st_dev, info.st_ino))
            continue
        if not root.is_dir():
            raise IsolationError(f"Cible de protection absente : {root}")
        for _, identity in _walk_files_without_reparse(root):
            identities.add(identity)
    return identities


def validate_10e_environment(
    env: Mapping[str, str] | None = None,
    *,
    executable: Path | None = None,
) -> IsolationPaths:
    """Validate the allowlisted 10E roots without creating or changing files."""
    values = os.environ if env is None else env
    if values.get("AVM_10E_MODE") != "1":
        raise IsolationError("AVM_10E_MODE=1 requis pour le lancement isolé")

    repo_root = _resolve_existing(
        values.get("AVM_10E_REPO_ROOT"), "AVM_10E_REPO_ROOT", directory=True
    )
    expected_venv = repo_root / ".venv"
    _require_expected_path(
        values.get("VIRTUAL_ENV"), expected_venv, "VIRTUAL_ENV", directory=True
    )
    expected_executable = _resolve_existing(
        str(expected_venv / "Scripts" / "python.exe"),
        "venv Python",
        directory=False,
    )
    running_executable = _resolve_existing(
        str(executable or Path(sys.executable)),
        "Python executable",
        directory=False,
    )
    if not _same_path(running_executable, expected_executable):
        raise IsolationError(
            f"Python hors environnement .venv : {running_executable}; "
            f"attendu {expected_executable}"
        )

    local_app_data = _resolve_existing(
        values.get("LOCALAPPDATA"), "LOCALAPPDATA", directory=True
    )
    user_profile = _resolve_existing(
        values.get("USERPROFILE"), "USERPROFILE", directory=True
    )
    expected_data = local_app_data / "AudioVideoManager-10E"
    expected_library = user_profile / "Music" / "AVM-10E-Test-Library"
    data_root = _require_expected_path(
        values.get("AVM_DATA_DIR"),
        expected_data,
        "AVM_DATA_DIR",
        directory=True,
    )
    library_root = _require_expected_path(
        values.get("AVM_LIBRARY_ROOT"),
        expected_library,
        "AVM_LIBRARY_ROOT",
        directory=True,
    )

    production_root = local_app_data / "AudioVideoManager"
    resolved_production = production_root.resolve(strict=False)
    if _same_path(data_root, resolved_production) or resolved_production in data_root.parents:
        raise IsolationError("AVM_DATA_DIR pointe vers ou sous le répertoire de production")
    queen_library = user_profile / "Music" / "AVM-06C-Test-Library"
    if _same_path(library_root, queen_library.resolve(strict=False)):
        raise IsolationError("AVM_LIBRARY_ROOT pointe vers la bibliothèque Queen de production")
    if data_root in library_root.parents or library_root in data_root.parents:
        raise IsolationError("Les racines données et bibliothèque se recouvrent")

    config_path = _resolve_existing(
        str(data_root / "config.json"), "config.json", directory=False
    )
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IsolationError(f"Configuration 10E illisible : {config_path}") from exc
    if not isinstance(config, dict):
        raise IsolationError("Configuration 10E invalide : objet JSON requis")

    jobs_dir = _require_expected_path(
        config.get("jobs_dir"),
        data_root / "jobs-10e",
        "config.jobs_dir",
        directory=True,
    )
    log_dir = _require_expected_path(
        config.get("log_dir"),
        data_root / "logs",
        "config.log_dir",
        directory=True,
    )
    configured_library = _require_expected_path(
        config.get("library_root"),
        library_root,
        "config.library_root",
        directory=True,
    )
    database_path = _resolve_existing(
        str(data_root / "avm.sqlite3"), "SQLite 10E", directory=False
    )
    program_files = _resolve_existing(
        values.get("ProgramFiles"), "ProgramFiles", directory=True
    )
    freaccmd_path = _require_expected_path(
        config.get("freaccmd_path"),
        program_files / "freac" / "freaccmd.exe",
        "config.freaccmd_path",
        directory=False,
    )

    production_jobs = production_root / "jobs"
    production_logs = production_root / "logs"
    queen_root = (
        user_profile
        / "Music"
        / "AVM-06C-Test-Library"
        / "Queen"
        / "Greatest Hits (1992)"
    )
    protected_ids = _protected_file_identities(
        [
            production_root,
            queen_root,
        ]
    )
    for root in (data_root, configured_library):
        for entry, identity in _walk_files_without_reparse(root):
            if identity in protected_ids:
                raise IsolationError(
                    f"Fichier 10E lié aux données de production : {entry}"
                )

    return IsolationPaths(
        repo_root=repo_root,
        data_root=data_root,
        library_root=configured_library,
        config_path=config_path,
        database_path=database_path,
        log_dir=log_dir,
        jobs_dir=jobs_dir,
        freaccmd_path=freaccmd_path,
    )


def preflight_main() -> int:
    try:
        paths = validate_10e_environment()
    except IsolationError as exc:
        print(f"AVM-10E PREFLIGHT FAIL: {exc}", file=sys.stderr)
        return 2
    print("AVM-10E PREFLIGHT PASS")
    for name, value in paths.__dict__.items():
        print(f"{name}={value}")
    print(f"python={Path(sys.executable).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(preflight_main())