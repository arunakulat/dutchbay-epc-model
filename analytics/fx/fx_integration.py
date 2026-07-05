"""FX Integration into Pipeline (v14R6).

Provides the main entry point for integrating FX blocks into ScenarioResult
during pipeline_v14 execution.

IMPORTANT: Uses TYPE_CHECKING to avoid circular import with contracts_v14.
  - Type hints use real ScenarioResult type (mypy/IDE happy)
  - Runtime uses Any alias (breaks import cycle)

Standards:
  - GWTF: Full type hints, clear module docstring
  - CASPER: Lender-grade result aggregation
  - CESSPIT: Fail-fast validation, clear error messages
  - CCCDIR: Fully commented, no shortcuts

Usage:
  from analytics.fx.fx_integration import integrate_fx_into_scenario_result

  scenario_result = integrate_fx_into_scenario_result(
      scenario_result=result,
      config=config,
      debt_result=debt_output,
      annual_rows=cf_rows,
  )
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, List, Mapping, Optional, Sequence

# TYPE_CHECKING: Import ScenarioResult for type hints only (breaks circular import)
if TYPE_CHECKING:
    from analytics.contracts_v14 import ScenarioResult
else:
    # Runtime: Use Any to avoid importing contracts_v14 at module load time
    ScenarioResult = Any  # type: ignore[misc,assignment]

from analytics.fx.fx_builder import (
    compute_fx_curve,
    compute_fx_risk_profile,
    compute_fx_structured_block,
)


def integrate_fx_into_scenario_result(
    *,
    scenario_result: ScenarioResult,
    config: Mapping[str, Any],
    debt_result: Mapping[str, Any],
    annual_rows: Sequence[Mapping[str, Any]],
    degraded_out: Optional[List[str]] = None,
) -> ScenarioResult:
    """
    Wire FX blocks into an existing ScenarioResult.

    This function is called from analytics.pipeline_v14_enhanced.run_v14_pipeline
    (the live pipeline) after the ScenarioResult is assembled. It:
    1. Computes FX structured block from config and debt output
    2. Generates FX curve (time-series rates)
    3. Calculates FX risk profile (VaR, CVaR, concentration)
    4. Returns new ScenarioResult with FX fields populated

    Args:
        scenario_result: Base ScenarioResult (with NPV, IRR, etc.)
        config: Project config dict (includes FX settings).
        debt_result: Output from plan_debt() module.
        annual_rows: Annual cashflow rows from compute_cashflow().
        degraded_out: Optional caller-owned collector (#785). When supplied, the
            fx builders append a human-readable reason for every SILENT fallback
            they take (malformed fx block, flat-curve substitution, degenerate
            risk profile) — the integration still succeeds; the caller decides
            how to disclose. None (default) preserves the exact legacy behaviour.

    Returns:
        New ScenarioResult with fx_block, fx_curve, fx_risk_profile populated.

    Raises:
        ValueError: If FX computation fails (invalid config or data).
        TypeError: If inputs are wrong types.

    Example:
        >>> result_with_fx = integrate_fx_into_scenario_result(
        ...     scenario_result=base_result,
        ...     config=config,
        ...     debt_result=debt_output,
        ...     annual_rows=cashflow_rows,
        ... )
        >>> print(result_with_fx.fx_block.strategy)
        'blended'
    """
    # Import ScenarioResult at runtime (inside function) to break circular dependency
    from analytics.contracts_v14 import ScenarioResult as ScenarioResultClass

    # CESSPIT: Input validation
    if not isinstance(scenario_result, ScenarioResultClass):
        raise TypeError(
            f"integrate_fx_into_scenario_result: "
            f"scenario_result must be ScenarioResult, got {type(scenario_result)}"
        )

    if not isinstance(config, Mapping):
        raise TypeError(
            f"integrate_fx_into_scenario_result: config must be Mapping, got {type(config)}"
        )

    if not isinstance(debt_result, Mapping):
        raise TypeError(
            f"integrate_fx_into_scenario_result: debt_result must be Mapping, got {type(debt_result)}"
        )

    if not isinstance(annual_rows, Sequence):
        raise TypeError(
            f"integrate_fx_into_scenario_result: annual_rows must be Sequence, got {type(annual_rows)}"
        )

    # Compute FX blocks
    try:
        fx_block = compute_fx_structured_block(
            config=config,
            debt_result=debt_result,
            annual_rows=annual_rows,
            degraded=degraded_out,
        )
        fx_curve = compute_fx_curve(
            config=config,
            annual_rows=annual_rows,
            degraded=degraded_out,
        )
        # Source the VaR shock from the scenario's declared FX volatility
        # (fx.uncertainty_pct) instead of a hardcoded 5%; default 0.05 when absent.
        fx_cfg = config.get("FX") or config.get("fx") or {}
        shock = 0.05
        if isinstance(fx_cfg, Mapping):
            raw_shock = fx_cfg.get("uncertainty_pct")
            if raw_shock is not None and float(raw_shock) > 0.0:
                shock = float(raw_shock)
            elif raw_shock is not None:
                # #785: a declared-but-non-positive fx.uncertainty_pct silently
                # replaced by the 0.05 default MOVES the reported VaR/CVaR vs
                # the declared config — disclose the substitution.
                if degraded_out is not None:
                    degraded_out.append(
                        f"fx.uncertainty_pct declared as {raw_shock!r} "
                        "(non-positive); VaR shock replaced by the 0.05 default"
                    )
        fx_risk_profile = compute_fx_risk_profile(
            fx_block=fx_block,
            fx_curve=fx_curve,
            var_shock_pct=shock,
            degraded=degraded_out,
        )
    except (ValueError, TypeError) as e:
        # CESSPIT: Clear error propagation
        raise ValueError(
            f"integrate_fx_into_scenario_result: FX computation failed: {e}"
        ) from e

    # Return new ScenarioResult with FX fields populated
    # (Use dataclass replace or manual instantiation for immutability)
    import dataclasses

    result_dict = dataclasses.asdict(scenario_result)
    result_dict["fx_block"] = fx_block
    result_dict["fx_curve"] = fx_curve
    result_dict["fx_risk_profile"] = fx_risk_profile

    return ScenarioResultClass(**result_dict)


__all__ = ["integrate_fx_into_scenario_result"]

# EOF - analytics/fx/fx_integration.py
