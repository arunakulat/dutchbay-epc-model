"""Three-statement output (P&L / cash flow / balance sheet) with tie-out checks (#479).

Lenders expect the model's KPIs to be backed by three articulating financial statements. This
module assembles them from the engine's own annual outputs — it adds no new finance logic
(CESSPIT: every number originates from the enriched ``annual_rows`` + ``debt_result``), and is
an additive, read-only view that cannot perturb the economics (KPI-neutral).

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

Articulation — by construction, with one INDEPENDENT tie-out
------------------------------------------------------------
Paid-in equity is the funding plug (capitalised cost + opening cash − debt drawn); cash rolls
via the cash-flow statement; PP&E = capex + IDC + cumulative augmentation − accumulated
depreciation; retained earnings roll (RE = prior + net income − distributions); distributions
are the full free-cash sweep (CFO + CFI − debt repaid). With those roll-forwards the balance
sheet balances **by construction** every year — so ``balance_sheet_balances`` /
``cashflow_reconciles`` / ``retained_earnings_rolls`` are articulation invariants asserted as a
guard against a builder regression, NOT independent checks on the engine.

The genuinely **independent** tie-out is ``debt_retires_to_residual``: the per-row principal +
balloon repayments, summed, must retire the engine's independently-stated drawn debt down to its
stated balloon residual (within tolerance). It catches a debt stream that does not amortise the
financed debt — the real consistency signal.

Documented limitations (honest, not silently wrong): the tax line is the engine's computed tax
(the model sequences cashflow → debt sizing, so it does not re-credit the full debt-interest
shield); distributions assume a 100% sweep; equity is the balancing item.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence

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
    distributions: float  # negative (to equity)
    cff: float  # financing
    net_change_in_cash: float
    closing_cash: float


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
    """Status of the articulation invariants + the independent debt-retirement check.

    ``balance_sheet_balances`` / ``cashflow_reconciles`` / ``retained_earnings_rolls`` are
    articulation INVARIANTS — true by construction, asserted as a guard against a builder
    regression. ``debt_retires_to_residual`` is the genuinely INDEPENDENT consistency check
    (the per-row principal+balloon repayments must retire the engine's stated drawn debt to its
    stated balloon residual).
    """

    balance_sheet_balances: bool
    debt_retires_to_residual: bool
    cashflow_reconciles: bool
    retained_earnings_rolls: bool
    max_abs_balance_residual: float
    debt_retirement_residual: float
    tolerance: float

    @property
    def all_pass(self) -> bool:
        return (
            self.balance_sheet_balances
            and self.debt_retires_to_residual
            and self.cashflow_reconciles
            and self.retained_earnings_rolls
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

    Returns:
        A :class:`ThreeStatementResult` with the three statements and the tie-out status.
    """
    paid_in_equity = gross_capitalised_cost + opening_cash - debt_drawn

    income: List[IncomeStatementRow] = []
    cash_flow: List[CashFlowRow] = []
    balance_sheet: List[BalanceSheetRow] = []

    cash = opening_cash
    accum_dep = 0.0
    cum_aug = 0.0
    retained = 0.0
    debt_balance = debt_drawn
    total_repaid = 0.0
    max_residual = 0.0
    cf_reconciles = True
    re_rolls = True

    for t, row in enumerate(annual_rows):
        year = int(_f(row, "year", t + 1))
        fx = 1.0
        if fx_rates is not None and t < len(fx_rates):
            rate = _f({"r": fx_rates[t]}, "r", 0.0)
            fx = rate if rate > 0 else 1.0

        # ---- debt (per-row, engine-mapped; already in `currency`) ------------
        interest = _f(row, "interest_usd")
        service = _f(row, "debt_service_total")
        principal = service - interest
        balloon = _f(row, "balloon_resolution")
        total_debt_repaid = principal + balloon

        # ---- P&L (LKR lines -> currency via fx; EBIT = EBITDA − depreciation) -
        revenue = _f(row, "revenue_lkr") / fx
        opex = _f(row, "opex_lkr") / fx
        ebitda = _f(row, "ebitda_lkr") / fx
        dep = _f(row, "total_depreciation_lkr") / fx
        tax = _f(row, "tax_lkr") / fx
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
        cfo = net_income + dep  # interest & tax already in net income
        cfi = -aug
        # Full sweep of free cash to equity after ALL debt repaid (amortisation + balloon).
        distributions = max(0.0, cfo + cfi - total_debt_repaid)
        cff = -total_debt_repaid - distributions
        net_change = cfo + cfi + cff
        cash += net_change
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
                distributions=-distributions,
                cff=cff,
                net_change_in_cash=net_change,
                closing_cash=cash,
            )
        )

        # ---- balance sheet ---------------------------------------------------
        accum_dep += dep
        ppe_net = gross_capitalised_cost + cum_aug - accum_dep
        debt_balance -= total_debt_repaid
        total_repaid += total_debt_repaid
        retained += net_income - distributions
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
        if abs(retained - (prior_re + net_income - distributions)) > tolerance:
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
    for path in _CAPEX_USD_PATHS:
        cur: Any = config
        for key in path:
            cur = cur.get(key) if isinstance(cur, Mapping) else None
        value = _f({"v": cur}, "v", 0.0) if cur is not None else 0.0
        if value > 0:
            return value
    return None


