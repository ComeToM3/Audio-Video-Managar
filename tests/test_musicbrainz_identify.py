"""AVM-04 — identification Disc ID / MusicBrainz / CAA (réseau simulé)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from audio_video_manager.metadata.apply_lookup import (
    apply_release_candidate,
    identify_disc,
    sheet_from_disc_read,
)
from audio_video_manager.metadata.cover_art import CoverArtResult, fetch_cover_art_info
from audio_video_manager.metadata.enums import (
    ApprovalState,
    CoverStatus,
    FieldTrust,
    MetadataProvenance,
)
from audio_video_manager.metadata.libdiscid_loader import LibdiscidMissingError
from audio_video_manager.metadata.models import FieldMeta, TocSnapshot
from audio_video_manager.metadata.musicbrainz_client import (
    DiscLookupResult,
    MusicBrainzError,
    ReleaseCandidate,
    compare_toc_to_medium,
    configure_musicbrainz,
    lookup_releases_by_discid,
)
from audio_video_manager.metadata.toc_reader import DiscReadResult
from audio_video_manager.metadata.validation import assert_can_start_archive_rip


DISC_ID = "testDiscIdXXXXXXXXXXXXXXXXXXX"


def _toc(n: int = 2) -> TocSnapshot:
    return TocSnapshot(
        first_track=1,
        last_track=n,
        track_offsets_sectors=[150 + i * 1000 for i in range(n)],
        track_durations_ms=[180_000 + i * 1000 for i in range(n)],
        audio_track_count=n,
        raw_source="mock",
    )


def _disc_read(n: int = 2) -> DiscReadResult:
    return DiscReadResult(disc_id=DISC_ID, toc=_toc(n), device="D:")


def _mb_release(
    rid: str,
    title: str,
    *,
    country: str = "FR",
    date: str = "1997",
    barcode: str = "1234567890123",
    label: str = "Test Label",
    catalog: str = "CAT-001",
    track_titles: list[str] | None = None,
    track_lengths: list[int] | None = None,
    disc_id: str = DISC_ID,
) -> dict:
    titles = track_titles or ["Track A", "Track B"]
    lengths = track_lengths or [180_000, 181_000]
    tracks = []
    for i, (t, ln) in enumerate(zip(titles, lengths), start=1):
        tracks.append(
            {
                "position": str(i),
                "recording": {
                    "id": f"rec-{rid}-{i}",
                    "title": t,
                    "length": ln,
                    "artist-credit": [{"artist": {"name": "Artist X"}}],
                },
            }
        )
    return {
        "id": rid,
        "title": title,
        "date": date,
        "country": country,
        "barcode": barcode,
        "status": "Official",
        "disambiguation": "",
        "artist-credit": [{"artist": {"name": "Artist X"}}],
        "label-info-list": [
            {"label": {"name": label}, "catalog-number": catalog},
        ],
        "release-group": {"id": f"rg-{rid}"},
        "medium-list": [
            {
                "position": "1",
                "disc-list": [{"id": disc_id}],
                "track-list": tracks,
            }
        ],
    }


def test_compare_toc_exact_and_mismatch() -> None:
    match, notes = compare_toc_to_medium([1000, 2000], [1000, 2000])
    assert match == "exact"
    assert notes == []
    match, _ = compare_toc_to_medium([1000, 2000], [1000, 5000])
    assert match == "partial"
    match, notes = compare_toc_to_medium([1000], [1000, 2000])
    assert match == "mismatch"
    assert notes


def test_lookup_no_result_404() -> None:
    def get_fn(*_a, **_k):
        import musicbrainzngs

        cause = MagicMock()
        cause.code = 404
        raise musicbrainzngs.ResponseError("not found", cause=cause)

    with patch(
        "audio_video_manager.metadata.musicbrainz_client._rate_limit",
        lambda: None,
    ):
        result = lookup_releases_by_discid(DISC_ID, get_releases_fn=get_fn)
    assert result.candidates == []
    assert "404" in result.message
    assert result.ambiguous is False


def test_lookup_network_error() -> None:
    def get_fn(*_a, **_k):
        import musicbrainzngs

        raise musicbrainzngs.NetworkError("down")

    with patch(
        "audio_video_manager.metadata.musicbrainz_client._rate_limit",
        lambda: None,
    ):
        with pytest.raises(MusicBrainzError, match="Réseau"):
            lookup_releases_by_discid(DISC_ID, get_releases_fn=get_fn)


def test_lookup_multiple_candidates_ambiguous() -> None:
    payload = {
        "disc": {
            "id": DISC_ID,
            "release-list": [
                _mb_release("rel-1", "Album Original", country="US", date="1995"),
                _mb_release(
                    "rel-2",
                    "Album Original",
                    country="FR",
                    date="2005",
                    catalog="RE-2005",
                    label="Reissue Label",
                ),
            ],
        }
    }

    with patch(
        "audio_video_manager.metadata.musicbrainz_client._rate_limit",
        lambda: None,
    ):
        result = lookup_releases_by_discid(
            DISC_ID,
            toc_durations_ms=[180_000, 181_000],
            get_releases_fn=lambda *_a, **_k: payload,
        )
    assert len(result.candidates) == 2
    assert result.ambiguous is True
    assert "manuelle" in result.message.lower()
    assert all(c.toc_match == "exact" for c in result.candidates)
    assert result.candidates[0].barcode == "1234567890123"
    assert result.candidates[1].catalog_numbers == ["RE-2005"]


def test_lookup_single_candidate_fields() -> None:
    payload = {
        "disc": {
            "id": DISC_ID,
            "release-list": [_mb_release("rel-only", "Seul Album")],
        }
    }
    with patch(
        "audio_video_manager.metadata.musicbrainz_client._rate_limit",
        lambda: None,
    ):
        result = lookup_releases_by_discid(
            DISC_ID,
            toc_durations_ms=[180_000, 181_000],
            get_releases_fn=lambda *_a, **_k: payload,
        )
    assert len(result.candidates) == 1
    c = result.candidates[0]
    assert c.title == "Seul Album"
    assert c.artist_credit == "Artist X"
    assert c.year == 1997
    assert c.labels == ["Test Label"]
    assert len(c.track_titles) == 2


def test_lookup_uses_release_track_length_before_recording_length() -> None:
    release = _mb_release(
        "rel-duration-source",
        "Durations",
        track_lengths=[139_000, 183_000],
    )
    tracks = release["medium-list"][0]["track-list"]
    tracks[0]["length"] = 144_040
    tracks[1]["length"] = 185_600
    payload = {"disc": {"id": DISC_ID, "release-list": [release]}}
    with patch(
        "audio_video_manager.metadata.musicbrainz_client._rate_limit",
        lambda: None,
    ):
        result = lookup_releases_by_discid(
            DISC_ID,
            toc_durations_ms=[144_000, 186_000],
            get_releases_fn=lambda *_a, **_k: payload,
        )
    candidate = result.candidates[0]
    assert candidate.track_durations_ms == [144_040, 185_600]
    assert candidate.toc_match == "exact"


def test_lookup_keeps_release_and_release_group_dates_separate() -> None:
    release = _mb_release("rel-date", "Date levels", date=None)
    release["release-group"].update(
        {
            "first-release-date": "2002",
            "primary-type": "Album",
            "secondary-type-list": ["Compilation"],
        }
    )
    payload = {"disc": {"id": DISC_ID, "release-list": [release]}}
    with patch(
        "audio_video_manager.metadata.musicbrainz_client._rate_limit",
        lambda: None,
    ):
        result = lookup_releases_by_discid(
            DISC_ID,
            get_releases_fn=lambda *_a, **_k: payload,
        )
    candidate = result.candidates[0]
    assert candidate.year is None
    assert candidate.release_group_first_release_date == "2002"
    assert candidate.release_group_primary_type == "Album"
    assert candidate.release_group_secondary_types == ["Compilation"]


def test_release_candidate_cannot_overwrite_approved_sheet() -> None:
    sheet = sheet_from_disc_read(_disc_read())
    sheet.approval = ApprovalState.APPROVED
    candidate = ReleaseCandidate(
        release_id="new-release",
        title="New title",
        artist_credit="Artist X",
    )
    with pytest.raises(ValueError, match="révoquer l'approbation"):
        apply_release_candidate(sheet, candidate)
    assert sheet.edition.album_title == ""


def test_replacing_candidate_clears_metadata_absent_from_new_release() -> None:
    sheet = sheet_from_disc_read(_disc_read())
    previous = ReleaseCandidate(
        release_id="old-release",
        title="Old Album",
        artist_credit="Old Artist",
        year=2001,
        country="CA",
        labels=["Old Label"],
        catalog_numbers=["OLD-1"],
        track_titles=["Old Track 1", "Old Track 2"],
        track_artists=["Old Artist", "Old Artist"],
        matched_medium_position=2,
        medium_count=2,
    )
    apply_release_candidate(
        sheet,
        previous,
        cover=CoverArtResult(
            release_id="old-release",
            status="confirmed",
            front_url="https://example.test/old.jpg",
            thumbnail_url="https://example.test/old-small.jpg",
            message="found",
        ),
    )
    sheet.edition.year_unavailable_justification = "Old edition note"

    replacement = ReleaseCandidate(
        release_id="new-release",
        title="New Album",
        artist_credit="New Artist",
    )
    apply_release_candidate(
        sheet,
        replacement,
        user_selected=True,
        replace_candidate=True,
    )

    assert sheet.edition.musicbrainz_release_id == "new-release"
    assert sheet.edition.year is None
    assert sheet.edition.country is None
    assert sheet.edition.label is None
    assert sheet.edition.catalog_number is None
    assert sheet.edition.cover_status == CoverStatus.MISSING
    assert sheet.edition.cover_path_or_url is None
    assert sheet.edition.year_unavailable_justification is None
    assert sheet.disc.disc_number == 1
    assert sheet.disc.disc_total == 1
    assert [track.title for track in sheet.tracks] == ["", ""]
    assert [track.artist for track in sheet.tracks] == ["", ""]
    assert [track.duration_ms for track in sheet.tracks] == _toc().track_durations_ms


def test_fuzzy_toc_candidate_is_prefilled_but_not_confirmed() -> None:
    read = _disc_read()
    candidate = ReleaseCandidate(
        release_id="toc-release",
        title="TOC Album",
        artist_credit="Artist X",
        year=1997,
        track_titles=["Track A", "Track B"],
        track_artists=["Artist X", "Artist X"],
        match_source="toc",
        toc_match="exact",
    )
    lookup = DiscLookupResult(
        disc_id=read.disc_id,
        candidates=[candidate],
        raw_release_count=1,
        message="TOC match",
        ambiguous=False,
    )

    sheet, _, _, decision = identify_disc(
        disc_read=read,
        lookup=lookup,
        fetch_cover=False,
    )

    assert decision.selected is candidate
    assert decision.auto_selected is False
    assert decision.require_manual_choice is True
    assert sheet.edition.album_title == "TOC Album"
    assert sheet.edition.field_meta["album_title"].trust == FieldTrust.AMBIGUOUS
    assert sheet.approval == ApprovalState.PENDING


def test_cdstub_prefills_available_fields_without_release_identity() -> None:
    read = _disc_read()
    stub = ReleaseCandidate(
        release_id="",
        title="Stub Album",
        artist_credit="Stub Artist",
        track_titles=["Stub Track 1", "Stub Track 2"],
        track_artists=["", ""],
        is_cdstub=True,
        match_source="cdstub",
        disc_id=read.disc_id,
        medium_track_count=2,
    )
    lookup = DiscLookupResult(
        disc_id=read.disc_id,
        candidates=[stub],
        raw_release_count=0,
        message="CD stub",
        ambiguous=True,
    )

    sheet, _, cover, decision = identify_disc(
        disc_read=read,
        lookup=lookup,
        fetch_cover=True,
    )

    assert decision.selected is stub
    assert sheet.edition.album_title == "Stub Album"
    assert sheet.edition.album_artist == "Stub Artist"
    assert sheet.edition.musicbrainz_release_id is None
    assert sheet.edition.year is None
    assert sheet.edition.field_meta["album_title"].trust == FieldTrust.AMBIGUOUS
    assert sheet.approval == ApprovalState.PENDING
    assert cover is None


def test_caa_404_unavailable() -> None:
    def urlopen(req, timeout=30):  # noqa: ARG001
        import urllib.error

        raise urllib.error.HTTPError(
            url="https://coverartarchive.org/release/x",
            code=404,
            msg="Not Found",
            hdrs=None,
            fp=None,
        )

    with patch(
        "audio_video_manager.metadata.cover_art._rate_limit",
        lambda: None,
    ):
        info = fetch_cover_art_info("release-missing", urlopen_fn=urlopen)
    assert info.status == "unavailable"
    assert info.front_url is None


def test_caa_found_confirmed() -> None:
    body = json.dumps(
        {
            "images": [
                {
                    "front": True,
                    "image": "https://example.test/front.jpg",
                    "thumbnails": {"250": "https://example.test/250.jpg"},
                }
            ]
        }
    ).encode()

    class Resp:
        status = 200

        def read(self):
            return body

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    with patch(
        "audio_video_manager.metadata.cover_art._rate_limit",
        lambda: None,
    ):
        info = fetch_cover_art_info("rel-ok", urlopen_fn=lambda *a, **k: Resp())
    assert info.status == "confirmed"
    assert info.front_url.endswith("front.jpg")
    assert info.thumbnail_url.endswith("250.jpg")


def test_identify_zero_candidates_no_auto_approve() -> None:
    empty = DiscLookupResult(
        disc_id=DISC_ID,
        candidates=[],
        raw_release_count=0,
        message="Aucun release MusicBrainz pour ce Disc ID (404).",
        ambiguous=False,
    )
    sheet, mb, cover, decision = identify_disc(
        disc_read=_disc_read(),
        lookup=empty,
        fetch_cover=False,
    )
    assert sheet.approval == ApprovalState.PENDING
    assert sheet.identity.disc_id == DISC_ID
    assert sheet.edition.album_title == ""
    assert cover is None
    assert mb.candidates == []
    assert decision.auto_selected is False
    with pytest.raises(Exception):
        assert_can_start_archive_rip(sheet)


def test_identify_multiple_candidates_stays_pending() -> None:
    cands = [
        ReleaseCandidate(
            release_id="a",
            title="A",
            artist_credit="X",
            toc_match="exact",
        ),
        ReleaseCandidate(
            release_id="b",
            title="A (réédition)",
            artist_credit="X",
            country="FR",
            year=2005,
            toc_match="exact",
            catalog_numbers=["RE"],
        ),
    ]
    lookup = DiscLookupResult(
        disc_id=DISC_ID,
        candidates=cands,
        raw_release_count=2,
        message="2 éditions candidates — sélection manuelle requise",
        ambiguous=True,
    )
    sheet, mb, _, decision = identify_disc(
        disc_read=_disc_read(),
        lookup=lookup,
        fetch_cover=False,
    )
    assert sheet.approval == ApprovalState.PENDING
    assert mb.ambiguous is True
    # Titres/artistes différents → proposition classée, mais vérification requise.
    assert decision.require_manual_choice is True
    assert decision.auto_selected is False
    assert decision.selected is decision.ranked[0].candidate
    assert sheet.edition.album_title == decision.selected.title
    assert sheet.edition.album_artist == decision.selected.artist_credit
    assert sheet.edition.field_meta["album_title"].trust == FieldTrust.AMBIGUOUS


def test_lookup_falls_back_to_fuzzy_toc_after_exact_404() -> None:
    calls: list[dict] = []

    def get_fn(_disc_id, **kwargs):
        calls.append(kwargs)
        if "toc" not in kwargs:
            import musicbrainzngs

            cause = MagicMock()
            cause.code = 404
            raise musicbrainzngs.ResponseError("not found", cause=cause)
        return {"release-list": [_mb_release("rel-toc", "TOC Album")]}

    with patch(
        "audio_video_manager.metadata.musicbrainz_client._rate_limit",
        lambda: None,
    ):
        result = lookup_releases_by_discid(
            DISC_ID,
            toc_durations_ms=[180_000, 181_000],
            toc_string="1 2 3000 150 1500",
            get_releases_fn=get_fn,
        )

    assert len(calls) == 2
    assert calls[1]["toc"] == "1 2 3000 150 1500"
    assert calls[1]["cdstubs"] is False
    assert len(result.candidates) == 1
    assert result.candidates[0].match_source == "toc"
    assert result.candidates[0].title == "TOC Album"


def test_identify_forwards_captured_toc_string_to_musicbrainz(monkeypatch) -> None:
    read = _disc_read()
    read = DiscReadResult(
        disc_id=read.disc_id,
        toc=read.toc,
        device=read.device,
        toc_string="1 2 3000 150 1500",
    )
    received: dict[str, object] = {}

    def lookup(disc_id, **kwargs):
        received.update(kwargs)
        return DiscLookupResult(
            disc_id=disc_id,
            candidates=[],
            raw_release_count=0,
            message="no match",
            ambiguous=False,
        )

    monkeypatch.setattr(
        "audio_video_manager.metadata.apply_lookup.lookup_releases_by_discid",
        lookup,
    )
    identify_disc(disc_read=read, fetch_cover=False)

    assert received["toc_string"] == "1 2 3000 150 1500"


def test_lookup_exposes_cdstub_as_unconfirmed_source() -> None:
    payload = {
        "cdstub": {
            "id": DISC_ID,
            "title": "Stub Album",
            "artist": "Stub Artist",
            "count": 2,
            "track-list": [
                {"title": "Stub Track 1"},
                {"title": "Stub Track 2"},
            ],
        }
    }
    with patch(
        "audio_video_manager.metadata.musicbrainz_client._rate_limit",
        lambda: None,
    ):
        result = lookup_releases_by_discid(
            DISC_ID,
            get_releases_fn=lambda *_args, **_kwargs: payload,
        )

    assert len(result.candidates) == 1
    stub = result.candidates[0]
    assert stub.is_cdstub is True
    assert stub.release_id == ""
    assert stub.selection_key == f"cdstub:{DISC_ID}"
    assert stub.title == "Stub Album"
    assert stub.artist_credit == "Stub Artist"
    assert stub.year is None
    assert "sans édition confirmée" in result.message


def test_cdstub_survives_fuzzy_lookup_network_error() -> None:
    payload = {
        "cdstub": {
            "id": DISC_ID,
            "title": "Stub Album",
            "artist": "Stub Artist",
            "count": 2,
        }
    }

    def get_fn(_disc_id, **kwargs):
        if "toc" in kwargs:
            import musicbrainzngs

            raise musicbrainzngs.NetworkError("offline")
        return payload

    with patch(
        "audio_video_manager.metadata.musicbrainz_client._rate_limit",
        lambda: None,
    ):
        result = lookup_releases_by_discid(
            DISC_ID,
            toc_string="1 2 3000 150 1500",
            get_releases_fn=get_fn,
        )

    assert len(result.candidates) == 1
    assert result.candidates[0].is_cdstub
    assert "Recherche TOC indisponible" in result.message


def test_identify_single_prefill_ambiguous_until_user_select() -> None:
    cand = ReleaseCandidate(
        release_id="only",
        title="Album Unique",
        artist_credit="Artist X",
        year=1997,
        country="FR",
        barcode="123",
        labels=["Lab"],
        catalog_numbers=["C1"],
        track_titles=["Track A", "Track B"],
        track_artists=["Artist X", "Artist X"],
        track_recording_ids=["r1", "r2"],
        matched_medium_position=1,
        medium_count=1,
        toc_match="exact",
    )
    lookup = DiscLookupResult(
        disc_id=DISC_ID,
        candidates=[cand],
        raw_release_count=1,
        message="1 édition",
        ambiguous=False,
    )
    cover = CoverArtResult(
        release_id="only",
        status="confirmed",
        front_url="https://example.test/c.jpg",
        thumbnail_url="https://example.test/t.jpg",
        message="ok",
    )
    with patch(
        "audio_video_manager.metadata.apply_lookup.fetch_cover_art_info",
        return_value=cover,
    ):
        sheet, _, cov, decision = identify_disc(
            disc_read=_disc_read(),
            lookup=lookup,
            fetch_cover=True,
        )
    assert sheet.approval == ApprovalState.PENDING
    assert decision.auto_selected is True
    assert sheet.edition.album_title == "Album Unique"
    # AVM-04C : unique → confirmed sur champs, approval toujours Pending
    assert sheet.edition.field_meta["album_title"].trust == FieldTrust.CONFIRMED
    assert sheet.edition.field_meta["album_title"].provenance == MetadataProvenance.MUSICBRAINZ
    assert cov is not None
    with pytest.raises(Exception):
        assert_can_start_archive_rip(sheet)


def test_user_select_confirms_but_still_needs_approve() -> None:
    sheet = sheet_from_disc_read(_disc_read())
    sheet.edition.is_compilation = False
    sheet.edition.field_meta["is_compilation"] = FieldMeta(trust=FieldTrust.CONFIRMED)
    cand = ReleaseCandidate(
        release_id="sel",
        title="Choisi",
        artist_credit="Artist X",
        year=1997,
        country="FR",
        barcode="999",
        labels=["Lab"],
        catalog_numbers=["C9"],
        track_titles=["Track A", "Track B"],
        track_artists=["Artist X", "Artist X"],
        track_recording_ids=["r1", "r2"],
        matched_medium_position=1,
        medium_count=1,
        toc_match="exact",
    )
    cover = CoverArtResult(
        release_id="sel",
        status="confirmed",
        front_url="https://example.test/c.jpg",
        thumbnail_url=None,
        message="ok",
    )
    apply_release_candidate(sheet, cand, cover=cover, user_selected=True)
    assert sheet.approval == ApprovalState.PENDING
    assert sheet.edition.field_meta["album_title"].trust == FieldTrust.CONFIRMED
    assert sheet.edition.cover_status == CoverStatus.CONFIRMED
    assert sheet.tracks[0].title == "Track A"
    with pytest.raises(Exception):
        assert_can_start_archive_rip(sheet)


def test_manual_correction_not_overwritten() -> None:
    sheet = sheet_from_disc_read(_disc_read())
    sheet.edition.album_title = "Titre manuel"
    sheet.edition.field_meta["album_title"] = FieldMeta(
        trust=FieldTrust.CONFIRMED,
        provenance=MetadataProvenance.USER_CORRECTION,
    )
    cand = ReleaseCandidate(
        release_id="x",
        title="Titre MB",
        artist_credit="Artist X",
        track_titles=["A", "B"],
        track_artists=["Artist X", "Artist X"],
    )
    apply_release_candidate(sheet, cand, user_selected=True)
    assert sheet.edition.album_title == "Titre manuel"


def test_diagnose_libdiscid_handles_missing() -> None:
    with patch(
        "audio_video_manager.metadata.toc_reader.import_discid",
        side_effect=LibdiscidMissingError("DLL absente"),
    ):
        from audio_video_manager.metadata.toc_reader import diagnose_libdiscid

        assert "DLL absente" in diagnose_libdiscid()


def test_libdiscid_loader_finds_vendor_dll() -> None:
    from audio_video_manager.metadata.libdiscid_loader import find_discid_dll

    dll = find_discid_dll()
    assert dll is not None
    assert dll.name == "discid.dll"
    assert dll.is_file()


def test_identify_multi_keeps_lookup_warning_after_validation() -> None:
    """Régression AVM-04B : apply_validation ne doit pas effacer le message multi-éditions."""
    lookup = DiscLookupResult(
        disc_id=DISC_ID,
        candidates=[
            ReleaseCandidate(release_id="a", title="A", artist_credit="X"),
            ReleaseCandidate(release_id="b", title="B", artist_credit="X"),
        ],
        raw_release_count=2,
        message="2 éditions candidates — sélection manuelle requise",
        ambiguous=True,
    )
    sheet, _, _, decision = identify_disc(
        disc_read=_disc_read(),
        lookup=lookup,
        fetch_cover=False,
    )
    assert decision.require_manual_choice is True
    assert sheet.validation_warnings
    assert any(
        "manuelle" in w.lower() or "non équivalentes" in w.lower()
        for w in sheet.validation_warnings
    )


def test_resolve_optical_ignores_freac_model_suffix() -> None:
    """fre:ac « iHAS324   C » ≠ lecteur C: — utiliser Win32 CD-ROM."""
    from audio_video_manager.metadata.toc_reader import resolve_optical_device_for_discid

    with patch(
        "audio_video_manager.metadata.toc_reader.list_cdrom_device_letters",
        return_value=["D:"],
    ):
        device, reason = resolve_optical_device_for_discid("ATAPI iHAS324   C")
    assert device == "D:"
    assert "Unique" in reason

    with patch(
        "audio_video_manager.metadata.toc_reader.list_cdrom_device_letters",
        return_value=[],
    ):
        device, reason = resolve_optical_device_for_discid("ATAPI iHAS324   C")
    assert device is None
    assert "non fiable" in reason
