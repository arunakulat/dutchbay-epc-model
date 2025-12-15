#!/usr/bin/env python3
"""Sensitivity utilities for Dutch Bay model."""

from __future__ import annotations

from dataclasses import replace
from typing import Iterable

import pandas as pd

from .core import ModelConfig, calculate_equity_irr


def one_way_sensitivity(
    cfg: ModelConfig,
    param: str,
    values: Iterable[float],
) -> pd.DataFrame:
    """Vary `param` over `values` and report equity IRR."""
    rows = []
    for v in values:
        cfg_mod = replace(cfg, **{param: v})
        irr = calculate_equity_irr(cfg_mod)
        rows.append({param: v, "equity_irr": irr})
    return pd.DataFrame(rows)
