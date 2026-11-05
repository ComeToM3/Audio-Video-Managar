from __future__ import annotations

import json
from datetime import date
from urllib.request import Request

import pytest

from audio_video_manager.metadata.enrichment import (
    DiscogsLookup,
    DiscogsReleaseEvidence,
    DiscogsTrack,
    build_enrichment_report,
    lookup_discogs_by_barcode,
)
from audio_video_manager.metadata.musicbrainz_client import ReleaseCandidate


BARCODE = "724353848620"
RELEASE_URL = "https://www.discogs.com/release/1169416-example"


def _discogs_payload(*, year=0, formats=None, data_quality="Needs Vote") -> dict:
    return {
        "id": 1169416,
        "uri": RELEASE_URL,
        "title": "Ses plus grands succès (pour vous au Québec)",
        "country": "Canada",
        "year": year,
        "data_quality": data_quality,
        "notes": "Compilation \u2117 and \u00a9 2002 EMI Music France.",
        "identifiers": [{"type": "Barcode", "value": "7 24353 84862 0"}],
        "labels": [{"name": "EMI Music Canada", "catno": "72435-38486-2-0"}],
        "formats": [
            {
                "name": "CD",
                "descriptions": formats or ["Compilation", "Reissue", "Remastered"],
            }
        ],
        "tracklist": [
            {"position": "1", "type_": "track", "title": "Emmenez-Moi", "duration": "3:34"}
        ],
    }


class _Response:
    def __init__(self, value: dict) -> None:
        self.value = value

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self) -> bytes:
        return json.dumps(self.value).encode("utf-8")


def test_discogs_lookup_requires_exact_barcode_and_uses_api_headers(monkeypatch) -> None:
    import audio_video_manager.metadata.enrichment as enrichment

    monkeypatch.setattr(enrichment, "_rate_limit", lambda **_kwargs: None)
    calls: list[Request] = []

    def urlopen(request: Request, *, timeout: int):
        assert timeout > 0
        calls.append(request)
        if "database/search" in request.full_url:
            return _Response(
                {
                    "results": [
                        {"id": 5, "barcode": ["724353848621"]},
                        {"id": 1169416, "barcode": ["7 2435-38486-2 0"]},
                    ]
                }
            )
        return _Response(_discogs_payload())

    result = lookup_discogs_by_barcode(
        BARCODE,
        token="test-token",
        urlopen_fn=urlopen,
        today=date(2026, 11, 4),
    )
    assert result.status == "matched"
    assert result.release is not None
    assert result.release.year is None
    assert result.release.catalog_numbers == ("72435-38486-2-0",)
    assert result.release.copyright_notice_years == (2002,)
    assert result.release.tracks == (DiscogsTrack(1, "Emmenez-Moi", 214_000),)
    assert len(calls) == 2
    assert calls[0].get_header("Authorization") == "Discogs token=test-token"
    assert calls[0].get_header("User-agent") == enrichment.DISCOGS_USER_AGENT


def test_discogs_ambiguous_barcode_never_selects_a_release(monkeypatch) -> None:
    import audio_video_manager.metadata.enrichment as enrichment

    monkeypatch.setattr(enrichment, "_rate_limit", lambda **_kwargs: None)
    calls = 0

    def urlopen(_request: Request, *, timeout: int):
        nonlocal calls
        calls += 1
        return _Response(
            {"results": [{"id": 1, "barcode": [BARCODE]}, {"id": 2, "barcode": [BARCODE]}]}
        )

    result = lookup_discogs_by_barcode(
        BARCODE,
        token="token",
        urlopen_fn=urlopen,
    )
    assert result.status == "ambiguous"
    assert result.release is None
    assert calls == 1


def test_discogs_requires_auth_after_documented_cutoff() -> None:
    result = lookup_discogs_by_barcode(BARCODE, token="", today=date(2026, 12, 1))
    assert result.status == "auth_required"


def test_enrichment_keeps_group_date_separate_and_merges_compilation_evidence() -> None:
    candidate = ReleaseCandidate(
        release_id="09bdc53c-46a6-4825-8ccf-b0608f56d746",
        title="Ses plus grands succès (pour vous au Québec)",
        artist_credit="Charles Aznavour",
        date=None,
        year=None,
        barcode=BARCODE,
        release_group_id="e005180f-f693-4f05-950a-27a4fac6e89d",
        release_group_first_release_date="2002",
        release_group_primary_type="Album",
        release_group_secondary_types=["Compilation"],
        track_titles=["Emmenez‐moi"],
    )
    discogs = DiscogsReleaseEvidence(
        release_id=1169416,
        source_url=RELEASE_URL,
        title=candidate.title,
        country="Canada",
        barcode=BARCODE,
        year=None,
        labels=("EMI Music Canada",),
        catalog_numbers=("72435-38486-2-0",),
        formats=("CD", "Compilation", "Reissue", "Remastered"),
        tracks=(DiscogsTrack(1, "Emmenez-Moi", 214_000),),
        data_quality="Needs Vote",
    )
    report = build_enrichment_report(
        candidate,
        DiscogsLookup("matched", release=discogs),
        retrieved_at="2026-11-04T00:00:00+00:00",
    )
    group_date = next(p for p in report.proposals if p.field.startswith("première publication"))
    assert group_date.value == "2002"
    assert not any(p.field == "year (édition précise)" and p.value == 2002 for p in report.proposals)
    assert [p.value for p in report.proposals if p.field == "is_compilation"] == [True, True]
    assert any(p.field == "is_reissue" and p.value is True for p in report.proposals)
    assert report.conflicts == []
    assert any(p.field == "tracklist" for p in report.proposals)
    rendered = report.to_html()
    assert "Data provided by Discogs." in rendered
    assert RELEASE_URL in rendered


