"""AVM-06 — cache pochettes R1."""

from __future__ import annotations

from pathlib import Path
from urllib.request import Request

from PySide6.QtGui import QImage

from audio_video_manager.paths import default_cover_cache_dir, ensure_app_dirs
from audio_video_manager.ui.cover_cache import cached_cover_path, fetch_cover_to_cache


def _png_bytes(tmp_path: Path) -> bytes:
    image = QImage(2, 2, QImage.Format.Format_RGB32)
    image.fill(0xFF336699)
    source = tmp_path / "source.png"
    assert image.save(str(source), "PNG")
    return source.read_bytes()


def test_cover_cache_dir_dedicated(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AVM_DATA_DIR", str(tmp_path / "data"))
    ensure_app_dirs()
    root = default_cover_cache_dir()
    assert root == tmp_path / "data" / "cache" / "covers"
    assert root.is_dir()
    assert "jobs" not in root.parts[-2:]


def test_cached_path_stable(tmp_path: Path) -> None:
    p1 = cached_cover_path("https://example.test/a/cover.jpg", tmp_path)
    p2 = cached_cover_path("https://example.test/a/cover.jpg", tmp_path)
    assert p1 == p2
    assert p1.suffix == ".jpg"


def test_fetch_uses_cache_hit(tmp_path: Path) -> None:
    url = "https://example.test/cover.png"
    dest = cached_cover_path(url, tmp_path)
    image_bytes = _png_bytes(tmp_path)
    dest.write_bytes(image_bytes)
    out = fetch_cover_to_cache(url, cache_dir=tmp_path)
    assert out == dest
    assert out.read_bytes() == image_bytes


def test_invalid_cache_entry_is_replaced_with_decodable_image(
    monkeypatch, tmp_path: Path
) -> None:
    url = "https://example.test/cover.png"
    dest = cached_cover_path(url, tmp_path)
    dest.write_bytes(b"not an image")
    image_bytes = _png_bytes(tmp_path)

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self) -> bytes:
            return image_bytes

    def fake_urlopen(request: Request, *, timeout: float):
        assert request.full_url == url
        assert timeout > 0
        return Response()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    out = fetch_cover_to_cache(url, cache_dir=tmp_path)

    assert out == dest
    assert out.read_bytes() == image_bytes
    assert not QImage.fromData(out.read_bytes()).isNull()
