"""Validated MusicBrainz client identity, shared by every lookup."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Mapping
from urllib.parse import urlsplit

from audio_video_manager import __version__

APPLICATION_NAME = "AudioVideoManager"
DEFAULT_CONTACT = "mailto:johan_dominguez@hotmail.com"
CONTACT_ENVIRONMENT_VARIABLE = "AVM_MUSICBRAINZ_CONTACT"
_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")
_LOCAL_RE = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+$")
_DOMAIN_LABEL_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")


class MusicBrainzIdentityError(ValueError):
    """The application cannot construct a valid MusicBrainz User-Agent."""


@dataclass(frozen=True)
class MusicBrainzIdentity:
    application: str
    version: str
    contact: str

    def as_tuple(self) -> tuple[str, str, str]:
        return self.application, self.version, self.contact


def _validate_contact(contact: str) -> str:
    value = contact.strip()
    if not value or any(char.isspace() or ord(char) < 32 for char in value):
        raise MusicBrainzIdentityError("Contact MusicBrainz vide ou contenant des espaces.")

    parsed = urlsplit(value)
    if parsed.scheme == "mailto":
        address = parsed.path
        if (
            parsed.netloc
            or parsed.query
            or parsed.fragment
            or address.count("@") != 1
            or len(address) > 254
        ):
            raise MusicBrainzIdentityError("Contact mailto invalide.")
        local, domain = address.rsplit("@", 1)
        labels = domain.split(".")
        if (
            not local
            or len(local) > 64
            or local.startswith(".")
            or local.endswith(".")
            or ".." in local
            or not _LOCAL_RE.fullmatch(local)
            or len(labels) < 2
            or any(not _DOMAIN_LABEL_RE.fullmatch(label) for label in labels)
        ):
            raise MusicBrainzIdentityError("Contact mailto invalide.")
        return value

    if parsed.scheme == "https":
        try:
            _ = parsed.port
        except ValueError as exc:
            raise MusicBrainzIdentityError("Port invalide dans le contact HTTPS.") from exc
        if (
            not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or not parsed.hostname or "." not in parsed.hostname
            or parsed.query
            or parsed.fragment
        ):
            raise MusicBrainzIdentityError("Contact HTTPS invalide.")
        return value

    raise MusicBrainzIdentityError("Le contact doit utiliser HTTPS ou mailto.")


def build_musicbrainz_identity(
    *,
    application: str = APPLICATION_NAME,
    version: str = __version__,
    contact: str,
) -> MusicBrainzIdentity:
    """Validate an explicit identity tuple before passing it to musicbrainzngs."""
    app = application.strip()
    ver = version.strip()
    if not app or any(char.isspace() for char in app):
        raise MusicBrainzIdentityError("Nom d'application invalide pour MusicBrainz.")
    if not _VERSION_RE.fullmatch(ver):
        raise MusicBrainzIdentityError("Version d'application MusicBrainz invalide.")
    return MusicBrainzIdentity(app, ver, _validate_contact(contact))


def resolve_musicbrainz_identity(
    env: Mapping[str, str] | None = None,
) -> MusicBrainzIdentity:
    """Resolve the project identity; only an explicit env override replaces the default."""
    values = os.environ if env is None else env
    contact = (
        values[CONTACT_ENVIRONMENT_VARIABLE]
        if CONTACT_ENVIRONMENT_VARIABLE in values
        else DEFAULT_CONTACT
    )
    return build_musicbrainz_identity(contact=contact)