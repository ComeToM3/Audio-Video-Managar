"""Read-only libdvdnav title and chapter enumeration for DVD-Video."""

from __future__ import annotations

import ctypes
import json
import os
import subprocess
import sys
from pathlib import Path

from audio_video_manager.metadata.video import DvdTitleCandidate, VideoChapter


_DVDNAV_STATUS_OK = 1
_DVD_TIMEBASE = 90_000
_MAX_TITLES = 999
_MAX_CHAPTERS = 10_000
_FORBIDDEN_DVDREAD_MARKERS = (
    b"libdvdcss-2.dll",
    b"dvdcss_open",
    b"LoadLibraryExA",
)
_WORKER_CODE = (
    "from audio_video_manager.extraction.dvd_navigation import _run_worker; _run_worker()"
)


class DvdNavigationError(RuntimeError):
    """The native DVD navigation backend could not enumerate a disc."""


class DvdNavigator:
    """Loads a CSS-disabled libdvdnav build from an explicit local directory."""

    def __init__(self, library_directory: str | Path, *, timeout_seconds: int = 30) -> None:
        if os.name != "nt":
            raise OSError("Le backend DVD natif AVM est disponible uniquement sous Windows.")
        directory = Path(library_directory).expanduser().resolve()
        nav_path = directory / "libdvdnav-4.dll"
        read_path = directory / "libdvdread-8.dll"
        if not nav_path.is_file() or not read_path.is_file():
            raise OSError("DLL libdvdnav/libdvdread absentes du répertoire configuré.")
        read_image = read_path.read_bytes()
        if any(marker in read_image for marker in _FORBIDDEN_DVDREAD_MARKERS):
            raise DvdNavigationError(
                "Le DLL libdvdread contient un chemin de chargement CSS interdit; il n'a pas été chargé."
            )
        self._directory = directory
        self._timeout_seconds = timeout_seconds
        self._dll_directory: object | None = None
        self._library: ctypes.CDLL | None = None
        self._crt: ctypes.CDLL | None = None

    def _load_libraries(self) -> None:
        if self._library is not None:
            return
        self._dll_directory = os.add_dll_directory(str(self._directory))
        try:
            self._library = ctypes.CDLL(str(self._directory / "libdvdnav-4.dll"))
            self._crt = ctypes.CDLL("ucrtbase.dll")
        except OSError:
            self._dll_directory.close()
            self._dll_directory = None
            raise
        self._bind_functions()

    def _bind_functions(self) -> None:
        assert self._library is not None and self._crt is not None
        library = self._library
        library.dvdnav_open.argtypes = [ctypes.POINTER(ctypes.c_void_p), ctypes.c_char_p]
        library.dvdnav_open.restype = ctypes.c_int32
        library.dvdnav_close.argtypes = [ctypes.c_void_p]
        library.dvdnav_close.restype = ctypes.c_int32
        library.dvdnav_err_to_string.argtypes = [ctypes.c_void_p]
        library.dvdnav_err_to_string.restype = ctypes.c_char_p
        library.dvdnav_get_number_of_titles.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_int32),
        ]
        library.dvdnav_get_number_of_titles.restype = ctypes.c_int32
        library.dvdnav_get_number_of_parts.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int32,
            ctypes.POINTER(ctypes.c_int32),
        ]
        library.dvdnav_get_number_of_parts.restype = ctypes.c_int32
        library.dvdnav_get_number_of_angles.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int32,
            ctypes.POINTER(ctypes.c_int32),
        ]
        library.dvdnav_get_number_of_angles.restype = ctypes.c_int32
        library.dvdnav_describe_title_chapters.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int32,
            ctypes.POINTER(ctypes.POINTER(ctypes.c_uint64)),
            ctypes.POINTER(ctypes.c_uint64),
        ]
        library.dvdnav_describe_title_chapters.restype = ctypes.c_uint32
        self._crt.free.argtypes = [ctypes.c_void_p]
        self._crt.free.restype = None

    def _error_message(self, handle: ctypes.c_void_p) -> str:
        assert self._library is not None
        try:
            message = self._library.dvdnav_err_to_string(handle)
        except (OSError, ValueError):
            return "Erreur libdvdnav sans détail."
        return message.decode("utf-8", errors="replace") if message else "Erreur libdvdnav."

    @staticmethod
    def _chapters(
        chapter_end_ticks: tuple[int, ...], duration_ticks: int
    ) -> tuple[VideoChapter, ...]:
        chapters: list[VideoChapter] = []
        for offset, chapter_end in enumerate(chapter_end_ticks):
            start_ticks = chapter_end_ticks[offset - 1] if offset else 0
            end_ticks = duration_ticks if offset == len(chapter_end_ticks) - 1 else chapter_end
            start = start_ticks / _DVD_TIMEBASE
            end = end_ticks / _DVD_TIMEBASE
            chapters.append(
                VideoChapter(
                    index=offset + 1,
                    start_seconds=start,
                    end_seconds=end if end >= start else None,
                )
            )
        return tuple(chapters)

    def enumerate_titles(self, source: str | Path) -> tuple[DvdTitleCandidate, ...]:
        request = json.dumps(
            {"directory": str(self._directory), "source": str(source)},
            ensure_ascii=True,
        )
        try:
            result = subprocess.run(
                [sys.executable, "-c", _WORKER_CODE],
                input=request,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self._timeout_seconds,
                check=False,
                creationflags=(
                    getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
                ),
            )
        except subprocess.TimeoutExpired as exc:
            raise DvdNavigationError(
                f"L'énumération DVD a dépassé le délai de {self._timeout_seconds} s."
            ) from exc
        payload = self._parse_worker_output(result.stdout or "")
        if result.returncode != 0 or payload.get("error"):
            detail = payload.get("error") or (result.stderr or "Erreur du worker libdvdnav.").strip()
            raise DvdNavigationError(str(detail))
        try:
            return tuple(
                DvdTitleCandidate(
                    title_index=int(item["title_index"]),
                    part_count=item.get("part_count"),
                    angle_count=item.get("angle_count"),
                    duration_seconds=item.get("duration_seconds"),
                    chapters=tuple(VideoChapter(**chapter) for chapter in item.get("chapters", ())),
                )
                for item in payload["titles"]
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise DvdNavigationError("Le worker libdvdnav a renvoyé des titres invalides.") from exc

    @staticmethod
    def _parse_worker_output(output: str) -> dict:
        for line in output.splitlines():
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict) and ("titles" in payload or "error" in payload):
                return payload
        raise DvdNavigationError("Le worker libdvdnav a renvoyé une réponse invalide.")

    def _enumerate_titles_in_process(self, source: str | Path) -> tuple[DvdTitleCandidate, ...]:
        self._load_libraries()
        assert self._library is not None and self._crt is not None
        handle = ctypes.c_void_p()
        source_bytes = os.fsencode(str(source))
        status = self._library.dvdnav_open(ctypes.byref(handle), source_bytes)
        if status != _DVDNAV_STATUS_OK or not handle.value:
            message = (
                self._error_message(handle)
                if handle.value
                else "Le lecteur DVD n'a pas pu être ouvert."
            )
            if handle.value:
                self._library.dvdnav_close(handle)
            raise DvdNavigationError(message)

        try:
            count = ctypes.c_int32()
            status = self._library.dvdnav_get_number_of_titles(handle, ctypes.byref(count))
            if status != _DVDNAV_STATUS_OK or count.value < 0 or count.value > _MAX_TITLES:
                raise DvdNavigationError(self._error_message(handle))
            candidates: list[DvdTitleCandidate] = []
            for title_index in range(1, count.value + 1):
                parts = ctypes.c_int32()
                part_status = self._library.dvdnav_get_number_of_parts(
                    handle, title_index, ctypes.byref(parts)
                )
                angles = ctypes.c_int32()
                angle_status = self._library.dvdnav_get_number_of_angles(
                    handle, title_index, ctypes.byref(angles)
                )
                chapter_array = ctypes.POINTER(ctypes.c_uint64)()
                duration = ctypes.c_uint64()
                chapter_count = self._library.dvdnav_describe_title_chapters(
                    handle,
                    title_index,
                    ctypes.byref(chapter_array),
                    ctypes.byref(duration),
                )
                if chapter_count > _MAX_CHAPTERS:
                    if chapter_array:
                        self._crt.free(ctypes.cast(chapter_array, ctypes.c_void_p))
                    raise DvdNavigationError("libdvdnav a renvoyé un nombre de chapitres invalide.")
                try:
                    chapter_end_ticks = (
                        tuple(chapter_array[index] for index in range(chapter_count))
                        if chapter_array
                        else ()
                    )
                finally:
                    if chapter_array:
                        self._crt.free(ctypes.cast(chapter_array, ctypes.c_void_p))
                candidates.append(
                    DvdTitleCandidate(
                        title_index=title_index,
                        part_count=parts.value if part_status == _DVDNAV_STATUS_OK else None,
                        angle_count=angles.value if angle_status == _DVDNAV_STATUS_OK else None,
                        duration_seconds=duration.value / _DVD_TIMEBASE,
                        chapters=self._chapters(chapter_end_ticks, duration.value),
                    )
                )
            return tuple(candidates)
        finally:
            self._library.dvdnav_close(handle)


def _run_worker() -> None:
    request = json.load(sys.stdin)
    try:
        navigator = DvdNavigator(request["directory"])
        candidates = navigator._enumerate_titles_in_process(request["source"])
        payload = {
            "titles": [
                {
                    "title_index": title.title_index,
                    "part_count": title.part_count,
                    "angle_count": title.angle_count,
                    "duration_seconds": title.duration_seconds,
                    "chapters": [
                        {
                            "index": chapter.index,
                            "start_seconds": chapter.start_seconds,
                            "end_seconds": chapter.end_seconds,
                            "title": chapter.title,
                        }
                        for chapter in title.chapters
                    ],
                }
                for title in candidates
            ]
        }
    except Exception as exc:
        payload = {"error": f"{type(exc).__name__}: {exc}"}
    print(json.dumps(payload, ensure_ascii=True))