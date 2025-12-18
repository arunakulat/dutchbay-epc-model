"""FX Integration into Pipeline (v14R6).

Provides the main entry point for integrating FX blocks into ScenarioResult
during pipeline_v14 execution.

Standards:
  - GWTF: Full type hints, clear module docstring
  - CASPER: Lender-grade result aggregation
  - CESSPIT: Fail-fast validation, clear error messages
  - CCCDIR: Fully commented, no shortcuts

Usage:
  from analytics.fx_integration import integrate_fx_into_scenario_result
  
  scenario_result = integrate_fx_into_scenario_result(
      scenario_result=result,
      config=config,
      debt_result=debt_output,
      annual_rows=cf_rows,
  )
"""

from typing import Any, Mapping, Sequence

from analytics.contracts_v14 import ScenarioResult
from analytics.fx.fx_builder import (
    compute_fx_structured_block,
    compute_fx_curve,
    compute_fx_risk_profile,
)


def integrate_fx_into_scenario_result(
    *,
    scenario_result: ScenarioResult,
    config: Mapping[str, Any],
    debt_result: Mapping[str, Any],
    annual_rows: Sequence[Mapping[str, Any]],
) -> ScenarioResult:
    """
    Wire FX blocks into an existing ScenarioResult.
    
    This function is called from pipeline_v14.run_full_pipeline_v14() after
    core scenario evaluation. It:
    1. Computes FX structured block from config and debt output
    2. Generates FX curve (time-series rates)
    3. Calculates FX risk profile (VaR, CVaR, concentration)
    4. Returns new ScenarioResult with FX fields populated
    
    Args:
        scenario_result: Base ScenarioResult (with NPV, IRR, etc.)
        config: Project config dict (includes FX settings).
        debt_result: Output from plan_debt() module.
        annual_rows: Annual cashflow rows from compute_cashflow().
    
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
    # CESSPIT: Input validation
    if not isinstance(scenario_result, ScenarioResult):
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
        )
        fx_curve = compute_fx_curve(
            config=config,
            annual_rows=annual_rows,
        )
        fx_risk_profile = compute_fx_risk_profile(
            fx_block=fx_block,
            fx_curve=fx_curve,
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

    return ScenarioResult(**result_dict)


__all__ = ["integrate_fx_into_scenario_result"]

# EOF - analytics/fx_integration.py
