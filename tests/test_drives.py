from audio_video_manager.extraction.drives import parse_list_drives_output


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
