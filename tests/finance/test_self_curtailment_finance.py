"""D6b (#885) — finance loss-key wiring of ONLY the self-curtailment fraction.

The SOLE KPI-mover of grid-epic #870, built DEFAULT-OFF. This suite pins, at Fable grade:

  1. **Default-off byte-identity.** With no ``grid.qsts.finance_wiring`` opt-in (every
     committed scenario), the composed ``curtailment_pct`` and the full-pipeline KPIs are
     byte-identical to the pre-D6b canon.
  2. **Only self-curtailment reaches finance.** The deemed-paid / grid-instructed fraction
     NEVER haircuts revenue (CEB SPPA): a result with a large ``deemed_paid_pct`` but zero
     ``self_curtailed_pct`` moves NOTHING.
  3. **The oracle diff.** With the opt-in ON and a canonical-contract test-double fraction,
     KPIs MOVE in the correct direction (projIRR / eqIRR / min_dscr all DOWN), with a
     magnitude tied to the self-curtailment fraction — a real, correctly-signed delta, not
     a trivially-true assertion.

The resolver's own unit behaviour (gating, deemed-paid exclusion, range guards, the
multiplicative composition) is covered directly; the KPI oracle drives the FULL pipeline.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, Dict

import pytest

from analytics.contracts_v14 import CurtailmentShareResult
from analytics.scenario_loader import load_scenario_config
from finance.self_curtailment_v14 import (
    FINANCE_WIRING_ENABLED_PATH,
    compose_curtailment,
    resolve_self_curtailment_decimal,
    self_curtailment_finance_wiring_enabled,
)
from tests._canon import LENDER_EQUITY_IRR as CANON_EQ_IRR
from tests._canon import LENDER_MIN_DSCR as CANON_MIN_DSCR
from tests._canon import LENDER_PROJECT_IRR as CANON_PROJ_IRR

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER = str(REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml")

# Committed 5th-gen canon (single source of truth: tests/_canon.py, #955).


_DECLARED_SITE_MODEL_PATH = "/test-double/declared-site-model.dss"


def _canonical_result_test_double(
    self_pct: float, *, deemed_pct: float = 0.0
) -> CurtailmentShareResult:
    """In-memory canonical-contract double; it is not project or lender evidence."""
    return CurtailmentShareResult(
        ran=True,
        feeder_source=_DECLARED_SITE_MODEL_PATH,
        feeder_input_kind="engineer_prepared_site_model",
        generated_input=False,
        observed_network_data=False,
        site_representative=True,
        canonical_finance_eligible=True,
        export_cap_mw=150.0,
        gross_energy_mwh=100_000.0,
        curtailed_total_mwh=(self_pct + deemed_pct) / 100.0 * 100_000.0,
        deemed_paid_energy_mwh=deemed_pct / 100.0 * 100_000.0,
        self_curtailed_pre_bess_mwh=self_pct / 100.0 * 100_000.0,
        bess_absorbed_energy_mwh=0.0,
        self_curtailed_energy_mwh=self_pct / 100.0 * 100_000.0,
        deemed_paid_pct=deemed_pct,
        self_curtailed_pct=self_pct,
        hours_self_curtailed=100,
        hours_total=8760,
        bankable=False,
        reason="canonical contract test double only; no site or lender evidence",
    )


def _enable_wiring(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Add the explicit finance-wiring opt-in + a real-feeder QSTS gate to a config dict."""
    grid = cfg.setdefault("grid", {})
    qsts = grid.setdefault("qsts", {})
    qsts["enabled"] = True
    qsts["input_kind"] = "engineer_prepared_site_model"
    qsts["feeder_model_path"] = _DECLARED_SITE_MODEL_PATH
    qsts["finance_wiring"] = {
        "enabled": True,
        "mode": "canonical",
        "canonical_eligible": True,
    }
    return cfg


# ─────────────────────────────────────────────────────────────────────────────
# 1. The opt-in switch — strict, literal True only (CESSPIT)
# ─────────────────────────────────────────────────────────────────────────────


