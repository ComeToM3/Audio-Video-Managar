"""Réconciliation jobs orphelins / récupération staging contrôlée (AVM-10B).

Règles absolues :
- Aucune suppression, purge, écrasement ou déplacement destructif automatique.
- Ne jamais marquer Abandonné sur la seule base de l’ancienneté.
- Reprise = nouveau job via fichiers FLAC existants (06F), jamais rip piste-à-piste.
"""

from __future__ import annotations

import json
import os
import subprocess
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from audio_video_manager.extraction.cd_ripper import collect_flac_files
from audio_video_manager.library.disc_match import (
    DiscMismatchError,
    assert_disc_matches_sheet,
)
from audio_video_manager.library.duplicates import (
    ACTIVE_JOB_STATES,
    RECOVERABLE_JOB_STATES,
    DuplicateBlockedError,
    DuplicateGate,
    assert_archive_allowed,
    assess_from_sheet,
)
from audio_video_manager.library.publish import CollisionPolicy
from audio_video_manager.logging_setup import get_logger
from audio_video_manager.metadata.enums import JobMode
from audio_video_manager.metadata.models import DiscMetadata
from audio_video_manager.metadata.repository import DiscMetadataRepository
from audio_video_manager.metadata.toc_reader import read_disc_toc
from audio_video_manager.metadata.validation import (
    ApprovalError,
    assert_can_start_archive_rip,
)
from audio_video_manager.orchestration.rip_lock import (
    LOCK_FILENAME,
    RipLockInfo,
    candidate_media_dirs,
    clear_rip_lock,
    is_lock_holder_active,
    job_root_from_workdir,
    read_rip_lock,
    release_recovery_file_lock,
    try_acquire_recovery_file_lock,
    write_rip_lock,
)
from audio_video_manager.storage.database import Database
from audio_video_manager.verification.flac_integrity import check_many

if TYPE_CHECKING:
    from audio_video_manager.orchestration.archive_job import ArchiveJobReport

log = get_logger("orchestration.reconciliation")

RECONCILE_NOTE = (
    "Interruption détectée au démarrage (AVM-10B) — "
    "aucun processus d’extraction actif confirmé. Fichiers non modifiés."
)
ABANDON_NOTE = "Abandonné depuis l’historique (fichiers non supprimés)."

_recovery_lock = threading.Lock()
_recovery_holder: str | None = None
_recovery_lock_dir: Path | None = None


class LivenessKind(str, Enum):
    PROCESS_ACTIVE = "process_active"
    INTERRUPTED_CONFIRMED = "interrupted_confirmed"
    UNCERTAIN = "uncertain"


