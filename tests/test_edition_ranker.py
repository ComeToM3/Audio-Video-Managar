"""AVM-04C — classement éditions, préférence CA, faux positifs."""

from __future__ import annotations

from audio_video_manager.metadata.apply_lookup import identify_disc
from audio_video_manager.metadata.edition_ranker import (
    DiffSeverity,
    compare_editions,
    editions_musically_equivalent,
    rank_and_select_releases,
)
from audio_video_manager.metadata.enums import ApprovalState, FieldTrust
from audio_video_manager.metadata.models import TocSnapshot
from audio_video_manager.metadata.musicbrainz_client import DiscLookupResult, ReleaseCandidate
from audio_video_manager.metadata.toc_reader import DiscReadResult
from audio_video_manager.metadata.validation import assert_can_start_archive_rip
import pytest


def _tracks(n: int = 17, title_prefix: str = "T") -> tuple[list[str], list[str], list[int]]:
    titles = [f"{title_prefix}{i}" for i in range(1, n + 1)]
    artists = ["Queen"] * n
    # MB durations; last track ~3.3s under TOC 262000
    durs = [122000 + i * 100 for i in range(n)]
    durs[-1] = 258733
    return titles, artists, durs


def _queen_us() -> ReleaseCandidate:
    titles, artists, durs = _tracks()
    titles[0] = "We Will Rock You"
    return ReleaseCandidate(
        release_id="aceaf449-ca32-443d-af49-993aeb5a56a7",
        title="Greatest Hits",
        artist_credit="Queen",
        date="1991",
        year=1991,
        country="US",
        barcode="720616126528",
        labels=["Hollywood Records"],
        catalog_numbers=["HR 61265-2"],
        track_titles=titles,
        track_artists=artists,
        track_durations_ms=durs,
        toc_match="partial",
        score_notes=["Piste 17: TOC 262000 ms vs MB 258733 ms"],
        medium_count=1,
        matched_medium_position=1,
    )


def _queen_ca() -> ReleaseCandidate:
    c = _queen_us()
    return ReleaseCandidate(
        release_id="4662a6ff-34e5-462f-bac0-584ac29cfd4d",
        title=c.title,
        artist_credit=c.artist_credit,
        date="1992",
        year=1992,
        country="CA",
        barcode=c.barcode,
        labels=list(c.labels),
        catalog_numbers=["CD 61265"],
        track_titles=list(c.track_titles),
        track_artists=list(c.track_artists),
        track_durations_ms=list(c.track_durations_ms),
        toc_match="partial",
        score_notes=list(c.score_notes),
        medium_count=1,
        matched_medium_position=1,
    )


def test_queen_equivalent_prefers_ca_keeps_toc_warning() -> None:
    us, ca = _queen_us(), _queen_ca()
    diffs = compare_editions(us, ca)
    assert editions_musically_equivalent(diffs)
    assert any(d.code == "country" and d.severity == DiffSeverity.MINOR for d in diffs)
    assert any(d.code == "catalog" for d in diffs)

    decision = rank_and_select_releases([us, ca], preferred_country="CA")
    assert decision.auto_selected is True
    assert decision.selected is not None
    assert decision.selected.country == "CA"
    assert decision.selected.catalog_numbers == ["CD 61265"]
    assert decision.selected.toc_match == "partial"  # pas forcé en exact
    assert any("262000" in w or "258733" in w for w in decision.warnings)
    assert "départage" in decision.summary.lower() or "préférence" in decision.summary.lower()
    assert decision.high_confidence_for_future_auto_approve is False


def test_queen_pref_us_selects_us() -> None:
    decision = rank_and_select_releases(
        [_queen_us(), _queen_ca()], preferred_country="US"
    )
    assert decision.auto_selected is True
    assert decision.selected is not None
    assert decision.selected.country == "US"


