from __future__ import annotations

from tests.integration.conftest import VCR_CONFIG


def test_vcr_cassette_library_dir() -> None:
    assert VCR_CONFIG["cassette_library_dir"] == "tests/cassettes"


def test_vcr_filters_authorization_header() -> None:
    assert "Authorization" in VCR_CONFIG["filter_headers"]
