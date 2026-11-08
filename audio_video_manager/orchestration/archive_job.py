"""Pipeline archive : match CD → rip/staging → tags → cover → publish C."""

from __future__ import annotations

import json
import re
import shutil
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from audio_video_manager.diagnostics.failure_kinds import FailureKind, format_user_error
from audio_video_manager.diagnostics.perf import PerfSession
from audio_video_manager.extraction.cd_ripper import (
    FreacCdRipper,
    ProgressCallback,
    RipRequest,
    RipResult,
    create_job_workdir,
)
from audio_video_manager.orchestration.rip_lock import (
    RipLockHeldError,
    clear_rip_lock,
    write_rip_lock,
)
from audio_video_manager.library.cover import (
    CoverMaterial,
    resolve_cover_for_sheet,
    write_cover_jpg,
)
from audio_video_manager.library.cover_geometry import analyze_cover_bytes
from audio_video_manager.library.disc_match import (
    DiscMismatchError,
    assert_disc_matches_sheet,
)
from audio_video_manager.library.duplicates import (
    DuplicateBlockedError,
    assert_archive_allowed,
    assess_from_sheet,
)
from audio_video_manager.library.disk_space import preflight_archive_paths
from audio_video_manager.library.paths import build_library_layout, inbox_job_dir
from audio_video_manager.library.publish import CollisionPolicy, PublishResult, publish_album
from audio_video_manager.library.tags import apply_flac_tags
from audio_video_manager.library.transfer import transfer_file
from audio_video_manager.logging_setup import get_logger
from audio_video_manager.metadata.enums import JobMode
from audio_video_manager.metadata.models import DiscMetadata
from audio_video_manager.metadata.path_preview import sanitize_segment
from audio_video_manager.metadata.toc_reader import DiscReadResult, read_disc_toc
from audio_video_manager.metadata.validation import (
    ApprovalError,
    assert_can_start_archive_rip,
)
from audio_video_manager.storage.database import Database
from audio_video_manager.verification.flac_decode import (
    FlacDecodeResult,
    decode_many,
    require_flac_decode,
)
from audio_video_manager.verification.flac_integrity import (
    FlacIntegrityResult,
    check_many,
)
from audio_video_manager.verification.rip_check import RipCheckResult, evaluate_rip_check
from audio_video_manager.verification.track_status import track_verification_status

log = get_logger("orchestration.archive_job")

