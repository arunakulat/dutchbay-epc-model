"""KPI regression oracle for the eight NSO 250MW BESS LTL scenarios.

Both `RECRUIT-01` reviewers of the change that corrected these scenarios' tax layer and
delivery timeline recorded the same gap: ``grep -rln "nso250" tests/`` returned nothing, so
every KPI claim ever made about these files rested on author self-report with no in-repo
receipt. That is the exposure `VERIFY-01` exists to close, and it is why the reviewers had to
re-derive the numbers by hand rather than read them off a guard. This module is that guard.

What it pins, and why each one earns its place:

* **The seven-KPI vector per scenario**, against the golden fixture
  ``tests/fixtures/finance/nso250_ltl_expected_kpis.json`` — so a change to the levy stack,
  the depreciation basis or the construction window cannot move the published economics
  silently. The oracle lives in the fixture, never in the scenario YAML, per the #996 D3b
  rule that a runtime input must not double as its own regression target.
* **The unit/portfolio scaling identity.** The four ``unit`` files are one 11 MW / 44 MWh site
  and the four ``portfolio`` files are the 24-site aggregate at the same capacity-weighted
  rate. Ratios are scale-invariant, so the two must agree to the basis point. They do today;
  if a future edit touches one denominator and not the other, this is what says so.
* **``enhanced_allowance_applies`` is false on every variant.** This is a negative control, not
  decoration. The allowance was switched on once, on the reasoning that each site's depreciable
  base sits inside the Second Schedule's USD 250k-3m band. It does not: the cheapest variant is
  USD 3.17m plant-only per site and the portfolio files run 25x-45x over. Two independent
  reviewers vetoed it. The guard fires if it is switched back on without the eligibility
  arithmetic changing.
* **The bonded-relief encoding.** ``relief.bonded_scheme`` must stay false on every variant,
  because ``finance/import_levies.py`` zeroes CID, PAL *and* SSCL behind that single flag and
  the scheme does not reach SSCL. Relief belongs on the individual rates. The test asserts the
  resulting ``duty_rate`` directly, so the encoding is pinned by its effect and not merely by
  its spelling.

Honest finding these scenarios carry, and this test therefore locks in: three of the four
variants sit at a NEGATIVE equity IRR. That is the result, not a defect — the awarded capacity
charges do not support the quoted OEM equipment prices. Only ``bidimplied``, which carries the
capex the winning bids can themselves fund, is positive. ``min_dscr`` sits at 0.867-0.869 on
every variant: that is the #790/#806 conservative fold-corrected annual covenant minimum, a
different and stricter view than the ``min_dscr_period`` sculpt floor of 1.300, and it is
pinned here so the distinction cannot be quietly lost.

Re-baseline deliberately: update the fixture and say why here.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from analytics.evaluation_v14 import evaluate_with_overrides
from finance.import_levies import resolve_indirect_taxes

REPO_ROOT = Path(__file__).resolve().parents[2]
SCEN_DIR = REPO_ROOT / "scenarios"

_EXPECTED = json.loads(
    (
        REPO_ROOT / "tests" / "fixtures" / "finance" / "nso250_ltl_expected_kpis.json"
    ).read_text()
)
SCENARIOS = sorted(k for k in _EXPECTED if not k.startswith("_"))

# Ratio KPIs are dimensionless; 1e-6 is far tighter than any economically meaningful move
# and loose enough to absorb platform float noise.
ABS_TOL = 1e-6


def _config(name: str) -> dict[str, Any]:
    loaded = yaml.safe_load((SCEN_DIR / f"{name}.yaml").read_text())
    assert isinstance(loaded, dict), f"{name}: scenario did not parse to a mapping"
    return loaded


@pytest.fixture(scope="module")
def kpis() -> dict[str, dict[str, float]]:
    """Run each scenario once; the pipeline is the expensive part of this module."""
    return {
        name: evaluate_with_overrides(config_path=str(SCEN_DIR / f"{name}.yaml"))
        for name in SCENARIOS
    }


def test_all_eight_scenarios_are_present() -> None:
    """The family is eight files; a silently dropped variant must fail, not pass vacuously."""
    on_disk = sorted(p.stem for p in SCEN_DIR.glob("nso250_ltl_*.yaml"))
    assert on_disk == SCENARIOS, f"scenario set drifted from the oracle: {on_disk}"
    assert len(SCENARIOS) == 8


@pytest.mark.parametrize("name", SCENARIOS)
def test_kpi_vector_matches_oracle(
    name: str, kpis: dict[str, dict[str, float]]
) -> None:
    """Each scenario's published economics are unchanged against the golden fixture."""
    actual, expected = kpis[name], _EXPECTED[name]
    for metric, want in expected.items():
        got = actual.get(metric)
        assert got is not None, f"{name}: pipeline returned no {metric}"
        assert got == pytest.approx(want, abs=ABS_TOL), (
            f"{name}.{metric} moved: expected {want!r}, got {got!r}. "
            "If this re-baseline is intended, update the fixture and the module docstring."
        )


