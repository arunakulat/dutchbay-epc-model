"""Strict opt-in native-currency flat CAPEX conversion and provenance."""

from __future__ import annotations

import copy
import math
from datetime import date
from typing import Any, Mapping


def _number(value: Any, path: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value <= 0
    ):
        raise ValueError(f"{path} must be a finite positive number")
    return float(value)


def _date(value: Any, path: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{path} must be an ISO date YYYY-MM-DD")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{path} must be an ISO date YYYY-MM-DD") from exc
    if parsed.isoformat() != value:
        raise ValueError(f"{path} must be an ISO date YYYY-MM-DD")
    return value


def _unique(mapping: Mapping[str, Any], path: str) -> None:
    keys = [k.lower() for k in mapping if isinstance(k, str)]
    if len(keys) != len(set(keys)):
        raise ValueError(f"{path} contains duplicate case variants")


def normalize_native_capex(config: Mapping[str, Any]) -> dict[str, Any]:
    """Resolve native CAPEX to USD once, preserving its declared provenance.

    Conversion FX must be explicitly declared as the financial-close rate, dated
    at that close, and equal the model's close spot. No source is authenticated.
    """
    cap_names = [k for k in config if isinstance(k, str) and k.lower() == "capex"]
    if not cap_names:
        return dict(config)
    candidates = [config[k] for k in cap_names if isinstance(config[k], Mapping)]
    if not any(
        any(
            isinstance(k, str) and k.lower() in {"input", "native_input_applied"}
            for k in c
        )
        for c in candidates
    ):
        return dict(config)
    _unique(config, "config")
    cap = config[cap_names[0]]
    _unique(cap, "capex")
    names = {k.lower(): k for k in cap if isinstance(k, str)}
    if cap_names[0] != "capex" or any(
        names.get(k, k) != k for k in ("input", "native_input_applied")
    ):
        raise ValueError("native CAPEX requires canonical lowercase capex.input keys")
    if "input" in cap and "native_input_applied" in cap:
        raise ValueError(
            "capex.input conflicts with already resolved native input; start from the authored config"
        )
    applied = cap.get("native_input_applied")
    if applied is not None:
        if not isinstance(applied, Mapping) or set(applied) != {
            "input",
            "usd_at_price_date",
        }:
            raise ValueError("invalid capex.native_input_applied provenance")
        block = applied["input"]
    else:
        block = cap.get("input")
    if not isinstance(block, Mapping):
        raise ValueError("capex.input must be a mapping")
    _unique(block, "capex.input")
    if set(block) != {
        "currency",
        "amount",
        "price_date",
        "conversion",
        "financial_close_date",
    }:
        raise ValueError(
            "capex.input requires exactly currency, amount, price_date, conversion and financial_close_date"
        )
    currency = block["currency"]
    if currency not in ("LKR", "USD"):
        raise ValueError("capex.input.currency must be LKR or USD")
    amount = _number(block["amount"], "capex.input.amount")
    price_date = _date(block["price_date"], "capex.input.price_date")
    close_date = _date(
        block["financial_close_date"], "capex.input.financial_close_date"
    )
    project = config.get("project")
    if isinstance(project, Mapping) and project.get("cod_year") is not None:
        from finance.debt_v14 import _resolve_construction_periods

        if int(close_date[:4]) != project["cod_year"] - _resolve_construction_periods(
            dict(config)
        ):
            raise ValueError(
                "capex.input.financial_close_date must match the model financial-close year"
            )
    if price_date > close_date:
        raise ValueError("capex.input.price_date cannot be after financial close")
    if applied is None and "price_basis_applied" in cap:
        raise ValueError(
            "capex.input cannot coexist with an applied price basis; use the authored config"
        )
    if "price_basis" in cap and "price_basis_applied" in cap:
        raise ValueError("capex.price_basis cannot coexist with price_basis_applied")
    if "cost_basis_year" in cap and cap["cost_basis_year"] != int(price_date[:4]):
        raise ValueError("capex.cost_basis_year must match capex.input.price_date")
    conversion = block["conversion"]
    if not isinstance(conversion, Mapping):
        raise ValueError("capex.input.conversion must be a mapping")
    _unique(conversion, "capex.input.conversion")
    if set(conversion) != {"rate_lkr_per_usd", "date", "source", "basis"}:
        raise ValueError(
            "capex.input.conversion requires rate_lkr_per_usd, date, source and basis"
        )
    rate = _number(
        conversion["rate_lkr_per_usd"], "capex.input.conversion.rate_lkr_per_usd"
    )
    if (
        conversion["basis"] != "financial_close"
        or _date(conversion["date"], "capex.input.conversion.date") != close_date
    ):
        raise ValueError(
            "capex.input.conversion must be the dated financial_close rate, not a quote-date rate"
        )
    if not isinstance(conversion["source"], str) or not conversion["source"].strip():
        raise ValueError(
            "capex.input.conversion.source must be a non-empty provenance string"
        )
    fx = config.get("fx")
    if not isinstance(fx, Mapping):
        raise ValueError(
            "capex.input requires fx.start_lkr_per_usd as the financial-close spot"
        )
    _unique(fx, "fx")
    spot = _number(fx.get("start_lkr_per_usd"), "fx.start_lkr_per_usd")
    if spot != rate:
        raise ValueError(
            "capex.input conversion rate must equal fx.start_lkr_per_usd at financial close"
        )
    aliases = {
        "usd_total",
        "epc_usd",
        "capex_total_usd",
        "total_capex_usd",
        "total_capex",
        "lkr_total",
    }
    forbidden = aliases | {
        "derive_from_breakdown",
        "breakdown",
        "contingency",
        "contingency_pct",
        "freight_pct",
    }
    for key in names:
        if key in forbidden and not (applied is not None and key == "usd_total"):
            raise ValueError(f"capex.{names[key]} conflicts with capex.input")
        if ("capex" in key or key.endswith(("_usd", "_lkr"))) and key not in {
            "native_input_applied",
            "cost_basis_year",
            "usd_total",
        }:
            raise ValueError(
                f"unsupported monetary key capex.{names[key]} with capex.input"
            )
    for section, keys in (
        ("finance", {"capex_total_usd", "capex_usd"}),
        ("costs", {"capex_total_usd", "capex_usd", "total_capex_usd", "total_capex"}),
        ("project", {"capex_usd", "capex_total_usd", "total_capex_usd"}),
    ):
        for name, value in config.items():
            if (
                isinstance(name, str)
                and name.lower() == section
                and isinstance(value, Mapping)
            ):
                _unique(value, name)
                if any(
                    isinstance(k, str)
                    and (
                        k.lower() in keys
                        or (
                            "capex" in k.lower()
                            and ("lkr" in k.lower() or "usd" in k.lower())
                        )
                    )
                    for k in value
                ):
                    raise ValueError(f"{name} CAPEX alias conflicts with capex.input")
    if any(
        isinstance(k, str)
        and "capex" in k.lower()
        and ("lkr" in k.lower() or "usd" in k.lower())
        for k in config
    ):
        raise ValueError("top-level CAPEX alias conflicts with capex.input")
    basis = cap.get("price_basis", cap.get("price_basis_applied"))
    if basis is not None:
        if not isinstance(basis, Mapping) or basis.get("price_year") != int(
            price_date[:4]
        ):
            raise ValueError(
                "capex.input.price_date must match capex.price_basis.price_year"
            )
    usd = amount / rate if currency == "LKR" else amount
    if not math.isfinite(usd) or usd <= 0:
        raise ValueError("capex.input resolves to a nonfinite or zero USD amount")
    if applied is not None:
        if applied["usd_at_price_date"] != usd:
            raise ValueError(
                "native CAPEX provenance is stale; start from the authored config"
            )
        factor = 1.0
        if "price_basis_applied" in cap:
            factor = cap["price_basis_applied"].get("factor")
            factor = _number(factor, "capex.price_basis_applied.factor")
        if cap.get("usd_total") != usd * factor:
            raise ValueError(
                "native CAPEX resolved USD is stale; override capex.input.amount before normalization"
            )
        return dict(config)
    out = copy.deepcopy(dict(config))
    out_cap = out["capex"]
    out_cap.pop("input")
    out_cap["usd_total"] = usd
    out_cap["native_input_applied"] = {
        "input": copy.deepcopy(dict(block)),
        "usd_at_price_date": usd,
    }
    return out
