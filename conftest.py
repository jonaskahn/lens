"""Root conftest for pytest.

The repository has multiple ``tests/`` directories (``libs/*/tests``,
``apps/*/tests``). To avoid pytest collecting them as the same ``tests``
package, this conftest pre-loads the test helper modules so they are
available in ``sys.modules`` by the time test modules are imported.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent


def _preload(alias: str, path: Path) -> None:
    if not path.exists():
        return
    spec = importlib.util.spec_from_file_location(alias, path)
    if spec is None or spec.loader is None:
        return
    module = importlib.util.module_from_spec(spec)
    sys.modules[alias] = module
    spec.loader.exec_module(module)


_preload(
    "_api_fakes",
    _ROOT / "apps" / "api" / "tests" / "_fakes.py",
)
_preload(
    "_cli_fakes",
    _ROOT / "apps" / "cli" / "tests" / "_fakes.py",
)
_preload(
    "_lib_fakes",
    _ROOT / "libs" / "application" / "tests" / "_fakes.py",
)
_preload(
    "_fakes",
    _ROOT / "libs" / "application" / "tests" / "_fakes.py",
)
_preload(
    "_pipeline_fakes",
    _ROOT / "libs" / "application" / "tests" / "_pipeline_fakes.py",
)
