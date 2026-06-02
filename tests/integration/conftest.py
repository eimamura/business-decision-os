from __future__ import annotations

import pytest


@pytest.fixture(scope="session")
def vcr_config() -> dict:  # type: ignore[type-arg]
    return {
        "cassette_library_dir": "tests/cassettes",
        "record_mode": "none",
        "match_on": ["uri", "method", "body"],
        "filter_headers": ["Authorization", "x-api-key"],
    }
