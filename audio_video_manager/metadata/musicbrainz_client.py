"""Client MusicBrainz (musicbrainzngs) — pas d'invention de données."""

from __future__ import annotations

import socket
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator

from audio_video_manager.logging_setup import get_logger
from audio_video_manager.metadata.musicbrainz_identity import (
    MusicBrainzIdentityError,
    build_musicbrainz_identity,
    resolve_musicbrainz_identity,
)

log = get_logger("metadata.musicbrainz")

# MusicBrainz : 1 req/s pour les apps anonymes — on reste conservateur
MIN_INTERVAL_SEC = 1.1

# Délai réseau borné — évite un blocage indéfini si la connexion est lente/perdue.
DEFAULT_TIMEOUT_SEC = 15.0
# Attente max acceptée pour un Retry-After (429) avant nouvel essai unique ;
# au-delà, on échoue plutôt que d'attendre indéfiniment.
MAX_RETRY_AFTER_SEC = 10.0


class MusicBrainzError(RuntimeError):
    pass


@dataclass
class ReleaseCandidate:
    """Édition candidate — champs uniquement s'ils sont présents dans la réponse."""

    release_id: str
    title: str
    artist_credit: str
    date: str | None = None
    year: int | None = None
    country: str | None = None
    barcode: str | None = None
    status: str | None = None
    disambiguation: str | None = None
    labels: list[str] = field(default_factory=list)
    catalog_numbers: list[str] = field(default_factory=list)
    medium_count: int | None = None
    matched_medium_position: int | None = None
    track_titles: list[str] = field(default_factory=list)
    track_artists: list[str] = field(default_factory=list)
    track_durations_ms: list[int | None] = field(default_factory=list)
    track_recording_ids: list[str | None] = field(default_factory=list)
    release_group_id: str | None = None
    release_group_first_release_date: str | None = None
    release_group_primary_type: str | None = None
    release_group_secondary_types: list[str] = field(default_factory=list)
    score_notes: list[str] = field(default_factory=list)
    toc_match: str = "unknown"  # exact | partial | mismatch | unknown
    match_source: str = "discid"  # discid | toc | cdstub
    is_cdstub: bool = False
    disc_id: str | None = None
    medium_track_count: int | None = None

    @property
    def selection_key(self) -> str:
        if self.is_cdstub:
            return f"cdstub:{self.disc_id or self.title or self.artist_credit}"
        return self.release_id


@dataclass
class DiscLookupResult:
    disc_id: str
    candidates: list[ReleaseCandidate]
    raw_release_count: int
    message: str
    ambiguous: bool


_last_call_monotonic = 0.0


def configure_musicbrainz(
    *,
    user_agent: tuple[str, str, str] | None = None,
    set_useragent_fn: Callable[..., None] | None = None,
) -> None:
    import musicbrainzngs

    try:
        identity = (
            build_musicbrainz_identity(
                application=user_agent[0],
                version=user_agent[1],
                contact=user_agent[2],
            )
            if user_agent is not None
            else resolve_musicbrainz_identity()
        )
    except MusicBrainzIdentityError as exc:
        raise MusicBrainzError(str(exc)) from exc
    fn = set_useragent_fn or musicbrainzngs.set_useragent
    fn(*identity.as_tuple())


def _rate_limit() -> None:
    global _last_call_monotonic
    now = time.monotonic()
    wait = MIN_INTERVAL_SEC - (now - _last_call_monotonic)
    if wait > 0:
        time.sleep(wait)
    _last_call_monotonic = time.monotonic()


@contextmanager
def _bounded_socket_timeout(seconds: float) -> Iterator[None]:
    """Borne le délai réseau par défaut pendant l'appel (restauré ensuite)."""
    previous = socket.getdefaulttimeout()
    socket.setdefaulttimeout(seconds)
    try:
        yield
    finally:
        socket.setdefaulttimeout(previous)


