from __future__ import annotations

from unittest.mock import patch

import musicbrainzngs
import pytest

from audio_video_manager import __version__
from audio_video_manager.metadata.musicbrainz_client import (
    MusicBrainzError,
    configure_musicbrainz,
    lookup_releases_by_discid,
)
from audio_video_manager.metadata.musicbrainz_identity import (
    APPLICATION_NAME,
    DEFAULT_CONTACT,
    MusicBrainzIdentityError,
    resolve_musicbrainz_identity,
)


def test_default_identity_uses_project_name_version_and_authorized_contact() -> None:
    identity = resolve_musicbrainz_identity({})
    assert identity.as_tuple() == (
        "AudioVideoManager",
        __version__,
        "mailto:johan_dominguez@hotmail.com",
    )
    assert identity.application == APPLICATION_NAME
    assert identity.contact == DEFAULT_CONTACT


@pytest.mark.parametrize(
    "contact",
    [
        "mailto:developer@example.org",
        "https://example.org/contact",
    ],
)
def test_valid_environment_override(contact: str) -> None:
    identity = resolve_musicbrainz_identity({"AVM_MUSICBRAINZ_CONTACT": contact})
    assert identity.contact == contact
    assert identity.version == __version__


@pytest.mark.parametrize(
    "contact",
    [
        "",
        "not-an-address",
        "ftp://example.org/contact",
        "https://",
        "https://user:password@example.org/contact",
        "mailto:johan@@example.com",
        "mailto:johan@example",
        "mailto:johan..dominguez@example.com",
        "mailto:johan@example.com?subject=private",
    ],
)
def test_invalid_environment_override_is_rejected(contact: str) -> None:
    with pytest.raises(MusicBrainzIdentityError):
        resolve_musicbrainz_identity({"AVM_MUSICBRAINZ_CONTACT": contact})


def test_configure_musicbrainz_passes_complete_default_user_agent(monkeypatch) -> None:
    monkeypatch.delenv("AVM_MUSICBRAINZ_CONTACT", raising=False)
    captured: list[tuple[str, str, str]] = []
    configure_musicbrainz(set_useragent_fn=lambda *args: captured.append(args))
    assert captured == [
        ("AudioVideoManager", __version__, "mailto:johan_dominguez@hotmail.com")
    ]


def test_lookup_configures_user_agent_before_api_call(monkeypatch) -> None:
    monkeypatch.setenv("AVM_MUSICBRAINZ_CONTACT", "mailto:avm-contact@example.org")
    calls: list[tuple[str, tuple[str, ...]]] = []

    def set_user_agent(*args) -> None:
        calls.append(("user-agent", args))

    def get_releases(*_args, **_kwargs):
        calls.append(("lookup", ()))
        return {"disc": {"release-list": []}}

    with (
        patch("musicbrainzngs.set_useragent", set_user_agent),
        patch(
            "audio_video_manager.metadata.musicbrainz_client._rate_limit",
            lambda: None,
        ),
    ):
        result = lookup_releases_by_discid(
            "test-disc-id",
            get_releases_fn=get_releases,
        )

    assert result.candidates == []
    assert calls == [
        ("user-agent", ("AudioVideoManager", __version__, "mailto:avm-contact@example.org")),
        ("lookup", ()),
    ]


def test_invalid_contact_fails_before_network_lookup(monkeypatch) -> None:
    monkeypatch.setenv("AVM_MUSICBRAINZ_CONTACT", "not a contact")
    network_calls: list[object] = []
    with pytest.raises(MusicBrainzError, match="Contact MusicBrainz"):
        lookup_releases_by_discid(
            "test-disc-id",
            get_releases_fn=lambda *_args, **_kwargs: network_calls.append(True),
        )
    assert network_calls == []
