# dutchbay_v13/params.py
from __future__ import annotations
"""
Centralized parameter loader and accessors.

- Loads a canonical YAML (and optional override YAML / dict)
- Validates (strict/relaxed) via dutchbay_v13.validate if available
- Exposes typed, policy-free getters used by cashflow/adapters

No business policy defaults here: floors, caps, rates must live in YAML.
"""
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Union, List, Mapping

try:  # Light dependency; present in this repo
    import yaml  # type: ignore
except Exception as e:  # pragma: no cover
    raise RuntimeError("PyYAML is required to load configuration") from e


# --------------------------- basic IO & merge ---------------------------

def _load_yaml_file(p: Union[str, Path]) -> Dict[str, Any]:
    path = Path(p)
    if not path.exists():
        raise FileNotFoundError(f"YAML not found: {path}")
    with path.open('r', encoding='utf-8') as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Top-level YAML must be a mapping/dict: {path}")
    return data


def _deep_merge(base: Dict[str, Any], override: Mapping[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = dict(base)
    for k, v in override.items():
        if isinstance(v, Mapping) and isinstance(out.get(k), Mapping):
            out[k] = _deep_merge(out[k], v)  # type: ignore[index]
        else:
            out[k] = v  # lists/scalars replace
    return out


# --------------------------- validation bridge -------------------------

def _maybe_validate(params: Dict[str, Any], mode: str = "strict") -> None:
    """Call project validator if available. No-op if module not present."""
    try:
        from .validate import validate as _validate  # type: ignore
    except Exception:
        return
    _validate(params, mode=mode)  # let it raise on failure


# --------------------------- public loader -----------------------------

def load_params(
    config: Optional[Union[str, Path]] = None,
    *override_paths: Union[str, Path],
    overrides: Optional[Mapping[str, Any]] = None,
    mode: str = "strict",
) -> Dict[str, Any]:
    """
    Load the canonical YAML + optional overrides, then validate.

    Args:
        config: path to the canonical inputs YAML (defaults to repo root
                'full_model_variables_updated.yaml', falling back to 'inputs/...'
                if not found).
        override_paths: optional additional YAMLs to deep-merge (later wins)
        overrides: optional in-memory mapping to deep-merge last
        mode: 'strict' or 'relaxed' (passed to validator)

    Returns:
        Fully merged parameter dict
    """
    if config is None:
        guess = Path.cwd() / "full_model_variables_updated.yaml"
        if not guess.exists():
            alt = Path.cwd() / "inputs" / "full_model_variables_updated.yaml"
            config_path = alt if alt.exists() else guess
        else:
            config_path = guess
    else:
        config_path = Path(config)

    params = _load_yaml_file(config_path)

    for p in override_paths:
        params = _deep_merge(params, _load_yaml_file(p))

    if overrides:
        params = _deep_merge(params, overrides)

    _maybe_validate(params, mode=mode)
    return params


# --------------------------- namespaced getters ------------------------

def _get(d: Dict[str, Any], path: Iterable[str], default: Any = None) -> Any:
    cur: Any = d
    for k in path:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def _as_float(v: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        return float(v) if v is not None else default
    except Exception:
        return default


# Project basics

def capacity_mw(p: Dict[str, Any]) -> float:
    v = _get(p, ["Project", "capacity_mw"])
    if v is None:
        v = p.get("capacity_mw")  # legacy
    return float(v) if v is not None else 1.0


def lifetime_years(p: Dict[str, Any]) -> int:
    v = _get(p, ["Project", "timeline", "lifetime_years"])
    if v is None:
        v = p.get("lifetime_years")  # legacy
    return int(_as_float(v, 20) or 20)


def availability(p: Dict[str, Any]) -> float:
    v = p.get("availability_pct")
    return max(0.0, min(1.0, (_as_float(v, 95.0) or 95.0) / 100.0))


def loss_factor(p: Dict[str, Any]) -> float:
    v = p.get("loss_factor")
    return max(0.0, min(1.0, _as_float(v, 0.0) or 0.0))


# Pricing

def tariff_usd_per_kwh(p: Dict[str, Any]) -> float:
    v = _get(p, ["Pricing", "tariff_usd_per_kwh"])
    if v is None:
        v = p.get("tariff_usd_per_kwh", p.get("tariff"))
    if v is None:
        raise KeyError("Pricing.tariff_usd_per_kwh is required in YAML (no in-code default).")
    return float(v)


# Capex / Opex (no policy baked in; floors only if provided)

def capex_usd(p: Dict[str, Any]) -> float:
    total = _get(p, ["Capex", "usd_total"])
    if total is not None:
        return float(total)
    per_mw = _get(p, ["Capex", "usd_per_mw"])
    floor_pm = _get(p, ["Capex", "floor_per_mw"], 0.0)
    if per_mw is None:
        raise KeyError("Capex.usd_total or Capex.usd_per_mw must be provided in YAML.")
    mw = capacity_mw(p)
    return max(float(per_mw) * mw, float(floor_pm) * mw)


def opex_usd_per_year(p: Dict[str, Any]) -> float:
    val = _get(p, ["Opex", "usd_per_year"])
    floor_usd = _get(p, ["Opex", "floor_usd_per_year"], 0.0)
    if val is None:
        if floor_usd:
            return float(floor_usd)
        raise KeyError("Opex.usd_per_year must be provided (no code default).")
    return max(float(val), float(floor_usd or 0.0))


# FX curve

def fx_curve_lkr_per_usd(p: Dict[str, Any], years: int) -> List[float]:
    explicit = _get(p, ["FX", "curve_lkr_per_usd"])
    if isinstance(explicit, list) and explicit:
        seq = [float(x) for x in explicit]
        if len(seq) >= years:
            return seq[:years]
        return seq + [seq[-1]] * (years - len(seq))

    start = _get(p, ["FX", "start_lkr_per_usd"])
    depr = _get(p, ["FX", "annual_depr"])
    if start is None or depr is None:
        raise KeyError("Provide FX.curve_lkr_per_usd OR both FX.start_lkr_per_usd and FX.annual_depr in YAML.")
    out: List[float] = []
    cur = float(start)
    for _ in range(max(1, years)):
        out.append(cur)
        cur *= (1.0 + float(depr))
    return out


# Financing terms (normalized view)

def financing_terms(p: Dict[str, Any]) -> Dict[str, Any]:
    ft = dict(_get(p, ["Financing_Terms"], {}) or {})
    # normalize child maps if absent
    ft.setdefault("mix", {})
    ft.setdefault("rates", {})
    ft.setdefault("reserves", {})
    ft.setdefault("fees", {})
    # Coerce a few types if present (no defaults here)
    for key in ("debt_ratio", "dscr_target", "min_dscr", "dscr_haircut_factor"):
        if key in ft and ft[key] is not None:
            ft[key] = float(ft[key])
    for key in ("tenor_years", "interest_only_years"):
        if key in ft and ft[key] is not None:
            ft[key] = int(ft[key])
    if "amortization" in ft and isinstance(ft["amortization"], str):
        ft["amortization"] = str(ft["amortization"]).lower()
    # mix caps
    mix = ft["mix"]
    for key in ("lkr_max", "dfi_max", "usd_commercial_min"):
        if key in mix and mix[key] is not None:
            mix[key] = float(mix[key])
    # rate floors
    rates = ft["rates"]
    for key in ("lkr_floor", "usd_floor", "dfi_floor"):
        if key in rates and rates[key] is not None:
            rates[key] = float(rates[key])
    # reserves
    res = ft["reserves"]
    for key in ("dsra_months", "receivables_guarantee_months"):
        if key in res and res[key] is not None:
            res[key] = int(res[key])
    # fees
    fees = ft["fees"]
    for key in ("upfront_pct", "commitment_pct"):
        if key in fees and fees[key] is not None:
            fees[key] = float(fees[key])
    return ft

    