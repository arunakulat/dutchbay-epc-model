"""
Stress Testing Module for DutchBay EPC Model (v14)

QUARANTINED (#473, MC-2/3) — BUILT BUT UNWIRED. This module is not reachable from any
production path: no Hydra CLI, no pipeline (``pipeline_v14_enhanced`` /
``pipeline_analytics_v14``), no report pack, no FastAPI app imports it. The only references
are its own test (``tests/legacy/test_stress_tests_v14.py``) and a commented-out stub in
``scripts/run_full_pipeline_sprint12.py``. It was moved out of ``analytics/`` into
``legacy/`` so the production tree honestly reflects what actually runs; the code and its git
history are preserved here. To REACTIVATE: wire ``StressTestEngine`` into a Hydra CLI under
``analytics/cli/`` and surface its output in the report, route its NPV/IRR through the
``evaluate_with_overrides`` gateway (dropping the direct ``finance.irr`` import), and fix the
mislabel noted below.

MC-4 HONESTY NOTE (#473): the result fields ``var_95_usd`` / ``cvar_95_usd`` are NOT
statistical Value-at-Risk / Conditional-VaR. They are a single DETERMINISTIC stress loss
(``max(0, base_npv - stressed_npv)``) and a fixed 1.25x buffer on it — there is no loss
distribution or tail quantile. Real empirical VaR/CVaR live in ``analytics/core/risk_metrics``
and ``analytics/sensitivity/tail_risk``. The names are kept as-is only because this is frozen
legacy code; do not copy this labelling into production.

Implements comprehensive stress testing scenarios:
- Interest rate shocks (±2%, ±5%)
- Market downturns (20%, 40%, 60%)
- Refinancing risk scenarios
- Inflation stress (2%, 4%, 6%)
- Combined severe scenarios

Produces (see the MC-4 note above — these are stress-loss scalars, not statistical tail risk):
- "VaR" at 95% label (a deterministic stress loss)
- "CVaR" label (a fixed 1.25x buffer)
- NPV and IRR impact analysis
- Break-even analysis

R7 Compliance: Uses finance.irr singleton for all NPV/IRR calculations
TYPE-01: 100% type hints
CLI-03: JSON serializable output
FIN-01: Comprehensive edge case handling
"""

import json
import logging
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from finance.irr import irr, npv  # R7: IRR/NPV from finance.irr ONLY

logger = logging.getLogger(__name__)


class StressScenario(Enum):
    """Available stress test scenarios."""

    RATE_SHOCK_UP_2PCT = "rate_shock_up_2pct"
    RATE_SHOCK_UP_5PCT = "rate_shock_up_5pct"
    RATE_SHOCK_DOWN_2PCT = "rate_shock_down_2pct"
    MARKET_DOWNTURN_20PCT = "market_down_20pct"
    MARKET_DOWNTURN_40PCT = "market_down_40pct"
    MARKET_DOWNTURN_60PCT = "market_down_60pct"
    INFLATION_2PCT = "inflation_2pct"
    INFLATION_4PCT = "inflation_4pct"
    INFLATION_6PCT = "inflation_6pct"
    COMBINED_SEVERE = "combined_severe"


