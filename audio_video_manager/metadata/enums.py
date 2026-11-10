"""Énumérations DiscMetadata."""

from __future__ import annotations

from enum import Enum


class FieldTrust(str, Enum):
    CONFIRMED = "confirmed"
    AMBIGUOUS = "ambiguous"
    MISSING = "missing"
    UNAVAILABLE = "unavailable"


class MetadataProvenance(str, Enum):
    """Origine d'une valeur — pas d'invention silencieuse."""

    MANUAL = "manual"
    TOC = "toc"
    USER_CORRECTION = "user_correction"
    # Réservés (non utilisés tant que MB non branché) :
    MUSICBRAINZ = "musicbrainz"
    COVER_ART_ARCHIVE = "cover_art_archive"
    DISCOGS = "discogs"
    FREAC_CDDB = "freac_cddb"


class ApprovalState(str, Enum):
    PENDING = "Pending"
    APPROVED = "Approved"
    REJECTED = "Rejected"


class JobMode(str, Enum):
    NORMAL = "normal"
    TECHNICAL_TEST = "technical_test"


class MediumFormat(str, Enum):
    AUDIO_CD = "audio_cd"
    DVD_VIDEO = "dvd_video"
    DVD_AUDIO = "dvd_audio"


class CoverStatus(str, Enum):
    CONFIRMED = "confirmed"
    UNAVAILABLE = "unavailable"
    MISSING = "missing"
    AMBIGUOUS = "ambiguous"
