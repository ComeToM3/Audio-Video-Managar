"""On-demand, non-persistent metadata evidence from official catalog APIs."""

from __future__ import annotations

import html
import json
import os
import re
import threading
import time
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from audio_video_manager.metadata.musicbrainz_client import ReleaseCandidate

DISCOGS_USER_AGENT = "AudioVideoManager/0.5.0"
DISCOGS_UNAUTHENTICATED_END_DATE = date(2026, 12, 1)
DISCOGS_ANONYMOUS_MIN_INTERVAL_SEC = 2.5  # 24 requests/minute, below the 25/min limit.
DISCOGS_AUTHENTICATED_MIN_INTERVAL_SEC = 1.05  # below the documented 60/min limit.
_REQUEST_TIMEOUT_SEC = 8

_last_discogs_request = 0.0
_discogs_rate_lock = threading.Lock()


@dataclass(frozen=True)
class MetadataEvidence:
    field: str
    value: Any
    source: str
    source_url: str
    confidence: str
    note: str
    retrieved_at: str


@dataclass(frozen=True)
class MetadataConflict:
    field: str
    evidence: tuple[MetadataEvidence, ...]
    note: str


@dataclass(frozen=True)
class DiscogsTrack:
    position: int
    title: str
    duration_ms: int | None


@dataclass(frozen=True)
class DiscogsReleaseEvidence:
    release_id: int
    source_url: str
    title: str
    country: str | None
    barcode: str | None
    year: int | None
    labels: tuple[str, ...]
    catalog_numbers: tuple[str, ...]
    formats: tuple[str, ...]
    tracks: tuple[DiscogsTrack, ...]
    data_quality: str | None
    copyright_notice_years: tuple[int, ...] = ()


@dataclass(frozen=True)
class TrackDurationComparison:
    number: int
    title: str
    toc_ms: int
    release_track_ms: int
    delta_ms: int


@dataclass(frozen=True)
class DiscogsLookup:
    status: str
    release: DiscogsReleaseEvidence | None = None
    message: str = ""


@dataclass
class EnrichmentReport:
    proposals: list[MetadataEvidence] = field(default_factory=list)
    conflicts: list[MetadataConflict] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)
    track_durations: list[TrackDurationComparison] = field(default_factory=list)

    def to_html(self) -> str:
        """Render escaped evidence with source attribution links for the UI."""
        chunks = ["<b>Propositions de métadonnées (non appliquées)</b><ul>"]
        uses_discogs = any(item.source == "Discogs" for item in self.proposals)
        for item in self.proposals:
            value = "inconnue" if item.value is None else html.escape(str(item.value))
            source = html.escape(item.source)
            url = _safe_source_url(item.source_url)
            source_link = (
                f'<a href="{html.escape(url, quote=True)}">{source}</a>'
                if url
                else source
            )
            attribution = (
                f' <a href="{html.escape(url, quote=True)}">Data provided by Discogs.</a>'
                if item.source == "Discogs" and url
                else ""
            )
            chunks.append(
                "<li><b>"
                + html.escape(item.field)
                + ":</b> "
                + value
                + f" — confiance {html.escape(item.confidence)} — {source_link}{attribution}. "
                + html.escape(item.note)
                + f" <small>Récupéré {html.escape(item.retrieved_at)}</small>"
                + "</li>"
            )
        chunks.append("</ul>")
        if uses_discogs:
            chunks.append(
                "<p>This application uses Discogs' API but is not affiliated with, "
                "sponsored or endorsed by Discogs.</p>"
            )
        if self.conflicts:
            chunks.append("<b>Conflits</b><ul>")
            for conflict in self.conflicts:
                values = "; ".join(
                    f'{item.source}: {item.value!s} '
                    f'(<a href="{html.escape(_safe_source_url(item.source_url), quote=True)}">source</a>, '
                    f'confiance {item.confidence})'
                    for item in conflict.evidence
                )
                chunks.append(
                    "<li><b>"
                    + html.escape(conflict.field)
                    + ":</b> "
                    + html.escape(values)
                    + " — "
                    + html.escape(conflict.note)
                    + "</li>"
                )
            chunks.append("</ul>")
        if self.track_durations:
            deltas = [item.delta_ms for item in self.track_durations]
            within = sum(delta <= 2000 for delta in deltas)
            chunks.append(
                "<p>Durées track MusicBrainz / TOC : "
                f"{within}/{len(deltas)} à ±2000 ms; écart maximal "
                f"{max(deltas)} ms.</p>"
            )
            outliers = [item for item in self.track_durations if item.delta_ms > 2000]
            if outliers:
                chunks.append("<ul>")
                for item in outliers:
                    chunks.append(
                        f"<li>Piste {item.number} ({html.escape(item.title)}): "
                        f"TOC {item.toc_ms} ms, release track {item.release_track_ms} ms, "
                        f"delta {item.delta_ms} ms.</li>"
                    )
                chunks.append("</ul>")
        if self.messages:
            chunks.append("<ul>" + "".join(f"<li>{html.escape(m)}</li>" for m in self.messages) + "</ul>")
        return "".join(chunks)


