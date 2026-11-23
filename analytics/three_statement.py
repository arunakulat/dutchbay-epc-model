"""Three-statement output (P&L / cash flow / balance sheet) with tie-out checks (#479, #1896).

Lenders expect the model's KPIs to be backed by three articulating financial statements. This
module assembles them from the engine's own annual outputs — it adds no new finance logic
(CESSPIT: every number originates from the enriched ``annual_rows`` + ``debt_result`` + the
equity waterfall), and is an additive, read-only view that cannot perturb the economics
(KPI-neutral).

Currency: presented in **USD** (the reported-KPI numeraire). DutchBay is a multi-currency
project — LKR revenue/opex/tax/depreciation but USD-denominated capex and debt — so the LKR
P&L lines are converted at each year's ``fx_rate`` while the per-year debt figures (already USD
on the enriched rows: ``interest_usd``, ``debt_service_total``, ``balloon_resolution``) and the
USD capex are used as-is, giving one coherent currency.

Debt attribution — consume the engine's mapped per-row columns (NOT raw period indices)
--------------------------------------------------------------------------------------
The pipeline enriches each operating ``annual_row`` with the per-year debt figures, correctly
mapped to the operating year AND folding the construction bridge period into operating year 1
(``_enrich_annual_rows_with_debt`` — the fix for the historical DSCR-out-of-phase /
phantom-lockup bug). This module reads those per-row columns (``interest_usd``,
``debt_service_total``, ``balloon_resolution``) rather than re-deriving from the raw
period-indexed ``debt_result`` arrays, so the interest/principal stream is phase-correct and the
year-1 bridge interest is not dropped.

Equity-waterfall reconciliation (#1896)
--------------------------------------
When the equity distribution waterfall applies (``build_three_statement_from_run`` with CFADS
rows and enabled equity distribution), the statements reconcile period by period to the equity
waterfall (``finance.equity_distribution_v14_hydra``):

- Income statement tax uses the equity-facing (levered-tax) schedule when available.
- Cash flow from operations includes ``cf_basis_adjustment`` (the CFADS risk haircut, any FX
  hedge basis or bridge CFADS credit, grossed-up interest WHT, senior-fee arrears settled, and
  terminal value), tying operating cash flow to the waterfall's ``cf_pre_debt_usd``.
- Distributions equal ``-equity_distribution_usd`` (including negative distributions when a
  sponsor cure / cash call occurs), and ``dividend_wht`` tracks remitted dividend withholding.
- Closing cash tracks SPV-held cash (``reserve_balance`` DSRA + ``locked_cash_balance`` trapped
  under covenant lock-up + ``retained_cash_balance`` from holdbacks / un-swept cash), releasing
  at the horizon (``terminal_release_usd``) and remaining non-negative across refinance years.
- When ``Financing_Terms.dsra.fund_at_close`` is enabled, ``opening_cash`` starts at
  ``initial_dsra_usd`` so COD paid-in equity matches Sources & Uses.

Articulation & independent tie-outs
-----------------------------------
Paid-in equity is the funding plug (capitalised cost + opening cash − debt drawn); cash rolls
via the cash-flow statement; PP&E = capex + IDC + cumulative augmentation − accumulated
depreciation; retained earnings roll forward cleanly. With those roll-forwards the balance
sheet balances **by construction** every year — so ``balance_sheet_balances`` /
``cashflow_reconciles`` / ``retained_earnings_rolls`` are articulation invariants asserted as a
guard against a builder regression.

Two **independent** tie-outs verify consistency:
- ``debt_retires_to_residual``: the per-row principal + balloon repayments, summed, must retire
  the engine's independently-stated drawn debt down to its stated balloon residual.
- ``waterfall_reconciles``: statement distributions, DSRA reserve balance/movement, and SPV
  closing cash match the equity waterfall period by period, with non-negative closing cash.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

#: Default tie-out tolerance, in the presentation currency (USD). The articulation invariants
#: hold to FP rounding; the independent debt-retirement check allows the same small slack.
DEFAULT_TIEOUT_TOLERANCE: float = 1.0


def _f(row: Mapping[str, Any], key: str, default: float = 0.0) -> float:
    value = row.get(key, default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class IncomeStatementRow:
    """One year of the P&L (presentation currency, default USD)."""

    year: int
    revenue: float
    opex: float
    ebitda: float
    depreciation: float
    ebit: float
    interest: float
    pretax_income: float
    tax: float
    net_income: float


@dataclass(frozen=True)
class CashFlowRow:
    """One year of the cash-flow statement (presentation currency; indirect method)."""

    year: int
    net_income: float
    depreciation: float
    cfo: float  # operating
    capex: float  # negative outflow (augmentation in operating years)
    cfi: float  # investing
    debt_principal: float  # negative (scheduled amortisation)
    balloon_repaid: float  # negative (balloon sweep at maturity)
    distributions: float  # negative (to equity); positive when sponsor cure
    cff: float  # financing
    net_change_in_cash: float
    closing_cash: float
    cf_basis_adjustment: float = 0.0
    dividend_wht: float = 0.0
    reserve_funded: float = 0.0
    reserve_movement: float = 0.0
    reserve_balance: float = 0.0
    locked_cash_balance: float = 0.0
    retained_cash_balance: float = 0.0


@dataclass(frozen=True)
class BalanceSheetRow:
    """One year of the balance sheet (presentation currency)."""

    year: int
    ppe_net: float
    cash: float
    total_assets: float
    debt: float
    paid_in_equity: float
    retained_earnings: float
    total_equity: float
    total_liabilities_and_equity: float
    balance_residual: float  # assets − (liabilities + equity); ~0 when it ties out


@dataclass(frozen=True)
class TieOutStatus:
    """Status of the articulation invariants + independent consistency checks.

    ``balance_sheet_balances`` / ``cashflow_reconciles`` / ``retained_earnings_rolls`` are
    articulation INVARIANTS — true by construction, asserted as a guard against a builder
    regression. ``debt_retires_to_residual`` and ``waterfall_reconciles`` are the genuinely
    INDEPENDENT consistency checks: per-row principal+balloon repayments retire drawn debt to
    the balloon residual, and statement distributions, reserve movements, and SPV closing
    cash match the equity waterfall period by period with non-negative closing cash (#1896).
    """

    balance_sheet_balances: bool
    debt_retires_to_residual: bool
    cashflow_reconciles: bool
    retained_earnings_rolls: bool
    max_abs_balance_residual: float
    debt_retirement_residual: float
    tolerance: float
    waterfall_reconciles: bool = True
    max_abs_waterfall_residual: float = 0.0

    @property
    def all_pass(self) -> bool:
        return (
            self.balance_sheet_balances
            and self.debt_retires_to_residual
            and self.cashflow_reconciles
            and self.retained_earnings_rolls
            and self.waterfall_reconciles
        )


@dataclass(frozen=True)
class ThreeStatementResult:
    """The three articulating statements (presentation currency) plus their tie-out status."""

    currency: str
    income_statement: List[IncomeStatementRow] = field(default_factory=list)
    cash_flow: List[CashFlowRow] = field(default_factory=list)
    balance_sheet: List[BalanceSheetRow] = field(default_factory=list)
    tie_outs: Optional[TieOutStatus] = None

    def to_dict(self) -> Dict[str, Any]:
        from dataclasses import asdict

        return asdict(self)


def build_three_statement(
    annual_rows: Sequence[Mapping[str, Any]],
    *,
    debt_drawn: float,
    balloon_residual: float = 0.0,
    gross_capitalised_cost: float,
    fx_rates: Optional[Sequence[float]] = None,
    currency: str = "USD",
    opening_cash: float = 0.0,
    tolerance: float = DEFAULT_TIEOUT_TOLERANCE,
    balloon_interest: Optional[Sequence[float]] = None,
    equity_rows: Optional[Sequence[Mapping[str, Any]]] = None,
    equity_schedule: Optional[Sequence[Mapping[str, Any]]] = None,
) -> ThreeStatementResult:
    """Assemble the three statements from the engine's enriched annual rows.

    Args:
        annual_rows: Operating-year rows. LKR P&L lines (``revenue_lkr``, ``opex_lkr``,
            ``ebitda_lkr``, ``total_depreciation_lkr``, ``tax_lkr``, optional
            ``bess_augmentation_capex_lkr``) are converted to ``currency`` via ``fx_rates``;
            the per-year debt figures (``interest_usd``, ``debt_service_total``,
            ``balloon_resolution``) are read as-is (already in ``currency`` = USD), so the
            interest/principal stream is the engine's phase-correct, bridge-folded one.
        debt_drawn: Total drawn senior debt (``currency``) at COD — the INDEPENDENT figure the
            per-row repayments must amortise. Sets the opening balance-sheet debt + the equity plug.
        balloon_residual: Debt remaining at maturity (``currency``); the debt-retirement check
            target. 0 for a fully-amortising structure.
        gross_capitalised_cost: Capitalised asset base at COD (capex + IDC), in ``currency``.
        fx_rates: Per-operating-year LKR/``currency`` rate for the LKR P&L lines. ``None`` (or a
            1.0 entry) leaves a line unconverted.
        currency: Presentation currency label (default ``"USD"``).
        opening_cash: Cash on the balance sheet at COD (e.g. a funded DSRA), in ``currency``.
        tolerance: Absolute (``currency``) tolerance for the tie-out checks.
        balloon_interest: Per-row interest accrued on the balloon after maturity
            (``currency``), which ``balloon_resolution`` pays first (#1396). That
            interest is an expense and only the remainder retires debt; interest a cash
            sweep could not pay is capitalised, so the remainder can be negative and the
            balance grows. ``None`` treats the whole row as principal.
        equity_rows: Optional equity-facing rows (levered tax). When supplied, ``tax_lkr``
            comes from ``equity_rows`` so the P&L tax matches the SPV's levered tax.
        equity_schedule: Optional equity waterfall schedule (from
            ``finance.equity_distribution_v14_hydra``). When supplied, distributions, DSRA
            reserve balances/movements, lock-up/retention balances, WHT, and closing cash tie
            period by period to the waterfall (#1896).

    Returns:
        A :class:`ThreeStatementResult` with the three statements and the tie-out status.
    """
    if equity_rows is not None and len(equity_rows) != len(annual_rows):
        raise ValueError(
            f"equity_rows length ({len(equity_rows)}) != annual_rows length ({len(annual_rows)})"
        )
    if equity_schedule is not None and len(equity_schedule) != len(annual_rows):
        raise ValueError(
            f"equity_schedule length ({len(equity_schedule)}) != annual_rows length ({len(annual_rows)})"
        )

    paid_in_equity = gross_capitalised_cost + opening_cash - debt_drawn

    income: List[IncomeStatementRow] = []
    cash_flow: List[CashFlowRow] = []
    balance_sheet: List[BalanceSheetRow] = []

    cash = opening_cash
    prev_reserve = opening_cash if equity_schedule is not None else 0.0
    wf_spv_cash = opening_cash
    locked_cash_bal = 0.0
    retained_cash_bal = 0.0
    accum_dep = 0.0
    cum_aug = 0.0
    retained = 0.0
    debt_balance = debt_drawn
    total_repaid = 0.0
    max_residual = 0.0
    max_wf_residual = 0.0
    cf_reconciles = True
    re_rolls = True
    wf_reconciles = True

    n_rows = len(annual_rows)
    for t, row in enumerate(annual_rows):
        tax_row = equity_rows[t] if equity_rows is not None else row
        year = int(_f(row, "year", t + 1))
        fx = 1.0
        if fx_rates is not None and t < len(fx_rates):
            rate = _f({"r": fx_rates[t]}, "r", 0.0)
            fx = rate if rate > 0 else 1.0

        # ---- debt (per-row, engine-mapped; already in `currency`) ------------
        scheduled_interest = _f(row, "interest_usd")
        service = _f(row, "debt_service_total")
        principal = service - scheduled_interest
        refi_interest = (
            float(balloon_interest[t])
            if balloon_interest is not None and t < len(balloon_interest)
            else 0.0
        )
        balloon = _f(row, "balloon_resolution") - refi_interest
        interest = scheduled_interest + refi_interest
        total_debt_repaid = principal + balloon

        # ---- P&L (LKR lines -> currency via fx; EBIT = EBITDA − depreciation) -
        revenue = _f(row, "revenue_lkr") / fx
        opex = _f(row, "opex_lkr") / fx
        ebitda = _f(row, "ebitda_lkr") / fx
        dep = _f(row, "total_depreciation_lkr") / fx
        tax = _f(tax_row, "tax_lkr") / fx
        ebit = ebitda - dep
        pretax_income = ebit - interest
        net_income = pretax_income - tax
        income.append(
            IncomeStatementRow(
                year=year,
                revenue=revenue,
                opex=opex,
                ebitda=ebitda,
                depreciation=dep,
                ebit=ebit,
                interest=interest,
                pretax_income=pretax_income,
                tax=tax,
                net_income=net_income,
            )
        )

        # ---- cash-flow statement (indirect) ---------------------------------
        aug = _f(row, "bess_augmentation_capex_lkr") / fx
        cum_aug += aug
        cfi = -aug

        if equity_schedule is not None:
            er = equity_schedule[t]
            cf_pre_debt_wf = _f(er, "cf_pre_debt_usd")
            wht_on_interest = _f(er, "wht_on_interest_usd")
            wht_on_dividends = _f(er, "wht_on_dividends_usd")
            arrears_settled = _f(er, "senior_fee_arrears_settled_usd")
            terminal_value = _f(er, "terminal_value_usd")
            eq_dist = _f(er, "equity_distribution_usd")
            wf_reserve_balance = _f(er, "reserve_balance_usd")
            wf_reserve_funded = _f(er, "reserve_funded_usd")
            covenant_locked = bool(er.get("covenant_locked", False))

            # Bridge from P&L (EBITDA - tax) to the waterfall's cash basis (CFADS after
            # risk haircut, FX hedge / bridge CFADS, grossed-up interest WHT, senior-fee
            # arrears settlement, and terminal proceeds).
            cf_basis_adj = (
                (cf_pre_debt_wf + aug - (ebitda - tax))
                - wht_on_interest
                - arrears_settled
                + terminal_value
            )
            cfo = net_income + dep + cf_basis_adj
            distributions_cf = (
                -eq_dist
            )  # negative = paid to equity; positive = sponsor cure
            div_wht_cf = -wht_on_dividends
            cff = -total_debt_repaid + distributions_cf + div_wht_cf
            net_change = cfo + cfi + cff
            cash += net_change

            reserve_mov = wf_reserve_balance - prev_reserve
            prior_retained_bal = retained_cash_bal
            non_reserve = max(0.0, cash - wf_reserve_balance)
            if t == n_rows - 1 and wf_reserve_balance == 0.0 and abs(cash) <= tolerance:
                locked_cash_bal = 0.0
                retained_cash_bal = 0.0
            elif covenant_locked or (
                locked_cash_bal > 0.0
                and eq_dist < 0.0
                and _f(er, "retained_cash_usd") == 0.0
            ):
                # Locked cash is exhausted before retained cash, and retained cash never
                # grows while covenant-locked or in a non-distributing shortfall branch.
                retained_cash_bal = min(retained_cash_bal, non_reserve)
                locked_cash_bal = max(0.0, non_reserve - retained_cash_bal)
            else:
                locked_cash_bal = 0.0
                retained_cash_bal = non_reserve

            wf_spv_cash += (
                cf_pre_debt_wf
                - _f(er, "debt_service_usd")
                - wht_on_interest
                - _f(er, "balloon_resolution_usd")
                - arrears_settled
                - wht_on_dividends
                - eq_dist
                + terminal_value
            )
            partition_sum = wf_reserve_balance + locked_cash_bal + retained_cash_bal
            period_wf_res = max(
                abs((-distributions_cf) - eq_dist),
                abs(reserve_mov - (wf_reserve_balance - prev_reserve)),
                abs(cash - wf_spv_cash),
                abs(partition_sum - cash),
                abs(service - _f(er, "debt_service_usd")),
                abs((balloon + refi_interest) - _f(er, "balloon_resolution_usd")),
                max(0.0, -cash),
                max(0.0, wf_reserve_balance - cash),
            )
            if t == n_rows - 1:
                period_wf_res = max(period_wf_res, abs(cash))
            if (
                not covenant_locked
                and prior_retained_bal == 0.0
                and _f(er, "retained_cash_usd") == 0.0
                and t < n_rows - 1
            ):
                period_wf_res = max(period_wf_res, abs(cash - wf_reserve_balance))
            max_wf_residual = max(max_wf_residual, period_wf_res)
            if period_wf_res > tolerance:
                wf_reconciles = False
            prev_reserve = wf_reserve_balance
            retained_delta = net_income + cf_basis_adj + distributions_cf + div_wht_cf
        else:
            cf_basis_adj = 0.0
            div_wht_cf = 0.0
            wf_reserve_funded = 0.0
            reserve_mov = 0.0
            wf_reserve_balance = 0.0
            locked_cash_bal = 0.0
            retained_cash_bal = 0.0
            cfo = net_income + dep  # interest & tax already in net income
            # Full sweep of free cash to equity after ALL debt repaid (amortisation + balloon).
            distributions_out = max(0.0, cfo + cfi - total_debt_repaid)
            distributions_cf = -distributions_out
            cff = -total_debt_repaid + distributions_cf
            net_change = cfo + cfi + cff
            cash += net_change
            retained_delta = net_income + distributions_cf

        cash_flow.append(
            CashFlowRow(
                year=year,
                net_income=net_income,
                depreciation=dep,
                cfo=cfo,
                capex=-aug,
                cfi=cfi,
                debt_principal=-principal,
                balloon_repaid=-balloon,
                distributions=distributions_cf,
                cff=cff,
                net_change_in_cash=net_change,
                closing_cash=cash,
                cf_basis_adjustment=cf_basis_adj,
                dividend_wht=div_wht_cf,
                reserve_funded=wf_reserve_funded,
                reserve_movement=reserve_mov,
                reserve_balance=wf_reserve_balance,
                locked_cash_balance=locked_cash_bal,
                retained_cash_balance=retained_cash_bal,
            )
        )

        # ---- balance sheet ---------------------------------------------------
        accum_dep += dep
        ppe_net = gross_capitalised_cost + cum_aug - accum_dep
        debt_balance -= total_debt_repaid
        total_repaid += total_debt_repaid
        retained += retained_delta
        total_assets = ppe_net + cash
        total_equity = paid_in_equity + retained
        total_le = debt_balance + total_equity
        residual = total_assets - total_le
        balance_sheet.append(
            BalanceSheetRow(
                year=year,
                ppe_net=ppe_net,
                cash=cash,
                total_assets=total_assets,
                debt=debt_balance,
                paid_in_equity=paid_in_equity,
                retained_earnings=retained,
                total_equity=total_equity,
                total_liabilities_and_equity=total_le,
                balance_residual=residual,
            )
        )

        # ---- invariant guards (by construction) -----------------------------
        max_residual = max(max_residual, abs(residual))
        prior_cash = cash_flow[t - 1].closing_cash if t > 0 else opening_cash
        if abs((cash - prior_cash) - net_change) > tolerance:
            cf_reconciles = False
        prior_re = balance_sheet[t - 1].retained_earnings if t > 0 else 0.0
        if abs(retained - (prior_re + retained_delta)) > tolerance:
            re_rolls = False

    # ---- the INDEPENDENT tie-out: do the per-row repayments retire the debt? --
    debt_retirement_residual = abs((debt_drawn - total_repaid) - balloon_residual)

    tie_outs = TieOutStatus(
        balance_sheet_balances=(max_residual <= tolerance),
        debt_retires_to_residual=(debt_retirement_residual <= max(tolerance, 1.0)),
        cashflow_reconciles=cf_reconciles,
        retained_earnings_rolls=re_rolls,
        max_abs_balance_residual=max_residual,
        debt_retirement_residual=debt_retirement_residual,
        tolerance=tolerance,
        waterfall_reconciles=wf_reconciles,
        max_abs_waterfall_residual=max_wf_residual,
    )
    return ThreeStatementResult(
        currency=currency,
        income_statement=income,
        cash_flow=cash_flow,
        balance_sheet=balance_sheet,
        tie_outs=tie_outs,
    )


#: Capex-total paths (USD), config-first — mirrors finance.epc_helper_v14 / debt_v14 keys,
#: read here as plain config data (no finance import; CCCDIR).
_CAPEX_USD_PATHS: tuple[tuple[str, ...], ...] = (
    ("capex", "usd_total"),
    ("capex", "epc_usd"),
    ("finance", "capex_usd"),
)


def _resolve_capex_usd(config: Mapping[str, Any]) -> Optional[float]:
    # When indirect taxes (import levies, #738) or a bottom-up breakdown are declared,
    # the capitalised base MUST be the identical LEVY-INCLUSIVE gross the debt engine
    # sizes on (finance.debt_v14._extract_capex_usd) and the NPV base uses
    # (analytics.core.metrics._derive_capex_usd) — otherwise PP&E and the paid-in-equity
    # plug book the PRE-levy base and the balance sheet only ties out via a prose
    # reconciliation footnote (#811). Delegate to that single resolver so the statements
    # reconcile natively. Levy-free flat configs take the unchanged flat path below and
    # stay byte-identical. This adds a call-time finance import (the CCCDIR-pure module
    # otherwise holds none) exactly as metrics._derive_capex_usd and
    # equity_distribution_v14_hydra already do.
    from finance.capex_price_basis import refuse_unapplied_price_basis
    from finance.import_levies import has_taxes_indirect

    refuse_unapplied_price_basis(config, "the three-statement capex resolver")
    capex_section = config.get("capex") if isinstance(config, Mapping) else None
    derive_from_breakdown = isinstance(capex_section, Mapping) and bool(
        capex_section.get("derive_from_breakdown")
    )
    if derive_from_breakdown or has_taxes_indirect(config):
        from finance.debt_v14 import _extract_capex_usd

        resolved = float(_extract_capex_usd(dict(config)))
        return resolved if resolved > 0 else None

    for path in _CAPEX_USD_PATHS:
        cur: Any = config
        for key in path:
            cur = cur.get(key) if isinstance(cur, Mapping) else None
        value = _f({"v": cur}, "v", 0.0) if cur is not None else 0.0
        if value > 0:
            return value
    return None


def _has_cashflow_config(config: Mapping[str, Any]) -> bool:
    """Return True when ``config`` carries enough scenario sections for ``build_annual_rows``."""
    keys = {str(k).lower() for k in config.keys()}
    return (
        "tax" in keys
        and "fx" in keys
        and bool(keys & {"project", "generation", "tariff", "revenue", "parameters"})
    )


def _resolve_equity_rows_and_schedule(
    pipeline_result: Mapping[str, Any],
    config: Mapping[str, Any],
    annual_rows: Sequence[Mapping[str, Any]],
    debt_result: Mapping[str, Any],
) -> Tuple[Optional[List[Mapping[str, Any]]], Optional[List[Dict[str, Any]]]]:
    """Resolve the equity-facing (levered-tax) rows and equity waterfall schedule (#1896)."""
    if not annual_rows:
        return None, None
    has_cfads = any(
        key in annual_rows[0]
        for key in ("cf_pre_debt", "cfads_usd", "cfads_final_lkr", "cfads_lkr")
    )
    if not has_cfads:
        return None, None

    from finance.equity_distribution_v14_hydra import (
        _build_distribution_config,
        build_equity_distribution_schedule,
    )

    dist_cfg = _build_distribution_config(config)
    if not dist_cfg.enabled:
        return None, None

    raw_eq_rows = pipeline_result.get("equity_rows")
    if isinstance(raw_eq_rows, list) and len(raw_eq_rows) == len(annual_rows):
        equity_rows: List[Mapping[str, Any]] = list(raw_eq_rows)
    elif _has_cashflow_config(config):
        from analytics.pipeline_v14_enhanced import (
            _equity_facing_rows,
            _senior_fee_lkr_series,
        )
        from finance.cashflow_v14 import build_annual_rows

        cfg_dict = dict(config)
        rows_list = [dict(r) for r in annual_rows]
        debt_dict = dict(debt_result)
        fee_series = _senior_fee_lkr_series(debt_dict, rows_list)
        equity_rows = list(
            _equity_facing_rows(
                cfg_dict,
                rows_list,
                debt_dict,
                fee_series,
                build_annual_rows=build_annual_rows,
            )
        )
    else:
        equity_rows = list(annual_rows)

    ed = pipeline_result.get("equity_distribution")
    if isinstance(ed, Mapping):
        status = str(ed.get("status", ""))
        if status == "disabled":
            return None, None
        raw_sched = ed.get("annual_distributions")
        if (
            status in ("computed", "defaulted")
            and isinstance(raw_sched, list)
            and len(raw_sched) == len(annual_rows)
        ):
            return equity_rows, [dict(r) for r in raw_sched]

    schedule = build_equity_distribution_schedule(
        annual_rows=equity_rows,
        debt_result=debt_result,
        distribution_config=dist_cfg,
    )
    if dist_cfg.terminal_value_usd > 0.0 and schedule:
        schedule[-1]["terminal_value_usd"] = dist_cfg.terminal_value_usd
        schedule[-1]["equity_distribution_usd"] = (
            float(schedule[-1]["equity_distribution_usd"]) + dist_cfg.terminal_value_usd
        )
    return equity_rows, schedule


def build_three_statement_from_run(
    pipeline_result: Mapping[str, Any],
    config: Mapping[str, Any],
    *,
    tolerance: float = DEFAULT_TIEOUT_TOLERANCE,
) -> Optional[ThreeStatementResult]:
    """Assemble the three statements (USD) from a ``run_v14_pipeline`` result, or ``None``.

    Reads the enriched ``annual_rows`` (LKR P&L + per-year USD debt columns), ``debt_result``
    (the independent drawn debt + balloon residual + IDC), and the equity waterfall schedule.
    The capitalised asset base (USD) is the financed capex (config ``capex.usd_total``) + IDC.
    Returns ``None`` when the required inputs are absent (so callers attach it opportunistically).
    """
    annual_rows = pipeline_result.get("annual_rows")
    debt_result = pipeline_result.get("debt_result")
    if not isinstance(annual_rows, list) or not annual_rows:
        return None
    if not isinstance(debt_result, Mapping):
        return None

    total_idc = float(debt_result.get("total_idc", 0.0) or 0.0)
    debt_principal_drawn = _f(dict(debt_result), "debt_total", 0.0) or _f(
        dict(debt_result), "max_debt_usd", 0.0
    )
    balloon_residual = _f(dict(debt_result), "balloon_residual", 0.0)
    capex_usd = _resolve_capex_usd(config)
    if capex_usd is None or debt_principal_drawn <= 0:
        return None
    # IDC is capitalised into BOTH the asset (PP&E gross) and the drawn loan balance, so it
    # appears on both sides and cancels in the equity plug; the per-row principal stream
    # amortises the full drawn balance (principal debt + IDC) down to the balloon residual.
    debt_drawn = debt_principal_drawn + total_idc
    gross_capitalised = capex_usd + total_idc

    funding = debt_result.get("funding") or {}
    opening_cash = (
        float(_f(funding, "initial_dsra_usd", 0.0))
        if isinstance(funding, Mapping) and bool(funding.get("fund_at_close"))
        else 0.0
    )
    equity_rows, equity_schedule = _resolve_equity_rows_and_schedule(
        pipeline_result, config, annual_rows, debt_result
    )

    fx_rates = [_f(row, "fx_rate", 0.0) for row in annual_rows]
    return build_three_statement(
        annual_rows,
        debt_drawn=debt_drawn,
        balloon_residual=balloon_residual,
        gross_capitalised_cost=gross_capitalised,
        fx_rates=fx_rates,
        currency="USD",
        opening_cash=opening_cash,
        tolerance=tolerance,
        balloon_interest=_balloon_interest_by_row(debt_result, len(annual_rows)),
        equity_rows=equity_rows,
        equity_schedule=equity_schedule,
    )


def _balloon_interest_by_row(
    debt_result: Mapping[str, Any], n_rows: int
) -> Optional[List[float]]:
    """Per-row interest accrued on the balloon after maturity, or ``None``.

    Read from the engine's period-indexed ``debt_result["balloon_interest"]`` (every
    treatment that carries the balloon past maturity accrues interest on it) and placed
    on rows through ``annual_row_debt_period_map``, the same map the pipeline uses to put
    ``balloon_resolution`` on rows, so the split lands on the row that carries the
    payment. A result without that key falls back to the refinanced tranche's own
    disclosure (#1396), its only interest-bearing balloon before the key existed.
    """
    series = debt_result.get("balloon_interest")
    if isinstance(series, (list, tuple)):
        by_period = {period: float(value or 0.0) for period, value in enumerate(series)}
    else:
        refinance = debt_result.get("refinance")
        if not isinstance(refinance, Mapping):
            return None
        by_period = {
            int(c["period"]): float(c["interest_usd"])
            for c in refinance.get("coverage_by_period") or []
        }
    out = [0.0] * n_rows
    for mapping in debt_result.get("annual_row_debt_period_map") or []:
        try:
            row, period = int(mapping["annual_row_index"]), int(mapping["debt_period"])
        except (KeyError, TypeError, ValueError):
            continue
        if 0 <= row < n_rows:
            out[row] = by_period.get(period, 0.0)
    return out


@dataclass(frozen=True)
class CashflowWaterfallRow:
    """One operating year of the cash-flow waterfall, ordered by payment priority (USD).

    Every figure is an engine-published per-row value. ``cfads`` is the PROJECT-basis CFADS
    (``cf_pre_debt``: post the risk haircut and maintenance capex, with UNLEVERED tax, the basis
    of the project IRR and NPV). It is not the DSCR numerator: the facility is sized and the
    DSCR divides on the coverage CFADS, which carries LEVERED tax (#1897).
    ``scheduled_debt_service`` is interest + scheduled principal, the DSCR denominator;
    ``balloon_sweep`` is the bullet retired at maturity (senior to equity but NOT part of the
    scheduled DSCR); ``cash_to_equity`` is the engine's project-basis residual.

    The reconciliation to the DSCR covenant (#1897), set when the row publishes the coverage
    CFADS and a debt result is given. The two CFADS bases differ in up to three ways, shown
    apart:

    - ``bridge_cfads_credit``: under the ``equity_cfads_match`` bridge treatment the waterfall
      credits the bridge period's CFADS to operating year 1 (``bridge_cfads_usd``); the
      coverage CFADS carries no such credit. Zero otherwise.
    - ``fee_in_project_basis``: the project basis deducts the senior fee inside EBITDA, so
      after the risk haircut; the coverage CFADS is before the fee. It is converted to USD at
      the row's own effective rate (``revenue_usd`` / ``revenue_lkr``), which is the hedged
      blend when an FX hedge applies.
    - ``tax_basis_difference``: what remains, the levered-tax difference (the interest tax
      shield, and the tax effect of the fee). It is zero in a year with no tax.

    So ``coverage_cfads`` (``cfads_coverage_usd``) = ``cfads`` - ``bridge_cfads_credit`` +
    ``fee_in_project_basis`` + ``tax_basis_difference``. The covenant then deducts the full ``senior_fee`` once:
    ``covenant_cfads`` = coverage - senior fee. ``covenant_debt_service`` is the debt service
    the covenant divides: the row's own debt period's service and, in operating year 1, the
    bridge period's service whatever the bridge treatment, as the engine's ``dscr_by_year``
    does. It can differ from ``scheduled_debt_service`` (the waterfall's), for example when the
    bridge is capitalised. ``covenant_dscr`` = covenant CFADS / covenant debt service. None
    where a figure is not published, or where no debt service falls in the year.
    """

    year: int
    cfads: float
    scheduled_debt_service: float
    balloon_sweep: float
    cash_to_equity: float
    coverage_cfads: Optional[float] = None
    bridge_cfads_credit: Optional[float] = None
    fee_in_project_basis: Optional[float] = None
    tax_basis_difference: Optional[float] = None
    senior_fee: Optional[float] = None
    covenant_cfads: Optional[float] = None
    covenant_debt_service: Optional[float] = None
    covenant_dscr: Optional[float] = None


@dataclass(frozen=True)
class CashflowWaterfall:
    """The CFADS → scheduled debt service → balloon → equity cascade per operating year + totals.

    Built from the engine's OWN published per-operating-year USD figures (``cf_pre_debt``,
    ``debt_service_total``, ``balloon_resolution``, ``cf_after_debt``) — a regrouping by payment
    priority, NOT a reconstruction. ``cfads`` is the project basis (unlevered tax), and
    ``scheduled_debt_service`` equals the debt service the DSCR divides. The balloon is shown
    SEPARATELY because it is senior to equity yet excluded from the scheduled DSCR.

    #1897: the DSCR numerator is the coverage CFADS (levered tax) less the senior fee, not the
    project-basis CFADS. Where the rows publish the coverage CFADS, each row also carries the
    reconciliation to the annual covenant DSCR, and ``has_coverage_basis`` is set. So a year in
    which the project-basis CFADS falls short of debt service (negative ``cash_to_equity``) is
    shown beside the covenant DSCR that the coverage basis still meets, with the difference
    named. ``cash_to_equity`` is the project-basis residual, not the sponsors' distributions:
    those come from the equity waterfall (reserves, lock-up), which sets the equity returns.
    """

    currency: str
    rows: List[CashflowWaterfallRow] = field(default_factory=list)
    total_cfads: float = 0.0
    total_scheduled_debt_service: float = 0.0
    total_balloon_sweep: float = 0.0
    total_cash_to_equity: float = 0.0
    has_coverage_basis: bool = False
    total_coverage_cfads: Optional[float] = None


def _period_by_row(debt_result: Mapping[str, Any], n_rows: int) -> Dict[int, int]:
    out: Dict[int, int] = {}
    for mapping in debt_result.get("annual_row_debt_period_map") or []:
        try:
            row, period = int(mapping["annual_row_index"]), int(mapping["debt_period"])
        except (KeyError, TypeError, ValueError):
            continue
        if 0 <= row < n_rows:
            out[row] = period
    return out


def _covenant_terms_by_row(
    debt_result: Optional[Mapping[str, Any]], n_rows: int
) -> List[Tuple[Optional[float], Optional[float]]]:
    """(senior fee, covenant debt service) per operating row, from the debt result.

    Both come from the debt period the row maps to. Operating year 1's covenant debt service
    also carries the bridge period's service when that period maps to no row, whatever the
    bridge treatment, as ``dscr_by_year`` does (``finance/debt/layer.py``).
    """
    out: List[Tuple[Optional[float], Optional[float]]] = [(None, None)] * n_rows
    if not isinstance(debt_result, Mapping):
        return out
    fees = debt_result.get("senior_fee_usd")
    service = debt_result.get("debt_service_total")
    if not isinstance(fees, (list, tuple)) or not isinstance(service, (list, tuple)):
        return out
    periods = _period_by_row(debt_result, n_rows)
    bridge = 0.0
    bridge_period = debt_result.get("cfads_bridge_debt_period")
    if bridge_period is not None:
        bp = int(bridge_period)
        if bp not in set(periods.values()) and 0 <= bp < len(service):
            bridge = float(service[bp] or 0.0)
    for row, period in periods.items():
        if not (0 <= period < len(fees) and period < len(service)):
            continue
        svc = float(service[period] or 0.0) + (bridge if row == 0 else 0.0)
        out[row] = (float(fees[period] or 0.0), svc)
    return out


def _usd_per_lkr(row: Mapping[str, Any]) -> Optional[float]:
    """The row's effective LKR-to-USD factor: the hedged blend when a hedge applies.

    The engine converts revenue and CFADS with the same linear blend of spot and hedged
    forward (``finance.cashflow_v14_fx._hedged_usd``), so revenue's own ratio is the factor;
    with no revenue in the row, the spot rate.
    """
    revenue_lkr = row.get("revenue_lkr")
    revenue_usd = row.get("revenue_usd")
    if revenue_lkr and revenue_usd is not None:
        return float(revenue_usd) / float(revenue_lkr)
    fx = row.get("fx_rate")
    return 1.0 / float(fx) if fx else None


def _fee_in_project_basis(row: Mapping[str, Any]) -> Optional[float]:
    """The senior fee as the project basis carries it: in USD, after the risk haircut."""
    fee_lkr = row.get("senior_fee_lkr")
    factor = _usd_per_lkr(row)
    if fee_lkr is None or factor is None:
        return None
    retained = 1.0 - float(row.get("risk_haircut_pct") or 0.0)
    return float(fee_lkr) * factor * retained


def build_cashflow_waterfall(
    annual_rows: Sequence[Mapping[str, Any]],
    *,
    currency: str = "USD",
    debt_result: Optional[Mapping[str, Any]] = None,
) -> CashflowWaterfall:
    """Regroup the engine's per-operating-year cash figures into a payment-priority waterfall.

    Sources every line from the engine's OWN published per-row USD columns so the waterfall ties
    line-for-line to the rest of the report — no reconstruction, no second source of truth:

    - ``cfads`` = ``cf_pre_debt`` — the risk-haircut, post-maintenance-capex CFADS on the
      PROJECT basis (unlevered tax). The DSCR numerator is the coverage CFADS below (#1897).
    - ``scheduled_debt_service`` = ``debt_service_total`` — interest + scheduled principal, i.e.
      the DSCR denominator shown in the Debt Structure & DSCR Profile section.
    - ``balloon_sweep`` = ``balloon_resolution`` — the bullet retired at maturity; senior to
      equity but NOT part of the scheduled DSCR, so the two sections do not disagree on coverage.
    - ``cash_to_equity`` = ``cf_after_debt`` (= cfads − scheduled − balloon), the engine's own
      residual; distributed in full under the model's 100% sweep.

    Args:
        annual_rows: The enriched operating-year rows (one per operating year, post-COD), carrying
            the engine's USD ``cf_pre_debt`` / ``debt_service_total`` / ``balloon_resolution`` /
            ``cf_after_debt`` columns.
        currency: Presentation-currency label (the engine figures are USD).
        debt_result: The run's debt result. When given, with rows that publish
            ``cfads_coverage_usd``, each row carries the reconciliation to its covenant DSCR
            (see :class:`CashflowWaterfallRow`; #1897).

    Returns:
        A :class:`CashflowWaterfall` with the per-year cascade rows and project-life totals.
    """
    rows: List[CashflowWaterfallRow] = []
    total_cfads = 0.0
    total_scheduled = 0.0
    total_balloon = 0.0
    total_cash = 0.0
    total_coverage = 0.0
    has_coverage = bool(annual_rows) and all(
        row.get("cfads_coverage_usd") is not None for row in annual_rows
    )
    terms = _covenant_terms_by_row(debt_result, len(annual_rows))
    for i, row in enumerate(annual_rows):
        cfads = _f(row, "cf_pre_debt")
        scheduled = _f(row, "debt_service_total")
        balloon = _f(row, "balloon_resolution")
        # cf_after_debt is the engine's own residual; reconstruct it only if a row omits it.
        cash_to_equity = _f(row, "cf_after_debt", cfads - scheduled - balloon)
        coverage: Optional[float] = None
        bridge_credit: Optional[float] = None
        in_project: Optional[float] = None
        difference: Optional[float] = None
        covenant_cfads: Optional[float] = None
        dscr: Optional[float] = None
        fee, covenant_service = terms[i] if has_coverage else (None, None)
        if has_coverage:
            coverage = _f(row, "cfads_coverage_usd")
            total_coverage += coverage
            if fee is not None:
                bridge_credit = _f(row, "bridge_cfads_usd", 0.0)
                in_project = _fee_in_project_basis(row)
                if in_project is not None:
                    difference = coverage - (cfads - bridge_credit) - in_project
                covenant_cfads = coverage - fee
                if covenant_service is not None and covenant_service > 0.0:
                    dscr = covenant_cfads / covenant_service
        rows.append(
            CashflowWaterfallRow(
                year=int(_f(row, "year", i + 1)),
                cfads=cfads,
                scheduled_debt_service=scheduled,
                balloon_sweep=balloon,
                cash_to_equity=cash_to_equity,
                coverage_cfads=coverage,
                bridge_cfads_credit=bridge_credit,
                fee_in_project_basis=in_project,
                tax_basis_difference=difference,
                senior_fee=fee,
                covenant_cfads=covenant_cfads,
                covenant_debt_service=covenant_service,
                covenant_dscr=dscr,
            )
        )
        total_cfads += cfads
        total_scheduled += scheduled
        total_balloon += balloon
        total_cash += cash_to_equity
    return CashflowWaterfall(
        currency=currency,
        rows=rows,
        total_cfads=total_cfads,
        total_scheduled_debt_service=total_scheduled,
        total_balloon_sweep=total_balloon,
        total_cash_to_equity=total_cash,
        has_coverage_basis=has_coverage,
        total_coverage_cfads=total_coverage if has_coverage else None,
    )


def verify_three_statement_waterfall_tieout(
    three_statement: ThreeStatementResult,
    equity_distribution: Mapping[str, Any],
    *,
    opening_cash: float = 0.0,
    tolerance: float = DEFAULT_TIEOUT_TOLERANCE,
) -> None:
    """Assert period-by-period equality between three statements and the equity waterfall (#1896).

    Verifies that all statement tie-outs pass and that distributions, DSRA reserve balances and
    movements, and SPV closing cash match ``equity_distribution["annual_distributions"]``
    period by period with non-negative closing cash. Raises ``ValueError`` on any divergence.
    """
    if three_statement.tie_outs is None or not three_statement.tie_outs.all_pass:
        raise ValueError(f"Three-statement tie-outs failed: {three_statement.tie_outs}")

    schedule = equity_distribution.get("annual_distributions")
    if not isinstance(schedule, Sequence) or isinstance(schedule, (str, bytes)):
        raise ValueError(
            "equity_distribution.annual_distributions is missing or invalid"
        )
    if len(three_statement.cash_flow) != len(schedule):
        raise ValueError(
            f"Cash-flow row count ({len(three_statement.cash_flow)}) != "
            f"waterfall schedule count ({len(schedule)})"
        )
    if len(three_statement.balance_sheet) != len(schedule):
        raise ValueError(
            f"Balance-sheet row count ({len(three_statement.balance_sheet)}) != "
            f"waterfall schedule count ({len(schedule)})"
        )

    prev_reserve = opening_cash
    wf_cash = opening_cash
    n_rows = len(schedule)
    for t, (cf, bs, er) in enumerate(
        zip(
            three_statement.cash_flow,
            three_statement.balance_sheet,
            schedule,
            strict=True,
        )
    ):
        year = cf.year
        wf_dist = _f(er, "equity_distribution_usd")
        stmt_dist = -cf.distributions
        if abs(stmt_dist - wf_dist) > tolerance:
            raise ValueError(
                f"Year {year}: statement distribution {stmt_dist:.2f} != "
                f"waterfall distribution {wf_dist:.2f}"
            )

        wf_res_bal = _f(er, "reserve_balance_usd")
        if abs(cf.reserve_balance - wf_res_bal) > tolerance:
            raise ValueError(
                f"Year {year}: statement reserve_balance {cf.reserve_balance:.2f} != "
                f"waterfall reserve_balance_usd {wf_res_bal:.2f}"
            )

        expected_mov = wf_res_bal - prev_reserve
        if abs(cf.reserve_movement - expected_mov) > tolerance:
            raise ValueError(
                f"Year {year}: statement reserve_movement {cf.reserve_movement:.2f} != "
                f"waterfall reserve movement {expected_mov:.2f}"
            )
        prev_reserve = wf_res_bal

        if cf.closing_cash < -tolerance:
            raise ValueError(
                f"Year {year}: statement closing_cash is negative ({cf.closing_cash:.2f})"
            )
        if abs(bs.cash - cf.closing_cash) > tolerance:
            raise ValueError(
                f"Year {year}: balance-sheet cash {bs.cash:.2f} != "
                f"cash-flow closing_cash {cf.closing_cash:.2f}"
            )

        wf_cash += (
            _f(er, "cf_pre_debt_usd")
            - _f(er, "debt_service_usd")
            - _f(er, "wht_on_interest_usd")
            - _f(er, "balloon_resolution_usd")
            - _f(er, "senior_fee_arrears_settled_usd")
            - _f(er, "wht_on_dividends_usd")
            - wf_dist
            + _f(er, "terminal_value_usd")
        )
        if abs(cf.closing_cash - wf_cash) > tolerance:
            raise ValueError(
                f"Year {year}: statement closing_cash {cf.closing_cash:.2f} != "
                f"waterfall SPV cash {wf_cash:.2f}"
            )
        if cf.closing_cash < wf_res_bal - tolerance:
            raise ValueError(
                f"Year {year}: statement closing_cash {cf.closing_cash:.2f} < "
                f"DSRA reserve balance {wf_res_bal:.2f}"
            )
        partition_sum = (
            cf.reserve_balance + cf.locked_cash_balance + cf.retained_cash_balance
        )
        if abs(partition_sum - cf.closing_cash) > tolerance:
            raise ValueError(
                f"Year {year}: SPV cash partition (reserve {cf.reserve_balance:.2f} + "
                f"locked {cf.locked_cash_balance:.2f} + "
                f"retained {cf.retained_cash_balance:.2f} = {partition_sum:.2f}) != "
                f"closing_cash {cf.closing_cash:.2f}"
            )
        if t == n_rows - 1 and abs(cf.closing_cash) > tolerance:
            raise ValueError(
                f"Year {year}: horizon closing_cash {cf.closing_cash:.2f} != 0 after terminal release"
            )


__all__ = [
    "DEFAULT_TIEOUT_TOLERANCE",
    "IncomeStatementRow",
    "CashFlowRow",
    "BalanceSheetRow",
    "TieOutStatus",
    "ThreeStatementResult",
    "CashflowWaterfallRow",
    "CashflowWaterfall",
    "build_three_statement",
    "build_three_statement_from_run",
    "build_cashflow_waterfall",
    "verify_three_statement_waterfall_tieout",
]