@pytest.mark.parametrize("variant", ["base", "bidimplied", "stress", "upside"])
def test_unit_and_portfolio_agree(
    variant: str, kpis: dict[str, dict[str, float]]
) -> None:
    """Ratio KPIs are scale-invariant, so one site and twenty-four must agree exactly."""
    unit = kpis[f"nso250_ltl_unit_{variant}"]
    portfolio = kpis[f"nso250_ltl_portfolio_{variant}"]
    for metric in ("project_irr", "equity_irr", "min_dscr_period", "min_dscr"):
        assert unit[metric] == pytest.approx(portfolio[metric], abs=ABS_TOL), (
            f"{variant}: unit and portfolio disagree on {metric} "
            f"({unit[metric]!r} vs {portfolio[metric]!r}) — a denominator has drifted."
        )


@pytest.mark.parametrize("name", SCENARIOS)
def test_enhanced_capital_allowance_stays_off(name: str) -> None:
    """Negative control: the allowance was vetoed on eligibility and must not creep back.

    The Second Schedule band is USD 250,000-3,000,000 of depreciable assets per undertaking.
    Every variant breaches it on the narrowest reading the claim itself invoked, so switching
    the allowance on requires the capex to change, not just the flag.
    """
    tax = _config(name)["tax"]
    assert tax["enhanced_allowance_applies"] is False, (
        f"{name}: enhanced_allowance_applies is true. Two RECRUIT-01 reviewers vetoed this "
        "because the depreciable base breaches the USD 250k-3m band on every reading. "
        "Re-enabling it needs the Second Schedule in the corpus, a reconciliation with "
        "project.boi_approved, and eligibility shown against this file's own capex.usd_total."
    )


@pytest.mark.parametrize("name", SCENARIOS)
def test_bonded_relief_leaves_sscl_standing(name: str) -> None:
    """SSCL survives the bonded scheme, so the relief must not be encoded via the flag.

    ``IndirectTaxes.duty_rate`` returns 0.0 for the whole CID+PAL+SSCL line when
    ``bonded_scheme`` is true. The scheme relieves CID, PAL, CESS and VAT — not SSCL, which is
    exempt only for raw materials imported for processing and re-export. Encoding relief on the
    individual rates keeps the 2.5% import SSCL live, which is what this asserts by effect.
    """
    config = _config(name)
    indirect = resolve_indirect_taxes(config)
    assert indirect is not None, f"{name}: no taxes_indirect block to resolve"
    assert (
        indirect.bonded_scheme is False
    ), f"{name}: relief.bonded_scheme is true, which zeroes SSCL along with CID and PAL."
    assert indirect.sscl_import_pct == pytest.approx(0.025, abs=ABS_TOL)
    assert indirect.duty_rate >= 0.025 - ABS_TOL, (
        f"{name}: duty_rate is {indirect.duty_rate!r}; the 2.5% import SSCL has been relieved "
        "by something. It is not relievable under the bonded scheme."
    )
