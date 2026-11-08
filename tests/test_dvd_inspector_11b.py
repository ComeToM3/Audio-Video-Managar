"""AVM-11B — inspection DVD en lecture seule, sans extraction réelle."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from audio_video_manager.extraction.dvd import DvdInspector
from audio_video_manager.extraction.dvd_navigation import DvdNavigationError, DvdNavigator
from audio_video_manager.metadata.video import (
    DvdTitleCandidate,
    VideoChapter,
    VideoInspectionStatus,
)


def _dvd_structure(root: Path) -> Path:
    video_ts = root / "VIDEO_TS"
    video_ts.mkdir(parents=True)
    (video_ts / "VIDEO_TS.IFO").write_bytes(b"DVDVIDEO-VMG" + bytes(20))
    (video_ts / "VTS_01_0.IFO").write_bytes(b"DVDVIDEO-VTS" + bytes(20))
    (video_ts / "VTS_02_0.IFO").write_bytes(b"DVDVIDEO-VTS" + bytes(20))
    return video_ts


def _ffprobe_path(tmp_path: Path) -> Path:
    path = tmp_path / "ffprobe.exe"
    path.write_bytes(b"fixture executable marker")
    return path


def _payload(*, incomplete: bool = False) -> dict:
    stream = {"index": 0, "codec_type": "video", "codec_name": "mpeg2video", "width": 720, "height": 480}
    audio = {"index": 1, "codec_type": "audio", "codec_name": "ac3", "channels": 6, "tags": {"language": "eng"}}
    if incomplete:
        audio.pop("index")
        audio.pop("channels")
        audio["tags"] = {}
    return {
        "format": {"format_name": "dvdvideo", "duration": "123.5"},
        "streams": [stream, audio, {"index": 2, "codec_type": "subtitle", "codec_name": "dvd_subtitle", "tags": {"language": "fra"}}],
        "chapters": [{"start_time": "0", "end_time": "60.25", "tags": {"title": "Chapter 1"}}],
    }


class FakeRunner:
    def __init__(self, *, has_dvdvideo: bool = True, media_payload: dict | None = None, media_error: str = "") -> None:
        self.has_dvdvideo = has_dvdvideo
        self.media_payload = media_payload or _payload()
        self.media_error = media_error
        self.calls: list[list[str]] = []

    def __call__(self, argv, **_kwargs):
        args = list(argv)
        self.calls.append(args)
        if "-version" in args:
            return SimpleNamespace(returncode=0, stdout="ffprobe version 7.1 fixture\n", stderr="")
        if "-demuxers" in args:
            line = " D  dvdvideo  DVD-Video demuxer\n" if self.has_dvdvideo else " D  mpeg MPEG-PS\n"
            return SimpleNamespace(returncode=0, stdout=line, stderr="")
        if self.media_error:
            return SimpleNamespace(returncode=1, stdout="", stderr=self.media_error)
        return SimpleNamespace(returncode=0, stdout=json.dumps(self.media_payload), stderr="")


class FakeNavigator:
    def __init__(self, candidates: tuple[DvdTitleCandidate, ...]) -> None:
        self.candidates = candidates
        self.sources: list[Path] = []

    def enumerate_titles(self, source: Path) -> tuple[DvdTitleCandidate, ...]:
        self.sources.append(source)
        return self.candidates


def test_inspects_requested_title_streams_chapters_and_no_output(tmp_path: Path) -> None:
    _dvd_structure(tmp_path)
    runner = FakeRunner()
    result = DvdInspector(_ffprobe_path(tmp_path), runner=runner).inspect(
        tmp_path, title_indices=(1,), angle_index=1
    )

    assert result.status == VideoInspectionStatus.INSPECTED
    assert result.title_set_numbers == (1, 2)
    assert len(result.titles) == 1
    title = result.titles[0]
    assert title.title_index == 1 and title.angle_index == 1
    assert title.duration_seconds == 123.5
    assert title.video_streams[0].codec_name == "mpeg2video"
    assert title.video_streams[0].width == 720 and title.video_streams[0].height == 480
    assert title.audio_streams[0].language == "eng"
    assert title.audio_streams[0].channels == 6
    assert title.subtitle_streams[0].language == "fra"
    assert title.chapters[0].end_seconds == 60.25
    media_call = runner.calls[-1]
    assert media_call[media_call.index("-f") + 1] == "dvdvideo"
    assert "-title" in media_call and "-show_streams" in media_call
    assert "-show_chapters" in media_call and "-i" in media_call
    assert not any(arg in media_call for arg in ("-y", "-c:v", "-c:a"))
    assert media_call[-1] == str(tmp_path)


def test_native_title_enumeration_requires_explicit_stream_probe(tmp_path: Path) -> None:
    _dvd_structure(tmp_path)
    runner = FakeRunner()
    navigator = FakeNavigator(
        (
            DvdTitleCandidate(
                title_index=1,
                part_count=2,
                angle_count=1,
                duration_seconds=120.0,
                chapters=(
                    VideoChapter(index=1, start_seconds=0.0, end_seconds=60.0),
                    VideoChapter(index=2, start_seconds=60.0, end_seconds=120.0),
                ),
            ),
        )
    )

    result = DvdInspector(
        _ffprobe_path(tmp_path), runner=runner, navigator=navigator
    ).inspect(tmp_path)

    assert result.status == VideoInspectionStatus.TITLE_SELECTION_REQUIRED
    assert result.title_candidates == navigator.candidates
    assert result.title_candidates[0].chapters[1].end_seconds == 120.0
    assert navigator.sources == [tmp_path]
    assert len(runner.calls) == 2, "aucun probe flux sans sélection explicite"


def test_auto_selection_probes_unique_longest_title_and_labels_heuristic(tmp_path: Path) -> None:
    _dvd_structure(tmp_path)
    runner = FakeRunner()
    navigator = FakeNavigator(
        (
            DvdTitleCandidate(title_index=1, duration_seconds=46.8),
            DvdTitleCandidate(title_index=2, duration_seconds=5403.6),
        )
    )

    result = DvdInspector(
        _ffprobe_path(tmp_path), runner=runner, navigator=navigator
    ).inspect(tmp_path, auto_select_main_title=True)

    assert result.status == VideoInspectionStatus.INSPECTED
    assert [title.title_index for title in result.titles] == [2]
    media_call = runner.calls[-1]
    assert media_call[media_call.index("-title") + 1] == "2"
    assert "heuristique" in result.diagnostic
    assert "5403.6 s" in result.warnings[0]


def test_auto_selection_refuses_equal_longest_durations(tmp_path: Path) -> None:
    _dvd_structure(tmp_path)
    runner = FakeRunner()
    navigator = FakeNavigator(
        (
            DvdTitleCandidate(title_index=1, duration_seconds=5403.6),
            DvdTitleCandidate(title_index=2, duration_seconds=5403.9),
        )
    )

    result = DvdInspector(
        _ffprobe_path(tmp_path), runner=runner, navigator=navigator
    ).inspect(tmp_path, auto_select_main_title=True)

    assert result.status == VideoInspectionStatus.TITLE_SELECTION_REQUIRED
    assert "ambiguë" in result.diagnostic
    assert len(runner.calls) == 2, "pas de probe flux lorsque le titre reste ambigu"


def test_title_enumeration_survives_missing_dvdvideo_demuxer(tmp_path: Path) -> None:
    _dvd_structure(tmp_path)
    candidate = DvdTitleCandidate(title_index=1, part_count=3)
    result = DvdInspector(
        _ffprobe_path(tmp_path),
        runner=FakeRunner(has_dvdvideo=False),
        navigator=FakeNavigator((candidate,)),
    ).inspect(tmp_path)

    assert result.status == VideoInspectionStatus.BACKEND_UNAVAILABLE
    assert result.title_candidates == (candidate,)
    assert "dvdvideo" in result.backend.diagnostic


def test_native_chapter_ticks_are_converted_from_90khz() -> None:
    chapters = DvdNavigator._chapters((5_400_000, 10_800_000), 10_800_000)

    assert chapters[0].start_seconds == 0.0
    assert chapters[0].end_seconds == 60.0
    assert chapters[1].start_seconds == 60.0
    assert chapters[1].end_seconds == 120.0


def test_native_worker_output_ignores_libdvdnav_log_lines() -> None:
    payload = DvdNavigator._parse_worker_output(
        'libdvdnav: DVD Title: Example\n{"titles": []}\nlibdvdnav: region mask 0x00\n'
    )

    assert payload == {"titles": []}


def test_native_navigator_refuses_libdvdcss_loader_before_loading(tmp_path: Path) -> None:
    (tmp_path / "libdvdnav-4.dll").write_bytes(b"not-loaded")
    (tmp_path / "libdvdread-8.dll").write_bytes(b"LoadLibraryExA libdvdcss-2.dll")

    with pytest.raises(DvdNavigationError, match="chemin de chargement CSS interdit"):
        DvdNavigator(tmp_path)


def test_native_enumeration_timeout_is_an_access_error_not_protection(tmp_path: Path) -> None:
    _dvd_structure(tmp_path)

    class TimeoutNavigator:
        def enumerate_titles(self, _source: Path) -> tuple[DvdTitleCandidate, ...]:
            raise DvdNavigationError("L'énumération DVD a dépassé le délai de 30 s.")

    result = DvdInspector(
        _ffprobe_path(tmp_path),
        runner=FakeRunner(),
        navigator=TimeoutNavigator(),
    ).inspect(tmp_path)

    assert result.status == VideoInspectionStatus.READ_ERROR
    assert "aucune protection n'est déduite" in result.diagnostic
    assert "timeout" in (result.technical_detail or "").casefold() or "délai" in (
        result.technical_detail or ""
    ).casefold()


def test_dvdvideo_backend_absent_reports_capability_limit(tmp_path: Path) -> None:
    video_ts = _dvd_structure(tmp_path)
    runner = FakeRunner(has_dvdvideo=False)
    result = DvdInspector(_ffprobe_path(tmp_path), runner=runner).inspect(
        tmp_path, title_indices=(1,)
    )

    assert result.status == VideoInspectionStatus.BACKEND_UNAVAILABLE
    assert result.video_ts_path == video_ts
    assert result.title_set_numbers == (1, 2)
    assert "n'expose pas dvdvideo" in result.diagnostic
    assert len(runner.calls) == 2, "aucun probe média sans capability dvdvideo"


def test_unknown_disk_and_invalid_video_ts_are_not_classified_as_dvd(tmp_path: Path) -> None:
    unknown = DvdInspector(_ffprobe_path(tmp_path), runner=FakeRunner()).inspect(tmp_path)
    assert unknown.status == VideoInspectionStatus.INVALID_STRUCTURE

    (tmp_path / "VIDEO_TS").mkdir()
    (tmp_path / "VIDEO_TS" / "VIDEO_TS.IFO").write_bytes(b"not an IFO")
    invalid = DvdInspector(_ffprobe_path(tmp_path), runner=FakeRunner()).inspect(tmp_path)
    assert invalid.status == VideoInspectionStatus.INVALID_STRUCTURE


def test_missing_backend_and_explicit_title_selection(tmp_path: Path) -> None:
    _dvd_structure(tmp_path)
    absent = DvdInspector(tmp_path / "missing-ffprobe.exe").inspect(tmp_path)
    assert absent.status == VideoInspectionStatus.BACKEND_UNAVAILABLE

    runner = FakeRunner()
    needs_title = DvdInspector(_ffprobe_path(tmp_path), runner=runner).inspect(tmp_path)
    assert needs_title.status == VideoInspectionStatus.TITLE_SELECTION_REQUIRED
    assert "numéro de titre explicite" in needs_title.diagnostic
    assert len(runner.calls) == 2
    with pytest.raises(ValueError, match="positifs"):
        DvdInspector(_ffprobe_path(tmp_path), runner=FakeRunner()).inspect(
            tmp_path, title_indices=(0,)
        )


@pytest.mark.parametrize("message", ["Unable to read next block of PGC", "Error reading from DVD."])
def test_zero_exit_code_with_dvd_read_error_is_not_inspected(tmp_path: Path, message: str) -> None:
    _dvd_structure(tmp_path)

    class ReadErrorRunner(FakeRunner):
        def __call__(self, argv, **kwargs):
            result = super().__call__(argv, **kwargs)
            if "-i" in argv:
                result.stderr = message
            return result

    result = DvdInspector(_ffprobe_path(tmp_path), runner=ReadErrorRunner()).inspect(
        tmp_path, title_indices=(1,)
    )

    assert result.status == VideoInspectionStatus.READ_ERROR
    assert result.technical_detail == message
    assert not result.titles
    assert "protection" not in result.diagnostic.casefold()


def test_read_error_and_invalid_ifo_are_reported(tmp_path: Path, monkeypatch) -> None:
    _dvd_structure(tmp_path)
    inspector = DvdInspector(_ffprobe_path(tmp_path), runner=FakeRunner())
    monkeypatch.setattr(inspector, "_read_header", lambda _path: (_ for _ in ()).throw(PermissionError("access denied")))
    denied = inspector.inspect(tmp_path)
    assert denied.status == VideoInspectionStatus.READ_ERROR
    assert "PermissionError" in (denied.technical_detail or "")


def test_protected_or_unsupported_source_is_not_bypassed(tmp_path: Path) -> None:
    _dvd_structure(tmp_path)
    runner = FakeRunner(media_error="Encrypted DVD detected; CSS protection")
    result = DvdInspector(_ffprobe_path(tmp_path), runner=runner).inspect(
        tmp_path, title_indices=(1,)
    )

    assert result.status == VideoInspectionStatus.PROTECTED_OR_UNSUPPORTED
    assert "aucune méthode de contournement" in result.diagnostic
    assert len(runner.calls) == 3, "un seul essai de lecture du titre"


def test_incomplete_probe_data_keeps_unknown_fields_empty(tmp_path: Path) -> None:
    _dvd_structure(tmp_path)
    result = DvdInspector(
        _ffprobe_path(tmp_path), runner=FakeRunner(media_payload=_payload(incomplete=True))
    ).inspect(tmp_path, title_indices=(1,))

    title = result.titles[0]
    assert result.status == VideoInspectionStatus.INSPECTED
    assert title.audio_streams[0].language is None
    assert title.audio_streams[0].channels is None
    assert title.audio_streams[0].index is None
    assert any("indisponibles" in warning for warning in result.warnings)


def test_pcm_dvd_sample_depth_is_preserved() -> None:
    inspector = DvdInspector()
    title, _, _ = inspector._parse_title(
        {"streams": [{"index": 1, "codec_type": "audio", "codec_name": "pcm_dvd",
                      "bits_per_raw_sample": "16"}]}, 1, 1
    )
    assert title.audio_streams[0].bits_per_raw_sample == 16


def test_title_timeout_is_reported_without_retry(tmp_path: Path) -> None:
    _dvd_structure(tmp_path)

    class TimeoutRunner(FakeRunner):
        def __call__(self, argv, **kwargs):
            if "-show_streams" in argv:
                self.calls.append(list(argv))
                raise subprocess.TimeoutExpired(argv, kwargs["timeout"])
            return super().__call__(argv, **kwargs)

    runner = TimeoutRunner()
    result = DvdInspector(_ffprobe_path(tmp_path), runner=runner).inspect(
        tmp_path, title_indices=(1,)
    )
    assert result.status == VideoInspectionStatus.READ_ERROR
    assert "dépassé le délai" in result.diagnostic
    assert len([call for call in runner.calls if "-show_streams" in call]) == 1