def _safe_source_url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme != "https" or parsed.hostname not in {
        "musicbrainz.org",
        "www.discogs.com",
        "discogs.com",
    }:
        return ""
    return value


def _digits(value: str | None) -> str:
    return "".join(ch for ch in (value or "") if ch.isdigit())


def _parse_duration(value: str | None) -> int | None:
    if not value:
        return None
    match = re.fullmatch(r"\s*(\d{1,3}):(\d{2})(?:\.(\d{1,3}))?\s*", value)
    if not match:
        return None
    minutes, seconds, fraction = match.groups()
    millis = int((fraction or "0").ljust(3, "0"))
    return (int(minutes) * 60 + int(seconds)) * 1000 + millis


def _rate_limit(*, authenticated: bool) -> None:
    global _last_discogs_request
    interval = (
        DISCOGS_AUTHENTICATED_MIN_INTERVAL_SEC
        if authenticated
        else DISCOGS_ANONYMOUS_MIN_INTERVAL_SEC
    )
    with _discogs_rate_lock:
        delay = interval - (time.monotonic() - _last_discogs_request)
        if delay > 0:
            time.sleep(delay)
        _last_discogs_request = time.monotonic()


def _get_json(
    url: str,
    *,
    token: str | None,
    urlopen_fn: Callable[..., Any],
    timeout: int,
) -> dict[str, Any]:
    headers = {"User-Agent": DISCOGS_USER_AGENT, "Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Discogs token={token}"
    request = Request(url, headers=headers)
    _rate_limit(authenticated=bool(token))
    with urlopen_fn(request, timeout=timeout) as response:
        data = json.loads(response.read().decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Discogs API returned a non-object JSON response")
    return data


def _parse_release(data: dict[str, Any]) -> DiscogsReleaseEvidence:
    release_id = int(data["id"])
    year_value = data.get("year")
    try:
        year = int(year_value) if int(year_value or 0) > 0 else None
    except (TypeError, ValueError):
        year = None
    labels = tuple(
        str(item.get("name"))
        for item in data.get("labels", [])
        if isinstance(item, dict) and item.get("name")
    )
    catalogs = tuple(
        str(item.get("catno"))
        for item in data.get("labels", [])
        if isinstance(item, dict) and item.get("catno")
    )
    formats = tuple(
        str(description)
        for fmt in data.get("formats", [])
        if isinstance(fmt, dict)
        for description in [fmt.get("name"), *(fmt.get("descriptions") or [])]
        if description
    )
    tracks: list[DiscogsTrack] = []
    for item in data.get("tracklist", []):
        if not isinstance(item, dict) or item.get("type_") not in (None, "track"):
            continue
        try:
            position = int(item.get("position") or len(tracks) + 1)
        except (TypeError, ValueError):
            position = len(tracks) + 1
        tracks.append(
            DiscogsTrack(
                position=position,
                title=str(item.get("title") or ""),
                duration_ms=_parse_duration(item.get("duration")),
            )
        )
    notes = str(data.get("notes") or "")
    copyright_years = tuple(
        sorted(
            {
                int(year)
                for year in re.findall(r"(?:℗|©)\s*(?:[^\d\n]{0,40})((?:19|20)\d{2})", notes)
            }
        )
    )
    return DiscogsReleaseEvidence(
        release_id=release_id,
        source_url=str(data.get("uri") or f"https://www.discogs.com/release/{release_id}"),
        title=str(data.get("title") or ""),
        country=str(data["country"]) if data.get("country") else None,
        barcode=next(
            (
                str(identifier.get("value"))
                for identifier in data.get("identifiers", [])
                if isinstance(identifier, dict)
                and str(identifier.get("type", "")).casefold() == "barcode"
            ),
            None,
        ),
        year=year,
        labels=labels,
        catalog_numbers=catalogs,
        formats=formats,
        tracks=tuple(tracks),
        data_quality=str(data["data_quality"]) if data.get("data_quality") else None,
        copyright_notice_years=copyright_years,
    )


def lookup_discogs_by_barcode(
    barcode: str | None,
    *,
    token: str | None = None,
    urlopen_fn: Callable[..., Any] = urlopen,
    timeout: int = _REQUEST_TIMEOUT_SEC,
    today: date | None = None,
) -> DiscogsLookup:
    """Fetch one exact barcode match from the documented Discogs API; never cache."""
    digits = _digits(barcode)
    if not digits:
        return DiscogsLookup("skipped", message="Aucun code-barres pour la recherche Discogs.")
    auth_token = token if token is not None else os.environ.get("AVM_DISCOGS_TOKEN")
    request_date = today or date.today()
    if not auth_token and request_date >= DISCOGS_UNAUTHENTICATED_END_DATE:
        return DiscogsLookup(
            "auth_required",
            message="Discogs exige une authentification API depuis le 1 décembre 2026.",
        )
    try:
        query = urlencode({"barcode": digits, "type": "release", "per_page": 10})
        search = _get_json(
            f"https://api.discogs.com/database/search?{query}",
            token=auth_token,
            urlopen_fn=urlopen_fn,
            timeout=timeout,
        )
        exact = [
            item
            for item in (search.get("results") or [])
            if any(_digits(value) == digits for value in (item.get("barcode") or []))
        ]
        if not exact:
            return DiscogsLookup("not_found", message="Aucun résultat Discogs au code-barres exact.")
        if len(exact) != 1:
            return DiscogsLookup(
                "ambiguous",
                message=f"{len(exact)} résultats Discogs partagent ce code-barres exact.",
            )
        release_id = int(exact[0]["id"])
        data = _get_json(
            f"https://api.discogs.com/releases/{release_id}",
            token=auth_token,
            urlopen_fn=urlopen_fn,
            timeout=timeout,
        )
        release = _parse_release(data)
        if _digits(release.barcode) != digits:
            return DiscogsLookup(
                "mismatch",
                message="Le détail Discogs ne confirme pas le code-barres exact.",
            )
        return DiscogsLookup("matched", release=release, message="Code-barres exact confirmé.")
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, KeyError, TypeError) as exc:
        return DiscogsLookup(
            "unavailable",
            message=f"Discogs indisponible : {type(exc).__name__}.",
        )


def _normal_title(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value).casefold()
    return " ".join(
        "".join(
            " " if unicodedata.category(char).startswith("P") else char
            for char in decomposed
            if not unicodedata.combining(char)
        )
        .split()
    )


def build_enrichment_report(
    candidate: ReleaseCandidate,
    discogs: DiscogsLookup | None = None,
    *,
    retrieved_at: str | None = None,
    toc_durations_ms: list[int] | None = None,
) -> EnrichmentReport:
    now = retrieved_at or datetime.now(timezone.utc).isoformat()
    result = EnrichmentReport()
    release_url = f"https://musicbrainz.org/release/{candidate.release_id}"
    group_url = (
        f"https://musicbrainz.org/release-group/{candidate.release_group_id}"
        if candidate.release_group_id
        else release_url
    )
    result.proposals.append(
        MetadataEvidence(
            field="year (édition précise)",
            value=candidate.year,
            source="MusicBrainz release",
            source_url=release_url,
            confidence="élevée" if candidate.year else "élevée (absence explicite)",
            note=(
                f"date release={candidate.date or 'absente'}; ne pas remplacer par la date du groupe"
                if candidate.year is None
                else f"date release={candidate.date}"
            ),
            retrieved_at=now,
        )
    )
    result.proposals.extend(
        [
            MetadataEvidence(
                field="album_title",
                value=candidate.title,
                source="MusicBrainz release",
                source_url=release_url,
                confidence="élevée",
                note="Titre porté par le release correspondant au Disc ID.",
                retrieved_at=now,
            ),
            MetadataEvidence(
                field="album_artist",
                value=candidate.artist_credit,
                source="MusicBrainz release",
                source_url=release_url,
                confidence="élevée",
                note="Artist credit du release.",
                retrieved_at=now,
            ),
            MetadataEvidence(
                field="country",
                value=candidate.country,
                source="MusicBrainz release",
                source_url=release_url,
                confidence="élevée" if candidate.country else "élevée (absence explicite)",
                note="Pays du release, distinct de la première publication du groupe.",
                retrieved_at=now,
            ),
            MetadataEvidence(
                field="barcode",
                value=candidate.barcode,
                source="MusicBrainz release",
                source_url=release_url,
                confidence="élevée" if candidate.barcode else "élevée (absence explicite)",
                note="Identifiant utilisé pour rechercher l'édition physique.",
                retrieved_at=now,
            ),
        ]
    )
    if candidate.release_group_first_release_date:
        result.proposals.append(
            MetadataEvidence(
                field="première publication (release-group, distincte de l'édition)",
                value=candidate.release_group_first_release_date,
                source="MusicBrainz release-group",
                source_url=group_url,
                confidence="élevée",
                note="Information contextuelle; ne pas utiliser comme année du pressage.",
                retrieved_at=now,
            )
        )
    if toc_durations_ms is not None:
        if len(toc_durations_ms) != len(candidate.track_durations_ms):
            result.conflicts.append(
                MetadataConflict(
                    field="track_count",
                    evidence=(),
                    note=(
                        f"TOC={len(toc_durations_ms)} pistes; release track="
                        f"{len(candidate.track_durations_ms)} pistes."
                    ),
                )
            )
        for index, toc_ms in enumerate(toc_durations_ms):
            if index >= len(candidate.track_durations_ms):
                break
            release_ms = candidate.track_durations_ms[index]
            if release_ms is None:
                continue
            result.track_durations.append(
                TrackDurationComparison(
                    number=index + 1,
                    title=(
                        candidate.track_titles[index]
                        if index < len(candidate.track_titles)
                        else ""
                    ),
                    toc_ms=int(toc_ms),
                    release_track_ms=int(release_ms),
                    delta_ms=abs(int(toc_ms) - int(release_ms)),
                )
            )

    if "Compilation" in candidate.release_group_secondary_types:
        result.proposals.append(
            MetadataEvidence(
                field="is_compilation",
                value=True,
                source="MusicBrainz release-group",
                source_url=group_url,
                confidence="élevée",
                note="Type secondaire Compilation; confirmation utilisateur requise.",
                retrieved_at=now,
            )
        )

    release = discogs.release if discogs and discogs.status == "matched" else None
    if release is None:
        if discogs and discogs.message:
            result.messages.append(discogs.message)
        else:
            result.messages.append("Aucune recherche Discogs effectuée.")
        return result

    confidence = "faible" if (release.data_quality or "").casefold() == "needs vote" else "moyenne"
    result.proposals.extend(
        [
            MetadataEvidence(
                field="year (édition précise)",
                value=release.year,
                source="Discogs",
                source_url=release.source_url,
                confidence=confidence,
                note=(
                    f"year={release.year}"
                    if release.year is not None
                    else "API year=0/absent : aucune année de release confirmée."
                ),
                retrieved_at=now,
            ),
            MetadataEvidence(
                field="is_compilation",
                value=True if any(x.casefold() == "compilation" for x in release.formats) else None,
                source="Discogs",
                source_url=release.source_url,
                confidence=confidence,
                note=f"Formats={', '.join(release.formats) or 'non renseignés'}; data_quality={release.data_quality or 'unknown'}.",
                retrieved_at=now,
            ),
            MetadataEvidence(
                field="label / numéro de catalogue",
                value="; ".join((*release.labels, *release.catalog_numbers)) or None,
                source="Discogs",
                source_url=release.source_url,
                confidence=confidence,
                note="Donnée de catalogue contributive; vérifier le livret/pressage physique.",
                retrieved_at=now,
            ),
            MetadataEvidence(
                field="album_title",
                value=release.title,
                source="Discogs",
                source_url=release.source_url,
                confidence=confidence,
                note=f"data_quality={release.data_quality or 'unknown'}.",
                retrieved_at=now,
            ),
            MetadataEvidence(
                field="barcode",
                value=release.barcode,
                source="Discogs",
                source_url=release.source_url,
                confidence="élevée",
                note="Code-barres exact utilisé pour sélectionner ce release.",
                retrieved_at=now,
            ),
            MetadataEvidence(
                field="is_reissue",
                value=True if any(x.casefold() == "reissue" for x in release.formats) else None,
                source="Discogs",
                source_url=release.source_url,
                confidence=confidence,
                note=(
                    "Format Discogs inclut Reissue; ne constitue pas une date de publication."
                    if any(x.casefold() == "reissue" for x in release.formats)
                    else "Aucune classification Reissue explicite."
                ),
                retrieved_at=now,
            ),
        ]
    )
    if release.copyright_notice_years:
        result.proposals.append(
            MetadataEvidence(
                field="copyright / phonogram dates (not release year)",
                value=", ".join(str(year) for year in release.copyright_notice_years),
                source="Discogs",
                source_url=release.source_url,
                confidence=confidence,
                note="Dates ℗/© tirées des notes; elles ne prouvent pas la date du pressage.",
                retrieved_at=now,
            )
        )

    by_field: dict[str, list[MetadataEvidence]] = {}
    for evidence in result.proposals:
        if evidence.value is not None:
            by_field.setdefault(evidence.field, []).append(evidence)
    for field_name, evidence in by_field.items():
        distinct = {str(item.value).casefold() for item in evidence}
        if len(distinct) > 1:
            result.conflicts.append(
                MetadataConflict(
                    field=field_name,
                    evidence=tuple(evidence),
                    note="Sources en désaccord; aucune valeur n'est appliquée automatiquement.",
                )
            )

    if candidate.track_titles and release.tracks:
        mb_titles = [_normal_title(title) for title in candidate.track_titles]
        dg_titles = [_normal_title(track.title) for track in release.tracks]
        mismatches = [
            index + 1
            for index, (left, right) in enumerate(zip(mb_titles, dg_titles))
            if left != right
        ]
        if len(mb_titles) != len(dg_titles) or mismatches:
            result.conflicts.append(
                MetadataConflict(
                    field="tracklist",
                    evidence=(
                        MetadataEvidence(
                            field="tracklist",
                            value=f"MusicBrainz: {len(mb_titles)} pistes",
                            source="MusicBrainz release",
                            source_url=release_url,
                            confidence="élevée",
                            note="Tracklist du medium associé au Disc ID.",
                            retrieved_at=now,
                        ),
                        MetadataEvidence(
                            field="tracklist",
                            value=f"Discogs: {len(dg_titles)} pistes; différences {mismatches}",
                            source="Discogs",
                            source_url=release.source_url,
                            confidence=confidence,
                            note="Tracklist du résultat exact par code-barres.",
                            retrieved_at=now,
                        ),
                    ),
                    note="Ordre ou titres différents; contrôler le livret avant approbation.",
                )
            )
        else:
            result.proposals.append(
                MetadataEvidence(
                    field="tracklist",
                    value=f"{len(mb_titles)} titres dans le même ordre",
                    source="Discogs",
                    source_url=release.source_url,
                    confidence=confidence,
                    note="Titres comparés après normalisation Unicode/casse/ponctuation.",
                    retrieved_at=now,
                )
            )
    if release.data_quality:
        result.messages.append(f"Qualité de la donnée Discogs : {release.data_quality}.")
    return result