class RecoveryVerdict(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_CONFIRM = "require_confirm"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _append_error_note(existing: str | None, note: str) -> str:
    if not existing or not str(existing).strip():
        return note
    if note in existing:
        return existing
    return f"{existing} | {note}"


@dataclass(frozen=True)
class JobSnapshot:
    id: str
    state: str
    step: str | None
    workdir: str | None
    started_at: str | None
    finished_at: str | None
    updated_at: str | None
    error_summary: str | None
    mode: str | None
    metadata_id: str | None
    disc_id: str | None
    collision_policy: str | None
    warnings_json: str | None
    library_path: str | None
    publish_allowed: int | None = None


@dataclass(frozen=True)
class JobSituation:
    job: JobSnapshot
    liveness: LivenessKind
    flac_count: int
    lock: RipLockInfo | None
    summary_fr: str
    action_hint_fr: str


@dataclass
class ReconcileAction:
    job_id: str
    before_state: str
    after_state: str
    liveness: LivenessKind
    changed: bool
    message_fr: str


@dataclass
class ReconciliationReport:
    scanned: int = 0
    actions: list[ReconcileAction] = field(default_factory=list)
    freaccmd_running: bool | None = None

    @property
    def changed_count(self) -> int:
        return sum(1 for a in self.actions if a.changed)

    @property
    def interrupted_ids(self) -> list[str]:
        return [
            a.job_id
            for a in self.actions
            if a.after_state == "Interrupted"
            and a.liveness == LivenessKind.INTERRUPTED_CONFIRMED
        ]

    @property
    def uncertain_ids(self) -> list[str]:
        return [a.job_id for a in self.actions if a.liveness == LivenessKind.UNCERTAIN]

    @property
    def active_ids(self) -> list[str]:
        return [
            a.job_id for a in self.actions if a.liveness == LivenessKind.PROCESS_ACTIVE
        ]


@dataclass(frozen=True)
class RecoveryAssessment:
    job_id: str
    verdict: RecoveryVerdict
    summary_fr: str
    detail_lines: list[str] = field(default_factory=list)
    flac_files: tuple[Path, ...] = ()
    metadata: DiscMetadata | None = None
    requires_rearchive_confirmation: bool = False
    offline_disc: bool = False


def list_job_flac_files(workdir: Path | str | None) -> list[Path]:
    """Inventaire FLAC zone A — lecture seule, ignore ``*.flac.temp`` et ``tagged/``."""
    if not workdir:
        return []
    found: list[Path] = []
    seen: set[str] = set()
    for d in candidate_media_dirs(Path(workdir)):
        for p in collect_flac_files(d):
            key = str(p.resolve())
            if key in seen:
                continue
            if "tagged" in {x.lower() for x in p.parts}:
                continue
            seen.add(key)
            found.append(p)
    return sorted(found, key=lambda p: p.name.lower())


def freaccmd_process_running() -> bool | None:
    """True si freaccmd.exe tourne, False sinon, None si indéterminable."""
    if os.name != "nt":
        return None
    try:
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        proc = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq freaccmd.exe", "/NH"],
            capture_output=True,
            text=True,
            timeout=15,
            creationflags=creationflags,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    out = (proc.stdout or "").lower()
    if "freaccmd.exe" in out:
        return True
    if proc.returncode not in (0, 1):
        return None
    return False


def _row_to_snapshot(row: object, cols: set[str]) -> JobSnapshot:
    keys = set(row.keys())  # type: ignore[attr-defined]

    def _get(name: str) -> object:
        return row[name] if name in keys and name in cols else None  # type: ignore[index]

    pub = _get("publish_allowed")
    return JobSnapshot(
        id=str(row["id"]),  # type: ignore[index]
        state=str(row["state"]),  # type: ignore[index]
        step=row["step"],  # type: ignore[index]
        workdir=row["workdir"],  # type: ignore[index]
        started_at=row["started_at"],  # type: ignore[index]
        finished_at=row["finished_at"],  # type: ignore[index]
        updated_at=_get("updated_at"),  # type: ignore[arg-type]
        error_summary=row["error_summary"],  # type: ignore[index]
        mode=_get("mode"),  # type: ignore[arg-type]
        metadata_id=_get("metadata_id"),  # type: ignore[arg-type]
        disc_id=_get("disc_id"),  # type: ignore[arg-type]
        collision_policy=_get("collision_policy"),  # type: ignore[arg-type]
        warnings_json=_get("warnings_json"),  # type: ignore[arg-type]
        library_path=_get("library_path"),  # type: ignore[arg-type]
        publish_allowed=int(pub) if pub is not None else None,  # type: ignore[arg-type]
    )


def list_unfinished_active_jobs(db: Database) -> list[JobSnapshot]:
    conn = db.connect()
    cols = {row[1] for row in conn.execute("PRAGMA table_info(jobs)").fetchall()}
    rows = conn.execute(
        f"""
        SELECT *
        FROM jobs
        WHERE finished_at IS NULL
          AND state IN ({",".join("?" for _ in ACTIVE_JOB_STATES)})
        ORDER BY COALESCE(started_at, updated_at, id) DESC
        """,
        tuple(ACTIVE_JOB_STATES),
    ).fetchall()
    return [_row_to_snapshot(r, cols) for r in rows]


def get_job_snapshot(db: Database, job_id: str) -> JobSnapshot | None:
    conn = db.connect()
    cols = {row[1] for row in conn.execute("PRAGMA table_info(jobs)").fetchall()}
    row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    if row is None:
        return None
    return _row_to_snapshot(row, cols)


def classify_job_liveness(
    job: JobSnapshot,
    *,
    freaccmd_running: bool | None,
) -> tuple[LivenessKind, RipLockInfo | None, str, str]:
    """Classifie sans utiliser l’âge du job."""
    lock = read_rip_lock(job.workdir)
    n = len(list_job_flac_files(job.workdir))

    if lock is not None and is_lock_holder_active(lock):
        return (
            LivenessKind.PROCESS_ACTIVE,
            lock,
            "Le processus applicatif lié à l’extraction est encore actif.",
            "Attendez la fin ou annulez depuis l’application qui a lancé l’extraction.",
        )
    if lock is not None and lock.identity_ok is False:
        return (
            LivenessKind.INTERRUPTED_CONFIRMED,
            lock,
            "Verrou périmé : le PID a été réutilisé par un autre processus "
            "(identité create_time incohérente).",
            "Vous pouvez abandonner ou reprendre depuis les fichiers s’ils sont valides.",
        )
    if lock is not None and lock.pid_alive is False:
        return (
            LivenessKind.INTERRUPTED_CONFIRMED,
            lock,
            "Verrou d’extraction présent mais processus mort — interruption confirmée.",
            "Vous pouvez abandonner ou reprendre depuis les fichiers s’ils sont valides.",
        )
    if lock is not None and lock.pid_alive is None:
        return (
            LivenessKind.UNCERTAIN,
            lock,
            "Verrou d’extraction illisible ou PID indéterminable.",
            "Vérifiez qu’aucune fenêtre AudioVideoManager / fre:ac n’est active.",
        )

    if freaccmd_running is True:
        return (
            LivenessKind.UNCERTAIN,
            None,
            "freaccmd.exe tourne encore — ce job pourrait être concerné (PID non lié).",
            "Attendez la fin de fre:ac avant toute action sur ce job.",
        )
    if freaccmd_running is None:
        return (
            LivenessKind.UNCERTAIN,
            None,
            "Impossible de vérifier freaccmd — état laissé inchangé.",
            "Relancez après avoir confirmé qu’aucune extraction n’est en cours.",
        )

    hint = (
        f"{n} fichier(s) FLAC encore présents (non modifiés)."
        if n
        else "Aucun FLAC complet détecté dans le dossier temporaire."
    )
    return (
        LivenessKind.INTERRUPTED_CONFIRMED,
        None,
        f"Aucune extraction fre:ac active. {hint}",
        "Consultez l’historique : abandonner ou reprendre depuis les fichiers (si éligible).",
    )


def build_job_situation(
    job: JobSnapshot,
    *,
    freaccmd_running: bool | None,
) -> JobSituation:
    kind, lock, summary, hint = classify_job_liveness(
        job, freaccmd_running=freaccmd_running
    )
    return JobSituation(
        job=job,
        liveness=kind,
        flac_count=len(list_job_flac_files(job.workdir)),
        lock=lock,
        summary_fr=summary,
        action_hint_fr=hint,
    )


def mark_job_interrupted(
    db: Database,
    job_id: str,
    *,
    note: str = RECONCILE_NOTE,
) -> bool:
    """→ Interrupted. Idempotent. Jamais Abandoned. Aucun fichier touché."""
    snap = get_job_snapshot(db, job_id)
    if snap is None:
        return False
    if snap.state == "Interrupted" and snap.finished_at:
        return False
    if snap.state == "Abandoned":
        return False
    if snap.state in {"Completed", "CompletedWithWarnings", "SkippedDuplicate"}:
        return False

    now = _utc_now()
    conn = db.connect()
    new_error = _append_error_note(snap.error_summary, note)
    cur = conn.execute(
        """
        UPDATE jobs
        SET state = ?, step = ?, updated_at = ?, finished_at = ?,
            error_summary = ?
        WHERE id = ?
          AND state NOT IN (
              'Completed', 'CompletedWithWarnings', 'SkippedDuplicate', 'Abandoned'
          )
          AND NOT (state = 'Interrupted' AND finished_at IS NOT NULL)
        """,
        ("Interrupted", "Interrupted", now, now, new_error, job_id),
    )
    changed = int(cur.rowcount or 0) > 0
    if changed:
        conn.execute(
            """
            INSERT INTO job_checkpoints(job_id, step, payload_json, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                job_id,
                "ReconciledInterrupted",
                json.dumps(
                    {"note": note, "previous_state": snap.state},
                    ensure_ascii=False,
                ),
                now,
            ),
        )
    conn.commit()
    return changed


def mark_job_abandoned(db: Database, job_id: str) -> bool:
    """Abandon explicite — état seulement. Idempotent."""
    snap = get_job_snapshot(db, job_id)
    if snap is None:
        return False
    if snap.state == "Abandoned":
        return False
    if snap.state in {"Completed", "CompletedWithWarnings", "SkippedDuplicate"}:
        raise ApprovalError(
            "Impossible d’abandonner une opération déjà terminée avec succès."
        )

    now = _utc_now()
    conn = db.connect()
    new_error = _append_error_note(snap.error_summary, ABANDON_NOTE)
    conn.execute(
        """
        UPDATE jobs
        SET state = ?, step = ?, updated_at = ?, finished_at = ?,
            error_summary = ?
        WHERE id = ?
        """,
        ("Abandoned", "Abandoned", now, now, new_error, job_id),
    )
    conn.execute(
        """
        INSERT INTO job_checkpoints(job_id, step, payload_json, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (
            job_id,
            "Abandoned",
            json.dumps(
                {"note": ABANDON_NOTE, "previous_state": snap.state},
                ensure_ascii=False,
            ),
            now,
        ),
    )
    conn.commit()
    return True


def reconcile_unfinished_jobs(
    db: Database,
    *,
    freaccmd_running_fn: Callable[[], bool | None] | None = None,
    apply: bool = True,
) -> ReconciliationReport:
    """
    Au démarrage : jobs actifs non terminés.

    PROCESS_ACTIVE / UNCERTAIN → aucune mutation.
    INTERRUPTED_CONFIRMED → Interrupted (si apply), jamais Abandoned.
    """
    probe = freaccmd_running_fn or freaccmd_process_running
    running = probe()
    report = ReconciliationReport(freaccmd_running=running)
    jobs = list_unfinished_active_jobs(db)
    report.scanned = len(jobs)

    for job in jobs:
        sit = build_job_situation(job, freaccmd_running=running)
        if sit.liveness == LivenessKind.INTERRUPTED_CONFIRMED:
            changed = False
            after = job.state
            if apply:
                changed = mark_job_interrupted(db, job.id)
                after = "Interrupted"
            report.actions.append(
                ReconcileAction(
                    job_id=job.id,
                    before_state=job.state,
                    after_state=after,
                    liveness=sit.liveness,
                    changed=changed,
                    message_fr=sit.summary_fr,
                )
            )
        else:
            report.actions.append(
                ReconcileAction(
                    job_id=job.id,
                    before_state=job.state,
                    after_state=job.state,
                    liveness=sit.liveness,
                    changed=False,
                    message_fr=sit.summary_fr,
                )
            )
    log.info(
        "Réconciliation : scanned=%s changed=%s freaccmd=%s",
        report.scanned,
        report.changed_count,
        running,
    )
    return report


def try_acquire_recovery(job_id: str, *, lock_dir: Path | None = None) -> bool:
    """Exclusion intra + inter-processus (fichier sous lock_dir si fourni)."""
    global _recovery_holder, _recovery_lock_dir
    with _recovery_lock:
        if _recovery_holder is not None:
            return False
        if lock_dir is not None:
            got = try_acquire_recovery_file_lock(lock_dir, job_id=job_id)
            if got is None:
                return False
            _recovery_lock_dir = Path(lock_dir)
        _recovery_holder = job_id
        return True


def release_recovery(job_id: str) -> None:
    global _recovery_holder, _recovery_lock_dir
    with _recovery_lock:
        if _recovery_holder == job_id:
            if _recovery_lock_dir is not None:
                release_recovery_file_lock(_recovery_lock_dir, job_id=job_id)
                _recovery_lock_dir = None
            _recovery_holder = None


def recovery_in_progress() -> str | None:
    with _recovery_lock:
        return _recovery_holder


def assess_recovery_from_files(
    db: Database,
    job_id: str,
    *,
    optical_device: str | None = None,
    allow_offline: bool = False,
    skip_optical_probe: bool = False,
) -> RecoveryAssessment:
    """Évalue une reprise depuis FLAC existants (pas de rip physique)."""
    from audio_video_manager.orchestration.archive_job import match_flacs_to_tracks

    details: list[str] = []
    snap = get_job_snapshot(db, job_id)
    if snap is None:
        return RecoveryAssessment(
            job_id=job_id,
            verdict=RecoveryVerdict.DENY,
            summary_fr="Opération introuvable dans la base.",
        )

    if snap.state in ACTIVE_JOB_STATES and snap.finished_at is None:
        return RecoveryAssessment(
            job_id=job_id,
            verdict=RecoveryVerdict.DENY,
            summary_fr=(
                "Cette opération est encore marquée active. "
                "Attendez la réconciliation ou la fin de l’extraction."
            ),
            detail_lines=[f"État actuel : {snap.state}"],
        )

    if snap.state not in RECOVERABLE_JOB_STATES:
        return RecoveryAssessment(
            job_id=job_id,
            verdict=RecoveryVerdict.DENY,
            summary_fr=f"Reprise depuis fichiers non proposée pour l’état « {snap.state} ».",
        )

    if (snap.mode or "") == JobMode.TECHNICAL_TEST.value and not snap.metadata_id:
        return RecoveryAssessment(
            job_id=job_id,
            verdict=RecoveryVerdict.DENY,
            summary_fr=(
                "Test technique sans fiche métadonnées approuvée — "
                "impossible de publier via reprise. "
                "Les fichiers restent dans le dossier temporaire."
            ),
            detail_lines=[
                "La reprise ne relance pas l’extraction CD piste par piste.",
            ],
        )

    if not snap.metadata_id:
        return RecoveryAssessment(
            job_id=job_id,
            verdict=RecoveryVerdict.DENY,
            summary_fr="Aucune fiche métadonnées liée à cette opération.",
        )

    repo = DiscMetadataRepository(db)
    sheet = repo.get(snap.metadata_id)
    if sheet is None:
        return RecoveryAssessment(
            job_id=job_id,
            verdict=RecoveryVerdict.DENY,
            summary_fr="Fiche métadonnées absente de la base.",
        )

    try:
        assert_can_start_archive_rip(sheet)
    except ApprovalError as exc:
        return RecoveryAssessment(
            job_id=job_id,
            verdict=RecoveryVerdict.DENY,
            summary_fr="La fiche métadonnées n’est pas approuvée ou est incomplète.",
            detail_lines=[str(exc)],
            metadata=sheet,
        )

    flacs = list_job_flac_files(snap.workdir)
    if not flacs:
        return RecoveryAssessment(
            job_id=job_id,
            verdict=RecoveryVerdict.DENY,
            summary_fr="Aucun fichier FLAC récupérable dans le dossier temporaire.",
            metadata=sheet,
        )

    try:
        ordered = match_flacs_to_tracks(flacs, len(sheet.tracks))
    except ApprovalError as exc:
        return RecoveryAssessment(
            job_id=job_id,
            verdict=RecoveryVerdict.DENY,
            summary_fr="Les fichiers FLAC ne correspondent pas à la fiche (nombre / numéros).",
            detail_lines=[str(exc)],
            metadata=sheet,
            flac_files=tuple(flacs),
        )

    integrity = check_many(ordered)
    bad = [i for i in integrity if not i.ok]
    if bad:
        return RecoveryAssessment(
            job_id=job_id,
            verdict=RecoveryVerdict.DENY,
            summary_fr="Au moins un FLAC est incomplet ou illisible (contrôle structurel).",
            detail_lines=[f"{b.path.name}: {b.message}" for b in bad[:8]],
            metadata=sheet,
            flac_files=tuple(ordered),
        )
    details.append(f"{len(ordered)} fichier(s) FLAC structurellement OK.")

    offline = False
    if not skip_optical_probe:
        try:
            disc = read_disc_toc(optical_device)
            assert_disc_matches_sheet(sheet, disc)
            details.append("Disque optique concordant avec la fiche approuvée.")
        except DiscMismatchError as exc:
            return RecoveryAssessment(
                job_id=job_id,
                verdict=RecoveryVerdict.DENY,
                summary_fr="Le disque présent ne correspond pas à la fiche approuvée.",
                detail_lines=[str(exc)],
                metadata=sheet,
                flac_files=tuple(ordered),
            )
        except Exception as exc:  # noqa: BLE001
            offline = True
            if not allow_offline:
                return RecoveryAssessment(
                    job_id=job_id,
                    verdict=RecoveryVerdict.REQUIRE_CONFIRM,
                    summary_fr=(
                        "Aucun disque lisible pour vérifier la correspondance. "
                        "Confirmez une reprise hors ligne (fiche approuvée + FLAC uniquement)."
                    ),
                    detail_lines=[str(exc), *details],
                    metadata=sheet,
                    flac_files=tuple(ordered),
                    offline_disc=True,
                )
            details.append(f"Reprise hors ligne acceptée (pas de TOC) : {exc}")
    else:
        offline = True
        details.append("Probe optique ignorée (test / mode staging).")

    dup = assess_from_sheet(db, sheet, exclude_job_id=job_id)
    try:
        assert_archive_allowed(dup, confirmed_rearchive=False)
    except DuplicateBlockedError as exc:
        if dup.gate == DuplicateGate.REQUIRE_CONFIRM:
            return RecoveryAssessment(
                job_id=job_id,
                verdict=RecoveryVerdict.REQUIRE_CONFIRM,
                summary_fr=dup.summary_fr or str(exc),
                detail_lines=list(dup.detail_lines) + details,
                metadata=sheet,
                flac_files=tuple(ordered),
                requires_rearchive_confirmation=True,
                offline_disc=offline,
            )
        return RecoveryAssessment(
            job_id=job_id,
            verdict=RecoveryVerdict.DENY,
            summary_fr=str(exc),
            detail_lines=list(dup.detail_lines) + details,
            metadata=sheet,
            flac_files=tuple(ordered),
            offline_disc=offline,
        )

    if dup.gate == DuplicateGate.REQUIRE_CONFIRM:
        return RecoveryAssessment(
            job_id=job_id,
            verdict=RecoveryVerdict.REQUIRE_CONFIRM,
            summary_fr=dup.summary_fr,
            detail_lines=list(dup.detail_lines) + details,
            metadata=sheet,
            flac_files=tuple(ordered),
            requires_rearchive_confirmation=True,
            offline_disc=offline,
        )

    return RecoveryAssessment(
        job_id=job_id,
        verdict=RecoveryVerdict.ALLOW,
        summary_fr=(
            "Reprise possible depuis les fichiers existants "
            "(nouvelle opération — pas de rip à la piste)."
        ),
        detail_lines=details + list(dup.detail_lines),
        metadata=sheet,
        flac_files=tuple(ordered),
        offline_disc=offline,
    )


def run_recovery_from_files(
    *,
    db: Database,
    source_job_id: str,
    library_root: Path,
    jobs_root: Path,
    collision_policy: CollisionPolicy = CollisionPolicy.RENAME,
    confirm_publish: bool = True,
    confirmed_rearchive: bool = False,
    allow_offline: bool = False,
    optical_device: str | None = None,
    skip_optical_probe: bool = False,
    cover_bytes: bytes | None = None,
    on_progress: Callable[[str, float | None], None] | None = None,
    cancel_event: threading.Event | None = None,
) -> ArchiveJobReport:
    """Nouveau job archive via staged_flac_files — source non détruite."""
    from audio_video_manager.orchestration.archive_job import run_archive_job

    if not try_acquire_recovery(source_job_id, lock_dir=Path(jobs_root)):
        holder = recovery_in_progress()
        raise ApprovalError(
            "Une récupération est déjà en cours"
            + (f" (réf. {holder[:8]}…)." if holder else ".")
            + " (verrou interprocessus ou local)."
        )

    try:
        assessment = assess_recovery_from_files(
            db,
            source_job_id,
            optical_device=optical_device,
            allow_offline=allow_offline,
            skip_optical_probe=skip_optical_probe,
        )
        if assessment.verdict == RecoveryVerdict.DENY:
            raise ApprovalError(assessment.summary_fr)
        if assessment.verdict == RecoveryVerdict.REQUIRE_CONFIRM:
            if assessment.requires_rearchive_confirmation and not confirmed_rearchive:
                raise ApprovalError(
                    assessment.summary_fr
                    + " — confirmation de réarchivage requise."
                )
            if assessment.offline_disc and not allow_offline:
                raise ApprovalError(
                    assessment.summary_fr + " — confirmation hors ligne requise."
                )
            assessment = assess_recovery_from_files(
                db,
                source_job_id,
                optical_device=optical_device,
                allow_offline=True if assessment.offline_disc else allow_offline,
                skip_optical_probe=skip_optical_probe,
            )
            if assessment.verdict == RecoveryVerdict.DENY:
                raise ApprovalError(assessment.summary_fr)
            if (
                assessment.verdict == RecoveryVerdict.REQUIRE_CONFIRM
                and assessment.requires_rearchive_confirmation
                and not confirmed_rearchive
            ):
                raise ApprovalError(assessment.summary_fr)

        if assessment.metadata is None or not assessment.flac_files:
            raise ApprovalError("Évaluation de reprise incomplète.")

        source_bytes = [p.read_bytes() for p in assessment.flac_files]
        source_mtimes = [p.stat().st_mtime for p in assessment.flac_files]

        report = run_archive_job(
            metadata=assessment.metadata,
            library_root=library_root,
            jobs_root=jobs_root,
            db=db,
            collision_policy=collision_policy,
            confirm_publish=confirm_publish,
            staged_flac_files=list(assessment.flac_files),
            skip_disc_match=True,
            confirmed_rearchive=confirmed_rearchive,
            cover_bytes=cover_bytes,
            on_progress=on_progress,
            cancel_event=cancel_event,
        )

        for p, data, mt in zip(assessment.flac_files, source_bytes, source_mtimes):
            if not p.is_file() or p.read_bytes() != data:
                log.error("Fichier source altéré pendant récupération : %s", p)
            elif p.stat().st_mtime != mt:
                log.warning("mtime source changé (contenu OK) : %s", p)

        snap = get_job_snapshot(db, source_job_id)
        if snap is not None:
            note = (
                f"Récupération contrôlée AVM-10B → nouveau job {report.job_id} "
                f"(état source conservé : {snap.state})."
            )
            conn = db.connect()
            conn.execute(
                """
                UPDATE jobs SET error_summary = ?, updated_at = ?
                WHERE id = ?
                """,
                (_append_error_note(snap.error_summary, note), _utc_now(), source_job_id),
            )
            conn.execute(
                """
                INSERT INTO job_checkpoints(job_id, step, payload_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    source_job_id,
                    "RecoverySpawned",
                    json.dumps(
                        {"new_job_id": report.job_id, "new_state": report.state},
                        ensure_ascii=False,
                    ),
                    _utc_now(),
                ),
            )
            conn.commit()

        return report
    finally:
        release_recovery(source_job_id)


# Réexports utiles
__all__ = [
    "ABANDON_NOTE",
    "LOCK_FILENAME",
    "LivenessKind",
    "RECONCILE_NOTE",
    "RecoveryAssessment",
    "RecoveryVerdict",
    "ReconciliationReport",
    "RipLockInfo",
    "assess_recovery_from_files",
    "build_job_situation",
    "clear_rip_lock",
    "freaccmd_process_running",
    "get_job_snapshot",
    "job_root_from_workdir",
    "list_job_flac_files",
    "list_unfinished_active_jobs",
    "mark_job_abandoned",
    "mark_job_interrupted",
    "read_rip_lock",
    "reconcile_unfinished_jobs",
    "recovery_in_progress",
    "release_recovery",
    "run_recovery_from_files",
    "try_acquire_recovery",
    "write_rip_lock",
]
