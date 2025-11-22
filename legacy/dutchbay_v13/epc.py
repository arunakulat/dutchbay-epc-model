from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Any
import json


@dataclass(frozen=True)
class EPCParams:
    base_cost_usd: float
    freight_pct: float  # 0..1
    contingency_pct: float  # 0..1
    fx_rate: float  # USD->LCY


def compute_epc(p: EPCParams) -> Dict[str, float]:
    freight = p.base_cost_usd * p.freight_pct
    subtotal = p.base_cost_usd + freight
    contingency = subtotal * p.contingency_pct
    total_usd = subtotal + contingency
    total_lcy = total_usd * p.fx_rate
    return {
        "freight_usd": freight,
        "contingency_usd": contingency,
        "total_epc_usd": total_usd,
        "total_epc_lcy": total_lcy,
    }


def run_epc(
    config: Optional[Dict[str, Any]] = None,
    config_path: Optional[str] = None,
    out_dir: str = "outputs/epc",
) -> int:
    if config is None and config_path is not None:
        import yaml  # type: ignore

        config = yaml.safe_load(Path(config_path).read_text(encoding="utf-8")) or {}
    cfg = config or {}

    p = EPCParams(
        base_cost_usd=float(cfg.get("base_cost_usd", 100_000_000.0)),
        freight_pct=float(cfg.get("freight_pct", 0.05)),
        contingency_pct=float(cfg.get("contingency_pct", 0.10)),
        fx_rate=float(cfg.get("fx_rate", 320.0)),
    )

    if not (0.0 <= p.freight_pct <= 1.0):
        raise ValueError("freight_pct must be in [0,1]")
    if not (0.0 <= p.contingency_pct <= 1.0):
        raise ValueError("contingency_pct must be in [0,1]")
    if p.base_cost_usd <= 0 or p.fx_rate <= 0:
        raise ValueError("base_cost_usd and fx_rate must be positive")

    res = compute_epc(p)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "epc_summary.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    return 0
