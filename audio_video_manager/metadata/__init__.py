"""Métadonnées fiche disque + identification MusicBrainz (AVM-03/04/04C)."""

from audio_video_manager.metadata.apply_lookup import (
    apply_release_candidate,
    identify_disc,
    sheet_from_disc_read,
)
from audio_video_manager.metadata.edition_ranker import (
    DiffSeverity,
    EditionDiff,
    SelectionDecision,
    compare_editions,
    editions_musically_equivalent,
    rank_and_select_releases,
)
from audio_video_manager.metadata.enums import (
    ApprovalState,
    CoverStatus,
    FieldTrust,
    JobMode,
    MediumFormat,
    MetadataProvenance,
)
from audio_video_manager.metadata.libdiscid_loader import LibdiscidMissingError
from audio_video_manager.metadata.models import (
    DiscMetadata,
    TocSnapshot,
    TrackMetadata,
    build_sheet_from_toc,
)
from audio_video_manager.metadata.musicbrainz_client import (
    DiscLookupResult,
    MusicBrainzError,
    ReleaseCandidate,
    lookup_releases_by_discid,
)
from audio_video_manager.metadata.path_preview import build_path_preview
from audio_video_manager.metadata.repository import DiscMetadataRepository
from audio_video_manager.metadata.toc_reader import (
    DiscReadResult,
    diagnose_libdiscid,
    list_cdrom_device_letters,
    read_disc_toc,
    resolve_optical_device_for_discid,
)
from audio_video_manager.metadata.validation import (
    ApprovalError,
    apply_validation,
    approve_sheet,
    assert_can_start_archive_rip,
    validate_disc_metadata,
)

__all__ = [
    "ApprovalError",
    "ApprovalState",
    "CoverStatus",
    "DiffSeverity",
    "DiscLookupResult",
    "DiscMetadata",
    "DiscMetadataRepository",
    "DiscReadResult",
    "EditionDiff",
    "FieldTrust",
    "JobMode",
    "LibdiscidMissingError",
    "MediumFormat",
    "MetadataProvenance",
    "MusicBrainzError",
    "ReleaseCandidate",
    "SelectionDecision",
    "TocSnapshot",
    "TrackMetadata",
    "apply_release_candidate",
    "apply_validation",
    "approve_sheet",
    "assert_can_start_archive_rip",
    "build_path_preview",
    "build_sheet_from_toc",
    "compare_editions",
    "diagnose_libdiscid",
    "editions_musically_equivalent",
    "identify_disc",
    "list_cdrom_device_letters",
    "lookup_releases_by_discid",
    "rank_and_select_releases",
    "read_disc_toc",
    "resolve_optical_device_for_discid",
    "sheet_from_disc_read",
    "validate_disc_metadata",
]
