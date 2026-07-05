"""#738: import levies + indirect-tax (VAT) config — mechanism tests.

Covers the single uplift source (``finance.import_levies``):

- pure cascade arithmetic per line (CID / PAL / SSCL on the import base; VAT on
  the duties-inclusive base, optionally on the full capex) and every relief
  toggle zeroing exactly its lines;
- CESSPIT fail-loud resolution (strict decimals, unknown-key rejection) and the
  pre-flight schema guard delegating to the SAME resolver (guard == engine);
- absent-block / zero-block byte-identity (the feature is inert until a
  scenario opts in);
- single-source consistency with levies ON: the debt engine, the NPV base and
  the equity base resolve the identical LEVY-INCLUSIVE gross; the depreciable
  base grosses the same uplift at year-0 FX; sources & uses disclose the levy
  share inside the gross capex line and still balance;
- opex VAT: applied to the escalated USD figure inside the one shared helper,
  tax-deductible via the EBITDA line, relieved toggle restores byte-identity;
- the capex Monte Carlo perturbs the PRE-LEVY base (no double count);
- breakdown/QRA interplay: the 0.5% breakdown-vs-usd_total cross-check operates
  on the PRE-levy base (no tolerance interaction).
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Dict

import pytest

from analytics.pipeline_v14_enhanced import run_v14_pipeline
from analytics.scenario_loader import load_scenario_config
from analytics.schema_guard import ConfigValidationError, validate_config_for_v14
from finance.cashflow_v14 import build_annual_rows
from finance.debt_v14 import _extract_capex_base_usd, _extract_capex_usd
from finance.import_levies import (
    IndirectTaxes,
    capex_uplift_from_config,
    capex_uplift_lines_usd,
    compute_capex_uplift_usd,
    has_taxes_indirect,
    resolve_indirect_taxes,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER = str(REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml")

# The verified 2026 SL stack for wind gensets (HS 8502.31): CID Free, PAL 5%,
# SSCL-on-imports 2.5%, unrecoverable VAT 18% (exempt supply => no input credit).
PRUDENT_BLOCK: Dict[str, Any] = {
    "import_share_pct": 0.69,
    "cid_pct": 0.0,
    "pal_pct": 0.05,
    "sscl_import_pct": 0.025,
    "vat_capex_pct": 0.18,
    "vat_on_full_capex": False,
    "vat_on_duties": True,
    "vat_opex_pct": 0.18,
    "relief": {
        "bonded_scheme": False,
        "vat_capex_relieved": True,  # BOI s.17 / bonded route (SINOHYDRO precedent)
        "vat_opex_relieved": False,
    },
}


def _levied_lender_config(block: Dict[str, Any]) -> Dict[str, Any]:
    """The committed lender case with a (replaced) taxes_indirect overlay."""
    cfg = copy.deepcopy(dict(load_scenario_config(LENDER)))
    cfg["taxes_indirect"] = copy.deepcopy(block)
    return cfg


def _stripped_lender_config() -> Dict[str, Any]:
    """The committed lender case with any taxes_indirect block removed."""
    cfg = copy.deepcopy(dict(load_scenario_config(LENDER)))
    cfg.pop("taxes_indirect", None)
    return cfg


def _resolve(block: Dict[str, Any]) -> IndirectTaxes:
    it = resolve_indirect_taxes({"taxes_indirect": block})
    assert it is not None
    return it


# --------------------------------------------------------------------------- #
# 1. Pure cascade arithmetic
# --------------------------------------------------------------------------- #


def test_prudent_cascade_lines_hand_check() -> None:
    """duties = 159.6M x 0.69 x (5% + 2.5%) = 8.2593M; VAT relieved -> 0."""
    it = _resolve(PRUDENT_BLOCK)
    lines = capex_uplift_lines_usd(159_600_000.0, it)
    import_base = 159_600_000.0 * 0.69  # 110.124M (WTG-line anchor)
    assert lines["cid_usd"] == 0.0
    assert lines["pal_usd"] == pytest.approx(import_base * 0.05, rel=1e-12)
    assert lines["sscl_import_usd"] == pytest.approx(import_base * 0.025, rel=1e-12)
    assert lines["vat_capex_usd"] == 0.0  # relieved
    assert lines["total_usd"] == pytest.approx(8_259_300.0, rel=1e-12)
    assert compute_capex_uplift_usd(159_600_000.0, it) == lines["total_usd"]


def test_vat_paid_on_import_share_includes_duties_in_base() -> None:
    block = copy.deepcopy(PRUDENT_BLOCK)
    block["relief"]["vat_capex_relieved"] = False
    it = _resolve(block)
    base = 100_000_000.0
    import_base = 69_000_000.0
    duties = import_base * 0.075
    expected_vat = (import_base + duties) * 0.18
    lines = capex_uplift_lines_usd(base, it)
    assert lines["vat_capex_usd"] == pytest.approx(expected_vat, rel=1e-12)
    assert lines["total_usd"] == pytest.approx(duties + expected_vat, rel=1e-12)


def test_vat_on_duties_false_uses_cif_only_base() -> None:
    block = copy.deepcopy(PRUDENT_BLOCK)
    block["relief"]["vat_capex_relieved"] = False
    block["vat_on_duties"] = False
    it = _resolve(block)
    lines = capex_uplift_lines_usd(100_000_000.0, it)
    assert lines["vat_capex_usd"] == pytest.approx(69_000_000.0 * 0.18, rel=1e-12)


def test_vat_on_full_capex_adds_domestic_share() -> None:
    block = copy.deepcopy(PRUDENT_BLOCK)
    block["relief"]["vat_capex_relieved"] = False
    block["vat_on_full_capex"] = True
    it = _resolve(block)
    base = 100_000_000.0
    import_base = 69_000_000.0
    duties = import_base * 0.075
    expected_vat = (import_base + duties + (base - import_base)) * 0.18
    assert capex_uplift_lines_usd(base, it)["vat_capex_usd"] == pytest.approx(
        expected_vat, rel=1e-12
    )


def test_bonded_relief_zeroes_exactly_the_duty_lines() -> None:
    block = copy.deepcopy(PRUDENT_BLOCK)
    block["relief"]["bonded_scheme"] = True
    block["relief"]["vat_capex_relieved"] = False
    it = _resolve(block)
    lines = capex_uplift_lines_usd(100_000_000.0, it)
    assert lines["pal_usd"] == lines["sscl_import_usd"] == lines["cid_usd"] == 0.0
    # VAT survives the bonded toggle (different instruments) and its base
    # carries no duties (they are zero under the bonded scheme).
    assert lines["vat_capex_usd"] == pytest.approx(69_000_000.0 * 0.18, rel=1e-12)


def test_opex_vat_rate_respects_relief_toggle() -> None:
    it = _resolve(PRUDENT_BLOCK)
    assert it.opex_vat_rate == 0.18
    relieved = copy.deepcopy(PRUDENT_BLOCK)
    relieved["relief"]["vat_opex_relieved"] = True
    assert _resolve(relieved).opex_vat_rate == 0.0


def test_absent_block_resolves_none_and_zero_uplift() -> None:
    assert resolve_indirect_taxes({}) is None
    assert resolve_indirect_taxes(None) is None
    assert has_taxes_indirect({}) is False
    assert capex_uplift_from_config({}) == 0.0
    # opex-VAT-only block: no capex lines -> zero uplift WITHOUT resolving capex
    # (a capex-less cashflow config with only vat_opex_pct must not raise).
    assert capex_uplift_from_config({"taxes_indirect": {"vat_opex_pct": 0.18}}) == 0.0


# --------------------------------------------------------------------------- #
# 2. Fail-loud resolution (CESSPIT) + guard == resolver
# --------------------------------------------------------------------------- #

_BAD_BLOCKS = [
    pytest.param({"pal_pct": -0.01, "import_share_pct": 0.5}, "pal_pct", id="negative"),
    pytest.param(
        {"vat_capex_pct": 18, "import_share_pct": 0.5}, "vat_capex_pct", id="percent"
    ),
    pytest.param(
        {"pal_pct": 0.05, "import_share_pct": 1.5}, "import_share_pct", id="share-gt-1"
    ),
    pytest.param({"pal_pct": 0.05}, "import_share_pct", id="share-missing"),
    pytest.param({"pal_pcts": 0.05}, "pal_pcts", id="unknown-key"),
    pytest.param(
        {"pal_pct": 0.05, "import_share_pct": 0.5, "relief": {"bonded": True}},
        "bonded",
        id="unknown-relief-key",
    ),
    pytest.param(
        {"pal_pct": 0.05, "import_share_pct": 0.5, "relief": [1]},
        "relief",
        id="relief-not-mapping",
    ),
    pytest.param(
        {"pal_pct": 0.05, "import_share_pct": 0.5, "vat_on_duties": "yes"},
        "vat_on_duties",
        id="non-bool-flag",
    ),
    pytest.param("bonded", "taxes_indirect", id="block-not-mapping"),
]


@pytest.mark.parametrize(("block", "needle"), _BAD_BLOCKS)
def test_malformed_block_fails_loud_and_guard_reuses_the_resolver(
    block: Any, needle: str
) -> None:
    """The resolver raises naming the key; pre-flight collects the SAME message."""
    cfg = {"taxes_indirect": block}
    with pytest.raises(ValueError, match="taxes_indirect") as resolver_exc:
        resolve_indirect_taxes(cfg)
    assert needle in str(resolver_exc.value)

    # Guard equivalence (#733a pattern): validate_config_for_v14 must surface the
    # resolver's exact message — pre-flight and call-time can never disagree.
    guarded = {"fx": {"start_lkr_per_usd": 333.79, "annual_depr": 0.0589}, **cfg}
    with pytest.raises(ConfigValidationError) as guard_exc:
        validate_config_for_v14(guarded, "test-config", modules=[])
    assert str(resolver_exc.value) in str(guard_exc.value)


def test_valid_block_passes_the_guard() -> None:
    cfg = {
        "fx": {"start_lkr_per_usd": 333.79, "annual_depr": 0.0589},
        "taxes_indirect": PRUDENT_BLOCK,
    }
    validate_config_for_v14(cfg, "test-config", modules=[])  # must not raise


# --------------------------------------------------------------------------- #
# 3. Absent-block / zero-block byte-identity
# --------------------------------------------------------------------------- #


def test_zero_rate_block_builds_bit_identical_rows() -> None:
    """An all-zero block is inert: row-for-row identical to no block at all."""
    base_cfg = _stripped_lender_config()
    zero_cfg = copy.deepcopy(base_cfg)
    zero_cfg["taxes_indirect"] = {
        "import_share_pct": 0.69,
        "cid_pct": 0.0,
        "pal_pct": 0.0,
        "sscl_import_pct": 0.0,
        "vat_capex_pct": 0.0,
        "vat_opex_pct": 0.0,
    }
    rows_absent = build_annual_rows(copy.deepcopy(base_cfg))
    rows_zero = build_annual_rows(copy.deepcopy(zero_cfg))
    assert len(rows_absent) == len(rows_zero)
    for r_a, r_b in zip(rows_absent, rows_zero, strict=True):
        assert r_a == r_b


def test_relieved_everything_is_row_identical_to_no_block() -> None:
    """Full relief (bonded + both VAT reliefs) restores the levy-free rows."""
    base_cfg = _stripped_lender_config()
    relieved_cfg = copy.deepcopy(base_cfg)
    full_relief = copy.deepcopy(PRUDENT_BLOCK)
    full_relief["relief"] = {
        "bonded_scheme": True,
        "vat_capex_relieved": True,
        "vat_opex_relieved": True,
    }
    relieved_cfg["taxes_indirect"] = full_relief
    rows_absent = build_annual_rows(copy.deepcopy(base_cfg))
    rows_relieved = build_annual_rows(copy.deepcopy(relieved_cfg))
    for r_a, r_b in zip(rows_absent, rows_relieved, strict=True):
        assert r_a == r_b


# --------------------------------------------------------------------------- #
# 4. Single-source consistency with levies ON (the audit invariant)
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def levied_cfg() -> Dict[str, Any]:
    return _levied_lender_config(PRUDENT_BLOCK)


@pytest.fixture(scope="module")
def levied_result(levied_cfg: Dict[str, Any]) -> Dict[str, Any]:
    return run_v14_pipeline(config=copy.deepcopy(levied_cfg))


def test_three_resolvers_agree_on_the_levy_inclusive_gross(
    levied_cfg: Dict[str, Any],
) -> None:
    from analytics.core.metrics import _derive_capex_usd
    from finance.equity_distribution_v14_hydra import _extract_capex_usd as equity_capex

    it = resolve_indirect_taxes(levied_cfg)
    assert it is not None
    base = _extract_capex_base_usd(dict(levied_cfg))
    gross = base + compute_capex_uplift_usd(base, it)
    assert base == pytest.approx(159_600_000.0, rel=1e-12)  # pre-levy base intact
    assert _extract_capex_usd(dict(levied_cfg)) == gross
    assert _derive_capex_usd(levied_cfg) == gross
    assert equity_capex(levied_cfg) == gross
    # The opt-out returns the PRE-LEVY base (the MC seam).
    assert _extract_capex_usd(dict(levied_cfg), include_import_levies=False) == base
    assert capex_uplift_from_config(levied_cfg) == pytest.approx(
        gross - base, rel=1e-12
    )


def test_depreciable_base_grosses_the_same_uplift_at_year0_fx(
    levied_cfg: Dict[str, Any],
) -> None:
    """Year-1 depreciation delta == uplift x fx0 x (plant/5 + civil/20 shares)."""
    from finance.cashflow_v14_fx import _fx_curve

    uplift = capex_uplift_from_config(levied_cfg)
    assert uplift == pytest.approx(8_259_300.0, rel=1e-12)
    fx0 = _fx_curve(dict(levied_cfg), 20)[0]
    tax = levied_cfg["tax"]
    dep_rate = float(tax["plant_capex_share"]) / float(
        tax["plant_depreciation_years"]
    ) + (1.0 - float(tax["plant_capex_share"])) / float(tax["civil_depreciation_years"])
    rows_off = build_annual_rows(_stripped_lender_config())
    rows_on = build_annual_rows(copy.deepcopy(levied_cfg))
    delta = rows_on[0]["total_depreciation_lkr"] - rows_off[0]["total_depreciation_lkr"]
    # rows_off carries the opex-VAT-free line too, but depreciation is untouched
    # by opex VAT, so the year-1 delta isolates the capitalized uplift exactly.
    assert delta == pytest.approx(uplift * fx0 * dep_rate, rel=1e-9)


def test_sources_and_uses_disclose_the_levy_inside_gross_capex(
    levied_result: Dict[str, Any], levied_cfg: Dict[str, Any]
) -> None:
    debt = levied_result["debt_result"] or {}
    su = debt["funding"]["sources_and_uses"]
    uses = su["uses"]
    it = resolve_indirect_taxes(levied_cfg)
    assert it is not None
    base = _extract_capex_base_usd(dict(levied_cfg))
    uplift = compute_capex_uplift_usd(base, it)
    assert uses["capex_usd"] == pytest.approx(base + uplift, abs=0.01)
    assert uses["import_levies_usd"] == pytest.approx(uplift, abs=0.01)
    # Breakdown disclosure, NOT a new addend: uses_total is capex + IDC + DSRA.
    assert su["uses_total_usd"] == pytest.approx(
        uses["capex_usd"] + uses["idc_usd"] + uses["initial_dsra_usd"], abs=0.02
    )
    assert su["balanced"] is True
    # Equity funds the gross-minus-debt: sources == uses.
    assert su["sources_total_usd"] == pytest.approx(su["uses_total_usd"], abs=1.0)


def test_levies_move_the_economics_in_the_prudent_direction(
    levied_result: Dict[str, Any],
) -> None:
    """Directional signature vs the levy-free case: value down, sculpt holds 1.30."""
    on = levied_result["kpis"]
    off = run_v14_pipeline(config=_stripped_lender_config())["kpis"]
    assert on["project_irr"] < off["project_irr"]
    assert on["equity_irr"] < off["equity_irr"]
    assert on["project_npv"] < off["project_npv"]
    assert on["total_cfads_usd"] < off["total_cfads_usd"]  # opex VAT bites CFADS
    # The dual-DSCR sculpt re-solves: the per-period floor holds the 1.30 target.
    assert on["min_dscr_period"] == pytest.approx(1.30, abs=1e-6)


# --------------------------------------------------------------------------- #
# 5. Opex VAT — the one shared arithmetic site
# --------------------------------------------------------------------------- #


def test_opex_vat_multiplies_the_escalated_usd_figure(
    levied_cfg: Dict[str, Any],
) -> None:
    rows = build_annual_rows(copy.deepcopy(levied_cfg))
    for row in rows:
        # opex_usd is the PRE-VAT escalated USD figure; opex_lkr carries the VAT.
        assert row["opex_lkr"] == pytest.approx(
            row["opex_usd"] * 1.18 * row["fx_rate"], rel=1e-12
        )


def test_opex_vat_is_tax_deductible(levied_cfg: Dict[str, Any]) -> None:
    """The VAT-inflated opex reduces taxable income (EBITDA-line deduction)."""
    capex_only = copy.deepcopy(levied_cfg)
    capex_only["taxes_indirect"] = copy.deepcopy(PRUDENT_BLOCK)
    capex_only["taxes_indirect"]["relief"]["vat_opex_relieved"] = True
    rows_vat = build_annual_rows(copy.deepcopy(levied_cfg))
    rows_novat = build_annual_rows(capex_only)
    for r_on, r_off in zip(rows_vat, rows_novat, strict=True):
        assert r_on["taxable_income_lkr"] <= r_off["taxable_income_lkr"] + 1e-6
    assert sum(r["tax_lkr"] for r in rows_vat) < sum(r["tax_lkr"] for r in rows_novat)
    # And the relieved opex line reproduces the pre-VAT arithmetic exactly.
    for row in rows_novat:
        assert row["opex_lkr"] == pytest.approx(
            row["opex_usd"] * row["fx_rate"], rel=1e-12
        )


# --------------------------------------------------------------------------- #
# 6. Capex Monte Carlo — no double count
# --------------------------------------------------------------------------- #


def test_mc_capex_perturbs_the_pre_levy_base(levied_cfg: Dict[str, Any]) -> None:
    from analytics.cost.mc_capex import run_capex_mc

    res = run_capex_mc(copy.deepcopy(levied_cfg), n_samples=4, sigma_pct=5.0, seed=7)
    # base_capex_usd is the PRE-LEVY base, not the levy-inclusive gross.
    assert res.base_capex_usd == pytest.approx(159_600_000.0, rel=1e-12)


def test_mc_trial_write_path_reproduces_the_levied_pipeline(
    levied_cfg: Dict[str, Any], levied_result: Dict[str, Any]
) -> None:
    """A factor-1.0 trial (write base to usd_total, rerun) == the levied run.

    This is exactly what run_capex_mc does per trial; with the pre-levy base fix
    the pipeline re-applies the levies once on the written base. Grossing the
    base first (the bug this guards) would levy the total twice and fail here.
    """
    trial_cfg = copy.deepcopy(levied_cfg)
    cap = dict(trial_cfg.get("capex", {}))
    cap.pop("derive_from_breakdown", None)
    cap["usd_total"] = _extract_capex_usd(
        dict(trial_cfg), include_import_levies=False
    )  # the MC seam
    trial_cfg["capex"] = cap
    kpis = run_v14_pipeline(config=trial_cfg)["kpis"]
    for key in ("project_irr", "equity_irr", "project_npv", "total_cfads_usd"):
        assert kpis[key] == pytest.approx(levied_result["kpis"][key], rel=1e-12), key


# --------------------------------------------------------------------------- #
# 7. Breakdown / QRA interplay — the 0.5% cross-check stays pre-levy
# --------------------------------------------------------------------------- #


def test_breakdown_cross_check_operates_on_the_pre_levy_base(
    levied_cfg: Dict[str, Any],
) -> None:
    """derive_from_breakdown + levies: no tolerance interaction, gross = sum + uplift.

    The committed WBS breakdown sums exactly to usd_total (159.6M); with the ~5.2%
    prudent uplift a GROSS-basis cross-check would blow the 0.5% tolerance and
    raise — passing here proves the check operates on the pre-levy base.
    """
    cfg = copy.deepcopy(levied_cfg)
    cfg["capex"]["derive_from_breakdown"] = True
    it = resolve_indirect_taxes(cfg)
    assert it is not None
    base = _extract_capex_base_usd(dict(cfg))  # breakdown sum == 159.6M
    assert base == pytest.approx(159_600_000.0, rel=1e-9)
    assert _extract_capex_usd(dict(cfg)) == pytest.approx(
        base + compute_capex_uplift_usd(base, it), rel=1e-12
    )


def test_qra_contingency_base_attracts_levies(levied_cfg: Dict[str, Any]) -> None:
    """QRA ordering (documented): the uplift applies to the QRA-INCLUSIVE base.

    With ``contingency.method: qra`` the base resolver recomputes contingency
    from the risk inputs (overriding the fixed line + any stated usd_total), and
    the levies then apply on that recomputed base — duties charged on the risk
    reserve too, the documented mildly-conservative ordering. Gross ==
    qra_base + the cascade on qra_base, with no cross-check interaction.
    """
    cfg = copy.deepcopy(levied_cfg)
    cfg["capex"]["derive_from_breakdown"] = True
    cfg["capex"]["contingency"] = {
        "method": "qra",
        "base_cost_uncertainty_pct": 12.0,
        "confidence_level": 0.80,
    }
    it = resolve_indirect_taxes(cfg)
    assert it is not None
    qra_base = _extract_capex_base_usd(dict(cfg))
    # QRA recomputes contingency off the ex-contingency line sum (157.206M), so
    # the base differs from (here: exceeds) the fixed-breakdown 159.6M total.
    assert qra_base > 159_600_000.0
    assert _extract_capex_usd(dict(cfg)) == pytest.approx(
        qra_base + compute_capex_uplift_usd(qra_base, it), rel=1e-12
    )


# --------------------------------------------------------------------------- #
# 8. The committed lendercase posture (#738 flip) + variant overlays
# --------------------------------------------------------------------------- #

FULL_RELIEF_OVERRIDE = str(
    REPO_ROOT / "scenarios" / "overrides" / "import_levies_full_relief.yaml"
)
FULL_STACK_OVERRIDE = str(
    REPO_ROOT / "scenarios" / "overrides" / "import_levies_full_stack_paid.yaml"
)

# Levy-OFF economics of the committed lendercase (strip taxes_indirect, KEEP the
# statutory SSCL exemption): the fee-off-pin precedent (#737). These pins give
# the absent-block identity a fixed empirical meaning — if the mechanism ever
# leaks into a block-less config, this breaks at 1e-12. Values = the live
# pipeline on the committed scenario minus the block (2026-07-05 flip).
LEVY_OFF_PROJECT_IRR = 0.02330086889477035
LEVY_OFF_EQUITY_IRR = -0.044381188877225974
LEVY_OFF_PROJECT_NPV = -68316613.91027918
LEVY_OFF_TOTAL_CFADS = 196144013.5233307
LEVY_OFF_DEBT_TOTAL = 70224000.0


def _merged_with_override(path: str) -> Dict[str, Any]:
    from omegaconf import OmegaConf

    merged = OmegaConf.merge(OmegaConf.load(LENDER), OmegaConf.load(path))
    out = OmegaConf.to_container(merged, resolve=True)
    assert isinstance(out, dict)
    return out


def test_committed_lendercase_carries_the_prudent_posture() -> None:
    """The YAML flip is the locked user decision — pin it so it cannot drift.

    PRUDENT: PAL 5% + import-SSCL 2.5% PAID on the 0.69 imported share, capex
    VAT relieved (BOI s.17/bonded), opex VAT 18% paid — and the revenue SSCL
    ZEROED on the statutory exemption (IPP-to-CEB supply).
    """
    cfg = dict(load_scenario_config(LENDER))
    it = resolve_indirect_taxes(cfg)
    assert it is not None
    assert it.import_share_pct == 0.69
    assert it.cid_pct == 0.0
    assert it.pal_pct == 0.05
    assert it.sscl_import_pct == 0.025
    assert it.vat_capex_pct == 0.18
    assert it.vat_opex_pct == 0.18
    assert it.vat_on_duties is True
    assert it.vat_on_full_capex is False
    assert it.bonded_scheme is False
    assert it.vat_capex_relieved is True  # capex VAT relieved at this posture
    assert it.vat_opex_relieved is False  # operating-phase VAT paid
    assert it.duty_rate == pytest.approx(0.075, rel=1e-12)
    assert it.capex_vat_rate == 0.0
    assert it.opex_vat_rate == 0.18
    # Revenue-side SSCL: statutory exemption committed (was 0.025 pre-#738).
    assert float(cfg["statutory"]["social_services_levy_pct"]) == 0.0
    # And the in-test PRUDENT_BLOCK mirror used above matches the committed one.
    assert resolve_indirect_taxes({"taxes_indirect": PRUDENT_BLOCK}) == it


def test_levy_off_strip_reproduces_the_relieved_economics_exactly() -> None:
    """Deleting the block (SSCL exemption kept) hits the levy-off pins at 1e-12."""
    kpis = run_v14_pipeline(config=_stripped_lender_config())["kpis"]
    assert kpis["project_irr"] == pytest.approx(LEVY_OFF_PROJECT_IRR, abs=1e-12)
    assert kpis["equity_irr"] == pytest.approx(LEVY_OFF_EQUITY_IRR, abs=1e-12)
    assert kpis["project_npv"] == pytest.approx(LEVY_OFF_PROJECT_NPV, rel=1e-12)
    assert kpis["total_cfads_usd"] == pytest.approx(LEVY_OFF_TOTAL_CFADS, rel=1e-12)


def test_full_relief_overlay_equals_the_levy_free_economics() -> None:
    """FULL RELIEF zeroes every line => exactly the block-absent economics."""
    res = run_v14_pipeline(config=_merged_with_override(FULL_RELIEF_OVERRIDE))
    kpis = res["kpis"]
    assert kpis["project_irr"] == pytest.approx(LEVY_OFF_PROJECT_IRR, abs=1e-12)
    assert kpis["equity_irr"] == pytest.approx(LEVY_OFF_EQUITY_IRR, abs=1e-12)
    assert kpis["project_npv"] == pytest.approx(LEVY_OFF_PROJECT_NPV, rel=1e-12)
    assert kpis["total_cfads_usd"] == pytest.approx(LEVY_OFF_TOTAL_CFADS, rel=1e-12)
    debt = res["debt_result"] or {}
    assert debt["debt_total"] == pytest.approx(LEVY_OFF_DEBT_TOTAL, rel=1e-12)
    # Financed capex back to the pre-levy base; zero disclosed levies.
    uses = debt["funding"]["sources_and_uses"]["uses"]
    assert uses["capex_usd"] == pytest.approx(159_600_000.0, abs=0.01)
    assert uses["import_levies_usd"] == 0.0


def test_full_stack_paid_overlay_directional_signature() -> None:
    """FULL STACK PAID (~$38.5M uplift): value further down, sculpt holds 1.30."""
    canon = run_v14_pipeline(config=LENDER)
    paid = run_v14_pipeline(config=_merged_with_override(FULL_STACK_OVERRIDE))
    k_canon, k_paid = canon["kpis"], paid["kpis"]
    assert k_paid["project_irr"] < k_canon["project_irr"]
    assert k_paid["equity_irr"] < k_canon["equity_irr"]
    assert k_paid["project_npv"] < k_canon["project_npv"]
    # The sculpt re-solves: the per-period floor holds the 1.30 target...
    assert k_paid["min_dscr_period"] == pytest.approx(1.30, abs=1e-6)
    # ...while the wider uplift de-levers the solved gearing further.
    g_canon = (canon["debt_result"] or {}).get("dual_dscr") or {}
    g_paid = (paid["debt_result"] or {}).get("dual_dscr") or {}
    assert g_paid["solved_gearing"] < g_canon["solved_gearing"]
    # Uplift hand-check: duties 8.2593M + VAT 18% on (import+duties+domestic).
    uses = (paid["debt_result"] or {})["funding"]["sources_and_uses"]["uses"]
    duties = 159_600_000.0 * 0.69 * 0.075
    vat = (159_600_000.0 + duties) * 0.18
    assert uses["import_levies_usd"] == pytest.approx(duties + vat, abs=0.01)