@dataclass
class StressResult:
    """Result of a single stress scenario (CLI-03: JSON serializable)."""

    scenario: str
    base_npv_usd: float
    stressed_npv_usd: float
    npv_change_usd: float
    npv_change_pct: float
    base_irr_pct: float
    stressed_irr_pct: float
    irr_change_bps: float
    var_95_usd: float
    cvar_95_usd: float
    break_even_point: Optional[float]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization (CLI-03)."""
        return asdict(self)


class StressTestEngine:
    """
    Stress testing engine for financial models.

    Implements scenario-based analysis with risk metrics.
    All NPV/IRR calculations use finance.irr singleton (R7).
    """

    def __init__(
        self,
        base_cash_flows: List[float],
        base_discount_rate: float,
        time_periods: int = 30,
    ) -> None:
        """
        Initialize stress test engine.

        Args:
            base_cash_flows: Base scenario cash flows
            base_discount_rate: Base discount rate (decimal, e.g., 0.08 for 8%)
            time_periods: Number of periods
        """
        self.base_cash_flows = base_cash_flows
        self.base_discount_rate = base_discount_rate
        self.time_periods = time_periods

        # Calculate base metrics using finance.irr (R7)
        self.base_npv = npv(base_discount_rate, base_cash_flows)
        irr_decimal = irr(base_cash_flows)
        self.base_irr = (irr_decimal * 100) if irr_decimal is not None else 0.0

    def apply_interest_rate_shock(self, shock_bps: int) -> float:
        """
        Apply interest rate shock to discount rate.

        Args:
            shock_bps: Shock in basis points (e.g., 200 for +2%)

        Returns:
            Shocked discount rate
        """
        shocked_rate = self.base_discount_rate + (shock_bps / 10000)
        return max(0.001, min(0.5, shocked_rate))  # Cap between 0.1% and 50%

    def apply_market_downturn(self, downturn_pct: float) -> List[float]:
        """
        Apply market downturn to cash flows.

        Args:
            downturn_pct: Downturn percentage (e.g., 0.20 for 20% decline)

        Returns:
            Stressed cash flows
        """
        factor = 1 - downturn_pct
        return [cf * factor for cf in self.base_cash_flows]

    def apply_inflation_stress(
        self, inflation_pct: float, cash_flows: Optional[List[float]] = None
    ) -> Tuple[List[float], float]:
        """
        Apply inflation stress to both cash flows and discount rate.

        Args:
            inflation_pct: Inflation rate (e.g., 0.04 for 4%)
            cash_flows: Series to erode. Defaults to the base cash flows; pass an
                already-stressed series to COMPOSE stresses (e.g. a downturn
                followed by inflation) without resetting to base.

        Returns:
            Tuple of (adjusted cash flows, adjusted discount rate)
        """
        source_cfs = self.base_cash_flows if cash_flows is None else cash_flows
        # Adjust CF for inflation erosion
        adjusted_cfs = [cf * (1 - inflation_pct * 0.3) for cf in source_cfs]
        # Adjust discount rate by Fisher equation
        adjusted_rate = self.base_discount_rate + inflation_pct
        return adjusted_cfs, adjusted_rate

    def run_scenario(self, scenario: StressScenario) -> StressResult:
        """
        Run a single stress scenario.

        Args:
            scenario: Scenario to run

        Returns:
            StressResult with all metrics
        """
        stressed_cfs = self.base_cash_flows.copy()
        stressed_rate = self.base_discount_rate

        # Apply scenario modifications
        if scenario == StressScenario.RATE_SHOCK_UP_2PCT:
            stressed_rate = self.apply_interest_rate_shock(200)
        elif scenario == StressScenario.RATE_SHOCK_UP_5PCT:
            stressed_rate = self.apply_interest_rate_shock(500)
        elif scenario == StressScenario.RATE_SHOCK_DOWN_2PCT:
            stressed_rate = self.apply_interest_rate_shock(-200)
        elif scenario == StressScenario.MARKET_DOWNTURN_20PCT:
            stressed_cfs = self.apply_market_downturn(0.20)
        elif scenario == StressScenario.MARKET_DOWNTURN_40PCT:
            stressed_cfs = self.apply_market_downturn(0.40)
        elif scenario == StressScenario.MARKET_DOWNTURN_60PCT:
            stressed_cfs = self.apply_market_downturn(0.60)
        elif scenario == StressScenario.INFLATION_2PCT:
            stressed_cfs, stressed_rate = self.apply_inflation_stress(0.02)
        elif scenario == StressScenario.INFLATION_4PCT:
            stressed_cfs, stressed_rate = self.apply_inflation_stress(0.04)
        elif scenario == StressScenario.INFLATION_6PCT:
            stressed_cfs, stressed_rate = self.apply_inflation_stress(0.06)
        elif scenario == StressScenario.COMBINED_SEVERE:
            # A genuinely severe combined scenario must COMPOUND the worst of each
            # single-stress dimension, otherwise it is not the most severe case
            # (a standalone 60% downturn would dominate it). The previous code
            # applied a mild 30% downturn and then overwrote it with
            # inflation-on-base, silently dropping the downturn entirely.
            stressed_cfs = self.apply_market_downturn(0.60)
            stressed_cfs, inflation_rate = self.apply_inflation_stress(
                0.06, cash_flows=stressed_cfs
            )
            # Discount rate carries BOTH the inflation Fisher adjustment and the
            # +500bps rate shock (capped like apply_interest_rate_shock).
            stressed_rate = max(0.001, min(0.5, inflation_rate + 500 / 10000))

        # Calculate stressed metrics using finance.irr (R7)
        stressed_npv = npv(stressed_rate, stressed_cfs)
        irr_decimal = irr(stressed_cfs)
        stressed_irr = (irr_decimal * 100) if irr_decimal is not None else 0.0

        # Calculate risk metrics
        npv_change = stressed_npv - self.base_npv
        npv_change_pct = (
            (npv_change / abs(self.base_npv)) * 100 if self.base_npv != 0 else 0
        )
        irr_change_bps = (stressed_irr - self.base_irr) * 100

        # Downside risk under this scenario: the LOSS relative to the base case
        # (non-negative; zero if the stress is actually accretive). This is a
        # deterministic stress loss — the per-scenario analogue of VaR — not the
        # old fabricated "5% of stressed NPV", which scaled with NPV and was
        # meaningless. cvar_95 keeps the conventional ~1.25x tail multiplier.
        var_95 = max(0.0, self.base_npv - stressed_npv)
        cvar_95 = var_95 * 1.25

        return StressResult(
            scenario=scenario.value,
            base_npv_usd=self.base_npv,
            stressed_npv_usd=stressed_npv,
            npv_change_usd=npv_change,
            npv_change_pct=npv_change_pct,
            base_irr_pct=self.base_irr,
            stressed_irr_pct=stressed_irr,
            irr_change_bps=irr_change_bps,
            var_95_usd=var_95,
            cvar_95_usd=cvar_95,
            break_even_point=None,
        )

    def run_all_scenarios(self) -> List[StressResult]:
        """Run all stress test scenarios (TEST-01: regression validation)."""
        results = []
        for scenario in StressScenario:
            result = self.run_scenario(scenario)
            results.append(result)
        return results

    def export_to_json(self, results: List[StressResult]) -> str:
        """Export results to JSON string (CLI-03: JSON serialization)."""
        data = {
            "base_metrics": {
                "npv_usd": self.base_npv,
                "irr_pct": self.base_irr,
                "discount_rate": self.base_discount_rate,
            },
            "stress_results": [r.to_dict() for r in results],
        }
        return json.dumps(data, indent=2)
