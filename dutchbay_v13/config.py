from __future__ import annotations

from typing import Any, Dict, Tuple
import os
import io
import yaml


def _parse_yaml_fallback(text: str) -> Dict[str, Any]:
    """
    Super-tolerant parser for key: value lines (only for emergencies).
    Booleans and numbers are coerced when obvious.
    """
    data: Dict[str, Any] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        try:
            if v.lower() in ("true", "false"):
                data[k] = v.lower() == "true"
            else:
                data[k] = float(v) if "." in v else int(v)
        except Exception:
            data[k] = v
    return data


def _flatten_grouped(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """
    Flatten shallow groups like {'finance': {...}, 'plant': {...}} into one level.
    Prefers top-level keys if collisions occur.
    """
    flat: Dict[str, Any] = dict(cfg)
    for k, v in list(cfg.items()):
        if isinstance(v, dict) and k not in ("cashflows",):
            for sk, sv in v.items():
                flat.setdefault(sk, sv)
    return flat


def _split_power_and_debt(d: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    debt = d.pop("debt", {}) if isinstance(d, dict) else {}
    return d, debt


def load_model_config(
    source: str | os.PathLike | io.StringIO,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Load YAML from a path or text stream. If YAML fails, use a tolerant fallback.
    Returns (flat_config, debt_section).
    """
    text: str
    if hasattr(source, "read"):
        text = str(source.read())
    else:
        p = os.fspath(source)
        with open(p, "r", encoding="utf-8") as f:
            text = f.read()

    try:
        cfg = yaml.safe_load(text) or {}
        if not isinstance(cfg, dict):
            cfg = {}
    except Exception:
        cfg = _parse_yaml_fallback(text)

    flat = _flatten_grouped(cfg)
    return _split_power_and_debt(flat)

# --- BEGIN AUTO-SHIM ---
def load_config(path_or_dict):
    """Very small loader that accepts a dict or YAML path."""
    if isinstance(path_or_dict, dict):
        return dict(path_or_dict)
    try:
        from pathlib import Path
        import yaml  # optional; if missing, use a naive parser
        p = Path(path_or_dict)
        with p.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        # ultra-naive key: value loader
        data = {}
        with open(path_or_dict, "r", encoding="utf-8") as f:
            for line in f:
                if ":" in line:
                    k, v = line.split(":", 1)
                    data[k.strip()] = v.strip()
        return data
# --- END AUTO-SHIM ---
