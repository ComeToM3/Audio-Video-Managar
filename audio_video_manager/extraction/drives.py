"""Parsing de ``freaccmd --list-drives`` (sortie réelle, non inventée)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from audio_video_manager.extraction.cd import CommandProbe, _run_probe
from pathlib import Path


@dataclass(frozen=True)
class CdDrive:
    number: int
    device_path: str
    designation: str

    def label(self) -> str:
        """Identifiant technique (logs / info-bulle) — pas pour le parcours utilisateur."""
        return f"{self.number}: {self.designation} ({self.device_path})"

    def friendly_label(self, drive_letter: str | None = None) -> str:
        """
        Libellé grand public.

        ``drive_letter`` : ex. ``D:`` issu de la détection Windows (jamais inventé).
        Sans lettre fiable : « Lecteur CD/DVD n°N » (N = index fre:ac + 1).
        """
        if drive_letter:
            letter = drive_letter.strip().rstrip("\\").upper()
            if len(letter) == 1 and letter.isalpha():
                letter = f"{letter}:"
            if len(letter) >= 2 and letter[0].isalpha() and letter[1] == ":":
                return f"Lecteur CD/DVD ({letter[:2]})"
        return f"Lecteur CD/DVD n°{self.number + 1}"


_ROW_RE = re.compile(
    r"^\s*(\d+)\s+(\S+)\s+(.+?)\s*$"
)


def parse_list_drives_output(text: str) -> list[CdDrive]:
    """
    Parse le tableau textuel de freaccmd.

    Format observé (v1.1.7)::

        Number	Device path	Designation
        ------------------------------------------------
        0	1:0:0		ATAPI iHAS324   C
    """
    drives: list[CdDrive] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("Number") or set(stripped) <= {"-", "—"}:
            continue
        if stripped.startswith("Available") or stripped.startswith("fre:ac"):
            continue
        if stripped.startswith("Copyright"):
            continue
        match = _ROW_RE.match(line)
        if not match:
            continue
        number_s, device, designation = match.groups()
        try:
            number = int(number_s)
        except ValueError:
            continue
        drives.append(
            CdDrive(
                number=number,
                device_path=device.strip(),
                designation=designation.strip(),
            )
        )
    return drives


def list_cd_drives(freaccmd: Path) -> tuple[list[CdDrive], CommandProbe]:
    """Appelle ``--list-drives`` et retourne (drives, probe brut)."""
    probe = _run_probe(freaccmd, "--list-drives")
    drives = parse_list_drives_output(probe.stdout or "")
    return drives, probe
