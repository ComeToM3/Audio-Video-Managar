from audio_video_manager.extraction.drives import parse_list_drives_output
from audio_video_manager.extraction.drives import CdDrive
from audio_video_manager.config import AppConfig
from audio_video_manager.metadata.models import TocSnapshot
from audio_video_manager.metadata.toc_reader import DiscReadResult
from audio_video_manager.ui.identify_worker import OpticalMediaScanWorker


SAMPLE = """fre:ac - free audio converter v1.1.7 (x86-64) command line interface
Copyright (C) 2001-2023 Robert Kausch

Available CD drives:

	Number	Device path	Designation
	------------------------------------------------
	0	1:0:0		ATAPI iHAS324   C
"""


def test_parse_list_drives_observed_format() -> None:
    drives = parse_list_drives_output(SAMPLE)
    assert len(drives) == 1
    assert drives[0].number == 0
    assert drives[0].device_path == "1:0:0"
    assert "iHAS324" in drives[0].designation
    assert drives[0].friendly_label("D:") == "Lecteur CD/DVD (D:)"
    assert "ATAPI" not in drives[0].friendly_label("D:")


def test_parse_empty() -> None:
    assert parse_list_drives_output("") == []


def test_optical_scan_worker_reports_no_disc_without_blocking_ui(monkeypatch, tmp_path) -> None:
    from types import SimpleNamespace

    monkeypatch.setattr(
        "audio_video_manager.ui.identify_worker.probe_freaccmd",
        lambda **_kwargs: SimpleNamespace(found=True, path=tmp_path / "freaccmd.exe", message=""),
    )
    monkeypatch.setattr(
        "audio_video_manager.ui.identify_worker.FreacCdRipper.list_drives",
        lambda _self: [CdDrive(0, "1:0:0", "ATAPI drive")],
    )
    monkeypatch.setattr(
        "audio_video_manager.ui.identify_worker.list_cdrom_device_letters",
        lambda: ["D:"],
    )

    def no_disc(device: str):
        raise RuntimeError(f"aucun disque dans {device}")

    monkeypatch.setattr("audio_video_manager.ui.identify_worker.read_disc_toc", no_disc)
    worker = OpticalMediaScanWorker(AppConfig())
    results = []
    worker.finished.connect(results.append)

    worker.run()

    assert len(results) == 1
    assert results[0].devices == ("D:",)
    assert results[0].drives[0].number == 0
    assert results[0].discs == ()
    assert results[0].read_errors == ("D:: aucun disque dans D:",)


def test_optical_scan_worker_returns_inserted_disc_by_windows_device(monkeypatch, tmp_path) -> None:
    from types import SimpleNamespace

    monkeypatch.setattr(
        "audio_video_manager.ui.identify_worker.probe_freaccmd",
        lambda **_kwargs: SimpleNamespace(found=False, path=None, message="freaccmd absent"),
    )
    monkeypatch.setattr(
        "audio_video_manager.ui.identify_worker.list_cdrom_device_letters",
        lambda: ["D:", "E:"],
    )
    toc = TocSnapshot(
        first_track=1,
        last_track=1,
        track_offsets_sectors=[0],
        track_durations_ms=[180_000],
        audio_track_count=1,
        raw_source="libdiscid",
    )

    def read(device: str):
        if device == "D:":
            raise RuntimeError("aucun disque")
        return DiscReadResult("disc-e", toc, device)

    monkeypatch.setattr("audio_video_manager.ui.identify_worker.read_disc_toc", read)
    worker = OpticalMediaScanWorker(AppConfig())
    results = []
    worker.finished.connect(results.append)

    worker.run()

    assert len(results) == 1
    assert results[0].devices == ("D:", "E:")
    assert [(disc.disc_id, disc.device) for disc in results[0].discs] == [("disc-e", "E:")]
    assert results[0].read_errors == ("D:: aucun disque",)
    assert results[0].freaccmd_error == "freaccmd absent"