def test_finance_wiring_path_documented() -> None:
    assert FINANCE_WIRING_ENABLED_PATH == "grid.qsts.finance_wiring.enabled"


def test_wiring_disabled_by_default_and_on_committed_lendercase() -> None:
    assert self_curtailment_finance_wiring_enabled(None) is False
    assert self_curtailment_finance_wiring_enabled({}) is False
    # The committed lendercase has a grid block but NO finance_wiring opt-in.
    assert (
        self_curtailment_finance_wiring_enabled(load_scenario_config(LENDER)) is False
    )


@pytest.mark.parametrize("truthy", [1, "true", "True", "yes", [1]])
def test_wiring_requires_literal_true_not_merely_truthy(truthy: object) -> None:
    cfg = {"grid": {"qsts": {"finance_wiring": {"enabled": truthy}}}}
    assert self_curtailment_finance_wiring_enabled(cfg) is False


def test_wiring_enabled_only_on_literal_true() -> None:
    cfg = {"grid": {"qsts": {"finance_wiring": {"enabled": True}}}}
    assert self_curtailment_finance_wiring_enabled(cfg) is True


@pytest.mark.parametrize(
    "cfg",
    [
        {"grid": "not-a-mapping"},
        {"grid": {"qsts": "not-a-mapping"}},
        {"grid": {"qsts": {"finance_wiring": "not-a-mapping"}}},
    ],
)
def test_wiring_tolerates_malformed_blocks(cfg: Dict[str, Any]) -> None:
    assert self_curtailment_finance_wiring_enabled(cfg) is False


# ─────────────────────────────────────────────────────────────────────────────
# 2. The resolver — ONLY self-curtailment, deemed-paid excluded, NO spurious pass
# ─────────────────────────────────────────────────────────────────────────────


def test_resolver_zero_when_wiring_off_even_with_canonical_test_double() -> None:
    """Opt-in OFF ⇒ 0.0 no matter how large the self-curtailment (default-off dominates)."""
    result = _canonical_result_test_double(self_pct=12.0)
    assert resolve_self_curtailment_decimal({}, result) == 0.0
    assert resolve_self_curtailment_decimal({"grid": {"qsts": {}}}, result) == 0.0


def test_resolver_reads_only_self_curtailment_not_deemed_paid() -> None:
    """A huge deemed-paid share with ZERO self-curtailment moves NOTHING (CEB SPPA)."""
    cfg = _enable_wiring({})
    deemed_heavy = _canonical_result_test_double(self_pct=0.0, deemed_pct=40.0)
    assert resolve_self_curtailment_decimal(cfg, deemed_heavy) == 0.0


def test_resolver_returns_self_fraction_when_enabled() -> None:
    cfg = _enable_wiring({})
    assert resolve_self_curtailment_decimal(
        cfg, _canonical_result_test_double(7.5)
    ) == pytest.approx(0.075)


def test_resolver_refuses_inert_notrun_result() -> None:
    """Opt-in set but the QSTS did not run (inert, energy None) ⇒ 0.0 (NO SPURIOUS PASS)."""
    cfg = _enable_wiring({})
    inert = CurtailmentShareResult(ran=False, feeder_source="none")
    assert resolve_self_curtailment_decimal(cfg, inert) == 0.0
    assert resolve_self_curtailment_decimal(cfg, None) == 0.0


def test_resolver_refuses_none_self_pct_when_ran_but_field_missing() -> None:
    cfg = _enable_wiring({})
    ran_but_none = replace(_canonical_result_test_double(8.0), self_curtailed_pct=None)
    with pytest.raises(ValueError, match="silent zero-loss pass"):
        resolve_self_curtailment_decimal(cfg, ran_but_none)


