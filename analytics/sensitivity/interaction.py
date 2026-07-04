"""Two-factor sensitivity interaction grid (#739).

Evaluates a KPI metric over the cross-product of two driver sweeps (low/base/high
each, via the same ``ParameterRangeConfig`` contract the one-way tornado uses) and
quantifies the INTERACTION between the drivers: the deviation of each joint cell
from the additive combination of the two one-way effects,

    interaction(a, b) = [m(a, b) - m(base)] - [m(a, base_b) - m(base)]
                                            - [m(base_a, b) - m(base)]

so a grid whose drivers act independently has an all-zero interaction surface,
and any structurally coupled pair (e.g. tariff x FX depreciation through the
LKR revenue line) surfaces with a non-zero corner. One-way tornadoes cannot
show this; the lender-facing gap is issue #739 (benchmarking report §5a).

Contract (CCCDIR): the result type ``TwoFactorInteractionGrid`` lives in
``analytics.contracts_v14``; evaluation goes ONLY through the
``evaluation_v14.evaluate_with_overrides`` gateway (ARCH-04).

Cost note: a grid is ``len(cases_a) x len(cases_b)`` full-pipeline evaluations
plus one true-base evaluation (10 for the default 3x3). This module is an
ANALYSIS primitive: do not wire it unconditionally into the synchronous report
route (see the #645 latency ledger entry); report wiring is a separate, gated
slice.

Assumptions and limitations:
    - Sweep points come from the declared contract (low/base/high); the grid
      resolution is deliberately coarse. It detects interaction presence and
      direction, not a full response surface.
    - The declared ``base_value`` of each parameter is trusted to equal the
      config's live value (same convention as the one-way engine); the true
      base cell is nevertheless evaluated with NO overrides so a mis-declared
      base surfaces as ``base_mismatch`` metadata instead of silently skewing
      the read.
"""

from __future__ import annotations

import copy
import logging
import math
from typing import Any, Dict, List, Mapping, Tuple

from analytics.contracts_v14 import ParameterRangeConfig, TwoFactorInteractionGrid
from analytics.evaluation_v14 import evaluate_with_overrides
from analytics.sensitivity.adapters import iter_param_cases_from_contract

# Intra-package shared internals (analytics.sensitivity.*): the one-way engine's
# resolve-guard, KPI coercion/extraction, and default run config are deliberately
# reused so the two sweep surfaces can never drift apart on validation or metric
# semantics.
from analytics.sensitivity.engine import (
    _DEFAULT_SENSITIVITY_RUN_CONFIG,
    SensitivityRunConfig,
    _coerce_kpis,
    _extract_scalar_metric,
    _resolves_in_config,
)

logger = logging.getLogger(__name__)

# Relative tolerance for the declared-base vs evaluated-base consistency check.
_BASE_MISMATCH_RTOL = 1e-6


def _validate_parameter(
    base_cfg: Mapping[str, Any],
    parameter: ParameterRangeConfig,
    run_cfg: SensitivityRunConfig,
) -> bool:
    """Fail loud (strict) when a driver does not resolve to an existing config path.

    Mirrors the one-way engine's audit-R1 guard: an override on a non-existent
    key creates a new, unused node and the whole sweep goes silently flat.
    Returns True when the driver resolves; in non-strict mode an unresolvable
    driver returns False (after warning) so the caller can DISCLOSE the flat
    axis in result metadata instead of leaving the grid silently degenerate.
    """
    if _resolves_in_config(base_cfg, parameter.variable_name):
        return True
    message = (
        f"interaction parameter '{parameter.variable_name}' does not resolve to an "
        "existing config path; its sweep would be a silent flat axis. Use a valid "
        "dotted path (e.g. project.capacity_factor, capex.usd_total, tariff.lkr_per_kwh)."
    )
    if run_cfg.strict:
        raise ValueError(message)
    logger.warning(message)
    return False