# Préfère 01, 1, track01 en tête de nom ; évite de capturer un « 92 » d’année.
_TRACK_NUM_RE = re.compile(
    r"^(?:track[\s._-]*)?(\d{1,2})\b|^(\d{1,2})(?=[\s._-])",
    re.I,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class ArchiveJobReport:
    job_id: str
    workdir: Path
    mode: JobMode
    metadata_id: str
    rip: RipResult | None = None
    flac_integrity: list[FlacIntegrityResult] = field(default_factory=list)
    rip_check: RipCheckResult | None = None
    cover: CoverMaterial | None = None
    publish: PublishResult | None = None
    inbox_dir: Path | None = None
    warnings: list[str] = field(default_factory=list)
    state: str = "Unknown"
    error: str | None = None
    failure_kind: FailureKind | None = None
    perf: dict | None = None


def _track_num_from_name(stem: str) -> int | None:
    m = _TRACK_NUM_RE.search(stem.strip())
    if not m:
        return None
    raw = m.group(1) or m.group(2)
    return int(raw) if raw else None


def match_flacs_to_tracks(
    flac_files: list[Path],
    track_count: int,
) -> list[Path]:
    """
    Ordonne les FLAC pour correspondre aux pistes 1..N.

    Heuristique : numéro en tête de nom ; sinon tri alpha.
    Lève si count ≠ attendu, numéros dupliqués, ou trou dans 1..N quand tous sont numérotés.
    """
    if len(flac_files) != track_count:
        raise ApprovalError(
            format_user_error(
                kind=FailureKind.INTEGRITY,
                summary=(
                    f"Nombre de fichiers FLAC ({len(flac_files)}) différent "
                    f"du nombre de pistes de la fiche ({track_count}). "
                    "Publication refusée pour éviter un album incomplet."
                ),
                technical=f"flac_count={len(flac_files)} track_count={track_count}",
                action="Vérifiez l’extraction ou le mapping des noms de fichiers.",
            )
        )

    scored: list[tuple[int, Path]] = []
    seen: dict[int, Path] = {}
    for p in flac_files:
        num = _track_num_from_name(p.stem)
        if num is None:
            scored.append((10_000, p))
            continue
        if num in seen:
            raise ApprovalError(
                format_user_error(
                    kind=FailureKind.INTEGRITY,
                    summary=f"Deux fichiers semblent correspondre à la piste {num}.",
                    technical=f"{seen[num].name} vs {p.name}",
                    action="Renommez ou retirez le doublon avant de republier.",
                )
            )
        seen[num] = p
        scored.append((num, p))
    scored.sort(key=lambda x: (x[0], x[1].name.lower()))
    if len(seen) == track_count:
        missing = [i for i in range(1, track_count + 1) if i not in seen]
        if missing:
            raise ApprovalError(
                format_user_error(
                    kind=FailureKind.INTEGRITY,
                    summary="Numéros de pistes manquants dans les noms de fichiers.",
                    technical=f"missing={missing}",
                    action="Vérifiez le motif de nommage fre:ac (--pattern=<track>).",
                )
            )
    return [p for _, p in scored]


def _checkpoint(db: Database | None, job_id: str, step: str, payload: dict) -> None:
    if db is None:
        return
    conn = db.connect()
    now = _utc_now()
    conn.execute(
        "UPDATE jobs SET state=?, step=?, updated_at=? WHERE id=?",
        (step, step, now, job_id),
    )
    conn.execute(
        """
        INSERT INTO job_checkpoints(job_id, step, payload_json, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (job_id, step, json.dumps(payload, ensure_ascii=False), now),
    )
    conn.commit()


def run_archive_job(
    *,
    metadata: DiscMetadata,
    library_root: Path,
    jobs_root: Path,
    freaccmd: Path | None = None,
    drive_number: int = 0,
    db: Database | None = None,
    flac_compression: int = 5,
    eject_after_rip: bool = False,
    collision_policy: CollisionPolicy = CollisionPolicy.RENAME,
    confirm_publish: bool = False,
    optical_device: str | None = None,
    disc_read: DiscReadResult | None = None,
    skip_disc_match: bool = False,
    staged_flac_files: list[Path] | None = None,
    cover_bytes: bytes | None = None,
    cover_urlopen_fn: Callable[..., object] | None = None,
    confirmed_rearchive: bool = False,
    on_progress: ProgressCallback | None = None,
    cancel_event: threading.Event | None = None,
) -> ArchiveJobReport:
    """
    Pipeline archive complet.

    - ``staged_flac_files`` : injecte des FLAC (tests / reprise) — **pas de rip fre:ac**.
    - ``confirm_publish=False`` : s'arrête après tagging en zone A (+ copie inbox B).
    - ``confirm_publish=True`` : publication zone C non destructive.
    - ``confirmed_rearchive`` : confirmation explicite pour réarchiver un disque déjà présent.
    """
    assert_can_start_archive_rip(metadata)
    dup = assess_from_sheet(db, metadata)
    try:
        assert_archive_allowed(dup, confirmed_rearchive=confirmed_rearchive)
    except DuplicateBlockedError:
        raise
    layout = build_library_layout(metadata)
    warnings: list[str] = list(metadata.validation_warnings)
    if dup.gate.value != "allow":
        warnings.append(f"doublon:{dup.gate.value}:{dup.summary_fr}")
    if confirmed_rearchive:
        warnings.append("rearchive_confirmed=true")
    perf = PerfSession(label="archive_job")

    def progress(msg: str, frac: float | None = None) -> None:
        if on_progress:
            on_progress(msg, frac)
        log.info("%s", msg)

    # 1) Disc match
    # Rip réel : TOUJOURS relecture TOC (un disc_read stale ne doit pas masquer un CD remplacé).
    # Staging : pas d’optique ; disc_read optionnel vs fiche seulement.
    if not skip_disc_match:
        progress("Vérification Disc ID / TOC…", 0.02)
        with perf.span("disc_match") as meta:
            try:
                if staged_flac_files is not None:
                    meta["optical_toc_read"] = False
                    meta["reused_disc_read"] = disc_read is not None
                    if disc_read is not None:
                        assert_disc_matches_sheet(metadata, disc_read)
                    else:
                        warnings.append(
                            "Correspondance Disc ID non vérifiée (pipeline staging injecté)."
                        )
                else:
                    fresh = read_disc_toc(optical_device)
                    meta["optical_toc_read"] = True
                    meta["reused_disc_read"] = False
                    assert_disc_matches_sheet(metadata, fresh)
                    if (
                        disc_read is not None
                        and disc_read.disc_id
                        and fresh.disc_id
                        and disc_read.disc_id != fresh.disc_id
                    ):
                        raise DiscMismatchError(
                            "Le disque a changé depuis l’identification — "
                            f"avant={disc_read.disc_id}, maintenant={fresh.disc_id}. "
                            "Archivage refusé."
                        )
            except DiscMismatchError as exc:
                raise DiscMismatchError(
                    f"CD présent ≠ fiche approuvée — rip/archivage refusé. {exc}"
                ) from exc

    job_id, rip_dir = create_job_workdir(jobs_root)
    workdir = rip_dir.parent
    started = _utc_now()
    meta_id = metadata.id

    if db is not None:
        conn = db.connect()
        conn.execute(
            """
            INSERT INTO jobs(
                id, state, step, workdir, started_at, updated_at,
                mode, metadata_id, publish_allowed,
                selected_release_mbid, collision_policy, warnings_json,
                disc_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                "Ripping" if staged_flac_files is None else "Tagging",
                "Ripping" if staged_flac_files is None else "Staging",
                str(workdir),
                started,
                started,
                JobMode.NORMAL.value,
                meta_id,
                1 if confirm_publish else 0,
                metadata.edition.musicbrainz_release_id,
                collision_policy.value,
                json.dumps(warnings, ensure_ascii=False),
                metadata.identity.disc_id,
            ),
        )
        conn.commit()

    rip: RipResult | None = None
    flacs: list[Path]
    decode_results: list[FlacDecodeResult] = []

    # 2a) Précontrôle espace disque (jobs + bibliothèque, volumes distincts)
    staged_bytes: int | None = None
    if staged_flac_files is not None:
        staged_bytes = sum(p.stat().st_size for p in staged_flac_files if p.is_file())
    disk_checks = preflight_archive_paths(
        jobs_dir=jobs_root,
        library_root=library_root,
        track_count=len(metadata.tracks),
        staged_total_bytes=staged_bytes,
    )
    for chk in disk_checks:
        log.info("disk_preflight: %s", chk.message)
        if not chk.ok:
            err = format_user_error(
                kind=FailureKind.PUBLISH,
                summary="Espace disque insuffisant pour l’archivage / la publication.",
                technical=chk.message,
                action=(
                    "Libérez de l’espace sur le volume concerné puis réessayez. "
                    "Aucun fichier utilisateur n’a été modifié."
                ),
            )
            _finish_failed(db, job_id, "Failed", err)
            return ArchiveJobReport(
                job_id=job_id,
                workdir=workdir,
                mode=JobMode.NORMAL,
                metadata_id=meta_id,
                state="Failed",
                error=err,
                failure_kind=FailureKind.PUBLISH,
                warnings=warnings,
                perf=perf.summary(),
            )

    # 2) Rip ou staging
    if staged_flac_files is not None:
        progress("Copie staging injecté → zone A…", 0.1)
        flacs = []
        with perf.span("staging_to_zone_a", items=len(staged_flac_files)) as meta:
            bytes_out = 0
            methods: dict[str, int] = {}
            for src in staged_flac_files:
                dest = rip_dir / src.name
                method = transfer_file(src, dest)
                methods[method] = methods.get(method, 0) + 1
                bytes_out += dest.stat().st_size
                flacs.append(dest)
            meta["bytes_out"] = bytes_out
            meta["transfer"] = methods
        rip = RipResult(
            success=True,
            cancelled=False,
            returncode=0,
            argv=("staged",),
            stdout="",
            stderr="",
            flac_files=flacs,
            workdir=rip_dir,
        )
        _checkpoint(db, job_id, "Staging", {"flac_count": len(flacs)})
    else:
        if freaccmd is None:
            raise ApprovalError("freaccmd requis pour rip archive (ou fournir staged_flac_files)")
        if cancel_event and cancel_event.is_set():
            raise ApprovalError("Annulé avant rip")
        progress("Extraction fre:ac → zone A…", 0.15)
        _checkpoint(db, job_id, "Ripping", {"drive": drive_number})
        ripper = FreacCdRipper(freaccmd)
        request = RipRequest(
            freaccmd=Path(freaccmd),
            drive_number=drive_number,
            workdir=rip_dir,
            flac_compression=flac_compression,
            eject_after_rip=eject_after_rip,
        )
        try:
            write_rip_lock(rip_dir, job_id=job_id)
        except RipLockHeldError as exc:
            err = format_user_error(
                kind=FailureKind.EXTRACTION,
                summary="Extraction déjà en cours sur ce dossier de travail.",
                technical=str(exc),
                action="Attendez la fin de l’extraction en cours ou réessayez plus tard.",
            )
            _finish_failed(db, job_id, "Failed", err)
            return ArchiveJobReport(
                job_id=job_id,
                workdir=workdir,
                mode=JobMode.NORMAL,
                metadata_id=meta_id,
                state="Failed",
                error=err,
                failure_kind=FailureKind.EXTRACTION,
                warnings=warnings,
            )
        try:
            with perf.span("freac_rip") as meta:
                rip = ripper.rip(
                    request, on_progress=on_progress, cancel_event=cancel_event
                )
                meta["items"] = len(rip.flac_files)
                meta["returncode"] = rip.returncode
                meta["bytes_out"] = sum(
                    p.stat().st_size for p in rip.flac_files if p.is_file()
                )
        finally:
            clear_rip_lock(rip_dir)
        flacs = list(rip.flac_files)
        if rip.cancelled:
            err = format_user_error(
                kind=FailureKind.CANCELLED,
                summary="Extraction annulée par l’utilisateur.",
                technical=f"returncode={rip.returncode}",
                action="Vous pouvez relancer l’archivage plus tard.",
            )
            _finish_failed(db, job_id, "Cancelled", err)
            return ArchiveJobReport(
                job_id=job_id,
                workdir=workdir,
                mode=JobMode.NORMAL,
                metadata_id=meta_id,
                rip=rip,
                state="Cancelled",
                error=err,
                failure_kind=FailureKind.CANCELLED,
                warnings=warnings,
            )
        if not rip.success:
            err = rip.error or "Échec d’extraction"
            _finish_failed(db, job_id, "Failed", err)
            return ArchiveJobReport(
                job_id=job_id,
                workdir=workdir,
                mode=JobMode.NORMAL,
                metadata_id=meta_id,
                rip=rip,
                state="Failed",
                error=err,
                failure_kind=FailureKind.EXTRACTION,
                warnings=warnings,
            )

    # 3) Intégrité structurelle + décodage intégral si outil présent
    progress("Contrôle d’intégrité des fichiers…", 0.4)
    try:
        ordered = match_flacs_to_tracks(flacs, len(metadata.tracks))
    except ApprovalError as exc:
        msg = str(exc)
        _finish_failed(db, job_id, "Failed", msg)
        return ArchiveJobReport(
            job_id=job_id,
            workdir=workdir,
            mode=JobMode.NORMAL,
            metadata_id=meta_id,
            rip=rip,
            state="Failed",
            error=msg,
            failure_kind=FailureKind.INTEGRITY,
            warnings=warnings,
        )
    with perf.span("flac_integrity_f08a", items=len(ordered)) as meta:
        integrity = check_many(ordered)
        meta["bytes_in"] = sum(p.stat().st_size for p in ordered if p.is_file())
    rip_check = evaluate_rip_check(
        integrity,
        rip_success=True,
        cancelled=False,
    )
    if not all(i.ok for i in integrity):
        bad = [i for i in integrity if not i.ok]
        err = format_user_error(
            kind=FailureKind.INTEGRITY,
            summary="Au moins un fichier FLAC est illisible ou corrompu (contrôle structurel).",
            technical="; ".join(f"{b.path.name}: {b.message}" for b in bad[:5]),
            action="Ne publiez pas cet album ; conservez le dossier job pour analyse.",
        )
        _finish_failed(db, job_id, "Failed", err)
        return ArchiveJobReport(
            job_id=job_id,
            workdir=workdir,
            mode=JobMode.NORMAL,
            metadata_id=meta_id,
            rip=rip,
            flac_integrity=integrity,
            rip_check=rip_check,
            state="Failed",
            error=err,
            failure_kind=FailureKind.INTEGRITY,
            warnings=warnings,
            perf=perf.summary(),
        )

    with perf.span("flac_decode_full", items=len(ordered)) as meta:
        decode_results = decode_many(ordered)
        meta["attempted"] = bool(decode_results and decode_results[0].attempted)
        meta["tool"] = decode_results[0].tool if decode_results else None
        meta["bytes_in"] = sum(p.stat().st_size for p in ordered if p.is_file())
    if decode_results and not decode_results[0].attempted:
        # AVM-10D : absence ffmpeg = non exécuté (pas un succès). Politique V1 = avertir
        # sauf AVM_REQUIRE_FLAC_DECODE=1 → blocage.
        warnings.append(decode_results[0].message)
        if require_flac_decode():
            err = format_user_error(
                kind=FailureKind.INTEGRITY,
                summary=(
                    "Décodage intégral obligatoire (AVM_REQUIRE_FLAC_DECODE) "
                    "mais ffmpeg est introuvable."
                ),
                technical=decode_results[0].message,
                action=(
                    "Installez ffmpeg ou définissez AVM_FFMPEG, "
                    "ou retirez AVM_REQUIRE_FLAC_DECODE pour accepter "
                    "le contrôle structurel seul (avec avertissement)."
                ),
            )
            _finish_failed(db, job_id, "Failed", err)
            return ArchiveJobReport(
                job_id=job_id,
                workdir=workdir,
                mode=JobMode.NORMAL,
                metadata_id=meta_id,
                rip=rip,
                flac_integrity=integrity,
                rip_check=rip_check,
                state="Failed",
                error=err,
                failure_kind=FailureKind.INTEGRITY,
                warnings=warnings,
                perf=perf.summary(),
            )
    failed_decode = [d for d in decode_results if d.attempted and not d.ok]
    if failed_decode:
        err = format_user_error(
            kind=FailureKind.INTEGRITY,
            summary="Le décodage intégral a échoué pour au moins une piste (CRC / trames).",
            technical="; ".join(f"{d.path.name}: {d.message}" for d in failed_decode[:5]),
            action="Conservez les fichiers du job ; ne publiez pas.",
        )
        _finish_failed(db, job_id, "Failed", err)
        return ArchiveJobReport(
            job_id=job_id,
            workdir=workdir,
            mode=JobMode.NORMAL,
            metadata_id=meta_id,
            rip=rip,
            flac_integrity=integrity,
            rip_check=rip_check,
            state="Failed",
            error=err,
            failure_kind=FailureKind.INTEGRITY,
            warnings=warnings,
            perf=perf.summary(),
        )

    # Durées vs TOC (avertissement, non bloquant hors tolérance large)
    toc = metadata.identity.toc
    if toc and len(toc.track_durations_ms) == len(ordered):
        for path, track, toc_ms in zip(
            ordered,
            sorted(metadata.tracks, key=lambda t: t.number),
            toc.track_durations_ms,
        ):
            info = next((i for i in integrity if i.path == path), None)
            if not info or not info.streaminfo or not info.streaminfo.duration_sec:
                continue
            delta_ms = abs(int(info.streaminfo.duration_sec * 1000) - toc_ms)
            if delta_ms > 1500:
                warnings.append(
                    f"Piste {track.number}: durée FLAC ≈ {info.streaminfo.duration_sec:.1f}s "
                    f"vs TOC {toc_ms} ms (écart {delta_ms} ms)."
                )

    _checkpoint(
        db,
        job_id,
        "FlacIntegrity",
        {
            "ok": True,
            "n": len(ordered),
            "decode": "ok" if decode_results and decode_results[0].attempted else "skipped",
        },
    )

    # 4) Cover
    progress("Pochette…", 0.5)
    with perf.span("cover_resolve") as meta:
        cover = resolve_cover_for_sheet(
            metadata, urlopen_fn=cover_urlopen_fn, injected=cover_bytes
        )
        meta["status"] = cover.status
        meta["source"] = cover.source
        if cover.data:
            meta["bytes_in"] = len(cover.data)
    if cover.status == "unavailable":
        warnings.append(cover.message)
    elif cover.status == "error":
        warnings.append(
            format_user_error(
                kind=FailureKind.METADATA,
                summary="La pochette n’a pas pu être récupérée.",
                technical=cover.message,
                action="L’album peut être publié sans pochette ; vous pourrez l’ajouter plus tard.",
            )
        )
    elif cover.status == "ok" and cover.data:
        geom = analyze_cover_bytes(cover.data, mime_hint=cover.mime)
        warnings.extend(geom.notes)
    embed_bytes = cover.data if cover.status == "ok" else None
    embed_mime = cover.mime if cover.status == "ok" else None

    # 5) Tagging — copie rip→tagged obligatoire (zone A conservée pour récupération)
    progress("Écriture tags mutagen…", 0.6)
    _checkpoint(db, job_id, "Tagging", {"tracks": len(ordered)})
    tracks_sorted = sorted(metadata.tracks, key=lambda t: t.number)
    tagged_dir = workdir / "tagged"
    tagged_dir.mkdir(parents=True, exist_ok=True)
    tagged_files: list[Path] = []
    with perf.span("tagging_copy_and_write", items=len(ordered)) as meta:
        bytes_out = 0
        for flac_src, track in zip(ordered, tracks_sorted):
            if cancel_event and cancel_event.is_set():
                err = format_user_error(
                    kind=FailureKind.INTERRUPTED,
                    summary="Archivage interrompu pendant l’écriture des tags.",
                    action="Les fichiers déjà tagués restent dans le dossier job.",
                )
                _finish_failed(db, job_id, "Interrupted", err)
                return ArchiveJobReport(
                    job_id=job_id,
                    workdir=workdir,
                    mode=JobMode.NORMAL,
                    metadata_id=meta_id,
                    rip=rip,
                    flac_integrity=integrity,
                    rip_check=rip_check,
                    cover=cover,
                    state="Interrupted",
                    error=err,
                    failure_kind=FailureKind.INTERRUPTED,
                    warnings=warnings,
                    perf=perf.summary(),
                )
            title_part = sanitize_segment(track.title or "", fallback="_")
            dest_name = f"{track.number:02d} - {title_part}.flac"
            dest = tagged_dir / dest_name
            if dest.exists():
                # Collision (numéro dupliqué ou titres convergents après
                # sanitisation) — jamais d'écrasement silencieux d'un FLAC déjà
                # tagué (AVM-19 P1-9).
                n = 2
                while True:
                    candidate = tagged_dir / f"{track.number:02d} - {title_part} ({n}).flac"
                    if not candidate.exists():
                        dest = candidate
                        break
                    n += 1
            # Copie physique : le tagging mutagen réécrit le fichier (pas de hardlink).
            shutil.copy2(flac_src, dest)
            apply_flac_tags(
                dest,
                metadata,
                track,
                cover_image=embed_bytes,
                cover_mime=embed_mime,
            )
            bytes_out += dest.stat().st_size
            tagged_files.append(dest)
        meta["bytes_out"] = bytes_out

    staged_cover: Path | None = None
    if embed_bytes:
        staged_cover = write_cover_jpg(tagged_dir / "cover.jpg", cover)

    # 6) Inbox B (toujours pour traçabilité) — hardlink si même volume
    progress("Zone B inbox…", 0.75)
    inbox = inbox_job_dir(library_root, job_id)
    inbox.mkdir(parents=True, exist_ok=True)
    with perf.span("inbox_transfer", items=len(tagged_files)) as meta:
        methods: dict[str, int] = {}
        bytes_out = 0
        for f in tagged_files:
            method = transfer_file(f, inbox / f.name)
            methods[method] = methods.get(method, 0) + 1
            bytes_out += f.stat().st_size
        if staged_cover:
            method = transfer_file(staged_cover, inbox / "cover.jpg")
            methods[method] = methods.get(method, 0) + 1
            bytes_out += staged_cover.stat().st_size
        meta["bytes_out"] = bytes_out
        meta["transfer"] = methods
    _checkpoint(db, job_id, "Organizing", {"inbox": str(inbox)})

    publish_result: PublishResult | None = None
    state = "ReadyToPublish"

    # 7) Publish C — revalidation doublons juste avant publication
    if confirm_publish:
        progress("Contrôle doublons avant publication…", 0.88)
        dup_pre_pub = assess_from_sheet(db, metadata, exclude_job_id=job_id)
        try:
            assert_archive_allowed(
                dup_pre_pub, confirmed_rearchive=confirmed_rearchive
            )
        except DuplicateBlockedError as exc:
            blocked = format_user_error(
                kind=FailureKind.PUBLISH,
                summary="Publication bloquée par les garde-fous doublons.",
                technical=str(exc),
                action=(
                    "Confirmez un réarchivage volontaire depuis l’assistant, "
                    "ou attendez la fin d’une opération concurrente."
                ),
            )
            _finish_failed(db, job_id, "Failed", blocked)
            return ArchiveJobReport(
                job_id=job_id,
                workdir=workdir,
                mode=JobMode.NORMAL,
                metadata_id=meta_id,
                rip=rip,
                flac_integrity=integrity,
                rip_check=rip_check,
                cover=cover,
                inbox_dir=inbox,
                warnings=warnings + [str(exc)],
                state="Failed",
                error=blocked,
                failure_kind=FailureKind.PUBLISH,
                perf=perf.summary(),
            )

        progress("Publication bibliothèque C…", 0.9)
        try:
            with perf.span("publish_c", items=len(tagged_files)) as meta:
                publish_result = publish_album(
                    library_root=Path(library_root),
                    layout=layout,
                    staged_tracks=tagged_files,
                    staged_cover=staged_cover,
                    policy=collision_policy,
                )
                meta["published"] = publish_result.published
                meta["skipped"] = publish_result.skipped
                meta["message"] = publish_result.message
        except RuntimeError as exc:
            # Copie interrompue / collision mid-write : rollback tenté dans publish_album
            pub_err = format_user_error(
                kind=FailureKind.PUBLISH,
                summary="La publication a été interrompue ou a rencontré une collision.",
                technical=str(exc),
                action=(
                    "Vérifiez le dossier album et `.avm-trash` ; "
                    "les fichiers tagués restent en zone A/B. "
                    "Sous Windows, une restauration trash peut être nécessaire manuellement."
                ),
            )
            _finish_failed(db, job_id, "Failed", pub_err)
            return ArchiveJobReport(
                job_id=job_id,
                workdir=workdir,
                mode=JobMode.NORMAL,
                metadata_id=meta_id,
                rip=rip,
                flac_integrity=integrity,
                rip_check=rip_check,
                cover=cover,
                inbox_dir=inbox,
                warnings=warnings,
                state="Failed",
                error=pub_err,
                failure_kind=FailureKind.PUBLISH,
                perf=perf.summary(),
            )
        if publish_result.skipped:
            state = "SkippedDuplicate"
            warnings.append(publish_result.message)
        elif publish_result.published:
            state = (
                "CompletedWithWarnings" if warnings else "Completed"
            )
            # Enregistrer release
            if db is not None and publish_result.album_dir:
                _record_release(
                    db,
                    metadata,
                    publish_result,
                    integrity=integrity,
                    decode_results=decode_results,
                    rip_check=rip_check,
                )
        else:
            state = "Failed"
            pub_err = format_user_error(
                kind=FailureKind.PUBLISH,
                summary="La publication dans la bibliothèque a échoué.",
                technical=publish_result.message,
                action=(
                    "Les fichiers tagués restent dans le dossier temporaire / inbox ; "
                    "aucun écrasement silencieux n’a été tenté."
                ),
            )
            _finish_failed(db, job_id, state, pub_err)
            return ArchiveJobReport(
                job_id=job_id,
                workdir=workdir,
                mode=JobMode.NORMAL,
                metadata_id=meta_id,
                rip=rip,
                flac_integrity=integrity,
                rip_check=rip_check,
                cover=cover,
                publish=publish_result,
                inbox_dir=inbox,
                warnings=warnings,
                state=state,
                error=pub_err,
                failure_kind=FailureKind.PUBLISH,
            )
    else:
        warnings.append(
            "Publication C non confirmée — fichiers en zone A/B uniquement."
        )
        state = "AwaitingPublishConfirmation"

    finished = _utc_now()
    if db is not None:
        conn = db.connect()
        conn.execute(
            """
            UPDATE jobs SET state=?, step=?, updated_at=?, finished_at=?,
                error_summary=?, warnings_json=?, library_path=?
            WHERE id=?
            """,
            (
                state,
                state,
                finished,
                finished if state.startswith("Completed") or state == "SkippedDuplicate" else None,
                None,
                json.dumps(warnings, ensure_ascii=False),
                str(publish_result.album_dir) if publish_result and publish_result.album_dir else None,
                job_id,
            ),
        )
        conn.commit()

    progress("Terminé.", 1.0)
    return ArchiveJobReport(
        job_id=job_id,
        workdir=workdir,
        mode=JobMode.NORMAL,
        metadata_id=meta_id,
        rip=rip,
        flac_integrity=integrity,
        rip_check=rip_check,
        cover=cover,
        publish=publish_result,
        inbox_dir=inbox,
        warnings=warnings,
        state=state,
        perf=perf.summary(),
    )


def _finish_failed(db: Database | None, job_id: str, state: str, error: str) -> None:
    if db is None:
        return
    now = _utc_now()
    conn = db.connect()
    conn.execute(
        """
        UPDATE jobs SET state=?, step=?, updated_at=?, finished_at=?, error_summary=?
        WHERE id=?
        """,
        (state, state, now, now, error, job_id),
    )
    conn.commit()


def _record_release(
    db: Database,
    metadata: DiscMetadata,
    publish: PublishResult,
    *,
    integrity: list[FlacIntegrityResult],
    decode_results: list[FlacDecodeResult],
    rip_check: RipCheckResult | None,
) -> None:
    """Persiste les résultats de contrôle **réellement** exécutés (AVM-10D)."""
    conn = db.connect()
    now = _utc_now()
    cur = conn.execute(
        """
        INSERT INTO releases(disc_id, mbid, album_artist, album, year, path, status, imported_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            metadata.identity.disc_id,
            metadata.edition.musicbrainz_release_id,
            metadata.edition.album_artist,
            metadata.edition.album_title,
            metadata.edition.year,
            str(publish.album_dir),
            "imported",
            now,
        ),
    )
    release_id = cur.lastrowid
    tracks = sorted(metadata.tracks, key=lambda t: t.number)
    for idx, (track, path) in enumerate(zip(tracks, publish.track_paths)):
        integ = integrity[idx] if idx < len(integrity) else None
        dec = decode_results[idx] if idx < len(decode_results) else None
        status = track_verification_status(integ, dec, rip_check)
        conn.execute(
            """
            INSERT INTO tracks(release_id, number, title, path, duration_ms, flac_ok, rip_check_status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                release_id,
                track.number,
                track.title,
                str(path),
                track.duration_ms,
                status.flac_ok,
                status.rip_check_status,
            ),
        )
    conn.commit()
