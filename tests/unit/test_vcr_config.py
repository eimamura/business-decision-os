"""Unit tests for the vcrpy cassette configuration fixture (T-040)."""
from __future__ import annotations

import importlib.util
import pathlib
import types


def _load_vcr_config_dict() -> dict:  # type: ignore[type-arg]
    """Load and call the vcr_config function from integration/conftest.py.

    The fixture decorator wraps the function, but we can reach the underlying
    callable via __wrapped__ (added by functools.wraps in pytest's fixture impl)
    or by inspecting the FixtureFunctionMarker.
    """
    spec = importlib.util.spec_from_file_location(
        "integration_conftest",
        pathlib.Path(__file__).parents[1] / "integration" / "conftest.py",
    )
    assert spec is not None
    module = types.ModuleType("integration_conftest")
    assert spec.loader is not None
    spec.loader.exec_module(module)  # type: ignore[attr-defined]

    fn = module.vcr_config  # type: ignore[attr-defined]
    # Unwrap the pytest fixture decorator to get the raw callable.
    raw = getattr(fn, "__wrapped__", None) or getattr(fn, "_pytestfixturefunction", None)
    if raw is None:
        # pytest stores the original function; fall back to calling via _pytestfixturefunction
        # attribute lookup path or direct call when not wrapped.
        try:
            return fn()  # type: ignore[no-any-return]
        except Exception:
            pass
    # Try __wrapped__ (pytest uses functools.wraps for some versions)
    callable_fn = getattr(fn, "__wrapped__", fn)
    return callable_fn()  # type: ignore[no-any-return]


def test_vcr_config_cassette_library_dir() -> None:
    """vcr_config must set cassette_library_dir to 'tests/cassettes'."""
    # Import the raw function body directly without pytest fixture machinery.
    # We verify correctness by calling the underlying logic, not the wrapped fixture.
    expected_dir = "tests/cassettes"

    # Parse expected output by examining the source rather than calling the fixture.
    # The fixture is a pure function returning a literal dict — read it directly.
    spec = importlib.util.spec_from_file_location(
        "integration_conftest_t040a",
        pathlib.Path(__file__).parents[1] / "integration" / "conftest.py",
    )
    assert spec is not None
    module = types.ModuleType("integration_conftest_t040a")
    assert spec.loader is not None

    # Temporarily replace the pytest.fixture decorator with identity so we can
    # call vcr_config() as a plain function.
    import pytest as _pytest

    original_fixture = _pytest.fixture

    def _identity_fixture(*args, **kwargs):  # type: ignore[no-untyped-def]
        """Return the function unchanged — no fixture wrapping."""
        if len(args) == 1 and callable(args[0]):
            return args[0]

        def decorator(fn):  # type: ignore[no-untyped-def]
            return fn

        return decorator

    import sys

    # Temporarily patch pytest.fixture in the module's import context.
    real_pytest = sys.modules.get("pytest")
    assert real_pytest is not None
    original = real_pytest.fixture
    real_pytest.fixture = _identity_fixture  # type: ignore[attr-defined]
    try:
        spec.loader.exec_module(module)  # type: ignore[attr-defined]
        config: dict = module.vcr_config()  # type: ignore[attr-defined]
    finally:
        real_pytest.fixture = original  # type: ignore[attr-defined]

    assert config["cassette_library_dir"] == expected_dir


def test_vcr_config_filters_authorization_header() -> None:
    """vcr_config must include 'Authorization' in filter_headers."""
    spec = importlib.util.spec_from_file_location(
        "integration_conftest_t040b",
        pathlib.Path(__file__).parents[1] / "integration" / "conftest.py",
    )
    assert spec is not None
    module = types.ModuleType("integration_conftest_t040b")
    assert spec.loader is not None

    import sys

    real_pytest = sys.modules.get("pytest")
    assert real_pytest is not None
    original = real_pytest.fixture

    def _identity_fixture(*args, **kwargs):  # type: ignore[no-untyped-def]
        if len(args) == 1 and callable(args[0]):
            return args[0]

        def decorator(fn):  # type: ignore[no-untyped-def]
            return fn

        return decorator

    real_pytest.fixture = _identity_fixture  # type: ignore[attr-defined]
    try:
        spec.loader.exec_module(module)  # type: ignore[attr-defined]
        config: dict = module.vcr_config()  # type: ignore[attr-defined]
    finally:
        real_pytest.fixture = original  # type: ignore[attr-defined]

    assert "Authorization" in config["filter_headers"]
