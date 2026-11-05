"""Données fictives — aucun accès au pipeline ni à la bibliothèque réelle."""

from __future__ import annotations

ALBUMS = [
    {
        "artist": "Queen",
        "title": "Greatest Hits",
        "year": 1992,
        "tracks": 17,
        "missing": False,
        "color": "#5C1A2E",
    },
    {
        "artist": "Daft Punk",
        "title": "Random Access Memories",
        "year": 2013,
        "tracks": 13,
        "missing": False,
        "color": "#1A3A5C",
    },
    {
        "artist": "Norah Jones",
        "title": "Come Away With Me",
        "year": 2002,
        "tracks": 14,
        "missing": True,
        "color": "#3D4A2A",
    },
]

JOBS = [
    {
        "when": "Aujourd’hui · 14:32",
        "title": "Queen — Greatest Hits",
        "state": "Terminé",
        "kind": "ok",
        "detail": "17 pistes publiées dans la bibliothèque.",
    },
    {
        "when": "Hier · 19:05",
        "title": "Extraction interrompue",
        "state": "Fichiers récupérables",
        "kind": "warn",
        "detail": "L’extraction s’est arrêtée. Des fichiers restent dans le dossier temporaire.",
    },
    {
        "when": "Lun. · 10:12",
        "title": "Identification hors ligne",
        "state": "Échec",
        "kind": "err",
        "detail": "Le réseau était indisponible. Vous pouvez réessayer ou saisir la fiche à la main.",
    },
]

ARCHIVE_STEPS = [
    "Disque",
    "Identification",
    "Approbation",
    "Extraction",
    "Terminé",
]

PIPELINE = [
    "Vérification du disque",
    "Extraction audio",
    "Contrôle des fichiers",
    "Mise en tags et pochette",
    "Organisation",
    "Publication",
]

TRACKS_DEMO = [
    (1, "We Will Rock You"),
    (2, "We Are the Champions"),
    (3, "Another One Bites the Dust"),
    (4, "Killer Queen"),
]
