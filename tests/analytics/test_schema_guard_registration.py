"""Regression: schema validation must register field specs deterministically.

Two latent defects motivated these tests:

1. ``schema_guard._MODULE_IMPORTS`` mapped the logical ``"cashflow"`` module to a
   single Python module (``finance.cashflow_v14``). But the EPC capex specs
   (``epc_usd_total`` and friends) are registered by ``finance.epc_helper_v14``,
   which was *not* mapped. So ``_ensure_module_registered("cashflow")`` never
   registered ``epc_usd_total`` unless ``epc_helper_v14`` happened to be imported
   already — silently turning a REQUIRED/error-severity check into a no-op. This
   was order-dependent (a fresh process skipped it) and only surfaced when an
   unrelated test ran the pipeline first.

2. The ``epc_usd_total`` spec listed only three paths, while the resolvers that
   actually feed the cashflow (``debt_v14._extract_capex_usd`` /
   ``metrics._derive_capex_usd``) honour a much broader set
   (``finance.capex_total_usd``, ``capex.total_capex_usd``, ``costs.*`` ...).
   Once (1) was fixed, strict mode would have rejected real configs the engine
   reads fine. The spec now mirrors those resolvers.

The first test runs in a *fresh* interpreter (like the cold-import guard) so the
registry genuinely starts empty — that is the only place the ordering bug bites.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from analytics.schema_guard import ConfigValidationError, validate_config_for_v14

REPO_ROOT = Path(__file__).resolve().parents[2]


# A complete, schema-valid v14 config whose capex is supplied via the
# finance.capex_total_usd alias (NOT the canonical capex.usd_total). The engine
# resolves capex from this path, so strict validation must accept it too.
def _valid_config() -> dict:
    return {
        "project": {
            "name": "schema_reg_test",
            "capacity_mw": 100.0,
            "capacity_factor_pct": 35.0,
            "project_life_years": 25,
        },
        "wind": {"weibull_k": 2.0, "weibull_lambda": 8.5, "hub_height_m": 120.0},
        "finance": {"capex_total_usd": 200e6, "discount_rate_pct": 8.0},
        "tariff": {"lkr_per_kwh": 24.0},
        "opex": {"usd_per_year": 5e6},
        "tax": {
            "corporate_tax_rate": 0.30,
            "depreciation_method": "straight_line",
            "depreciation_start_year": 1,
            "depreciation_years": 15,
            "enhanced_allowance_applies": False,
            "enhanced_capital_allowance_pct": 1.0,
            "loss_carryforward_years": 25,
            "tax_holiday_start_year": 1,
            "tax_holiday_years": 0,
            "wht_on_interest_to_nonresidents": 0.0,
            "wht_on_interest_enabled": False,
            "wht_gross_up": False,
        },
        "fx": {"start_lkr_per_usd": 300.0, "annual_depr": 0.02},
        "debt": {"target_dscr": 1.4, "interest_rate_pct": 6.0, "term_years": 18},
    }


def test_cashflow_validation_registers_epc_specs_in_fresh_process() -> None:
    """A fresh process must register epc_usd_total when validating "cashflow".

    The EPC specs live in finance.epc_helper_v14, not finance.cashflow_v14, so
    _ensure_module_registered("cashflow") must import BOTH. The assertions run in
    a subprocess so the registry truly starts empty (the only state in which the
    omission was observable).
    """
    code = (
        "import sys\n"
        "import analytics.schema_guard as sg\n"
        "from analytics.config_schema import get_required_fields\n"
        "assert 'finance.epc_helper_v14' not in sys.modules, 'epc_helper eagerly imported'\n"
        "sg._ensure_module_registered('cashflow')\n"
        "specs = {s.name: s for s in get_required_fields('cashflow')}\n"
        "assert 'epc_usd_total' in specs, sorted(specs)\n"
        "paths = {'.'.join(p) for p in specs['epc_usd_total'].paths}\n"
        "need = {'capex.usd_total', 'finance.capex_total_usd', 'capex.total_capex_usd'}\n"
        "assert need <= paths, sorted(paths)\n"
        "print('OK')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPO_ROOT,
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT)},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"


def test_strict_validation_accepts_capex_total_usd_alias() -> None:
    """A config supplying capex via finance.capex_total_usd must validate."""
    validate_config_for_v14(_valid_config(), "<test>", ["cashflow", "debt"])


def test_strict_validation_rejects_missing_capex() -> None:
    """With the EPC specs now deterministically registered, a config with NO
    resolvable capex must fail strict validation on epc_usd_total."""
    cfg = _valid_config()
    cfg["finance"].pop("capex_total_usd")
    with pytest.raises(ConfigValidationError, match="epc_usd_total"):
        validate_config_for_v14(cfg, "<test>", ["cashflow", "debt"])