def _retry_after_seconds(exc: Exception) -> float | None:
    """Extrait un en-tête ``Retry-After`` numérique de l'exception HTTP sous-jacente."""
    cause = getattr(exc, "cause", None)
    headers = getattr(cause, "headers", None)
    if headers is None:
        return None
    try:
        raw = headers.get("Retry-After")
    except AttributeError:
        return None
    if not raw:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _artist_credit_str(credit: Any) -> str:
    if isinstance(credit, str):
        return credit
    if isinstance(credit, list):
        parts: list[str] = []
        for item in credit:
            if isinstance(item, dict):
                if "artist" in item and isinstance(item["artist"], dict):
                    parts.append(str(item["artist"].get("name", "")))
                elif "name" in item:
                    parts.append(str(item["name"]))
                joinphrase = item.get("joinphrase")
                if joinphrase:
                    parts.append(str(joinphrase))
            elif isinstance(item, str):
                parts.append(item)
        return "".join(parts).strip()
    return ""


def _parse_year(date: str | None) -> int | None:
    if not date:
        return None
    try:
        return int(date[:4])
    except ValueError:
        return None


def _extract_labels(release: dict[str, Any]) -> tuple[list[str], list[str]]:
    labels: list[str] = []
    catalogs: list[str] = []
    for li in release.get("label-info-list") or []:
        lab = li.get("label") or {}
        name = lab.get("name")
        if name:
            labels.append(str(name))
        cat = li.get("catalog-number")
        if cat:
            catalogs.append(str(cat))
    return labels, catalogs


def _medium_tracks(medium: dict[str, Any]) -> tuple[list[str], list[str], list[int | None], list[str | None]]:
    titles: list[str] = []
    artists: list[str] = []
    durs: list[int | None] = []
    rec_ids: list[str | None] = []
    for t in medium.get("track-list") or []:
        rec = t.get("recording") or {}
        titles.append(str(rec.get("title") or t.get("title") or ""))
        artists.append(_artist_credit_str(rec.get("artist-credit") or t.get("artist-credit") or ""))
        length = t.get("length") or rec.get("length")
        if length is not None:
            try:
                durs.append(int(length))
            except (TypeError, ValueError):
                durs.append(None)
        else:
            durs.append(None)
        rec_ids.append(str(rec["id"]) if rec.get("id") else None)
    return titles, artists, durs, rec_ids


def compare_toc_to_medium(
    toc_durations_ms: list[int],
    medium_durations_ms: list[int | None],
    *,
    tolerance_ms: int = 2000,
) -> tuple[str, list[str]]:
    """Compare durées TOC vs medium MB — ne force pas une correspondance."""
    notes: list[str] = []
    if len(toc_durations_ms) != len(medium_durations_ms):
        notes.append(
            f"Nombre de pistes TOC={len(toc_durations_ms)} "
            f"≠ medium MB={len(medium_durations_ms)}"
        )
        return "mismatch", notes
    mismatches = 0
    for i, (a, b) in enumerate(zip(toc_durations_ms, medium_durations_ms), start=1):
        if b is None:
            notes.append(f"Piste {i}: durée MB absente")
            mismatches += 1
            continue
        if abs(a - b) > tolerance_ms:
            notes.append(f"Piste {i}: TOC {a} ms vs MB {b} ms")
            mismatches += 1
    if mismatches == 0:
        return "exact", notes
    if mismatches < len(toc_durations_ms):
        return "partial", notes
    return "mismatch", notes


