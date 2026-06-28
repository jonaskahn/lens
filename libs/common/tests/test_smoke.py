"""Smoke tests for the bootstrap skeleton.

These tests exist purely so `make test` runs successfully on the bootstrap
skeleton. They will be replaced by real unit tests as more code lands.
"""

from __future__ import annotations


def test_given_skeleton_when_importing_common_then_version_is_set() -> None:
    from lens_common import __version__

    assert __version__ == "0.1.0"


def test_given_skeleton_when_importing_domain_then_version_is_set() -> None:
    from lens_domain import __version__

    assert __version__ == "0.1.0"


def test_given_skeleton_when_importing_application_then_version_is_set() -> None:
    from lens_application import __version__

    assert __version__ == "0.1.0"