def build_three_statement_from_run(
    pipeline_result: Mapping[str, Any],
    config: Mapping[str, Any],
    *,
    tolerance: float = DEFAULT_TIEOUT_TOLERANCE,
) -> Optional[ThreeStatementResult]:
    """Assemble the three statements (USD) from a ``run_v14_pipeline`` result, or ``None``.

    Reads the enriched ``annual_rows`` (LKR P&L + per-year USD debt columns) and ``debt_result``
    (the independent drawn debt + balloon residual + IDC). The capitalised asset base (USD) is
    the financed capex (config ``capex.usd_total``) + IDC. Returns ``None`` when the required
    inputs are absent (so callers attach it opportunistically).
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

    fx_rates = [_f(row, "fx_rate", 0.0) for row in annual_rows]
    return build_three_statement(
        annual_rows,
        debt_drawn=debt_drawn,
        balloon_residual=balloon_residual,
        gross_capitalised_cost=gross_capitalised,
        fx_rates=fx_rates,
        currency="USD",
        tolerance=tolerance,
    )


@dataclass(frozen=True)
class CashflowWaterfallRow:
    """One operating year of the cash-flow waterfall, ordered by payment priority (USD).

    Every figure is an engine-published per-row value, so the cascade ties line-for-line to the
    rest of the report: ``cfads`` is the lender CFADS (post-tax, post-maintenance-capex, and post
    the risk haircut the DSCR uses); ``scheduled_debt_service`` is interest + scheduled principal,
    the DSCR denominator; ``balloon_sweep`` is the bullet retired at maturity (senior to equity
    but NOT part of the scheduled DSCR); ``cash_to_equity`` is what remains for the sponsors.
    """

    year: int
    cfads: float
    scheduled_debt_service: float
    balloon_sweep: float
    cash_to_equity: float


@dataclass(frozen=True)
class CashflowWaterfall:
    """The CFADS → scheduled debt service → balloon → equity cascade per operating year + totals.

    Built from the engine's OWN published per-operating-year USD figures (``cf_pre_debt``,
    ``debt_service_total``, ``balloon_resolution``, ``cf_after_debt``) — a regrouping by payment
    priority, NOT a reconstruction. So ``cfads`` equals the CFADS the DSCR numerator uses (and
    ``total_cfads`` the report's headline CFADS), and ``scheduled_debt_service`` equals the Debt
    Structure & DSCR Profile section's debt service — the report does not present two
    contradictory coverage numbers. The balloon is shown SEPARATELY because it is senior to equity
    yet excluded from the scheduled DSCR. The model sweeps 100% of post-senior cash to equity, so
    ``cash_to_equity`` is the distribution (no reserve build-up beyond the DSRA funded at close).
    """

    currency: str
    rows: List[CashflowWaterfallRow] = field(default_factory=list)
    total_cfads: float = 0.0
    total_scheduled_debt_service: float = 0.0
    total_balloon_sweep: float = 0.0
    total_cash_to_equity: float = 0.0


def build_cashflow_waterfall(
    annual_rows: Sequence[Mapping[str, Any]],
    *,
    currency: str = "USD",
) -> CashflowWaterfall:
    """Regroup the engine's per-operating-year cash figures into a payment-priority waterfall.

    Sources every line from the engine's OWN published per-row USD columns so the waterfall ties
    line-for-line to the rest of the report — no reconstruction, no second source of truth:

    - ``cfads`` = ``cf_pre_debt`` — the risk-haircut, post-tax, post-maintenance-capex CFADS the
      DSCR numerator uses (so ``total_cfads`` matches the report's headline CFADS).
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

    Returns:
        A :class:`CashflowWaterfall` with the per-year cascade rows and project-life totals.
    """
    rows: List[CashflowWaterfallRow] = []
    total_cfads = 0.0
    total_scheduled = 0.0
    total_balloon = 0.0
    total_cash = 0.0
    for i, row in enumerate(annual_rows):
        cfads = _f(row, "cf_pre_debt")
        scheduled = _f(row, "debt_service_total")
        balloon = _f(row, "balloon_resolution")
        # cf_after_debt is the engine's own residual; reconstruct it only if a row omits it.
        cash_to_equity = _f(row, "cf_after_debt", cfads - scheduled - balloon)
        rows.append(
            CashflowWaterfallRow(
                year=int(_f(row, "year", i + 1)),
                cfads=cfads,
                scheduled_debt_service=scheduled,
                balloon_sweep=balloon,
                cash_to_equity=cash_to_equity,
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
]
