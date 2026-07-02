"""Tests for the report global-sensitivity (Morris) adapter (MC-1 / #468).

The canonical screening engine is injected as a fake so these never run the real
multi-evaluation Morris pass — they exercise this adapter's temp-file handling,
driver mapping, ranking (and the sort fallback), and best-effort degradation.
"""

from __future__ import annotations

from typing import Any, Dict

from app.services.report_global_sa import GlobalSABlock, compute_report_global_sa

_SCENARIO = {"monte_carlo": {"parameters": [{"name": "tariff.lkr_per_kwh"}]}}


def _morris_result() -> Dict[str, Any]:
    return {
        "method": "morris",
        "n_runs": 112,
        "metrics": {
            "project_irr": {
                "drivers": {
                    "tariff.lkr_per_kwh": {"mu_star": 0.0493, "sigma": 0.0050},
                    "capex.usd_total": {"mu_star": 0.0318, "sigma": 0.0033},
                    "opex.usd_per_year": {"mu_star": 0.0140, "sigma": 0.0027},
                },
                "ranking": [
                    "tariff.lkr_per_kwh",
                    "capex.usd_total",
                    "opex.usd_per_year",
                ],
            }
        },
    }


def test_global_sa_maps_and_keeps_ranking() -> None:
    block = compute_report_global_sa(
        _SCENARIO, runner=lambda _p, *, metrics, n_trajectories: _morris_result()
    )
    assert isinstance(block, GlobalSABlock)
    assert block.method == "morris" and block.metric == "project_irr"
    assert block.n_runs == 112
    assert [d.name for d in block.drivers] == [
        "tariff.lkr_per_kwh",
        "capex.usd_total",
        "opex.usd_per_year",
    ]
    top = block.drivers[0]
    assert top.mu_star == 0.0493 and top.sigma == 0.0050


def test_global_sa_sorts_by_mu_star_when_no_ranking() -> None:
    result = _morris_result()
    del result["metrics"]["project_irr"]["ranking"]  # force the mu_star sort fallback
    block = compute_report_global_sa(
        _SCENARIO, runner=lambda _p, *, metrics, n_trajectories: result
    )
    assert block is not None
    assert [d.name for d in block.drivers][0] == "tariff.lkr_per_kwh"  # widest mu_star


def test_global_sa_returns_none_when_runner_raises() -> None:
    def _boom(_p: str, *, metrics: Any, n_trajectories: int) -> Dict[str, Any]:
        raise RuntimeError("SALib missing / no parameters")

    assert compute_report_global_sa(_SCENARIO, runner=_boom) is None


def test_global_sa_returns_none_when_no_drivers() -> None:
    empty = {
        "method": "morris",
        "n_runs": 0,
        "metrics": {"project_irr": {"drivers": {}}},
    }
    assert (
        compute_report_global_sa(
            _SCENARIO, runner=lambda _p, *, metrics, n_trajectories: empty
        )
        is None
    )


def _flagged_result(flag: str, reason_key: str, reason: str) -> Dict[str, Any]:
    """An engine result whose target metric is FLAGGED: zeroed placeholder drivers."""
    return {
        "method": "morris",
        "n_runs": 112,
        "metrics": {
            "project_irr": {
                "drivers": {
                    "tariff.lkr_per_kwh": {"mu_star": 0.0, "sigma": 0.0},
                    "capex.usd_total": {"mu_star": 0.0, "sigma": 0.0},
                },
                "ranking": ["tariff.lkr_per_kwh", "capex.usd_total"],
                flag: True,
                reason_key: reason,
                "masked": {"nan_poisoned": flag == "nan_poisoned"},
            }
        },
    }


def test_global_sa_omits_section_for_nan_poisoned_metric() -> None:
    """Fable blocker on #644: a nan_poisoned metric carries ZEROED placeholder drivers;
    rendering them would print every driver at 0.00% with no caveat — a confident false
    claim (e.g. 'FX does not influence the IRR'). The documented CASPER degrade path is
    to omit the section: the adapter returns None, and the template's existing
    `if ctx.global_sa` guard (pinned by test_html_omits_global_sa_section_when_absent)
    drops the section end-to-end."""
    flagged = _flagged_result(
        "nan_poisoned",
        "nan_poisoned_reason",
        "12 of 16 trajectories (75%) contain non-finite outputs",
    )
    assert (
        compute_report_global_sa(
            _SCENARIO, runner=lambda _p, *, metrics, n_trajectories: flagged
        )
        is None
    )


def test_global_sa_omits_section_for_flat_metric() -> None:
    """A flat_metric result is the same zeroed-placeholder shape (verified: the template
    renders it as an uncaveated all-0.00% table too), so it takes the same omission."""
    flagged = _flagged_result(
        "flat_metric",
        "flat_metric_reason",
        "the metric does not move under these sweeps",
    )
    assert (
        compute_report_global_sa(
            _SCENARIO, runner=lambda _p, *, metrics, n_trajectories: flagged
        )
        is None
    )


def test_global_sa_renders_clean_metric_with_explicit_false_flags() -> None:
    """A clean engine result carrying the explicit falsy #644 flags renders unchanged."""
    result = _morris_result()
    result["metrics"]["project_irr"]["flat_metric"] = False
    result["metrics"]["project_irr"]["nan_poisoned"] = False
    block = compute_report_global_sa(
        _SCENARIO, runner=lambda _p, *, metrics, n_trajectories: result
    )
    assert isinstance(block, GlobalSABlock)
    assert [d.name for d in block.drivers][0] == "tariff.lkr_per_kwh"


def test_global_sa_honours_metric_argument() -> None:
    captured: Dict[str, Any] = {}

    def _runner(_p: str, *, metrics: Any, n_trajectories: int) -> Dict[str, Any]:
        captured["metrics"] = list(metrics)
        return {
            "method": "morris",
            "n_runs": 1,
            "metrics": {
                "equity_irr": {"drivers": {"x": {"mu_star": 0.1, "sigma": 0.0}}}
            },
        }

    block = compute_report_global_sa(_SCENARIO, metric="equity_irr", runner=_runner)
    assert captured["metrics"] == ["equity_irr"]
    assert block is not None and block.metric == "equity_irr"
