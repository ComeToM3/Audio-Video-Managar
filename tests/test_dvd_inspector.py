"""AVM-11B : fixtures synthétiques non protégées, aucune extraction."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from audio_video_manager.extraction import dvd
from audio_video_manager.extraction.cd import CommandProbe


@pytest.fixture()
def dvd_tree(tmp_path: Path) -> Path:
    directory = tmp_path / "VIDEO_TS"
    directory.mkdir()
    for name, content in {
        "VIDEO_TS.IFO": b"DVDVIDEO-VMG",
        "VIDEO_TS.BUP": b"DVDVIDEO-VMG",
        "VTS_01_0.IFO": b"DVDVIDEO-VTS",
        "VTS_01_0.BUP": b"DVDVIDEO-VTS",
        "VTS_01_1.VOB": b"synthetic placeholder, not playable",
    }.items():
        (directory / name).write_bytes(content)
    return directory


@pytest.fixture()
def probe_data() -> dict:
    return {
        "streams": [
            {
                "index": 0, "codec_type": "video", "codec_name": "mpeg2video",
                "width": 720, "height": 576, "avg_frame_rate": "25/1",
                "display_aspect_ratio": "16:9", "field_order": "tt",
            },
            {
                "index": 1, "codec_type": "audio", "codec_name": "ac3",
                "channels": 6, "sample_rate": "48000", "tags": {"language": "eng"},
            },
            {
                "index": 2, "codec_type": "audio", "codec_name": "pcm_dvd",
                "channels": 2, "sample_rate": "48000", "tags": {"language": "fra"},
            },
            {"index": 3, "codec_type": "subtitle", "codec_name": "dvd_subtitle"},
        ],
        "chapters": [
            {"id": 0, "start_time": "0.000", "end_time": "123.400", "tags": {"title": "Intro"}},
            {"id": 1, "start_time": "123.400", "end_time": "3600.000"},
        ],
        "format": {"duration": "3600.000", "format_name": "dvdvideo"},
    }


@pytest.fixture()
def working_probe(monkeypatch: pytest.MonkeyPatch, probe_data: dict) -> list:
    calls = []

    def run(executable, *args):
        calls.append((str(executable), *args))
        if "-demuxers" in args:
            output = "Demuxers:\n D  dvdvideo       DVD-Video\n D  mpeg MPEG-PS"
        elif "demuxer=dvdvideo" in args:
            output = "Demuxer dvdvideo [DVD-Video]:\n  -title <int> .D........."
        elif "-i" in args:
            output = json.dumps(probe_data)
        else:
            output = "synthetic ffprobe fixture"
        return CommandProbe((str(executable), *args), 0, output, "")

    monkeypatch.setattr(dvd, "_run_probe", run)
    return calls


def inspector() -> dvd.DvdInspector:
    return dvd.DvdInspector(
        ffprobe=Path("/fixture/ffprobe"), ffmpeg=Path("/fixture/ffmpeg"),
        no_css_environment=True,
    )


def test_structure_root_and_video_ts(dvd_tree: Path):
    direct = dvd.inspect_dvd_structure(dvd_tree)
    assert dvd.inspect_dvd_structure(dvd_tree.parent) == direct
    assert direct.title_sets == (1,)
    assert not direct.warnings


def test_case_insensitive_structure_and_multiple_title_sets(dvd_tree: Path):
    (dvd_tree / "VTS_02_0.IFO").write_bytes(b"DVDVIDEO-VTS")
    (dvd_tree / "VTS_02_1.VOB").write_bytes(b"synthetic")
    (dvd_tree / "VIDEO_TS.IFO").rename(dvd_tree / "video_ts.ifo")
    directory = dvd_tree.rename(dvd_tree.parent / "video_ts")
    result = dvd.inspect_dvd_structure(directory.parent)
    assert result.title_sets == (1, 2)
    assert result.warnings == ("VTS_02_0.BUP absent.",)


@pytest.mark.parametrize("filename", ["VIDEO_TS.IFO", "VTS_01_0.IFO", "VTS_01_1.VOB"])
def test_incomplete_structure(dvd_tree: Path, filename: str):
    (dvd_tree / filename).unlink()
    result = inspector().inspect(dvd_tree)
    assert result.status == "invalid_structure"
    assert filename in result.message or "VTS" in result.message


@pytest.mark.parametrize("filename", ["VIDEO_TS.IFO", "VTS_01_0.IFO"])
def test_bad_ifo_signature(dvd_tree: Path, filename: str):
    (dvd_tree / filename).write_bytes(b"not an IFO")
    assert inspector().inspect(dvd_tree).status == "invalid_structure"


def test_missing_and_non_dvd_sources(tmp_path: Path):
    assert inspector().inspect(tmp_path / "missing").status == "source_missing"
    assert inspector().inspect(tmp_path).status == "invalid_structure"
    ordinary = tmp_path / "ordinary.vob"
    ordinary.write_bytes(b"not a disc")
    assert inspector().inspect(ordinary).status == "invalid_structure"


def test_structure_io_error(dvd_tree: Path, monkeypatch: pytest.MonkeyPatch):
    def denied(*args):
        raise PermissionError("drive access denied")

    monkeypatch.setattr(Path, "open", denied)
    result = inspector().inspect(dvd_tree)
    assert result.status == "read_error"
    assert "drive access denied" in result.message


def test_default_never_probes_commercial_disc(dvd_tree: Path, monkeypatch: pytest.MonkeyPatch):
    def forbidden(*args):
        pytest.fail("No metadata/tool probe allowed for unknown protection")

    monkeypatch.setattr(dvd, "_run_probe", forbidden)
    before = {p.name: p.read_bytes() for p in dvd_tree.iterdir()}
    result = inspector().inspect(dvd_tree)
    assert result.status == "structure_only"
    assert result.title is None
    assert "protection indéterminées" in result.message
    assert before == {p.name: p.read_bytes() for p in dvd_tree.iterdir()}


def test_unprotected_selected_title_and_read_only_argv(dvd_tree: Path, working_probe: list):
    result = inspector().inspect(dvd_tree, title_number=2, known_unprotected=True)
    assert result.status == "inspected"
    assert result.title.title_number == 2
    assert result.title.duration_seconds == 3600
    assert result.title.streams[0].field_order == "tt"
    assert result.title.streams[1].channels == 6
    assert result.title.streams[2].codec == "pcm_dvd"
    assert result.title.streams[3].kind == "subtitle"
    assert result.title.chapters[1].start_seconds == 123.4
    assert working_probe[-1] == (
        "/fixture/ffprobe", "-v", "error", "-f", "dvdvideo", "-title", "2",
        "-show_streams", "-show_chapters", "-show_format", "-of", "json",
        "-i", str(dvd_tree),
    )
    assert result.probe.stdout
    assert len(working_probe) == 5


def test_unverified_dependency_stack_never_opens_media(dvd_tree: Path, working_probe: list):
    obj = inspector()
    obj.no_css_environment = False
    result = obj.inspect(dvd_tree, known_unprotected=True)
    assert result.status == "backend_unverified"
    assert result.probe is None
    assert not working_probe


@pytest.mark.parametrize("number", [0, 100, -1, "1", True, 1.5])
def test_invalid_title_is_controlled(dvd_tree: Path, number, working_probe: list):
    assert inspector().inspect(dvd_tree, title_number=number).status == "invalid_title"
    assert not working_probe


def test_actual_demuxer_list_not_version_controls_capability(monkeypatch: pytest.MonkeyPatch):
    def run(executable, *args):
        return CommandProbe(
            (str(executable), *args), 0,
            "ffprobe version 8 --enable-libdvdread --enable-libdvdnav\n D mpeg MPEG-PS",
            "Unknown format 'dvdvideo'.",
        )

    monkeypatch.setattr(dvd, "_run_probe", run)
    result = dvd.probe_dvd_tool(Path("/fixture/ffprobe"))
    assert result.status == "dvdvideo_unavailable"
    assert not result.dvdvideo
    assert not result.title_option
    assert len(result.probes) == 4


def test_ffmpeg_support_does_not_imply_ffprobe_support(dvd_tree: Path, working_probe: list):
    obj = inspector()
    assert dvd.probe_dvd_tool(obj.ffmpeg).status == "available"
    obj.ffprobe = None
    result = obj.inspect(dvd_tree, known_unprotected=True)
    assert result.status == "tool_missing"
    assert result.structure is not None
    assert len(working_probe) == 4


@pytest.mark.parametrize(
    ("failure", "expected"),
    [(FileNotFoundError("missing"), "tool_error"), (PermissionError("denied"), "tool_error"),
     (subprocess.TimeoutExpired("ffprobe", 15), "tool_error")],
)
def test_launch_errors_and_timeouts_are_controlled(
    dvd_tree: Path, monkeypatch: pytest.MonkeyPatch, failure, expected: str,
):
    def fail(*args, **kwargs):
        assert kwargs["timeout"] == 15
        assert not kwargs.get("shell", False)
        raise failure

    monkeypatch.setattr(subprocess, "run", fail)
    result = inspector().inspect(dvd_tree, known_unprotected=True)
    assert result.status == expected
    assert result.capabilities.probes[0].error


@pytest.mark.parametrize("stderr", ["Input/output error", "Permission denied", "CSS encrypted DVD"])
def test_read_failure_is_not_proof_of_protection(
    dvd_tree: Path, working_probe: list, monkeypatch: pytest.MonkeyPatch, stderr: str,
):
    run = dvd._run_probe

    def fail(executable, *args):
        if "-i" in args:
            return CommandProbe((str(executable), *args), 1, "", stderr)
        return run(executable, *args)

    monkeypatch.setattr(dvd, "_run_probe", fail)
    result = inspector().inspect(dvd_tree, known_unprotected=True)
    assert result.status == "read_error"
    assert result.probe.stderr == stderr
    assert "ne prouve pas une protection" in result.message


def test_metadata_timeout(dvd_tree: Path, working_probe: list, monkeypatch: pytest.MonkeyPatch):
    run = dvd._run_probe

    def timeout(executable, *args):
        if "-i" in args:
            return CommandProbe((str(executable), *args), None, "", "", "timeout after 15s")
        return run(executable, *args)

    monkeypatch.setattr(dvd, "_run_probe", timeout)
    result = inspector().inspect(dvd_tree, known_unprotected=True)
    assert result.status == "probe_error"
    assert "timeout" in result.message


@pytest.mark.parametrize("text", ["not json", "[]", "{}", '{"streams": null}', '{"streams": [null]}'])
def test_bad_json_is_controlled(
    dvd_tree: Path, working_probe: list, monkeypatch: pytest.MonkeyPatch, text: str,
):
    run = dvd._run_probe

    def invalid(executable, *args):
        if "-i" in args:
            return CommandProbe((str(executable), *args), 0, text, "")
        return run(executable, *args)

    monkeypatch.setattr(dvd, "_run_probe", invalid)
    assert inspector().inspect(dvd_tree, known_unprotected=True).status == "invalid_metadata"


@pytest.mark.parametrize("duration", ["NaN", "inf", "-1"])
def test_invalid_duration(probe_data: dict, duration: str):
    probe_data["format"]["duration"] = duration
    with pytest.raises(ValueError):
        dvd.parse_dvd_probe(json.dumps(probe_data), Path("/fixture/VIDEO_TS"), 1)


def test_unknown_values_are_not_invented_and_ntsc_preserved(probe_data: dict):
    probe_data.pop("format")
    probe_data.pop("chapters")
    probe_data["streams"][0].update(height=480, avg_frame_rate="30000/1001")
    result = dvd.parse_dvd_probe(json.dumps(probe_data), Path("/fixture/VIDEO_TS"), 1)
    assert result.duration_seconds is None
    assert result.chapters == ()
    assert result.streams[0].frame_rate == "30000/1001"
    assert result.streams[3].language is None


def test_reuses_ffmpeg_discovery_and_sibling_ffprobe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    ffmpeg = tmp_path / "ffmpeg.exe"
    ffprobe = tmp_path / "ffprobe.exe"
    ffprobe.touch()
    monkeypatch.setattr(dvd, "find_flac_decode_tool", lambda: ffmpeg)
    monkeypatch.setattr(dvd.shutil, "which", lambda name: None)
    obj = dvd.DvdInspector()
    assert obj.ffmpeg == ffmpeg
    assert obj.ffprobe == ffprobe


def test_no_tools_is_explicit(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(dvd, "find_flac_decode_tool", lambda: None)
    monkeypatch.setattr(dvd.shutil, "which", lambda name: None)
    assert dvd.DvdInspector().ffprobe is None
    assert dvd.probe_dvd_tool(None).status == "tool_missing"


def test_extraction_remains_disabled():
    assert "reportée" in str(dvd.DvdExtractionNotAvailableError())
