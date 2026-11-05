"""Fixtures pytest — isolement AVM_DATA_DIR + hooks Qt (AVM-10C / 10C.2)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

# Marqueurs / isolation CI
UI_TEST_FILES = frozenset(
    {
        "test_ux_06o.py",
        "test_ui_design_06l.py",
        "test_ui_shell.py",
        "test_ui_library_history_06h.py",
        "test_library_qml_08b.py",
        "test_humanisation_06i.py",
        "test_ui_w3_prefill.py",
        "test_ui_collision_replace_disabled.py",
        "test_history_06n.py",
        "test_qthread_07b.py",
        "test_qt_teardown_10c1.py",
        "test_qt_teardown_10c2.py",
    }
)


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "qt_ui: tests PySide6/QML (isolation sous-processus CI)")
    config.addinivalue_line(
        "markers",
        "requires_freac: nécessite freaccmd.exe (skipped sinon — jamais compté PASS)",
    )
    config.addinivalue_line(
        "markers", "requires_discid: nécessite discid.dll chargeable"
    )
    config.addinivalue_line(
        "markers", "requires_ffmpeg: nécessite ffmpeg pour décodage"
    )
    config.addinivalue_line(
        "markers", "windows_real: validation Windows réelle (hors CI minimale)"
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    for item in items:
        path = Path(str(item.fspath)).name
        if path in UI_TEST_FILES:
            item.add_marker(pytest.mark.qt_ui)


@pytest.fixture(autouse=True)
def _avm_qt_ui_teardown(request: pytest.FixtureRequest):
    """AVM-10C.2 — teardown central après chaque test Qt (widgets orphelins)."""
    yield
    if request.node.get_closest_marker("qt_ui") is None:
        return
    try:
        from tests.qt_support import qt_session_cleanup

        qt_session_cleanup()
    except Exception:  # noqa: BLE001
        # Ne pas masquer l’échec du test ; le cleanup best-effort ne doit pas lever
        pass


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """
    Fin de session Qt : cleanup ordonné toujours ; ``os._exit`` seulement si
    ``AVM_QT_SAFE_EXIT=1`` (contournement CI — pas une preuve GO 10C.2).
    """
    qt_items = [i for i in session.items if i.get_closest_marker("qt_ui") is not None]
    if not qt_items:
        return
    try:
        from tests.qt_support import pytest_safe_exit, qt_session_cleanup

        qt_session_cleanup()
    except Exception:  # noqa: BLE001
        pass
    # Défaut 10C.2 = fermeture naturelle (« 0 »). « 1 » = contournement secours.
    if os.environ.get("AVM_QT_SAFE_EXIT", "0") == "1":
        try:
            from tests.qt_support import pytest_safe_exit

            pytest_safe_exit(int(exitstatus))
        except Exception:  # noqa: BLE001
            return


@pytest.fixture()
def avm_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    data = tmp_path / "avm-data"
    data.mkdir()
    monkeypatch.setenv("AVM_DATA_DIR", str(data))
    monkeypatch.setenv("AVM_LIBRARY_ROOT", str(tmp_path / "library"))
    return data


@pytest.fixture()
def freac_available() -> Path | None:
    from audio_video_manager.extraction.cd import probe_freaccmd

    st = probe_freaccmd(run_probes=False)
    if st.found and st.path:
        return Path(st.path)
    return None


@pytest.fixture()
def ffmpeg_available() -> Path | None:
    from audio_video_manager.verification.flac_decode import find_flac_decode_tool

    return find_flac_decode_tool()


@pytest.fixture()
def discid_available() -> bool:
    try:
        from audio_video_manager.metadata.libdiscid_loader import (
            import_discid,
            prepare_libdiscid_search_path,
        )

        prepare_libdiscid_search_path()
        import_discid()
        return True
    except Exception:  # noqa: BLE001
        return False
