"""AVM-06 — libellés FR de progression (AC-U1-8)."""

from audio_video_manager.ui.progress_labels import map_progress_message


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


def test_map_hides_raw_freac_processing() -> None:
    assert map_progress_message("Processing file: 1.flac") == "Piste 1 — titre non déterminé"
    assert map_progress_message("Démarrage freaccmd…") == "Extraction audio"