def test_enrichment_reports_conflicting_exact_release_years() -> None:
    candidate = ReleaseCandidate(
        release_id="mb-release",
        title="Album",
        artist_credit="Artist",
        date="2001",
        year=2001,
    )
    discogs = DiscogsReleaseEvidence(
        release_id=42,
        source_url=RELEASE_URL,
        title="Album",
        country="Canada",
        barcode=None,
        year=2002,
        labels=(),
        catalog_numbers=(),
        formats=(),
        tracks=(),
        data_quality="Complete and Correct",
    )
    report = build_enrichment_report(candidate, DiscogsLookup("matched", discogs))
    assert len(report.conflicts) == 1
    assert report.conflicts[0].field == "year (édition précise)"
    assert "désaccord" in report.conflicts[0].note.casefold()


def test_toc_duration_comparison_is_not_duplicated_with_discogs() -> None:
    candidate = ReleaseCandidate(
        release_id="mb-release",
        title="Album",
        artist_credit="Artist",
        track_titles=["For me… formidable"],
        track_durations_ms=[144_040],
    )
    discogs = DiscogsReleaseEvidence(
        release_id=42,
        source_url=RELEASE_URL,
        title="Album",
        country="Canada",
        barcode=None,
        year=None,
        labels=(),
        catalog_numbers=(),
        formats=(),
        tracks=(DiscogsTrack(1, "For Me...Formidable", 141_000),),
        data_quality="Needs Vote",
    )
    report = build_enrichment_report(
        candidate,
        DiscogsLookup("matched", discogs),
        toc_durations_ms=[144_000],
    )
    assert len(report.track_durations) == 1
    assert report.track_durations[0].delta_ms == 40
    assert not any(conflict.field == "tracklist" for conflict in report.conflicts)


def test_aznavour_medium_track_durations_match_toc_within_one_second() -> None:
    toc = [
        214000, 215000, 192000, 246000, 187000, 144000, 191000, 143000,
        144000, 186000, 188000, 171000, 153000, 356000, 227000, 230000,
        222000, 225000, 158000, 205000, 186000, 111000,
    ]
    release_track_lengths = [
        213693, 215040, 191933, 246493, 186906, 143893, 190600, 142706,
        144040, 186026, 188240, 170826, 153533, 356080, 227093, 230533,
        221946, 224920, 158360, 205173, 185600, 110040,
    ]
    candidate = ReleaseCandidate(
        release_id="09bdc53c-46a6-4825-8ccf-b0608f56d746",
        title="Ses plus grands succès (pour vous au Québec)",
        artist_credit="Charles Aznavour",
        track_titles=[f"Track {number}" for number in range(1, 23)],
        track_durations_ms=release_track_lengths,
    )
    report = build_enrichment_report(candidate, toc_durations_ms=toc)
    assert len(report.track_durations) == 22
    assert max(item.delta_ms for item in report.track_durations) == 960
    assert not any(conflict.field == "track_count" for conflict in report.conflicts)


def test_aznavour_discogs_track_titles_match_musicbrainz_order() -> None:
    mb_titles = [
        "Emmenez‐moi", "Et moi dans mon coin", "Je te réchaufferai", "La Bohème",
        "Dans tes bras", "Les Comédiens", "Il faut savoir", "Hier encore",
        "For me… formidable", "J’en déduis que je t’aime", "Mes emmerdes",
        "Et pourtant", "Sur ma vie", "Les Plaisirs démodés", "La Mamma",
        "Les Deux Guitares", "Tu t’laisses aller", "L’amour c’est comme un jour",
        "Le Temps", "Je m’voyais déjà", "Plus bleu que tes yeux", "Reste",
    ]
    discogs_titles = [
        "Emmenez-Moi", "Et Moi Dans Mon Coin", "Je Te Réchaufferai", "La Bohème",
        "Dans Tes Bras", "Les Comédiens", "Il Faut Savoir", "Hier Encore",
        "For Me...Formidable", "J'En Déduis Que Je T'Aime", "Mes Emmerdes",
        "Et Pourtant", "Sur Ma Vie", "Les Plaisirs Démodés", "La Mamma",
        "Les Deux Guitares", "Tu T'Laisses Aller", "L'Amour C'Est Comme Un Jour",
        "Le Temps", "Je M'Voyais Déjà", "Plus Bleu Que Tes Yeux", "Reste",
    ]
    candidate = ReleaseCandidate(
        release_id="09bdc53c-46a6-4825-8ccf-b0608f56d746",
        title="Ses plus grands succès (pour vous au Québec)",
        artist_credit="Charles Aznavour",
        track_titles=mb_titles,
    )
    discogs = DiscogsReleaseEvidence(
        release_id=1169416,
        source_url=RELEASE_URL,
        title=candidate.title,
        country="Canada",
        barcode=BARCODE,
        year=None,
        labels=("EMI Music Canada",),
        catalog_numbers=("72435-38486-2-0",),
        formats=("CD", "Compilation", "Reissue", "Remastered"),
        tracks=tuple(
            DiscogsTrack(index, title, None)
            for index, title in enumerate(discogs_titles, start=1)
        ),
        data_quality="Needs Vote",
    )
    report = build_enrichment_report(candidate, DiscogsLookup("matched", discogs))
    assert not any(conflict.field == "tracklist" for conflict in report.conflicts)
    assert any(
        proposal.field == "tracklist" and proposal.value == "22 titres dans le même ordre"
        for proposal in report.proposals
    )
