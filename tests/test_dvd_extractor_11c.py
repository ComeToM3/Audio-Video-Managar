"""AVM-11C DVD-to-MKV service tests using synthetic DVD structures."""

from __future__ import annotations

import io
import json
import subprocess
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from audio_video_manager.extraction.dvd import DvdInspector
from audio_video_manager.extraction.dvd_extractor import (
    DvdExtractionCancelled,
    DvdExtractionConfirmationRequired,
    DvdExtractionError,
    DvdExtractionPlan,
    DvdExtractionRightsRequired,
    DvdExtractionService,
)
from audio_video_manager.metadata.video import (
    DvdTitleCandidate,
    VideoChapter,
    VideoInspectionStatus,
    VideoStream,
)


def _dvd_structure(root: Path) -> Path:
    video_ts = root / "VIDEO_TS"
    video_ts.mkdir(parents=True)
    (video_ts / "VIDEO_TS.IFO").write_bytes(b"DVDVIDEO-VMG" + bytes(20))
    (video_ts / "VTS_01_0.IFO").write_bytes(b"DVDVIDEO-VTS" + bytes(20))
    (video_ts / "VTS_01_1.VOB").write_bytes(bytes(1024))
    return video_ts


def _dvd_payload() -> dict:
    return {
        "format": {"format_name": "dvdvideo", "duration": "2.0"},
        "streams": [
            {"index": 0, "codec_type": "video", "codec_name": "mpeg2video", "width": 720, "height": 480},
            {"index": 1, "codec_type": "audio", "codec_name": "ac3", "sample_rate": "48000", "channels": 2, "channel_layout": "stereo", "tags": {"language": "eng"}},
            {"index": 2, "codec_type": "subtitle", "codec_name": "dvd_subtitle", "tags": {"language": "fra"}},
        ],
        "chapters": [{"start_time": "0.0", "end_time": "2.0", "tags": {"title": "Chapter 1"}}],
    }


def _mkv_payload(*, drop_subtitle: bool = False, audio_only: bool = False) -> dict:
    payload = _dvd_payload()
    payload["format"] = {"format_name": "matroska,webm", "duration": "2.0"}
    if drop_subtitle:
        payload["streams"] = payload["streams"][:-1]
    if audio_only:
        payload["streams"] = [
            stream for stream in payload["streams"] if stream["codec_type"] == "audio"
        ]
    return payload


class FakeRunner:
    def __init__(self, *, drop_subtitle: bool = False, audio_only: bool = False) -> None:
        self.drop_subtitle = drop_subtitle
        self.audio_only = audio_only
        self.calls: list[list[str]] = []

    def __call__(self, argv, **_kwargs):
        args = list(argv)
        self.calls.append(args)
        if "-version" in args:
            return SimpleNamespace(returncode=0, stdout="ffprobe version fixture\n", stderr="")
        if "-demuxers" in args:
            return SimpleNamespace(returncode=0, stdout=" D  dvdvideo DVD-Video\n", stderr="")
        if "-show_format" in args and args[-1].endswith((".mkv", ".mka")):
            payload = _mkv_payload(
                drop_subtitle=self.drop_subtitle,
                audio_only=self.audio_only,
            )
        else:
            payload = _dvd_payload()
        return SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr="")


class FakeNavigator:
    def enumerate_titles(self, _source: Path) -> tuple[DvdTitleCandidate, ...]:
        return (
            DvdTitleCandidate(
                title_index=1,
                part_count=1,
                angle_count=1,
                duration_seconds=2.0,
                chapters=(VideoChapter(index=1, start_seconds=0.0, end_seconds=2.0),),
            ),
            DvdTitleCandidate(
                title_index=2,
                part_count=1,
                angle_count=2,
                duration_seconds=20.0,
                chapters=(VideoChapter(index=1, start_seconds=0.0, end_seconds=20.0),),
            ),
        )


class FakeProcess:
    def __init__(self, argv, **_kwargs) -> None:
        self.argv = list(argv)
        _process_calls.append(self.argv)
        self.returncode = 0
        self.stdout = io.StringIO("out_time_us=2000000\nout_time=00:00:02.000\nprogress=end\n")
        self.stderr = io.StringIO("")
        if "matroska" in self.argv:
            Path(self.argv[-1]).write_bytes(b"fixture mkv bytes")

    def poll(self) -> int | None:
        return self.returncode

    def wait(self, timeout: float | None = None) -> int:
        return self.returncode

    def terminate(self) -> None:
        self.returncode = -15

    def kill(self) -> None:
        self.returncode = -9


