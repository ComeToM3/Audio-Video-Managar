"""AVM-06 — libellés FR de progression (AC-U1-8)."""

from audio_video_manager.ui.progress_labels import (
    map_progress_message,
    parse_completed_track_number,
    parse_track_number_from_progress,
)


def test_map_extraction_and_publish() -> None:
    assert map_progress_message("Extraction fre:ac en cours") == "Extraction audio"
    assert map_progress_message("Publication bibliothèque") == "Publication"
    assert map_progress_message("Vérification Disc ID") == "Vérification du disque"
    assert map_progress_message("Contrôle d'intégrité F-08a") == "Contrôle des fichiers"
    assert map_progress_message("Tags mutagen + pochette") == "Mise en tags et pochette"
    assert map_progress_message("Organisation zone B / inbox") == "Organisation"


def test_map_empty_fallback() -> None:
    assert map_progress_message("") == "En cours…"
    assert map_progress_message("étape inconnue xyz") == "étape inconnue xyz"


def test_silent_freac_heartbeat_remains_visible() -> None:
    message = "fre:ac est actif; aucun nouvel événement observé depuis 5 s."
    assert map_progress_message(message) == message


def test_map_hides_raw_freac_processing() -> None:
    assert map_progress_message("Processing file: 1.flac") == "Piste 1 — titre non déterminé"
    assert map_progress_message("Démarrage freaccmd…") == "Extraction audio"


def test_parse_real_freac_completed_track_event() -> None:
    event = "Processing file: Audio CD 0 - Track 4...done."
    assert parse_track_number_from_progress(event) == 4
    assert parse_completed_track_number(event) == 4
    assert map_progress_message(
        event, track_titles=["A", "B", "C", "D"], track_total=10
    ) == "Piste 4/10 — D"
    assert parse_completed_track_number(
        "Processing file: Audio CD 0 - Track 4..."
    ) is None