@pytest.mark.parametrize("nonfinite", [float("nan"), float("inf"), float("-inf")])
def test_resolver_refuses_nonfinite_self_pct_when_ran(nonfinite: float) -> None:
    cfg = _enable_wiring({})
    malformed = replace(
        _canonical_result_test_double(8.0), self_curtailed_pct=nonfinite
    )
    with pytest.raises(ValueError, match="must be finite"):
        resolve_self_curtailment_decimal(cfg, malformed)


def test_result_contract_preserves_legacy_positional_field_order() -> None:
    legacy = CurtailmentShareResult(True, "/legacy/feeder.dss", 150.0, 1_000.0)
    assert legacy.ran is True
    assert legacy.feeder_source == "/legacy/feeder.dss"
    assert legacy.export_cap_mw == 150.0
    assert legacy.gross_energy_mwh == 1_000.0
    assert legacy.feeder_input_kind is None


def test_resolver_refuses_synthetic_result_even_when_finance_flag_is_on() -> None:
    # Use a valid canonical configuration so this exercises the independent RESULT gate,
    # not merely the surrounding configuration gate.
    cfg = _enable_wiring({})
    synthetic = CurtailmentShareResult(
        ran=True,
        feeder_source="/fixtures/issue923.dss",
        feeder_input_kind="synthetic_placeholder",
        generated_input=True,
        site_representative=False,
        canonical_finance_eligible=False,
        source_manifest_sha256="a" * 64,
        self_curtailed_pct=8.0,
    )
    with pytest.raises(ValueError, match="noncanonical feeder result"):
        resolve_self_curtailment_decimal(cfg, synthetic)


@pytest.mark.parametrize(
    "qsts_patch",
    [
        {},
        {
            "enabled": True,
            "input_kind": "synthetic_placeholder",
            "feeder_model_path": "/fixtures/issue923.dss",
            "finance_wiring": {
                "enabled": True,
                "mode": "synthetic_counterfactual",
                "canonical_eligible": False,
            },
        },
        {
            "enabled": True,
            "input_kind": "engineer_prepared_site_model",
            "feeder_model_path": "/feeders/site.dss",
            "finance_wiring": {"enabled": True},
        },
        {
            "enabled": True,
            "input_kind": ["engineer_prepared_site_model"],
            "feeder_model_path": "/feeders/site.dss",
            "finance_wiring": {
                "enabled": True,
                "mode": "canonical",
                "canonical_eligible": True,
            },
        },
        {
            "enabled": True,
            "input_kind": "engineer_prepared_site_model",
            "use_synthetic_demo": True,
            "feeder_model_path": "/feeders/site.dss",
            "finance_wiring": {
                "enabled": True,
                "mode": "canonical",
                "canonical_eligible": True,
            },
        },
        {
            "enabled": True,
            "input_kind": "engineer_prepared_site_model",
            "use_synthetic_demo": "true",
            "feeder_model_path": "/feeders/site.dss",
            "finance_wiring": {
                "enabled": True,
                "mode": "canonical",
                "canonical_eligible": True,
            },
        },
    ],
)
def test_resolver_rechecks_canonical_config_for_direct_callers(
    qsts_patch: Dict[str, Any],
) -> None:
    cfg = {"grid": {"qsts": qsts_patch or {"finance_wiring": {"enabled": True}}}}
    with pytest.raises(ValueError, match="canonical finance configuration refused"):
        resolve_self_curtailment_decimal(cfg, _canonical_result_test_double(8.0))


def test_resolver_refuses_result_source_mismatch() -> None:
    cfg = _enable_wiring({})
    mismatched = replace(
        _canonical_result_test_double(8.0), feeder_source="/other/model.dss"
    )
    with pytest.raises(ValueError, match="noncanonical feeder result"):
        resolve_self_curtailment_decimal(cfg, mismatched)


def test_contract_requires_observed_flag_for_utility_observed_kind() -> None:
    with pytest.raises(ValueError, match="requires observed_network_data=true"):
        replace(
            _canonical_result_test_double(8.0),
            feeder_input_kind="utility_observed_model",
            observed_network_data=False,
        )