class StalledProcess:
    def __init__(self, *_args, **_kwargs) -> None:
        self.returncode = None
        self.stdout = io.StringIO("")
        self.stderr = io.StringIO("")

    def poll(self) -> int | None:
        return self.returncode

    def wait(self, timeout: float | None = None) -> int:
        return self.returncode or 0

    def terminate(self) -> None:
        self.returncode = -15

    def kill(self) -> None:
        self.returncode = -9


class ProgressProcess(StalledProcess):
    def __init__(self) -> None:
        super().__init__()
        self.stdout = io.StringIO(
            "out_time_us=1000000\nout_time=00:00:01.000\nprogress=continue\n"
        )


def _service(
    tmp_path: Path,
    *,
    drop_subtitle: bool = False,
    audio_only: bool = False,
    timeout: float = 1.0,
):
    _process_calls.clear()
    source = tmp_path / "source"
    source.mkdir()
    _dvd_structure(source)
    ffprobe = tmp_path / "ffprobe.exe"
    ffmpeg = tmp_path / "ffmpeg.exe"
    ffprobe.write_bytes(b"fixture")
    ffmpeg.write_bytes(b"fixture")
    inspector = DvdInspector(
        ffprobe_path=ffprobe,
        runner=FakeRunner(drop_subtitle=drop_subtitle),
        navigator=FakeNavigator(),
    )
    destination_dir = tmp_path / "TestLibrary"
    destination_dir.mkdir()
    service = DvdExtractionService(
        ffmpeg_path=ffmpeg,
        inspector=inspector,
        runner=FakeRunner(drop_subtitle=drop_subtitle, audio_only=audio_only),
        popen_factory=FakeProcess,
        inactivity_timeout_seconds=timeout,
    )
    return service, source, destination_dir


def test_preflight_suggests_longest_title_without_extracting(tmp_path: Path) -> None:
    service, source, destination = _service(tmp_path)
    plan = service.prepare(source, destination / "master.mkv")

    assert plan.suggested_title_index == 2
    assert [candidate.title_index for candidate in plan.inspection.title_candidates] == [1, 2]
    assert not (destination / "master.mkv").exists()


def test_confirmation_is_required_before_any_ffmpeg_process(tmp_path: Path) -> None:
    service, source, destination = _service(tmp_path)
    plan = service.prepare(source, destination / "master.mkv")

    with pytest.raises(DvdExtractionConfirmationRequired):
        service.extract(plan, title_index=2)

    assert not (destination / "master.mkv").exists()


def test_both_extraction_modes_require_rights_attestation(tmp_path: Path) -> None:
    service, source, destination = _service(tmp_path)
    mkv_plan = service.prepare(source, destination / "master.mkv")
    mka_plan = service.prepare(source, destination / "audio.mka")

    with pytest.raises(DvdExtractionRightsRequired):
        service.extract(mkv_plan, title_index=2, confirmed=True)
    with pytest.raises(DvdExtractionRightsRequired):
        service.extract_audio(
            mka_plan,
            title_index=2,
            audio_stream_indices=(1,),
            confirmed=True,
        )

    assert not (destination / "master.mkv").exists()
    assert not (destination / "audio.mka").exists()


def test_extract_maps_all_streams_copies_without_reencoding_and_publishes(tmp_path: Path) -> None:
    service, source, destination = _service(tmp_path)
    plan = service.prepare(source, destination / "master.mkv")
    progress: list[tuple[str, float | None]] = []

    result = service.extract(
        plan,
        title_index=2,
        angle_index=2,
        confirmed=True,
        rights_attested=True,
        on_progress=lambda message, fraction: progress.append((message, fraction)),
    )

    assert result.output_path.is_file()
    assert result.title_index == 2 and result.angle_index == 2
    assert result.duration_seconds == 2.0
    assert {stream.codec_type for stream in result.streams} == {"video", "audio", "subtitle"}
    assert result.chapter_count == 1
    extraction_call = next(call for call in _process_calls if "matroska" in call)
    assert extraction_call[extraction_call.index("-title") + 1] == "2"
    assert extraction_call[extraction_call.index("-angle") + 1] == "2"
    assert extraction_call[extraction_call.index("-map") + 1] == "0"
    assert extraction_call[extraction_call.index("-c") + 1] == "copy"
    assert "-y" not in extraction_call
    assert any("Validation" in message or "Validation" in message for message, _ in progress)
    assert not list(destination.glob(".avm-dvd-*"))


