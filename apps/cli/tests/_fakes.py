"""In-memory UoW fakes for the CLI tests.

We import from the application tests directory via ``importlib.util`` so
the public ``lens_application`` package surface stays minimal. The module
is registered under a unique name to avoid collisions with sibling
``tests/`` packages.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_FAKES_SRC = Path(__file__).resolve().parent.parent.parent.parent / "libs" / "application" / "tests" / "_fakes.py"
_SPEC = importlib.util.spec_from_file_location("_cli_fakes", _FAKES_SRC)
assert _SPEC is not None
assert _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
sys.modules["_cli_fakes"] = _MODULE
_SPEC.loader.exec_module(_MODULE)

InMemoryUnitOfWork = _MODULE.InMemoryUnitOfWork
reset_in_memory_store = _MODULE.reset_in_memory_store

__all__ = ["InMemoryUnitOfWork", "reset_in_memory_store"]
