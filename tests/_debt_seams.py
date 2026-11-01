"""Patch a debt-engine seam where the engine looks it up, not on the façade.

The debt engine's code lives in the ``finance.debt`` package behind the
``finance.debt_v14`` façade. Each function there reads its collaborators from its own
module's globals, and every module inside the package imports the names it uses
(``from finance.debt.layer import apply_debt_layer``), never the module that defines
them. So a function called from several modules is looked up in each of them:

* a patch on the façade reaches no engine call (``tests/lint/test_debt_package_boundary.py``
  rule 2 fails it); and
* a patch on the module that defines the function reaches only the calls made inside that
  module. ``apply_debt_layer`` is defined in ``finance.debt.layer`` but called from
  ``sizing``, ``balloon`` and ``plan``.

:func:`wrap_everywhere` replaces a function in every engine module that binds it, under
any name, and returns where it did so. Assert that the list is non-empty, and bound the
calls your wrapper records from below, so that a wrapper that reaches nothing fails.
The boundary lint's rule 3 keeps the package's own imports in the name-binding form this
relies on.
"""

from __future__ import annotations

import importlib
import pkgutil
from types import ModuleType
from typing import Any, Callable

import pytest

import finance.debt


def engine_modules() -> list[ModuleType]:
    """``finance.debt`` itself and every module in it: the code behind the façade."""
    return [finance.debt] + [
        importlib.import_module(f"finance.debt.{info.name}")
        for info in pkgutil.iter_modules(finance.debt.__path__)
    ]


def wrap_everywhere(
    monkeypatch: pytest.MonkeyPatch,
    real: Callable[..., Any],
    wrapper: Callable[..., Any],
) -> list[str]:
    """Replace ``real`` with ``wrapper`` wherever an engine module binds it.

    A binding is found by identity over each module's globals, so a module that imported
    the function under another name is wrapped too. Returns the ``module.name`` of each
    binding replaced; an empty list means the seam is wrapped nowhere.
    """
    patched = []
    for module in engine_modules():
        for name, value in sorted(vars(module).items()):
            if value is real:
                monkeypatch.setattr(module, name, wrapper)
                patched.append(f"{module.__name__}.{name}")
    return patched
