"""Controls for ``tests/_debt_seams.py``: a wrapped seam records the engine's calls.

These pin why the helper exists (#1502 domain review, P-7 and P-8). A patch on the
module that defines a debt-engine function misses every call made from the other modules
that imported it, so a test that patches only there can pass while measuring nothing.
``wrap_everywhere`` reaches those calls, including through a binding under another name.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import finance.debt
import finance.debt.layer
import finance.debt.sizing
from analytics.evaluation_v14 import evaluate_with_overrides
from finance import debt_v14
from tests._debt_seams import engine_modules, wrap_everywhere

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER_CONFIG = str(REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml")


def _counting(calls: list[int]) -> Any:
    real = debt_v14.apply_debt_layer

    def wrapper(**kwargs: Any) -> Any:
        calls.append(1)
        return real(**kwargs)

    return wrapper


def test_engine_modules_include_the_package_itself() -> None:
    modules = engine_modules()
    assert modules[0] is finance.debt
    # The package and its 14 modules; an empty enumeration would make every use vacuous.
    assert len(modules) >= 15, [m.__name__ for m in modules]


def test_a_patch_on_the_defining_module_alone_records_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The control for P-7: the remedy the boundary lint used to give is a dead patch."""
    calls: list[int] = []
    monkeypatch.setattr(finance.debt.layer, "apply_debt_layer", _counting(calls))
    evaluate_with_overrides(LENDER_CONFIG, overrides={}, return_full_result=True)
    assert calls == []


def test_wrap_everywhere_records_the_engine_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[int] = []
    real = debt_v14.apply_debt_layer
    patched = wrap_everywhere(monkeypatch, real, _counting(calls))
    assert f"{real.__module__}.{real.__name__}" in patched
    assert len(patched) >= 2, patched
    evaluate_with_overrides(LENDER_CONFIG, overrides={}, return_full_result=True)
    assert len(calls) > 100


def test_wrap_everywhere_finds_a_binding_under_another_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The control for P-8(e): an alias is found by identity, not by name."""
    real = debt_v14.apply_debt_layer
    monkeypatch.setattr(finance.debt.sizing, "_aliased_layer", real, raising=False)

    def wrapper(**kwargs: Any) -> Any:
        return real(**kwargs)

    patched = wrap_everywhere(monkeypatch, real, wrapper)
    assert "finance.debt.sizing._aliased_layer" in patched
    assert finance.debt.sizing._aliased_layer is wrapper  # type: ignore[attr-defined]
    assert finance.debt.sizing.apply_debt_layer is wrapper