def test_audio_only_extract_copies_only_selected_tracks_to_mka(tmp_path: Path) -> None:
    service, source, destination = _service(tmp_path, audio_only=True)
    plan = service.prepare(source, destination / "audio.mka")
    result = service.extract_audio(
        plan,
        title_index=2,
        angle_index=2,
        audio_stream_indices=(1,),
        confirmed=True,
        rights_attested=True,
    )

    assert result.output_path == destination / "audio.mka"
    assert result.output_path.is_file()
    assert result.streams and all(stream.codec_type == "audio" for stream in result.streams)
    assert result.streams[0].codec_name == "ac3"
    assert result.streams[0].language == "eng"
    assert result.chapter_count == 1
    audio_call = next(call for call in _process_calls if "matroska" in call)
    assert audio_call[audio_call.index("-title") + 1] == "2"
    assert audio_call[audio_call.index("-angle") + 1] == "2"
    assert "0:1" in audio_call
    assert "0:0" not in audio_call
    assert audio_call[audio_call.index("-c:a") + 1] == "copy"
    assert "-vn" in audio_call and "-y" not in audio_call
    assert not list(destination.glob(".avm-dvd-audio-*"))


@pytest.mark.parametrize("mode", ["mkv", "mka"])
@pytest.mark.parametrize("matching", [True, False])
def test_pcm_conversion_requires_matching_sample_hashes(tmp_path: Path, mode: str, matching: bool) -> None:
    service, source, destination = _service(tmp_path, audio_only=mode == "mka")

    class PcmRunner(FakeRunner):
        def __call__(self, argv, **kwargs):
            result = super().__call__(argv, **kwargs)
            if "-show_format" not in argv:
                return result
            payload = json.loads(result.stdout)
            audio = next(stream for stream in payload["streams"] if stream["codec_type"] == "audio")
            if argv[-1].endswith((".mkv", ".mka")):
                audio["codec_name"] = "pcm_s16le"
                audio.pop("channel_layout", None)
            else:
                audio["codec_name"] = "pcm_dvd"
                audio["bits_per_raw_sample"] = "16"
            result.stdout = json.dumps(payload)
            return result

    class PcmProcess(FakeProcess):
        def __init__(self, argv, **kwargs):
            super().__init__(argv, **kwargs)
            if "hash" in argv:
                is_output = str(argv[-1]).endswith("-sortie.sha256")
                digit = "b" if is_output and not matching else "a"
                Path(argv[-1]).write_text("SHA256=" + digit * 64 + "\n", encoding="ascii")

    service._inspector._runner = PcmRunner()
    service._runner = PcmRunner(audio_only=mode == "mka")
    service._popen_factory = PcmProcess
    output = destination / f"master.{mode}"
    plan = service.prepare(source, output)
    kwargs = {"title_index": 1, "confirmed": True, "rights_attested": True}
    if mode == "mka":
        kwargs["audio_stream_indices"] = (1,)
        extract = service.extract_audio
    else:
        extract = service.extract
    with pytest.raises(DvdExtractionConfirmationRequired):
        extract(plan, **kwargs)
    if matching:
        result = extract(plan, allow_pcm_conversion=True, **kwargs)
        assert result.output_path.is_file()
        assert any("échantillons vérifiés" in warning for warning in result.warnings)
        call = next(call for call in _process_calls if "matroska" in call)
        assert "pcm_s16le" in call
        assert len([call for call in _process_calls if "hash" in call]) == 2
    else:
        with pytest.raises(DvdExtractionError, match="échantillons PCM"):
            extract(plan, allow_pcm_conversion=True, **kwargs)
        assert not output.exists()
        assert not list(destination.glob(".avm-dvd-*"))


def test_pcm_conversion_rejects_unknown_or_unsupported_depth() -> None:
    stream = VideoStream(index=1, codec_type="audio", codec_name="pcm_dvd", sample_rate=48000,
                         channels=2, channel_layout="stereo", bits_per_raw_sample=24)
    with pytest.raises(DvdExtractionError, match="16 bits"):
        DvdExtractionService._pcm_conversions((stream,), allowed=True)


