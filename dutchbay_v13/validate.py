# dutchbay_v13/validate.py
from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Union

Pathish = Union[str, Path]

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None  # type: ignore

# Try optional jsonschema if present; otherwise we do a lightweight structural check.
try:  # pragma: no cover
    import jsonschema  # type: ignore
except Exception:  # pragma: no cover
    jsonschema = None  # type: ignore


# ---------------------------
# Schema discovery (optional)
# ---------------------------

def _schema_paths() -> List[Path]:
    """
    Where to look for YAML schemas. We use:
      - package default: dutchbay_v13/inputs/schema
      - any extra paths hinted by dutchbay_v13.schema.EXTRA_SCHEMA_PATHS (if present)
      - env var EXTRA_SCHEMA_PATHS (colon-separated)
    """
    paths: List[Path] = []
    pkg_root = Path(__file__).resolve().parent
    default = pkg_root / "inputs" / "schema"
    if default.exists():
        paths.append(default)

    # optional code-level hint
    try:
        from . import schema as _schema_mod  # type: ignore
        extra = getattr(_schema_mod, "EXTRA_SCHEMA_PATHS", [])
        for p in extra or []:
            pp = Path(p).expanduser().resolve()
            if pp.exists():
                paths.append(pp)
    except Exception:
        pass

    # optional env override
    env = os.environ.get("EXTRA_SCHEMA_PATHS")
    if env:
        for p in env.split(":"):
            pp = Path(p).expanduser().resolve()
            if pp.exists():
                paths.append(pp)

    # De-dup while preserving order
    seen: set = set()
    uniq: List[Path] = []
    for p in paths:
        if str(p) not in seen:
            seen.add(str(p))
            uniq.append(p)
    return uniq


def _load_yaml_file(path: Pathish) -> Dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"YAML not found: {p}")
    if yaml is None:
        raise RuntimeError("PyYAML is not available in this environment.")
    with p.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
        if not isinstance(data, dict):
            raise TypeError(f"Top-level YAML must be a mapping, got {type(data).__name__}")
        return data


def _load_financing_schema() -> Optional[Dict[str, Any]]:
    """
    Best-effort: load financing_terms.schema.yaml if found in any schema path.
    """
    names = {"financing_terms.schema.yaml", "Financing_Terms.schema.yaml"}
    for base in _schema_paths():
        for name in names:
            cand = base / name
            if cand.exists():
                try:
                    return _load_yaml_file(cand)
                except Exception:
                    # ignore corrupted schema; fall back to lightweight check
                    return None
    return None


# ------------------------------------
# Public API used by scenario_runner
# ------------------------------------

def load_params_from_file(path: Pathish) -> Dict[str, Any]:
    """
    Load a config YAML (e.g., full_model_variables_updated.yaml) into a dict.
    """
    return _load_yaml_file(path)


def _lightweight_financing_check(d: Dict[str, Any], strict: bool) -> None:
    """
    Minimal structural guardrails when jsonschema is unavailable.
    Only enforces obvious typos and nesting under Financing_Terms.
    """
    ft = d.get("Financing_Terms")
    if ft is None:
        return
    if not isinstance(ft, dict):
        raise TypeError("Financing_Terms must be a mapping.")

    allowed_top = {
        "debt_ratio",
        "tenor_years",
        "interest_only_years",
        "amortization",
        "dscr_target",
        "min_dscr",
        "mix",
        "rates",
        "reserves",
        "fees",
        "dscr_haircut_factor",
    }
    allowed_mix = {"lkr_max", "dfi_max", "usd_commercial_min"}
    allowed_rates = {"lkr_floor", "usd_floor", "dfi_floor"}
    allowed_reserves = {"dsra_months", "receivables_guarantee_months"}
    allowed_fees = {"upfront_pct", "commitment_pct"}

    if strict:
        unknown = set(ft.keys()) - allowed_top
        if unknown:
            raise ValueError(f"Unknown Financing_Terms keys (strict): {sorted(unknown)}")

    mix = ft.get("mix")
    if mix is not None:
        if not isinstance(mix, dict):
            raise TypeError("Financing_Terms.mix must be a mapping.")
        if strict:
            unk = set(mix.keys()) - allowed_mix
            if unk:
                raise ValueError(f"Unknown Financing_Terms.mix keys (strict): {sorted(unk)}")

    rates = ft.get("rates")
    if rates is not None:
        if not isinstance(rates, dict):
            raise TypeError("Financing_Terms.rates must be a mapping.")
        if strict:
            unk = set(rates.keys()) - allowed_rates
            if unk:
                raise ValueError(f"Unknown Financing_Terms.rates keys (strict): {sorted(unk)}")

    reserves = ft.get("reserves")
    if reserves is not None:
        if not isinstance(reserves, dict):
            raise TypeError("Financing_Terms.reserves must be a mapping.")
        if strict:
            unk = set(reserves.keys()) - allowed_reserves
            if unk:
                raise ValueError(f"Unknown Financing_Terms.reserves keys (strict): {sorted(unk)}")

    fees = ft.get("fees")
    if fees is not None:
        if not isinstance(fees, dict):
            raise TypeError("Financing_Terms.fees must be a mapping.")
        if strict:
            unk = set(fees.keys()) - allowed_fees
            if unk:
                raise ValueError(f"Unknown Financing_Terms.fees keys (strict): {sorted(unk)}")


def validate_params_dict(d: Dict[str, Any], mode: Optional[str] = None) -> Dict[str, Any]:
    """
    Validate a params dict. STRICT raises on unknown/invalid keys.
    RELAXED tolerates harmless extras.
    If jsonschema is present and a schema is found, we validate with it; otherwise we do a lightweight check.
    """
    vm = (mode or os.environ.get("VALIDATION_MODE") or "relaxed").strip().lower()
    strict = vm == "strict"

    schema = _load_financing_schema() if jsonschema is not None else None
    if schema and jsonschema is not None:
        try:
            jsonschema.validate(instance=d, schema=schema)  # type: ignore
        except Exception as e:
            if not strict:
                # In relaxed mode, only re-raise structural errors; unknown fields are allowed.
                raise
            raise
    else:
        _lightweight_financing_check(d, strict=strict)

    return d


# -----------------------
# CLI entry for `-m`
# -----------------------

def _cli() -> int:
    ap = argparse.ArgumentParser(description="Validate a DutchBay YAML config.")
    ap.add_argument("file", help="Path to YAML file.")
    ap.add_argument("--mode", choices=["strict", "relaxed"], default=None,
                    help="Override validation mode (default: env VALIDATION_MODE or relaxed).")
    args = ap.parse_args()

    try:
        data = load_params_from_file(args.file)
        validate_params_dict(data, mode=args.mode)
        print("OK: validation passed")
        return 0
    except Exception as e:
        print(f"ERROR: {e}")
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_cli())

    