def lookup_releases_by_discid(
    disc_id: str,
    *,
    toc_durations_ms: list[int] | None = None,
    toc_string: str | None = None,
    get_releases_fn: Callable[..., dict[str, Any]] | None = None,
) -> DiscLookupResult:
    """
    Interroge MusicBrainz ``get_releases_by_discid``.

    ``get_releases_fn`` injectable pour les tests (pas d'invention côté prod).
    """
    configure_musicbrainz()
    import musicbrainzngs

    fn = get_releases_fn or musicbrainzngs.get_releases_by_discid

    def _call(**query: Any) -> dict[str, Any]:
        with _bounded_socket_timeout(DEFAULT_TIMEOUT_SEC):
            return fn(
                disc_id,
                includes=["artists", "recordings", "labels", "release-groups"],
                **query,
            )

    def _request(**query: Any) -> dict[str, Any] | None:
        _rate_limit()
        try:
            return _call(**query)
        except musicbrainzngs.ResponseError as exc:  # type: ignore[attr-defined]
            cause = getattr(exc, "cause", None)
            status = getattr(cause, "code", None) if cause is not None else None
            if status == 404:
                return None
            if status == 429:
                retry_after = _retry_after_seconds(exc)
                if retry_after is not None and 0 <= retry_after <= MAX_RETRY_AFTER_SEC:
                    log.info(
                        "MusicBrainz 429 — attente %.1fs puis nouvel essai unique",
                        retry_after,
                    )
                    time.sleep(retry_after)
                    _rate_limit()
                    try:
                        return _call(**query)
                    except Exception as retry_exc:  # noqa: BLE001
                        raise MusicBrainzError(
                            f"MusicBrainz limite de débit (429) persistante après attente: {retry_exc}"
                        ) from retry_exc
                suffix = (
                    f" (Retry-After={retry_after:.0f}s, au-delà du délai accepté)"
                    if retry_after is not None
                    else ""
                )
                raise MusicBrainzError(
                    f"MusicBrainz limite de débit (429) — réessayez plus tard{suffix}"
                ) from exc
            raise MusicBrainzError(f"Erreur MusicBrainz: {exc}") from exc
        except musicbrainzngs.NetworkError as exc:  # type: ignore[attr-defined]
            raise MusicBrainzError(f"Réseau MusicBrainz: {exc}") from exc
        except TimeoutError as exc:
            raise MusicBrainzError(
                f"Délai MusicBrainz dépassé ({DEFAULT_TIMEOUT_SEC:.0f}s): {exc}"
            ) from exc
        except Exception as exc:  # noqa: BLE001
            raise MusicBrainzError(f"MusicBrainz: {exc}") from exc

    def _release_list(raw: dict[str, Any] | None) -> list[dict[str, Any]]:
        disc_block = raw.get("disc") if isinstance(raw, dict) else None
        if isinstance(disc_block, dict) and "release-list" in disc_block:
            return list(disc_block.get("release-list") or [])
        return list((raw or {}).get("release-list") or [])

    exact_raw = _request()
    exact_releases = _release_list(exact_raw)
    stub_data = (exact_raw or {}).get("cdstub")
    release_list = exact_releases
    match_source = "discid"
    fuzzy_error: str | None = None
    if not exact_releases and toc_string:
        try:
            fuzzy_raw = _request(toc=toc_string, cdstubs=False)
        except MusicBrainzError as exc:
            if stub_data is None:
                raise
            fuzzy_error = str(exc)
        else:
            release_list = _release_list(fuzzy_raw)
            if release_list:
                match_source = "toc"

    candidates: list[ReleaseCandidate] = []
    seen_release_ids: set[str] = set()
    for rel in release_list:
        release_id = str(rel.get("id", ""))
        if release_id and release_id in seen_release_ids:
            continue
        if release_id:
            seen_release_ids.add(release_id)
        labels, catalogs = _extract_labels(rel)
        date = rel.get("date")
        mediums = rel.get("medium-list") or []
        # Choisir le medium qui référence ce disc-id si possible
        matched_pos = None
        chosen = None
        for med in mediums:
            discs = med.get("disc-list") or []
            if any(d.get("id") == disc_id for d in discs):
                chosen = med
                matched_pos = int(med.get("position") or 1)
                break
        if chosen is None and mediums:
            if toc_durations_ms is None:
                chosen = mediums[0]
            else:
                def medium_score(medium: dict[str, Any]) -> tuple[int, int]:
                    _, _, durations, _ = _medium_tracks(medium)
                    match, _ = compare_toc_to_medium(toc_durations_ms, durations)
                    priority = {"exact": 0, "partial": 1, "mismatch": 2, "unknown": 3}
                    delta = sum(
                        abs(source - target)
                        for source, target in zip(toc_durations_ms, durations)
                        if target is not None
                    )
                    delta += abs(len(toc_durations_ms) - len(durations)) * 1_000_000
                    return priority[match], delta

                chosen = min(mediums, key=medium_score)
            matched_pos = int(chosen.get("position") or 1)

        titles: list[str] = []
        artists: list[str] = []
        durs: list[int | None] = []
        rec_ids: list[str | None] = []
        toc_match = "unknown"
        notes: list[str] = []
        if chosen is not None:
            titles, artists, durs, rec_ids = _medium_tracks(chosen)
            if toc_durations_ms is not None:
                toc_match, notes = compare_toc_to_medium(toc_durations_ms, durs)

        rg = rel.get("release-group") or {}
        candidates.append(
            ReleaseCandidate(
                release_id=str(rel.get("id", "")),
                title=str(rel.get("title", "")),
                artist_credit=_artist_credit_str(rel.get("artist-credit")),
                date=date,
                year=_parse_year(date),
                country=rel.get("country"),
                barcode=rel.get("barcode"),
                status=rel.get("status"),
                disambiguation=rel.get("disambiguation"),
                labels=labels,
                catalog_numbers=catalogs,
                medium_count=len(mediums) or None,
                matched_medium_position=matched_pos,
                track_titles=titles,
                track_artists=artists,
                track_durations_ms=durs,
                track_recording_ids=rec_ids,
                release_group_id=str(rg["id"]) if rg.get("id") else None,
                release_group_first_release_date=rg.get("first-release-date") or None,
                release_group_primary_type=rg.get("primary-type") or None,
                release_group_secondary_types=[
                    str(value)
                    for value in (rg.get("secondary-type-list") or [])
                    if value
                ],
                score_notes=notes,
                toc_match=toc_match,
                match_source=match_source,
                disc_id=disc_id,
                medium_track_count=len(titles),
            )
        )

    if isinstance(stub_data, dict):
        raw_tracks = stub_data.get("track-list") or []
        if isinstance(raw_tracks, dict):
            raw_tracks = raw_tracks.get("track") or raw_tracks.get("track-list") or []
        if not isinstance(raw_tracks, list):
            raw_tracks = []
        track_titles = [str(track.get("title") or "") for track in raw_tracks]
        track_artists = [
            _artist_credit_str(track.get("artist-credit") or track.get("artist") or "")
            for track in raw_tracks
        ]
        track_durations: list[int | None] = []
        for track in raw_tracks:
            try:
                track_durations.append(int(track["length"]) if track.get("length") is not None else None)
            except (TypeError, ValueError):
                track_durations.append(None)
        stub_id = str(stub_data.get("id") or disc_id)
        candidates.append(
            ReleaseCandidate(
                release_id="",
                title=str(stub_data.get("title") or ""),
                artist_credit=str(stub_data.get("artist") or ""),
                barcode=str(stub_data["barcode"]) if stub_data.get("barcode") else None,
                track_titles=track_titles,
                track_artists=track_artists,
                track_durations_ms=track_durations,
                match_source="cdstub",
                is_cdstub=True,
                disc_id=stub_id,
                medium_track_count=(
                    len(raw_tracks)
                    or int(stub_data.get("count") or stub_data.get("track-count") or 0)
                    or None
                ),
            )
        )

    release_candidates = [candidate for candidate in candidates if not candidate.is_cdstub]
    has_stub = any(candidate.is_cdstub for candidate in candidates)
    ambiguous = len(release_candidates) > 1 or has_stub
    if release_candidates and match_source == "toc":
        msg = f"{len(release_candidates)} édition(s) trouvée(s) par correspondance TOC."
    elif release_candidates and len(release_candidates) > 1:
        msg = (
            f"{len(release_candidates)} éditions candidates — sélection manuelle requise "
            "(rééditions / pays / labels possibles)."
        )
    elif release_candidates:
        msg = "1 édition candidate MusicBrainz."
    elif has_stub:
        msg = "CD stub MusicBrainz disponible; métadonnées provisoires, sans édition confirmée."
        if fuzzy_error:
            msg += f" Recherche TOC indisponible : {fuzzy_error}"
    elif toc_string:
        msg = "Aucune édition MusicBrainz pour ce Disc ID ni pour la TOC."
    else:
        msg = "Aucun release MusicBrainz pour ce Disc ID (404)."

    log.info(
        "MB discid=%s source=%s releases=%s stubs=%s",
        disc_id,
        match_source,
        len(release_candidates),
        int(has_stub),
    )
    return DiscLookupResult(
        disc_id=disc_id,
        candidates=candidates,
        raw_release_count=len(release_list),
        message=msg,
        ambiguous=ambiguous,
    )
