"""MC distribution-integrity guard (capability/provenance audit, HIGH 3/3).

The engine must (a) reject ill-ordered bounds (low > high) and (b) flag when a
swept driver's band excludes the scenario's own deterministic base, so an MC P50
that cannot reconcile to the base case is never reported silently.
"""

from __future__ import annotations

import pytest

from analytics.mc.engine import MonteCarloConfigError, MonteCarloEngine


def _cfg(low: float, high: float, base: float = 159_600_000.0) -> dict:
    return {
        "capex": {"usd_total": base},
        "monte_carlo": {"parameters": [{"name": "capex.usd_total", "low": low, "high": high}]},
    }


def test_ill_ordered_bounds_raise() -> None:
    with pytest.raises(MonteCarloConfigError, match="well-ordered"):
        MonteCarloEngine(_cfg(low=174_000_000.0, high=126_000_000.0))


def test_base_outside_band_is_flagged() -> None:
    # base 159.6M sits ABOVE the band's high — recorded in base_outside_bounds.
    eng = MonteCarloEngine(_cfg(low=126_000_000.0, high=140_000_000.0))
    assert eng._base_outside_bounds == ["capex.usd_total"]


def test_base_within_band_not_flagged() -> None:
    eng = MonteCarloEngine(_cfg(low=140_000_000.0, high=180_000_000.0))
    assert eng._base_outside_bounds == []


def test_canonical_scenarios_have_centered_bands() -> None:
    """After the recentering, no shipped scenario sweeps a band that excludes its base."""
    import glob

    import yaml

    def resolve(cfg: dict, dotted: str):
        cur = cfg
        for k in dotted.split("."):
            cur = cur.get(k) if isinstance(cur, dict) else None
            if cur is None:
                return None
        return cur

    offenders = []
    for f in sorted(glob.glob("scenarios/*.yaml")):
        try:
            cfg = next(iter(yaml.safe_load_all(open(f))), None)
        except yaml.YAMLError:
            continue
        if not isinstance(cfg, dict):
            continue
        for p in (cfg.get("monte_carlo") or {}).get("parameters") or []:
            if not isinstance(p, dict) or "name" not in p:
                continue
            low, high = p.get("low"), p.get("high")
            base = resolve(cfg, p["name"])
            if low is None or high is None or base is None:
                continue
            try:
                if not (float(low) <= float(base) <= float(high)):
                    offenders.append((f.split("/")[-1], p["name"]))
            except (TypeError, ValueError):
                continue
    assert offenders == [], f"MC bands excluding their base: {offenders}"