def test_audio_only_requires_explicit_audio_track_selection(tmp_path: Path) -> None:
    service, source, destination = _service(tmp_path, audio_only=True)
    plan = service.prepare(source, destination / "audio.mka")

    with pytest.raises(ValueError, match="au moins une piste audio"):
        service.extract_audio(
            plan,
            title_index=2,
            audio_stream_indices=(),
            confirmed=True,
            rights_attested=True,
        )
    with pytest.raises(ValueError, match="n’est pas une piste audio"):
        service.extract_audio(
            plan,
            title_index=2,
            audio_stream_indices=(0,),
            confirmed=True,
            rights_attested=True,
        )


def test_mkv_with_silently_dropped_subtitle_is_rejected_and_cleaned(tmp_path: Path) -> None:
    service, source, destination = _service(tmp_path, drop_subtitle=True)
    plan = service.prepare(source, destination / "master.mkv")

    with pytest.raises(DvdExtractionError, match="flux du MKV diffèrent"):
        service.extract(plan, title_index=2, confirmed=True, rights_attested=True)

    assert not (destination / "master.mkv").exists()
    assert not list(destination.glob(".avm-dvd-*"))


def test_preflight_refuses_existing_destination(tmp_path: Path) -> None:
    service, _source, destination = _service(tmp_path)
    target = destination / "existing.mkv"
    target.write_bytes(b"keep")

    with pytest.raises(FileExistsError):
        service.prepare(tmp_path, target)

    assert target.read_bytes() == b"keep"


def test_extract_rejects_modified_plan_destination_inside_source(tmp_path: Path) -> None:
    service, source, destination = _service(tmp_path)
    plan = service.prepare(source, destination / "safe.mkv")
    unsafe_plan = DvdExtractionPlan(
        source=source,
        destination=source / "VIDEO_TS" / "must-not-be-created.mkv",
        inspection=plan.inspection,
        suggested_title_index=plan.suggested_title_index,
        estimated_output_bytes=plan.estimated_output_bytes,
    )

    with pytest.raises(ValueError, match="destination ne peut pas être dans"):
        service.extract(
            unsafe_plan, title_index=2, confirmed=True, rights_attested=True
        )

    assert not (source / "VIDEO_TS" / "must-not-be-created.mkv").exists()


def test_ffmpeg_worker_refuses_css_dll_in_its_search_directory(tmp_path: Path) -> None:
    service, _source, _destination = _service(tmp_path)
    (tmp_path / "libdvdcss-2.dll").write_bytes(b"not-loaded")

    with pytest.raises(DvdExtractionError, match="backend CSS interdit"):
        service._ffmpeg_child_environment(tmp_path)


def test_cancel_before_extraction_does_not_start_or_publish(tmp_path: Path) -> None:
    service, source, destination = _service(tmp_path)
    plan = service.prepare(source, destination / "master.mkv")
    cancelled = threading.Event()
    cancelled.set()

    with pytest.raises(DvdExtractionCancelled):
        service.extract(
            plan,
            title_index=2,
            confirmed=True,
            rights_attested=True,
            cancel_event=cancelled,
        )

    assert not (destination / "master.mkv").exists()


_process_calls: list[list[str]] = []


def test_monitored_process_stops_on_inactivity(tmp_path: Path) -> None:
    service, _video_ts, _destination = _service(
        tmp_path, timeout=0.02
    )
    service._popen_factory = lambda *args, **kwargs: _record_stalled_process(args, kwargs)
    _process_calls.clear()

    with pytest.raises(DvdExtractionError, match="Timeout d’inactivité"):
        service._run_monitored(
            ["ffmpeg", "-i", "dvd"],
            duration_seconds=10,
            cancel_event=None,
            on_progress=None,
            phase="test",
            fraction_start=0,
            fraction_span=1,
        )


def test_monitored_process_terminates_when_cancelled_during_progress(tmp_path: Path) -> None:
    service, _source, _destination = _service(tmp_path)
    service._popen_factory = lambda *args, **kwargs: _record_progress_process(args, kwargs)
    cancel = threading.Event()

    def cancel_after_progress(_message: str, _fraction: float | None) -> None:
        cancel.set()

    with pytest.raises(DvdExtractionCancelled):
        service._run_monitored(
            ["ffmpeg", "-i", "dvd"],
            duration_seconds=10,
            cancel_event=cancel,
            on_progress=cancel_after_progress,
            phase="test",
            fraction_start=0,
            fraction_span=1,
        )


def _record_stalled_process(args, kwargs):
    _process_calls.append(list(args[0]))
    return StalledProcess()


def _record_progress_process(args, kwargs):
    _process_calls.append(list(args[0]))
    return ProgressProcess()