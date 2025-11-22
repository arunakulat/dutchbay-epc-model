from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

import pandas as pd

ValidatorFn = Callable[[Any], bool]
PathSpec = Tuple[str, ...]


@dataclass(frozen=True)
class RequiredFieldSpec:
    """
    Canonical description of a config field needed by a module.

    Attributes
    ----------
    module:
        Logical owner (e.g. "cashflow", "debt", "irr", "monte_carlo").
    name:
        Logical key ("corporate_tax_rate", "project_life_years", ...).
    paths:
        Candidate YAML paths we will try in order. Each path is a tuple
        of keys, e.g. ("tax", "corporate_tax_rate_pct").
    required:
        True = must be present/valid for this pipeline mode.
    severity:
        "error" or "warning" (warnings may be surfaced but not block).
    description:
        Human-friendly explanation used in error messages / schema dumps.
    validator:
        Optional predicate that returns True when the resolved value is
        considered valid.
    """

    module: str
    name: str
    paths: Sequence[PathSpec]
    required: bool = True
    severity: str = "error"
    description: str = ""
    validator: Optional[ValidatorFn] = field(default=None)


# Global registry keyed by module name
_REGISTRY: Dict[str, List[RequiredFieldSpec]] = {}


def register_required_fields(
    module: str,
    specs: Iterable[RequiredFieldSpec],
) -> None:
    """
    Register one or more RequiredFieldSpec objects for a module.

    Intended usage is at module import time, e.g.:

        _CASHFLOW_SPECS = [
            RequiredFieldSpec(...),
            ...
        ]
        register_required_fields("cashflow", _CASHFLOW_SPECS)
    """
    if module not in _REGISTRY:
        _REGISTRY[module] = []
    _REGISTRY[module].extend(specs)


def get_required_fields(module: Optional[str] = None) -> List[RequiredFieldSpec]:
    """
    Return all registered specs, optionally filtered by module.

    Parameters
    ----------
    module:
        If provided, limit results to this logical module name
        (e.g. "cashflow"). If None, return specs from all modules.
    """
    if module is None:
        out: List[RequiredFieldSpec] = []
        for specs in _REGISTRY.values():
            out.extend(specs)
        return out
    return list(_REGISTRY.get(module, []))


def build_schema_dataframe() -> pd.DataFrame:
    """
    Flatten the registry into a DataFrame for inspection/debugging.

    Columns:
      - module
      - name
      - path_candidates (list[str])
      - required
      - severity
      - description

    This is primarily for developer use (e.g. exporting the current
    expected schema to Excel for lenders or internal IC review).
    """
    rows: List[Dict[str, Any]] = []

    for spec in get_required_fields():
        rows.append(
            {
                "module": spec.module,
                "name": spec.name,
                "path_candidates": [".".join(p) for p in spec.paths],
                "required": spec.required,
                "severity": spec.severity,
                "description": spec.description,
            }
        )

    if not rows:
        return pd.DataFrame(
            columns=[
                "module",
                "name",
                "path_candidates",
                "required",
                "severity",
                "description",
            ]
        )

    df = pd.DataFrame(rows)
    df = df.sort_values(["module", "name"]).reset_index(drop=True)
    return df


__all__ = [
    "RequiredFieldSpec",
    "register_required_fields",
    "get_required_fields",
    "build_schema_dataframe",
    "ValidatorFn",
    "PathSpec",
]
