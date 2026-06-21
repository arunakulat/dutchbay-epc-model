"""VaR/CVaR of the FX deficit distribution must use the upper (loss) tail.

``scripts/analysis/fx_correlation_module`` is a standalone script (the directory
is not a package), so load it by path. Regression for the wrong-tail bug where
VaR_95 was taken as the ~5th percentile (a near-minimum loss), understating risk.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import numpy as np
import pytest

_MOD_PATH = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "analysis"
    / "fx_correlation_module.py"
)


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("fx_correlation_module", _MOD_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_var_cvar_use_upper_loss_tail() -> None:
    mod = _load_module()
    losses = np.arange(0.0, 1000.0)  # 0..999, mean ~499.5
    var, cvar = mod._var_cvar_from_losses(losses, 0.95)
    # VaR_95 is a tail loss == the 95th percentile (the explicit guard: VaR >= mean).
    assert var == pytest.approx(float(np.percentile(losses, 95.0)))
    assert var >= float(losses.mean())
    # CVaR (expected shortfall in the worst 5%) is at or beyond VaR.
    assert cvar >= var
    assert cvar == pytest.approx(float(losses[losses >= var].mean()))


def test_var_cvar_empty_distribution() -> None:
    mod = _load_module()
    assert mod._var_cvar_from_losses(np.array([], dtype=float), 0.95) == (0.0, 0.0)