@pytest.mark.parametrize(
    ("field", "bad_value"),
    [
        ("ran", 1),
        ("generated_input", 0),
        ("site_representative", 1),
        ("canonical_finance_eligible", 1),
    ],
)
def test_contract_refuses_nonboolean_result_flags(
    field: str, bad_value: object
) -> None:
    with pytest.raises(ValueError, match="literal boolean"):
        replace(_canonical_result_test_double(8.0), **{field: bad_value})


def test_contract_refuses_contradictory_synthetic_provenance_serialization() -> None:
    with pytest.raises(ValueError, match="Synthetic/test.*contradictory"):
        CurtailmentShareResult(
            ran=True,
            feeder_source="/generated/issue923.dss",
            feeder_input_kind="synthetic_placeholder",
            generated_input=False,
            observed_network_data=True,
            site_representative=True,
            canonical_finance_eligible=True,
            bankable=True,
            self_curtailed_pct=8.0,
        )


def test_resolver_refuses_boolean_self_curtailment_percentage() -> None:
    cfg = _enable_wiring({})
    malformed = replace(_canonical_result_test_double(8.0), self_curtailed_pct=True)
    with pytest.raises(ValueError, match="must be a real finite number"):
        resolve_self_curtailment_decimal(cfg, malformed)


def test_resolver_rejects_negative_or_full_shed() -> None:
    cfg = _enable_wiring({})
    with pytest.raises(ValueError, match="negative"):
        resolve_self_curtailment_decimal(cfg, _canonical_result_test_double(-1.0))
    with pytest.raises(ValueError, match="entire plant"):
        resolve_self_curtailment_decimal(cfg, _canonical_result_test_double(100.0))


# ─────────────────────────────────────────────────────────────────────────────
# 3. compose_curtailment — multiplicative, byte-identical at zero
# ─────────────────────────────────────────────────────────────────────────────


def test_compose_is_byte_identical_at_zero_self() -> None:
    for config_c in (0.0, 0.02, 0.08):
        assert compose_curtailment(config_c, 0.0) == config_c  # exact IEEE identity


def test_compose_is_multiplicative_not_additive() -> None:
    # 1 - (1-0.05)(1-0.10) = 0.145, NOT 0.15 (no double-count).
    assert compose_curtailment(0.05, 0.10) == pytest.approx(0.145)


def test_compose_range_guards() -> None:
    with pytest.raises(ValueError):
        compose_curtailment(1.0, 0.0)
    with pytest.raises(ValueError):
        compose_curtailment(0.0, 1.0)


# ─────────────────────────────────────────────────────────────────────────────
# 4. Default-off byte-identity through _build_cashflow_params
# ─────────────────────────────────────────────────────────────────────────────


def test_build_params_curtailment_byte_identical_default_off() -> None:
    from finance.cashflow_v14_params import _build_cashflow_params

    base = load_scenario_config(LENDER)
    assert (
        _build_cashflow_params(base).curtailment_pct == 0.0
    )  # canon default, untouched


