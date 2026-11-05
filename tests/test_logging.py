from __future__ import annotations

from pathlib import Path

from audio_video_manager.logging_setup import get_logger, setup_logging


def test_rotating_log_file_created(avm_home: Path) -> None:
    log_dir = avm_home / "logs"
    log_file = setup_logging(log_dir, console=False)
    assert log_file == log_dir / "avm.log"

    logger = get_logger("test")
    logger.info("hello-phase0")
    for handler in logger.handlers:
        handler.flush()
    # Le logger enfant propage vers avm ; flush handlers racine.
    root = get_logger("avm")
    for handler in root.handlers:
        handler.flush()

    assert log_file.is_file()
    content = log_file.read_text(encoding="utf-8")
    assert "hello-phase0" in content
