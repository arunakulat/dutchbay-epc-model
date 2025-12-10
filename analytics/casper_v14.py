from __future__ import annotations

from typing import Any, Dict, Sequence, Tuple

from analytics import evaluation_v14
from analytics.casper_payload import build_casper_payload
from analytics.contracts_v14 import CasperResult, SensitivitySuite

"""
analytics.casper_v14

CASPER / GWTF-compliant orchestrator for the v14 lender stack.

Design
------
- This module is a *thin* wrapper over analytics.evaluation_v14.
- All heavy lifting (schema load, v14 pipeline, Monte Carlo, tail risk)
  remains in evaluation_v14.evaluate_with_casper_tail_risk.
- This layer's only job is to:
    * expose a clear CASPER-oriented entry point, and
    * translate CasperResult -> JSON payload via build_casper_payload.

GWTF / CESSPIT guardrails
-------------------------
- No direct imports from finance.* or run_full_pipeline_v14.
- All evaluation goes through analytics.evaluation_v14.
- JSON contract stays pinned by CasperResult + CASPER_CONTRACT_VERSION,
  tested separately in test_casper_contract_freeze.py.
"""


def evaluate_with_casper_tail_risk_and_payload(
    *,
    config_path: str,
    monte_carlo_config_path: str | None = None,
    sensitivity_suite: SensitivitySuite | None = None,
    metric: str = "project_irr",
    confidence: float = 0.9,
    validation_mode: str = "strict",
    validation_modules: Sequence[str] | None = None,
) -> Tuple[CasperResult, Dict[str, Any]]:
    """
    Run full CASPER v14 orchestration and return both:

    1. CasperResult (typed contracts_v14 surface)
    2. JSON-safe CASPER payload dict (for APIs / dashboards)

    Parameters
    ----------
    config_path:
        Path to the YAML v14 scenario config.

    monte_carlo_config_path:
        Optional path to a Monte Carlo config. If None, the underlying
        evaluation_v14 logic will use its default / inline configuration,
        matching the behavior covered by existing tests.

    sensitivity_suite:
        Optional pre-computed SensitivitySuite. If None, the CASPER
        orchestrator in evaluation_v14 may still attach tail-risk
        information based on Monte Carlo alone.

    metric:
        Key metric for tail-risk analysis (e.g. "project_irr").

    confidence:
        Tail-risk confidence level (e.g. 0.9 for 90% CVaR-style views).

    validation_mode:
        Validation mode for the v14 pipeline ("strict", "relaxed", etc.).

    validation_modules:
        Optional list of validation modules (["cashflow", "debt"], ...).

    Returns
    -------
    (CasperResult, dict[str, Any])
        - casper: typed CASPER result surface (contracts_v14)
        - payload: JSON-friendly CASPER payload as emitted by
          analytics.casper_payload.build_casper_payload
    """
    casper = evaluation_v14.evaluate_with_casper_tail_risk(
        config_path=config_path,
        monte_carlo_config_path=monte_carlo_config_path,
        sensitivity_suite=sensitivity_suite,
        metric=metric,
        confidence=confidence,
        validation_mode=validation_mode,
        validation_modules=(
            list(validation_modules) if validation_modules is not None else None
        ),
    )

    if casper.scenario is None:
        raise ValueError("CasperResult.scenario is None; cannot build CASPER payload.")

    payload = build_casper_payload(
        scenario=casper.scenario,
        monte_carlo=casper.monte_carlo,
        sensitivity=casper.sensitivities,
        generation=getattr(casper, "generation", None),
        technology_breakdown=casper.multi_tech_generation_breakdown,
        metadata=casper.metadata,
    )

    return casper, payload


__all__ = [
    "evaluate_with_casper_tail_risk_and_payload",
]