def test_build_params_composes_self_curtailment_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With the opt-in on + a real 10% self-curtailment, curtailment_pct becomes 0.10."""
    import finance.cashflow_v14_params as params_mod

    monkeypatch.setattr(
        "analytics.grid.curtailment_qsts.run_qsts_curtailment",
        lambda _cfg: _canonical_result_test_double(10.0, deemed_pct=25.0),
    )
    cfg = _enable_wiring(load_scenario_config(LENDER))
    built = params_mod._build_cashflow_params(cfg)
    # config curtailment_pct is 0.0, so composed == self fraction exactly.
    assert built.curtailment_pct == pytest.approx(0.10)


# ─────────────────────────────────────────────────────────────────────────────
# 5. THE ORACLE DIFF — full-pipeline KPIs move DOWN, correctly signed
# ─────────────────────────────────────────────────────────────────────────────


def _run_kpis(cfg: Dict[str, Any]) -> Dict[str, float]:
    from analytics.pipeline_v14_enhanced import run_v14_pipeline

    kpis: Dict[str, float] = run_v14_pipeline(config=cfg, validation_mode="strict")[
        "kpis"
    ]
    return kpis


def test_oracle_default_off_matches_committed_canon() -> None:
    """Sanity anchor: the untouched lendercase reproduces the pinned 5th-gen canon."""
    kpis = _run_kpis(load_scenario_config(LENDER))
    assert kpis["project_irr"] == pytest.approx(CANON_PROJ_IRR, abs=1e-9)
    assert kpis["equity_irr"] == pytest.approx(CANON_EQ_IRR, abs=1e-9)
    assert kpis["min_dscr"] == pytest.approx(CANON_MIN_DSCR, abs=1e-9)


def test_oracle_self_curtailment_moves_kpis_down_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The KPI oracle diff: a canonical-contract 8% test double
    reduces net energy → CFADS, so projIRR / eqIRR / min_dscr all move DOWN, and the
    committed default stays byte-identical. This is the sole authorized KPI move.
    """
    monkeypatch.setattr(
        "analytics.grid.curtailment_qsts.run_qsts_curtailment",
        # 8% contract-oracle self-curtailment + a LARGE 30% deemed-paid share that must not bite.
        lambda _cfg: _canonical_result_test_double(8.0, deemed_pct=30.0),
    )

    before = _run_kpis(load_scenario_config(LENDER))  # default-off canon
    after = _run_kpis(_enable_wiring(load_scenario_config(LENDER)))  # wiring ON

    # Before == the pinned canon (default-off leaks nowhere).
    assert before["project_irr"] == pytest.approx(CANON_PROJ_IRR, abs=1e-9)
    assert before["equity_irr"] == pytest.approx(CANON_EQ_IRR, abs=1e-9)
    assert before["min_dscr"] == pytest.approx(CANON_MIN_DSCR, abs=1e-9)

    # After: a strictly-worse, correctly-signed contract-oracle move on every headline KPI.
    assert after["project_irr"] < before["project_irr"] - 1e-6
    assert after["equity_irr"] < before["equity_irr"] - 1e-6
    assert after["min_dscr"] < before["min_dscr"] - 1e-6
    assert after["total_cfads_usd"] < before["total_cfads_usd"]  # less net energy
    assert after["project_npv"] < before["project_npv"]


def test_oracle_deemed_paid_alone_does_not_move_kpis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Proof deemed-paid never haircuts revenue: a result with 35% deemed-paid but ZERO
    self-curtailment leaves the KPIs byte-identical to the default-off canon even with the
    finance wiring ENABLED.
    """
    monkeypatch.setattr(
        "analytics.grid.curtailment_qsts.run_qsts_curtailment",
        lambda _cfg: _canonical_result_test_double(0.0, deemed_pct=35.0),
    )
    kpis = _run_kpis(_enable_wiring(load_scenario_config(LENDER)))
    assert kpis["project_irr"] == pytest.approx(CANON_PROJ_IRR, abs=1e-9)
    assert kpis["equity_irr"] == pytest.approx(CANON_EQ_IRR, abs=1e-9)
    assert kpis["min_dscr"] == pytest.approx(CANON_MIN_DSCR, abs=1e-9)


def test_oracle_magnitude_scales_with_self_curtailment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A larger self-curtailment fraction moves projIRR strictly further down — the delta
    is tied to the fraction, not a fixed spurious offset.
    """

    def _kpis_for(self_pct: float) -> Dict[str, float]:
        monkeypatch.setattr(
            "analytics.grid.curtailment_qsts.run_qsts_curtailment",
            lambda _cfg: _canonical_result_test_double(self_pct),
        )
        return _run_kpis(_enable_wiring(load_scenario_config(LENDER)))

    small = _kpis_for(4.0)
    large = _kpis_for(12.0)
    assert large["project_irr"] < small["project_irr"] - 1e-6
    assert large["min_dscr"] < small["min_dscr"] - 1e-6
