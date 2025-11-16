#!/usr/bin/env python3
"""
WACC & hurdle-rate engine driven entirely by a YAML configuration.

Usage:
    python wacc_engine_yaml.py wacc_config.yaml

The YAML must provide:
  - project metadata
  - capital_structure (tax_rate, hurdle margins)
  - debt tranches
  - equity tranches

All project-specific financial variables live in the YAML, not in this script.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from typing import List, Optional, Dict, Any

try:
    import yaml  # type: ignore
except ImportError as exc:  # pragma: no cover - simple env guard
    raise SystemExit(
        "PyYAML is required. Install with:\n    pip install pyyaml"
    ) from exc


@dataclass
class DebtTranche:
    name: str
    share_of_capital: float  # fraction of TOTAL capital (e.g. 0.385 for 38.5%)
    base_rate: float         # nominal interest rate as decimal (e.g. 0.07 for 7%)
    guarantee_fee_bps: float = 0.0  # annual guarantee/PRI fee in bps on outstanding
    upfront_fee_bps: float = 0.0    # one-off upfront fee in bps on principal
    fee_amort_years: Optional[int] = None  # if None, upfront fee ignored in effective rate

    def effective_rate(self) -> float:
        """Effective annual debt cost including guarantee and amortised upfront fee."""
        guarantee = self.guarantee_fee_bps / 10_000.0
        upfront = 0.0
        if self.upfront_fee_bps and self.fee_amort_years:
            upfront = (self.upfront_fee_bps / 10_000.0) / float(self.fee_amort_years)
        return self.base_rate + guarantee + upfront


@dataclass
class EquityTranche:
    name: str
    share_of_capital: float  # fraction of TOTAL capital (e.g. 0.165 for 16.5%)
    target_irr: float        # required return as decimal (e.g. 0.16 for 16%)
    is_foreign: bool = False


def compute_cost_of_debt(debt: List[DebtTranche]) -> Dict[str, float]:
    """Return blended debt share and pre-tax cost of debt."""
    if not debt:
        return {"debt_share": 0.0, "cost_debt_pre_tax": 0.0}

    total_capital_share = sum(d.share_of_capital for d in debt)
    if total_capital_share <= 0:
        raise ValueError("Debt tranches must have positive share_of_capital.")

    debt_share = total_capital_share  # since share_of_capital is relative to total capital

    # Weight within debt bucket
    cost_pre_tax = 0.0
    for d in debt:
        weight_in_debt = d.share_of_capital / debt_share
        cost_pre_tax += weight_in_debt * d.effective_rate()

    return {
        "debt_share": debt_share,
        "cost_debt_pre_tax": cost_pre_tax,
    }


def compute_cost_of_equity(equity: List[EquityTranche]) -> Dict[str, float]:
    """Return blended equity share, cost of equity and foreign equity hurdle (if any)."""
    if not equity:
        return {
            "equity_share": 0.0,
            "cost_equity": 0.0,
            "foreign_equity_hurdle": 0.0,
        }

    total_capital_share = sum(e.share_of_capital for e in equity)
    if total_capital_share <= 0:
        raise ValueError("Equity tranches must have positive share_of_capital.")

    equity_share = total_capital_share

    blended = 0.0
    for e in equity:
        weight_in_equity = e.share_of_capital / equity_share
        blended += weight_in_equity * e.target_irr

    foreign_tranches = [e for e in equity if e.is_foreign]
    foreign_hurdle = 0.0
    if foreign_tranches:
        total_foreign_share = sum(e.share_of_capital for e in foreign_tranches)
        for e in foreign_tranches:
            w = e.share_of_capital / total_foreign_share
            foreign_hurdle += w * e.target_irr

    return {
        "equity_share": equity_share,
        "cost_equity": blended,
        "foreign_equity_hurdle": foreign_hurdle,
    }


def compute_wacc_and_hurdles(
    debt: List[DebtTranche],
    equity: List[EquityTranche],
    tax_rate: float,
    project_hurdle_margin_bps: float,
    equity_hurdle_margin_bps: float,
) -> Dict[str, float]:
    """Compute WACC and hurdle benchmarks using explicit inputs (no hidden defaults)."""
    debt_metrics = compute_cost_of_debt(debt)
    equity_metrics = compute_cost_of_equity(equity)

    d_share = debt_metrics["debt_share"]
    e_share = equity_metrics["equity_share"]

    if abs(d_share + e_share - 1.0) > 1e-6:
        raise ValueError(
            f"Capital structure must sum to 1.0; got debt_share={d_share:.4f}, "
            f"equity_share={e_share:.4f}"
        )

    cost_debt_pre_tax = debt_metrics["cost_debt_pre_tax"]
    cost_debt_after_tax = cost_debt_pre_tax * (1.0 - tax_rate)
    cost_equity = equity_metrics["cost_equity"]

    wacc = d_share * cost_debt_after_tax + e_share * cost_equity

    project_hurdle = wacc + project_hurdle_margin_bps / 10_000.0
    blended_equity_hurdle = cost_equity + equity_hurdle_margin_bps / 10_000.0

    return {
        "wacc": wacc,
        "debt_share": d_share,
        "equity_share": e_share,
        "cost_debt_pre_tax": cost_debt_pre_tax,
        "cost_debt_after_tax": cost_debt_after_tax,
        "cost_equity": cost_equity,
        "blended_equity_hurdle": blended_equity_hurdle,
        "foreign_equity_hurdle": equity_metrics["foreign_equity_hurdle"],
        "project_hurdle": project_hurdle,
    }


def format_results(results: Dict[str, float]) -> str:
    """Pretty-print results as percentages."""
    def pct(x: float) -> str:
        return f"{x * 100:5.2f}%"

    lines = [
        f"WACC (after tax)          : {pct(results['wacc'])}",
        "",
        f"Debt share                : {results['debt_share']*100:5.1f}%",
        f"  Cost of debt (pre-tax)  : {pct(results['cost_debt_pre_tax'])}",
        f"  Cost of debt (after-tax): {pct(results['cost_debt_after_tax'])}",
        "",
        f"Equity share              : {results['equity_share']*100:5.1f}%",
        f"  Blended cost of equity  : {pct(results['cost_equity'])}",
        f"  Blended equity hurdle   : {pct(results['blended_equity_hurdle'])}",
    ]

    if results["foreign_equity_hurdle"] > 0:
        lines.append(
            f"  Foreign equity hurdle   : {pct(results['foreign_equity_hurdle'])}"
        )

    lines.append("")
    lines.append(f"Project hurdle (IRR target): {pct(results['project_hurdle'])}")

    return "\n".join(lines)


def load_config(path: str) -> Dict[str, Any]:
    """Load YAML config from the given path and return as a dict."""
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    if not isinstance(cfg, dict):
        raise ValueError("Top-level YAML structure must be a mapping.")

    return cfg


def parse_tranches_from_config(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Create DebtTranche and EquityTranche lists plus capital-structure inputs."""
    cap = cfg.get("capital_structure") or {}
    try:
        tax_rate = float(cap["tax_rate"])
    except KeyError as exc:
        raise KeyError("capital_structure.tax_rate is required in the YAML config") from exc

    project_hurdle_margin_bps = float(cap.get("project_hurdle_margin_bps", 0.0))
    equity_hurdle_margin_bps = float(cap.get("equity_hurdle_margin_bps", 0.0))

    debt_cfg = cfg.get("debt") or []
    equity_cfg = cfg.get("equity") or []

    debt_tranches: List[DebtTranche] = []
    for d in debt_cfg:
        debt_tranches.append(
            DebtTranche(
                name=str(d["name"]),
                share_of_capital=float(d["share_of_capital"]),
                base_rate=float(d["base_rate"]),
                guarantee_fee_bps=float(d.get("guarantee_fee_bps", 0.0)),
                upfront_fee_bps=float(d.get("upfront_fee_bps", 0.0)),
                fee_amort_years=(
                    int(d["fee_amort_years"])
                    if d.get("fee_amort_years") is not None
                    else None
                ),
            )
        )

    equity_tranches: List[EquityTranche] = []
    for e in equity_cfg:
        equity_tranches.append(
            EquityTranche(
                name=str(e["name"]),
                share_of_capital=float(e["share_of_capital"]),
                target_irr=float(e["target_irr"]),
                is_foreign=bool(e.get("is_foreign", False)),
            )
        )

    return {
        "tax_rate": tax_rate,
        "project_hurdle_margin_bps": project_hurdle_margin_bps,
        "equity_hurdle_margin_bps": equity_hurdle_margin_bps,
        "debt_tranches": debt_tranches,
        "equity_tranches": equity_tranches,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compute WACC & hurdle rates from a YAML configuration."
    )
    parser.add_argument(
        "config",
        help="Path to YAML configuration file.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Also print a JSON blob of the results.",
    )

    args = parser.parse_args()

    cfg = load_config(args.config)
    parsed = parse_tranches_from_config(cfg)

    results = compute_wacc_and_hurdles(
        debt=parsed["debt_tranches"],
        equity=parsed["equity_tranches"],
        tax_rate=parsed["tax_rate"],
        project_hurdle_margin_bps=parsed["project_hurdle_margin_bps"],
        equity_hurdle_margin_bps=parsed["equity_hurdle_margin_bps"],
    )

    print(format_results(results))

    if args.json:
        print("\nJSON output:\n" + json.dumps(results, indent=2, sort_keys=True))


if __name__ == "__main__":  # pragma: no cover
    main()

    