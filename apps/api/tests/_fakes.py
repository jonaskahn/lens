"""In-memory UoW fakes for the API tests.

We import from the application tests directory via ``importlib.util`` so
the public ``lens_application`` package surface stays minimal.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_FAKES_SRC = Path(__file__).resolve().parent.parent.parent.parent / "libs" / "application" / "tests" / "_fakes.py"
_SPEC = importlib.util.spec_from_file_location("tests._fakes", _FAKES_SRC)
assert _SPEC is not None
assert _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
sys.modules["tests._fakes"] = _MODULE
_SPEC.loader.exec_module(_MODULE)

InMemoryUnitOfWork = _MODULE.InMemoryUnitOfWork
reset_in_memory_store = _MODULE.reset_in_memory_store
InMemoryStore = _MODULE.InMemoryStore

__all__ = ["InMemoryStore", "InMemoryUnitOfWork", "reset_in_memory_store"]
