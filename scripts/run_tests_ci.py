#!/usr/bin/env python3
"""Orchestrateur de tests AVM-10C — assertions + codes de sortie process.

- Domaine : un process pytest + JUnit.
- UI Qt : **un sous-processus par fichier** (isolation Mode B 07A).
- Tout rc ∉ {0} après PASS JUnit → **échec** (crash natif non toléré).
- Tests non exécutés (skip deps) listés explicitement — jamais comptés PASS.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JUNIT_DIR = ROOT / ".ci" / "junit"
DEFAULT_REPORT = ROOT / ".ci" / "avm10c-results.json"

# Codes Windows connus (bash peut tronquer à 8 bits)
WIN_ACCESS_VIOLATION = 0xC0000005  # 3221225477
WIN_STACK_BUFFER = 0xC0000409  # 3221226505

UI_FILES = [
    "tests/test_metadata_dialog_sources.py",
    "tests/test_history_06n.py",
    "tests/test_ux_06o.py",
    "tests/test_ui_design_06l.py",
    "tests/test_ui_shell.py",
    "tests/test_ui_library_history_06h.py",
    "tests/test_library_qml_08b.py",
    "tests/test_humanisation_06i.py",
    "tests/test_ui_w3_prefill.py",
    "tests/test_ui_collision_replace_disabled.py",
    "tests/test_qthread_07b.py",
    "tests/test_qt_teardown_10c1.py",
    "tests/test_qt_teardown_10c2.py",
]

DOMAIN_GLOBS = [
    "tests/test_musicbrainz_identity.py",
    "tests/test_metadata_enrichment.py",
    "tests/test_10e_isolation.py",
    "tests/test_reconciliation_10b.py",
    "tests/test_reconciliation_10c.py",
    "tests/test_archive_recovery_staging.py",
    "tests/test_archive_pipeline.py",
    "tests/test_duplicates_06k.py",
    "tests/test_hardlink_security_06gp1.py",
    "tests/test_database.py",
    "tests/test_config.py",
    "tests/test_logging.py",
    "tests/test_cd_ripper.py",
    "tests/test_freaccmd.py",
    "tests/test_flac_integrity.py",
    "tests/test_integrity_10d.py",
    "tests/test_rip_check.py",
    "tests/test_rip_job.py",
    "tests/test_disc_metadata.py",
    "tests/test_musicbrainz_identify.py",
    "tests/test_edition_ranker.py",
    "tests/test_approval_fingerprint.py",
    "tests/test_diagnostics_06g.py",
    "tests/test_perf_06gp.py",
    "tests/test_drives.py",
    "tests/test_cover_cache.py",
    "tests/test_progress_labels.py",
]


@dataclass
class ProcResult:
    label: str
    argv: list[str]
    returncode: int
    duration_sec: float
    junit_path: str | None
    tests: int = 0
    failures: int = 0
    errors: int = 0
    skipped: int = 0
    native_crash: bool = False
    ok: bool = False
    note: str = ""


@dataclass
class SuiteReport:
    ok: bool
    results: list[ProcResult] = field(default_factory=list)
    skipped_unavailable: list[str] = field(default_factory=list)
    env: dict = field(default_factory=dict)


def _classify_rc(rc: int) -> tuple[bool, str]:
    """Retourne (is_native_crash, label)."""
    if rc == 0:
        return False, "ok"
    # Windows NTSTATUS sometimes passed as unsigned 32-bit
    unsigned = rc & 0xFFFFFFFF
    if unsigned in (WIN_ACCESS_VIOLATION, 3221225477) or rc in (-1073741819, 139):
        return True, "0xC0000005 ACCESS_VIOLATION"
    if unsigned in (WIN_STACK_BUFFER, 3221226505) or rc in (-1073740791, 127, 137):
        # 127/137 souvent vus sous Git Bash pour STACK
        return True, "0xC0000409 STACK_BUFFER / fatal"
    if rc > 255 and (unsigned & 0xF0000000) == 0xC0000000:
        return True, f"NTSTATUS 0x{unsigned:08X}"
    return False, f"pytest_exit_{rc}"


def _parse_junit(path: Path) -> tuple[int, int, int, int]:
    if not path.is_file():
        return 0, 0, 0, 0
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        return 0, 0, 0, 0
    # pytest may emit <testsuites> or <testsuite>
    suites = []
    if root.tag == "testsuites":
        suites = list(root)
    elif root.tag == "testsuite":
        suites = [root]
    tests = failures = errors = skipped = 0
    for s in suites:
        tests += int(s.attrib.get("tests", 0))
        failures += int(s.attrib.get("failures", 0))
        errors += int(s.attrib.get("errors", 0))
        skipped += int(s.attrib.get("skipped", 0))
    return tests, failures, errors, skipped


def _run_pytest(
    label: str,
    targets: list[str],
    junit_path: Path,
    *,
    extra_args: list[str] | None = None,
    env: dict | None = None,
    timeout: int = 600,
) -> ProcResult:
    junit_path.parent.mkdir(parents=True, exist_ok=True)
    argv = [
        sys.executable,
        "-m",
        "pytest",
        *targets,
        "-q",
        f"--junitxml={junit_path}",
        "--tb=line",
        # AVM-10C.2 : diagnostics ON (ne plus couper unraisableexception)
        "-o",
        "addopts=-q",
    ]
    if extra_args:
        argv.extend(extra_args)
    run_env = os.environ.copy()
    run_env.setdefault("QT_QPA_PLATFORM", "offscreen")
    run_env.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")
    # Fermeture naturelle par défaut ; AVM_QT_SAFE_EXIT=1 reste un secours CI
    run_env.setdefault("AVM_QT_SAFE_EXIT", "0")
    if env:
        run_env.update(env)
    t0 = time.perf_counter()
    try:
        proc = subprocess.run(
            argv,
            cwd=str(ROOT),
            env=run_env,
            timeout=timeout,
        )
        rc = int(proc.returncode)
    except subprocess.TimeoutExpired:
        return ProcResult(
            label=label,
            argv=argv,
            returncode=124,
            duration_sec=time.perf_counter() - t0,
            junit_path=str(junit_path),
            native_crash=False,
            ok=False,
            note="timeout",
        )
    duration = time.perf_counter() - t0
    tests, failures, errors, skipped = _parse_junit(junit_path)
    native, note = _classify_rc(rc)
    # GO : rc==0 et junit sans fail/error
    ok = (rc == 0) and failures == 0 and errors == 0 and not native
    if native:
        ok = False
        note = f"NATIVE_CRASH {note} after junit tests={tests} fail={failures}"
    elif rc != 0:
        note = note
    return ProcResult(
        label=label,
        argv=argv,
        returncode=rc,
        duration_sec=round(duration, 3),
        junit_path=str(junit_path),
        tests=tests,
        failures=failures,
        errors=errors,
        skipped=skipped,
        native_crash=native,
        ok=ok,
        note=note,
    )


def probe_deps() -> dict:
    info: dict = {"freaccmd": None, "discid": False, "ffmpeg": None}
    try:
        sys.path.insert(0, str(ROOT))
        from audio_video_manager.extraction.cd import probe_freaccmd
        from audio_video_manager.verification.flac_decode import find_flac_decode_tool

        st = probe_freaccmd(run_probes=False)
        info["freaccmd"] = str(st.path) if st.found and st.path else None
        tool = find_flac_decode_tool()
        info["ffmpeg"] = str(tool) if tool else None
        try:
            from audio_video_manager.metadata.libdiscid_loader import (
                import_discid,
                prepare_libdiscid_search_path,
            )

            prepare_libdiscid_search_path()
            import_discid()
            info["discid"] = True
        except Exception as exc:  # noqa: BLE001
            info["discid"] = False
            info["discid_error"] = str(exc)
    except Exception as exc:  # noqa: BLE001
        info["probe_error"] = str(exc)
    return info


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AVM-10C test orchestrator")
    parser.add_argument("--junit-dir", type=Path, default=DEFAULT_JUNIT_DIR)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--skip-ui", action="store_true")
    parser.add_argument("--ui-only", action="store_true")
    parser.add_argument("--domain-only", action="store_true")
    args = parser.parse_args(argv)

    junit_dir = args.junit_dir
    junit_dir.mkdir(parents=True, exist_ok=True)
    results: list[ProcResult] = []
    skipped_unavail: list[str] = []
    deps = probe_deps()

    if not deps.get("freaccmd"):
        skipped_unavail.append(
            "requires_freac: freaccmd absent — tests live rip non exécutés "
            "(fixtures mock uniquement)"
        )
    if not deps.get("discid"):
        skipped_unavail.append("requires_discid: discid non chargeable")
    if not deps.get("ffmpeg"):
        skipped_unavail.append(
            "requires_ffmpeg: ffmpeg absent — décodage intégral non validé ici"
        )

    if not args.ui_only:
        domain_targets = [p for p in DOMAIN_GLOBS if (ROOT / p).is_file()]
        results.append(
            _run_pytest(
                "domain",
                domain_targets,
                junit_dir / "domain.xml",
                timeout=900,
            )
        )

    if not args.domain_only and not args.skip_ui:
        for rel in UI_FILES:
            path = ROOT / rel
            if not path.is_file():
                skipped_unavail.append(f"missing_file:{rel}")
                continue
            safe = rel.replace("/", "_").replace("\\", "_")
            results.append(
                _run_pytest(
                    f"ui:{rel}",
                    [rel],
                    junit_dir / f"{safe}.xml",
                    timeout=300,
                )
            )

    overall = all(r.ok for r in results) and len(results) > 0
    report = SuiteReport(
        ok=overall,
        results=results,
        skipped_unavailable=skipped_unavail,
        env={
            "python": sys.version,
            "platform": sys.platform,
            "deps": deps,
        },
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(asdict(report), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print("=== AVM-10C CI summary ===")
    for r in results:
        status = "OK" if r.ok else "FAIL"
        print(
            f"[{status}] {r.label} rc={r.returncode} "
            f"tests={r.tests} fail={r.failures} err={r.errors} skip={r.skipped} "
            f"native={r.native_crash} ({r.note}) {r.duration_sec}s"
        )
    if skipped_unavail:
        print("--- Non exécuté / indisponible (pas PASS) ---")
        for s in skipped_unavail:
            print(f"  · {s}")
    print(f"Report: {args.report}")
    print(f"OVERALL: {'GO' if overall else 'NO-GO'}")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
