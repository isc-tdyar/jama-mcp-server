"""Integration test fixtures - disable autouse fixtures from root conftest."""
import pytest


@pytest.fixture(autouse=True)
def reset_environment_for_tests():
    """Override the autouse fixture from root conftest to do nothing.

    Integration tests need to use real environment variables,
    not the mock values set by the root conftest fixture.
    """
    pass  # Do nothing - let real env vars through