def build_two_factor_interaction_grid(
    *,
    base_config: Mapping[str, Any],
    base_config_path: str = "<in-memory>",
    param_a: ParameterRangeConfig,
    param_b: ParameterRangeConfig,
    metric_key: str,
    run_cfg: SensitivityRunConfig = _DEFAULT_SENSITIVITY_RUN_CONFIG,
) -> TwoFactorInteractionGrid:
    """Build the two-factor interaction grid for ``param_a`` x ``param_b``.

    Args:
        base_config: Full scenario config mapping (kept immutable; deep-copied).
        base_config_path: Provenance label carried into the result metadata.
        param_a: First driver (grid rows), one-way sweep contract.
        param_b: Second driver (grid columns), one-way sweep contract.
        metric_key: KPI key to extract from each evaluation (e.g. ``project_irr``).
        run_cfg: Engine knobs; ``strict`` gates the resolve-validation fail-loud.

    Returns:
        ``TwoFactorInteractionGrid`` with the raw metric surface, the
        interaction surface (deviation from one-way additivity), and
        disclosure metadata.

    Raises:
        ValueError: strict mode and a driver path does not resolve; both
            drivers target the same config key (a "grid" over one key is a
            mislabelled one-way sweep and must not render as an interaction);
            or the metric EVALUATES to NaN on the base or a marginal (edge)
            cell — a NaN value is the same failure as a missing key (FIN-01)
            and must not slide through the disclosure machinery.
        KeyError: the metric is missing on the BASE or a MARGINAL (edge) cell —
            without those every interaction term is undefined, so the failure
            is loud (FIN-01). Interior joint cells that fail (missing, non-
            numeric, OR NaN-valued) are recorded as NaN and disclosed via
            ``metadata['n_failed_cells']``, never silently substituted.
        TypeError: the metric is present but non-numeric (same edge/interior
            split as ``KeyError``).

    Note:
        A metric whose UPSTREAM producer silently substitutes a default on
        failure (e.g. ``equity_irr`` defaulting to 0.0 when the equity
        distribution is not computed, the #769 family) is indistinguishable
        from a real value here — the same caveat as the one-way tornado.
        Prefer metrics whose failure surfaces as absence or NaN.
    """
    base_cfg = copy.deepcopy(dict(base_config))

    unresolved: List[str] = []
    for parameter in (param_a, param_b):
        if not _validate_parameter(base_cfg, parameter, run_cfg):
            unresolved.append(parameter.variable_name)
    if param_a.variable_name == param_b.variable_name:
        raise ValueError(
            f"interaction grid needs two DISTINCT drivers; both are "
            f"'{param_a.variable_name}'"
        )

    cases_a: List[Tuple[str, Dict[str, Any]]] = iter_param_cases_from_contract(param_a)
    cases_b: List[Tuple[str, Dict[str, Any]]] = iter_param_cases_from_contract(param_b)
    # The additivity decomposition below indexes the base marginals at [0]; pin
    # the adapter's (base, low, high) emission order rather than assuming it.
    if not cases_a[0][0].endswith("=base") or not cases_b[0][0].endswith("=base"):
        raise RuntimeError(
            "iter_param_cases_from_contract no longer emits the base case first; "
            "the interaction decomposition depends on that order"
        )

    # True base: NO overrides (the one-way engine's convention), so a declared
    # base_value that drifted from the config surfaces as metadata, not skew.
    base_out = evaluate_with_overrides(
        config_path=None, raw_config=base_cfg, overrides={}
    )
    base_metric = _extract_scalar_metric(_coerce_kpis(base_out), metric_key)
    if not math.isfinite(base_metric):
        # A non-finite VALUE (NaN or inf) is the same failure as a missing key:
        # without a loud stop here it would flow through every delta below and
        # produce an all-NaN surface (NaN via NaN-propagation, inf via inf-inf)
        # that reads as "no interaction, nothing failed" (FIN-01).
        raise ValueError(
            f"metric '{metric_key}' evaluated to non-finite {base_metric!r} on the "
            "base case; the whole interaction surface would be undefined — fix "
            "the metric or scenario"
        )

    values: List[List[float]] = []
    n_failed = 0
    for ia, (label_a, ov_a) in enumerate(cases_a):
        row: List[float] = []
        for ib, (label_b, ov_b) in enumerate(cases_b):
            overrides = {**ov_a, **ov_b}
            is_edge = ia == 0 or ib == 0  # base row/column = the marginals
            try:
                out = evaluate_with_overrides(
                    config_path=None, raw_config=base_cfg, overrides=overrides
                )
                val = _extract_scalar_metric(_coerce_kpis(out), metric_key)
            except (KeyError, TypeError):
                if is_edge:
                    # Base/marginal failure makes every interaction term
                    # undefined -> the whole grid is meaningless: fail loud.
                    raise
                val = float("nan")
            # A metric that EVALUATES to a non-finite value (NaN or inf) is
            # treated identically to a missing one: it would otherwise bypass
            # the disclosure machinery (NaN slides through the except-arm
            # untouched and the isnan headline filter would hide it; an inf
            # base turns the whole surface into quiet inf-inf NaNs).
            if not math.isfinite(val):
                if is_edge:
                    raise ValueError(
                        f"metric '{metric_key}' failed to evaluate (non-finite/"
                        f"missing) on marginal cell ({label_a}, {label_b}); every "
                        "interaction term depends on the marginals — fail loud "
                        "(FIN-01)"
                    )
                logger.warning(
                    "interaction cell (%s, %s) failed to evaluate '%s'; "
                    "recorded as NaN and disclosed in metadata",
                    label_a,
                    label_b,
                    metric_key,
                )
                val = float("nan")  # uniform failure representation (inf -> NaN)
                n_failed += 1
            row.append(val)
        values.append(row)

    declared_base_cell = values[0][0]
    base_mismatch = not math.isclose(
        declared_base_cell, base_metric, rel_tol=_BASE_MISMATCH_RTOL, abs_tol=0.0
    )
    if base_mismatch:
        logger.warning(
            "interaction grid declared-base cell (%.10g) != evaluated base (%.10g) "
            "for metric '%s' — a driver's declared base_value drifted from the "
            "config; deltas below use the DECLARED-base cell for internal "
            "consistency, and the mismatch is disclosed in metadata",
            declared_base_cell,
            base_metric,
            metric_key,
        )

    # Interaction surface vs the declared-base grid frame: all three terms come
    # from the SAME evaluated grid, so a base_value drift cancels within the
    # decomposition rather than contaminating every cell.
    interaction: List[List[float]] = []
    max_abs_interaction = 0.0
    for ia in range(len(cases_a)):
        irow: List[float] = []
        for ib in range(len(cases_b)):
            joint = values[ia][ib] - declared_base_cell
            eff_a = values[ia][0] - declared_base_cell
            eff_b = values[0][ib] - declared_base_cell
            term = joint - eff_a - eff_b
            irow.append(term)
            if not math.isnan(term):
                max_abs_interaction = max(max_abs_interaction, abs(term))
        interaction.append(irow)

    return TwoFactorInteractionGrid(
        metric_name=metric_key,
        param_a_name=param_a.variable_name,
        param_b_name=param_b.variable_name,
        a_labels=[label for label, _ in cases_a],
        b_labels=[label for label, _ in cases_b],
        values=values,
        interaction=interaction,
        base_metric=base_metric,
        max_abs_interaction=max_abs_interaction,
        metadata={
            "base_config_path": base_config_path,
            "n_evaluations": 1 + len(cases_a) * len(cases_b),
            "n_failed_cells": n_failed,
            "base_mismatch": base_mismatch,
            "declared_base_cell": declared_base_cell,
            # Non-strict mode only: drivers that did not resolve (their axis is
            # structurally flat). Empty under strict (unresolvable raises).
            "unresolved_drivers": unresolved,
            "param_a_label": param_a.label or param_a.variable_name,
            "param_b_label": param_b.label or param_b.variable_name,
        },
    )