def test_different_track_titles_manual() -> None:
    a = _queen_ca()
    b = ReleaseCandidate(
        release_id="other",
        title="Greatest Hits",
        artist_credit="Queen",
        country="CA",
        year=1992,
        track_titles=["Different"] + a.track_titles[1:],
        track_artists=list(a.track_artists),
        track_durations_ms=list(a.track_durations_ms),
        toc_match="partial",
        score_notes=list(a.score_notes),
        catalog_numbers=["X"],
        labels=["Hollywood Records"],
    )
    diffs = compare_editions(a, b)
    assert not editions_musically_equivalent(diffs)
    decision = rank_and_select_releases([a, b], preferred_country="CA")
    assert decision.auto_selected is False
    assert decision.require_manual_choice is True
    assert decision.selected is None


def test_track_count_mismatch_blocking() -> None:
    a = _queen_ca()
    b = ReleaseCandidate(
        release_id="short",
        title="Greatest Hits",
        artist_credit="Queen",
        country="CA",
        track_titles=a.track_titles[:10],
        track_artists=a.track_artists[:10],
        track_durations_ms=a.track_durations_ms[:10],
        toc_match="mismatch",
        score_notes=["Nombre de pistes TOC=17 ≠ medium MB=10"],
    )
    decision = rank_and_select_releases([a, b], preferred_country="CA")
    # a viable, b blocking — not equivalent pair for auto among both;
    # only one viable → still can auto-select the viable one alone? 
    # viable = [a] only if b.toc_blocking
    assert decision.auto_selected is True
    assert decision.selected is not None
    assert decision.selected.release_id == a.release_id


def test_toc_blocking_alone_requires_manual() -> None:
    bad = ReleaseCandidate(
        release_id="bad",
        title="X",
        artist_credit="Y",
        country="CA",
        track_titles=["A"],
        track_durations_ms=[1000],
        toc_match="mismatch",
        score_notes=["Nombre de pistes TOC=17 ≠ medium MB=1"],
    )
    decision = rank_and_select_releases([bad], preferred_country="CA")
    assert decision.auto_selected is False
    assert decision.require_manual_choice is True


def test_identify_queen_applies_ca_pending() -> None:
    toc = TocSnapshot(
        first_track=1,
        last_track=17,
        track_offsets_sectors=[150] * 17,
        track_durations_ms=[122000] * 16 + [262000],
        audio_track_count=17,
        raw_source="mock",
    )
    read = DiscReadResult(disc_id="DsXlPG1OQWhceSELb2Eiq5rx1wU-", toc=toc, device="D:")
    lookup = DiscLookupResult(
        disc_id=read.disc_id,
        candidates=[_queen_us(), _queen_ca()],
        raw_release_count=2,
        message="2 éditions",
        ambiguous=True,
    )
    sheet, _, _, decision = identify_disc(
        disc_read=read,
        lookup=lookup,
        fetch_cover=False,
        preferred_release_country="CA",
        auto_approve_high_confidence=True,  # doit rester ignoré
    )
    assert decision.auto_selected is True
    assert sheet.edition.country == "CA"
    assert sheet.edition.catalog_number == "CD 61265"
    assert sheet.edition.field_meta["album_title"].trust == FieldTrust.CONFIRMED
    assert sheet.approval == ApprovalState.PENDING
    assert any("partial" in w or "262000" in w for w in sheet.validation_warnings)
    with pytest.raises(Exception):
        assert_can_start_archive_rip(sheet)


def test_preferred_country_not_provenance_claim() -> None:
    decision = rank_and_select_releases(
        [_queen_us(), _queen_ca()], preferred_country="CA"
    )
    assert "provenance" not in decision.summary.lower() or "pas comme provenance" in decision.summary.lower()
    assert "pas comme provenance" in decision.summary.lower()


def test_config_defaults_country_and_auto_approve() -> None:
    from audio_video_manager.config import AppConfig

    cfg = AppConfig()
    assert cfg.preferred_release_country == "CA"
    assert cfg.auto_approve_high_confidence is False
