"""
analytics.mc.engine

Canonical Monte Carlo engine for v14 analytics.
GWTF/CASPER-friendly: no CLI code, no side-effectful imports at module import time.

Design goals
- Single public entrypoint: run_monte_carlo_analysis(...)
- Single engine class: MonteCarloEngine
- All production scenario evaluation goes through analytics.evaluation_v14.evaluate_with_overrides
- Correlation + degradation are optional steps (plug-ins), not separate engines.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import warnings
from dataclasses import asdict, dataclass
from statistics import NormalDist
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np

from analytics.contracts_v14 import MonteCarloResult
from analytics.core.covenant_breach import prob_breach
from analytics.evaluation_v14 import evaluate_with_overrides
from analytics.mc.aggregate import aggregate_trials
from analytics.mc.convergence import convergence_diagnostic, percentile_ci_diagnostic
from analytics.mc.correlation import (
    CorrelationSpec,
    align_correlation_to_params,
    apply_correlation_structure,
    load_correlation_from_config,
)

# MOVE -> SHIM (#639): the covenant-floor resolvers now live in the dependency-light
# analytics.mc.covenant module (shared with the CASPER mc_risk block, which must not
# import this heavy engine module). Re-exported here under their original private
# names so the engine path and any existing importer are behaviorally unchanged.
from analytics.mc.covenant import resolve_config_value as _resolve_config_value
from analytics.mc.covenant import (
    resolve_min_dscr_covenant as _resolve_min_dscr_covenant,
)
from analytics.mc.degradation import apply_degradation_if_enabled
from analytics.mc.fixed_debt_coverage import fixed_debt_coverage_by_row
from analytics.mc.samplers import generate_lhs_samples, generate_sobol_samples
from analytics.run_modes import POLICIES, resolve_run_mode

logger = logging.getLogger(__name__)


class MonteCarloConfigError(ValueError):
    """Raised when a ``monte_carlo`` config block does not match the engine contract.

    CESSPIT (schema strict) / CASPER (predictable error responses): a malformed
    ``monte_carlo.parameters`` block must fail with a clear, actionable message
    rather than a cryptic ``TypeError`` from deep inside the sampler. Subclasses
    :class:`ValueError` so existing ``except ValueError`` callers keep working.
    """


@dataclass(frozen=True)
class MonteCarloRunMeta:
    n_trials: int
    seed: int
    sampler: str
    common_random_numbers: bool
    param_names: Tuple[str, ...]
    config_hash: str


def _stable_config_hash(cfg: Mapping[str, Any]) -> str:
    payload = json.dumps(
        cfg, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def _num_override(overrides: Mapping[str, Any], *keys: str, default: float) -> float:
    """Resolve the first numeric override across the given keys, else ``default``.

    Robust to BOTH the generic smoke-test names ("capex") and the real dotted MC
    parameter names ("capex.usd_total"), and to NESTED override dicts: a value that is
    a mapping (e.g. ``{"capex": {"usd_total": ...}}`` from dotted-key expansion) is
    skipped rather than crashing ``float(dict)`` — which previously defeated this
    deliberately fail-soft fallback (audit R1).
    """
    for key in keys:
        value = overrides.get(key)
        if isinstance(value, bool):  # bool is an int subclass — not a numeric override
            continue
        if isinstance(value, (int, float)):
            return float(value)
    return float(default)


def _toy_metric_fallback(overrides: Mapping[str, Any]) -> dict[str, float]:
    """Return deterministic toy KPIs for MC engine smoke tests.

    This path is used only when the base configuration is intentionally minimal
    and cannot satisfy the full v14 finance schema. It keeps the MC sampler,
    aggregator, and export flow testable without weakening production schema
    validation in evaluation_v14 or pipeline_v14_enhanced.
    """
    capex = _num_override(overrides, "capex", "capex.usd_total", default=100.0)
    tariff = _num_override(overrides, "tariff", "tariff.lkr_per_kwh", default=0.10)
    capacity_factor = _num_override(
        overrides, "capacity_factor", "project.capacity_factor", default=0.35
    )
    opex = _num_override(overrides, "opex_annual", "opex.usd_per_year", default=2.5)

    capex_scale = capex / 100.0 if capex < 1_000_000 else capex / 100_000_000.0
    tariff_scale = tariff / 0.10 if tariff else 1.0
    cf_scale = capacity_factor / 0.35 if capacity_factor else 1.0
    opex_scale = opex / 2.5 if opex < 1_000_000 else opex / 2_500_000.0

    project_irr = max(0.0, 0.13 * tariff_scale * cf_scale / max(capex_scale, 0.01))
    dscr_min = max(0.01, 1.35 * tariff_scale * cf_scale / max(capex_scale, 0.01))
    project_npv = (
        tariff_scale * cf_scale - capex_scale - 0.05 * opex_scale
    ) * 10_000_000.0

    return {
        "project_irr": float(project_irr),
        "project_npv": float(project_npv),
        # Emit the SAME 7 canonical metric keys a real trial returns (incl. equity_irr /
        # equity_npv) so a run that MIXES real and toy-fallback trials yields uniform-length
        # metric arrays. Previously the toy path omitted the equity keys, so any run with
        # >=1 real trial built ragged arrays and tripped the equal-length guard, crashing
        # the whole MC. These remain toy smoke values (levered slightly off the project KPIs).
        "equity_irr": float(max(0.0, project_irr * 0.95)),
        "equity_npv": float(project_npv * 0.85),
        "dscr_min": float(dscr_min),
        "llcr": float(max(dscr_min * 1.10, 0.01)),
        "plcr": float(max(dscr_min * 1.05, 0.01)),
        # Tag so aggregate_trials can count toy-fallback usage and consumers can
        # detect a degenerate run where real evaluation failed on every trial.
        "_toy_fallback": True,
    }


def _resolve_percentiles(raw: Any) -> Optional[Tuple[int, ...]]:
    """Resolve a scenario's monte_carlo.percentiles into a sorted int tuple, else None.

    Returns None (so the aggregator's documented default applies —
    ``analytics.mc.aggregate.DEFAULT_PERCENTILES`` = (1, 5, 10, 50, 90, 95, 99),
    raw percentiles with P99/P1 first-class per #599) when the key is absent or
    malformed, rather than silently ignoring a well-formed request. A scenario
    that pins ``monte_carlo.percentiles`` (all committed lender/capex scenarios
    pin [10, 25, 50, 75, 90]) is honored exactly and is unaffected by the default.
    """
    if not isinstance(raw, (list, tuple)) or not raw:
        return None
    out: List[int] = []
    for p in raw:
        try:
            out.append(int(p))
        except (TypeError, ValueError):
            return None
    return tuple(sorted(out))


def _tail_risk(
    trial_metrics: Sequence[Mapping[str, Any]], confidence: float
) -> Dict[str, Dict[str, float]]:
    """Downside VaR/CVaR per metric at ``confidence`` from the raw trial arrays.

    CVaR here is the Expected Shortfall (ES) — the same statistic under its other
    standard name. For return-style metrics (higher is better) the downside lives in
    the lower tail, so VaR is the (1 - confidence) quantile and CVaR/ES is the mean of
    the trials at or below it. Consumes the scenario's var_confidence /
    cvar_confidence (previously ignored).

    Small-sample caveat: the tail mean rests on only ``(1 - confidence) * n`` trials —
    at n=1000 a 99% ES averages ~10 raw trials (too noisy for a covenant/pricing input
    on its own), and ES converges slower than the mean, so a tight mean CI from the
    post-hoc convergence diagnostic (``analytics.mc.convergence``, #643) does not
    certify the tail.
    """
    if not (0.0 < confidence < 1.0) or not trial_metrics:
        return {}
    q = 1.0 - confidence
    keys = {
        k
        for tm in trial_metrics
        for k, v in tm.items()
        if not k.startswith("_")
        and isinstance(v, (int, float))
        and not isinstance(v, bool)
    }
    out: Dict[str, Dict[str, float]] = {}
    for k in sorted(keys):
        vals = np.array(
            [
                float(tm[k])
                for tm in trial_metrics
                if isinstance(tm.get(k), (int, float))
                and not isinstance(tm.get(k), bool)
                and math.isfinite(float(tm[k]))
            ],
            dtype=float,
        )
        if vals.size == 0:
            continue
        var = float(np.quantile(vals, q))
        tail = vals[vals <= var]
        cvar = float(tail.mean()) if tail.size else var
        out[k] = {"var": var, "cvar": cvar}
    return out


def _finite(value: Any) -> Optional[float]:
    """``value`` as a finite float, else ``None`` (bools are not numbers here)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    out = float(value)
    return out if math.isfinite(out) else None


def _trial_fixed_debt_min_dscr(
    base_debt_result: Mapping[str, Any], trial_debt_result: Mapping[str, Any]
) -> Optional[float]:
    """Min covenant DSCR of a trial's CFADS against the FIXED (financial-close) debt.

    A committed loan cannot retroactively shrink when a production year disappoints, yet the
    per-trial pipeline RE-SIZES debt (DSCR sculpting), pinning every trial's min_dscr at the
    covenant target and reporting ZERO breach probability. This tests each trial's CFADS
    against the BASE case's committed debt instead, on the basis the covenant is tested on
    (#1728). The per-row coverage, its basis and its stated limits are
    :func:`analytics.mc.fixed_debt_coverage.fixed_debt_coverage_by_row` (moved there
    unchanged for #1836). Returns ``None`` when no operating row carries base service or the
    trial publishes no CFADS for those rows.
    """
    vals = [
        dscr
        for _, _, dscr in fixed_debt_coverage_by_row(
            base_debt_result, trial_debt_result
        )
    ]
    return min(vals) if vals else None


#: Distribution shapes the sampler can honor (besides the calibrated FX driver). A declared
#: shape outside this set is a config error (previously silently sampled uniform — decorative).
_SUPPORTED_DISTRIBUTIONS = frozenset({"uniform", "triangular", "normal", "lognormal"})
#: Parameters whose band must name where it comes from (#1898). An FX depreciation band
#: sets the main risk driver of an LKR-revenue project, so an unsourced one is refused
#: rather than sampled. ``source`` is a free-text citation on the parameter mapping.
_SOURCED_BAND_PARAMS = frozenset(
    {"fx.annual_depr", "opex.currency_split.usd_lkr_depreciation_pct"}
)
_Z975 = (
    1.959963984540054  # Phi^-1(0.975): low/high read as a 95% CI for normal/lognormal
)


def _inv_cdf_shaped(u: float, kind: str, low: float, high: float, mode: float) -> float:
    """Inverse-CDF of a non-uniform shape from a unit draw u in (0,1).

    ``low``/``high`` are the support for ``triangular`` (peak at ``mode``) and the ~95%
    confidence interval for ``normal``/``lognormal``. Keeping the draw a unit uniform lets
    the engine source it from the existing stratified-LHS / CRN / correlation machinery.
    """
    u = min(1.0 - 1e-12, max(1e-12, float(u)))
    if high <= low:
        return low
    if kind == "triangular":
        fc = (mode - low) / (high - low)
        if u < fc:
            return low + math.sqrt(u * (high - low) * (mode - low))
        return high - math.sqrt((1.0 - u) * (high - low) * (high - mode))
    if kind == "normal":
        mean = 0.5 * (low + high)
        sd = (high - low) / (2.0 * _Z975)
        return mean + sd * NormalDist(0.0, 1.0).inv_cdf(u) if sd > 0 else mean
    if kind == "lognormal":
        lo = low if low > 0 else 1e-12
        mu = 0.5 * (math.log(lo) + math.log(high))
        sigma = (math.log(high) - math.log(lo)) / (2.0 * _Z975)
        return (
            math.exp(mu + sigma * NormalDist(0.0, 1.0).inv_cdf(u))
            if sigma > 0
            else math.exp(mu)
        )
    return low + u * (high - low)  # uniform fallback (not normally reached)


class MonteCarloEngine:
    """Canonical Monte Carlo engine.

    Common random numbers (MC-9, #473): ``common_random_numbers`` (default true) applies
    CRN *within a single run* — every sampled driver dimension is drawn from one
    ``seed``-seeded stream, so re-running with the same seed reproduces the trial set exactly
    (MRM-01) and the stratified-LHS structure is shared across dimensions. CRN *across separate
    runs/variants* (e.g. pairing a base vs a stressed run on identical draws to reduce the
    variance of their difference) is a deliberately external concern: pass the SAME ``seed``
    (and the same param set/order) to both ``MonteCarloEngine`` instances and the draws line
    up. This is by design, not a defect — the engine does not implicitly couple two runs.

    Toy fallback (MC-9, #473): off by default (#962). A trial whose full v14 evaluation raises
    stops the run with the trial's error rather than reporting fabricated KPIs. A smoke config
    may opt in with ``monte_carlo.allow_toy_fallback: true``; the engine then appends a
    deterministic toy-metric stand-in so the run still yields an array, tags the trial
    ``_toy_fallback`` and counts it in ``toy_fallback_count``. Declared lender and IC modes
    forbid the fallback even if the config explicitly enables it.
    """

    def __init__(
        self,
        base_config: Mapping[str, Any],
        *,
        seed: int = 123,
        common_random_numbers: bool = True,
        correlation: Optional[CorrelationSpec] = None,
    ) -> None:
        # Deep-convert OmegaConf DictConfig to a plain dict so that
        # _deep_merge_config (in evaluation_v14) receives a fully plain
        # mapping.  A shallow dict(OmegaConf_object) leaves nested values
        # as DictConfig, which causes _deep_merge_config to overwrite them
        # with plain dicts on merge, silently dropping sibling keys that
        # were not in the override.  When base_config is already a plain
        # Mapping (the normal case from tests and CLI), this is a no-op.
        try:
            from omegaconf import DictConfig, OmegaConf

            if isinstance(base_config, DictConfig):
                self._base_config: Dict[str, Any] = OmegaConf.to_container(  # type: ignore[assignment]
                    base_config, resolve=True, throw_on_missing=False
                )
            else:
                self._base_config = dict(base_config)
        except ImportError:
            self._base_config = dict(base_config)

        self._seed = int(seed)
        self._crn = bool(common_random_numbers)
        # Honor an authored monte_carlo.correlation matrix by default: the complete, tested
        # correlation facility was wired into NO live path, so an enabled:true matrix in a
        # scenario was silently ignored and every driver sampled independently. An explicitly
        # passed CorrelationSpec still takes precedence; absent both, it stays None (independent
        # sampling, byte-identical for scenarios with no correlation block).
        self._correlation = (
            correlation
            if correlation is not None
            else load_correlation_from_config(self._base_config)
        )

        (
            self._param_names,
            self._param_bounds,
            self._param_kinds,
            self._dead_param_names,
            self._base_outside_bounds,
        ) = self._extract_param_definitions(self._base_config)
        self._refuse_native_capex_conflicts(
            self._base_config, self._param_names, self._param_kinds
        )
        self._refuse_bare_capex_on_full_scenario(self._base_config, self._param_names)
        # Opt-in per parameter (#1762): a swept capex.usd_total on a derive_from_breakdown
        # scenario scales the breakdown line items pro rata so the two stay reconciled.
        self._breakdown_reconciliation: Dict[str, str] = (
            self._extract_breakdown_reconciliation(self._base_config)
        )
        # #1629: dry-run the trial path's CAPEX resolution at each parameter's bounds and
        # refuse, before sampling, a sweep the trials would refuse. Runs while the bounds
        # are still the authored ones (_init_distribution_shapes rewrites shaped bounds).
        self._dry_run_capex_resolution()

        # MC-7 (#487): re-index the correlation matrix onto the ACTIVE parameter set. A
        # scenario authors its matrix against the parameters it declares; a consumer that
        # OVERRIDES monte_carlo.parameters (e.g. fx-calibration's single fx_calibrated driver)
        # while inheriting the correlation block would otherwise hit a shape mismatch in
        # apply_correlation_structure. align_correlation_to_params subsets/reorders via the
        # spec's param_names (no-op when they already match -> byte-identical lender case).
        self._correlation = align_correlation_to_params(
            self._correlation, self._param_names
        )

        _mc_cfg = self._base_config.get("monte_carlo", {})

        # Sampler selection (opt-in via monte_carlo.sampler: "sobol"). Default "lhs" keeps the
        # canonical Latin-Hypercube path — byte-identical to every existing run. Sobol is a
        # low-discrepancy QMC alternative offered for the model's SMOOTHER KPIs only (see
        # generate_sobol_samples / #589); it rounds the trial count up to a power of two.
        self._sampler: str = self._resolve_sampler(_mc_cfg)

        # Fixed-debt covenant-stress (opt-in via monte_carlo.fixed_debt_stress: true).
        self._fixed_debt_stress: bool = (
            bool(_mc_cfg.get("fixed_debt_stress", False))
            if isinstance(_mc_cfg, Mapping)
            else False
        )
        # Resolve outside the trial's fail-soft exception handler: a malformed mode must
        # never itself trigger fabricated KPIs. The existing policy is a permission ceiling;
        # permissive/undeclared modes retain the engine setting, including explicit false.
        self._run_mode = resolve_run_mode(self._base_config)
        # Off unless the config opts in (#962, owner decision 2026-11-21): a failed trial
        # stops the run rather than being replaced by a fabricated toy metric. Smoke configs
        # that exercise the toy path declare ``allow_toy_fallback: true``.
        self._allow_toy_fallback: bool = (
            bool(_mc_cfg.get("allow_toy_fallback", False))
            if isinstance(_mc_cfg, Mapping)
            else False
        )
        if self._run_mode is not None:
            self._allow_toy_fallback = (
                self._allow_toy_fallback and POLICIES[self._run_mode].allow_toy_fallback
            )
        self._fixed_debt_covenant: float = _resolve_min_dscr_covenant(self._base_config)

        # Market-calibrated FX driver (opt-in via a distribution: fx_calibrated param).
        self._fx_sampler: Any = None
        self._fx_param_index: Optional[int] = None
        self._fx_param_name: Optional[str] = None
        self._fx_drive_drift: bool = True
        self._fx_calibration: Any = None
        if "fx_calibrated" in self._param_kinds:
            self._init_fx_calibration()
        # #1898: a calibrated FX driver that also drives the drift writes fx.annual_depr on
        # every trial, so a separately sampled fx.annual_depr would be silently overwritten.
        if self._fx_calibration is not None and self._fx_drive_drift:
            if "fx.annual_depr" in self._param_names:
                raise MonteCarloConfigError(
                    "monte_carlo.parameters samples fx.annual_depr while the fx_calibrated "
                    "driver also sets it (monte_carlo.fx_calibration.drive_drift is true), "
                    "so the sampled draw would be overwritten. Remove one, or set "
                    "drive_drift: false."
                )

        # Hybrid CF coupling: when project.capacity_factor is swept on a multi-tech scenario,
        # the per-tech capacity factors must move WITH it or the in-cashflow ±1% reconciliation
        # raises (per-tech Σ cap·cf vs project cap·cf) — so the headline driver was inert
        # (every shocked trial fell to toy fallback). Captured here, applied per trial.
        self._cf_coupling: Optional[Tuple[float, Dict[str, float]]] = None
        self._init_cf_coupling()

        # Non-uniform sampler shapes (triangular/normal/lognormal) — opt-in per param. Before
        # this, a declared `distribution` was decorative (the sampler was uniform-only).
        self._shaped_params: Dict[int, Tuple[str, float, float, float]] = {}
        self._init_distribution_shapes()

        # Provenance stamp. Built here with the config-time fields (seed, sampler, CRN,
        # param_names, config_hash) that are known before a run; n_trials is filled with the
        # EFFECTIVE trial count in run() (which may exceed the request under Sobol rounding)
        # via _build_run_meta, so the frozen record is truthful rather than a n_trials=0
        # placeholder (#649). config_hash is consumed by the run() metadata dict.
        self._meta = self._build_run_meta(n_trials=0)

    def _build_run_meta(self, *, n_trials: int) -> MonteCarloRunMeta:
        """Assemble the immutable :class:`MonteCarloRunMeta` provenance stamp.

        Called once in ``__init__`` (with ``n_trials=0`` before any run) and re-called in
        ``run()`` with the effective trial count so the stamp records the number of trials
        actually evaluated (#649). All other fields are config-time invariants of the engine
        instance. Pure metadata — no KPI or behavioural effect.
        """
        return MonteCarloRunMeta(
            n_trials=int(n_trials),
            seed=self._seed,
            sampler=self._sampler,
            common_random_numbers=self._crn,
            param_names=tuple(self._param_names),
            config_hash=_stable_config_hash(self._base_config),
        )

    def _init_fx_calibration(self) -> None:
        """Resolve + calibrate the market FX driver once (opt-in fx_calibrated param).

        The pinned anchor spot is the scenario's own ``fx.start_lkr_per_usd``; the
        calibration (drift + regime-mixture vol) is built from the provenance-pinned
        historical vintage via :func:`analytics.fx.fx_calibration.calibrate_from_config`.
        """
        from analytics.fx.fx_calibration import calibrate_from_config

        idx = self._param_kinds.index("fx_calibrated")
        self._fx_param_index = idx
        self._fx_param_name = self._param_names[idx]

        fx_cfg = self._base_config.get("fx", {})
        fx_cfg = fx_cfg if isinstance(fx_cfg, Mapping) else {}
        rates = fx_cfg.get("rates", {})
        pinned = fx_cfg.get("start_lkr_per_usd") or (
            rates.get("lkr_per_usd") if isinstance(rates, Mapping) else None
        )
        if pinned is None:
            raise MonteCarloConfigError(
                "A distribution: fx_calibrated parameter requires fx.start_lkr_per_usd "
                "(the pinned anchor spot the calibrated shocks scale around)."
            )
        calibration = calibrate_from_config(
            self._base_config, pinned_spot=float(pinned)
        )
        mc = self._base_config.get("monte_carlo", {})
        fxc = mc.get("fx_calibration", {}) if isinstance(mc, Mapping) else {}
        self._fx_drive_drift = (
            bool(fxc.get("drive_drift", True)) if isinstance(fxc, Mapping) else True
        )
        self._fx_calibration = calibration
        self._fx_sampler = calibration.sampler()
        logger.info(
            "MC FX calibrated from %s vintage (%s..%s): annual_depr=%.4f, crisis_prob=%.3f, "
            "sigma_normal_1y=%.3f, sigma_crisis_1y=%.3f",
            calibration.provider,
            calibration.date_range[0],
            calibration.date_range[1],
            calibration.annual_depr,
            calibration.crisis_prob,
            calibration.sigma_normal_1y,
            calibration.sigma_crisis_1y,
        )

    @staticmethod
    def _set_dotted(overrides: Dict[str, Any], dotted: str, value: Any) -> None:
        """Set a (possibly dotted) key in the nested override dict."""
        keys = dotted.split(".")
        d = overrides
        for k in keys[:-1]:
            nxt = d.get(k)
            if not isinstance(nxt, dict):
                nxt = {}
                d[k] = nxt
            d = nxt
        d[keys[-1]] = value

    def _apply_fx_calibration(
        self, overrides: Dict[str, Any], sample_row: np.ndarray
    ) -> Dict[str, Any]:
        """Map the unit LHS draw for the fx_calibrated dim to a calibrated spot.

        Reads the unit draw u∈[0,1] for the FX dimension, maps it through the
        regime-mixture inverse-CDF to a spot, overwrites the fx override (the static
        builder placed the raw u there), injects the data-derived fx.annual_depr when
        drive_drift, and records the realised spot back into ``sample_row`` so the
        aggregated/reported MC input is the spot (not the unit draw).
        """
        if (
            self._fx_sampler is None
            or self._fx_param_index is None
            or self._fx_param_name is None
        ):
            return overrides
        u = float(sample_row[self._fx_param_index])
        spot = self._fx_sampler.spot_from_unit(u)
        self._set_dotted(overrides, self._fx_param_name, spot)
        if self._fx_drive_drift:
            self._set_dotted(overrides, "fx.annual_depr", self._fx_sampler.drift)
        sample_row[self._fx_param_index] = (
            spot  # record the spot for aggregation/reporting
        )
        return overrides

    def _init_cf_coupling(self) -> None:
        """Capture base CFs for hybrid project.capacity_factor coupling (if applicable).

        Active only when project.capacity_factor is a swept param AND the scenario carries
        per-tech generation capacity factors the year-1 reconciliation counts. The counted
        set is the one shared helper the tornado and global SA also use
        (``analytics.sensitivity.engine.coupled_technology_capacity_factors``, #1817), so a
        storage block or a numeric-string capacity factor is treated the same on every
        path. Wind-only scenarios with no generation.technologies block need no coupling
        (self._cf_coupling stays None).
        """
        if "project.capacity_factor" not in self._param_names:
            return
        from analytics.sensitivity.engine import coupled_technology_capacity_factors

        base_tech_cfs = coupled_technology_capacity_factors(self._base_config)
        proj = self._base_config.get("project")
        base_proj_cf = (
            proj.get("capacity_factor") if isinstance(proj, Mapping) else None
        )
        if not base_tech_cfs or not base_proj_cf:
            return
        self._cf_coupling = (float(base_proj_cf), base_tech_cfs)

    def _init_distribution_shapes(self) -> None:
        """Set up non-uniform shaped params: store (kind, low, high, mode) and rewrite the
        LHS bound to (0,1) so the sampler yields a stratified unit draw to inverse-CDF.

        Triangular mode defaults to the scenario's base value (peak at the deterministic case)
        when it lies in [low, high], else the band midpoint.
        """
        for idx, kind in enumerate(self._param_kinds):
            if kind not in ("triangular", "normal", "lognormal"):
                continue
            low, high = self._param_bounds[idx]
            base = _resolve_config_value(self._base_config, self._param_names[idx])
            mode = (
                base
                if (base is not None and low <= base <= high)
                else 0.5 * (low + high)
            )
            self._shaped_params[idx] = (kind, float(low), float(high), float(mode))
            self._param_bounds[idx] = (0.0, 1.0)

    def _apply_distribution_shapes(
        self, overrides: Dict[str, Any], sample_row: np.ndarray
    ) -> Dict[str, Any]:
        """Map each shaped param's unit LHS draw through its inverse-CDF, overwriting the raw
        unit value the static builder placed and recording the shaped value for aggregation.
        """
        if not self._shaped_params:
            return overrides
        for idx, (kind, low, high, mode) in self._shaped_params.items():
            val = _inv_cdf_shaped(float(sample_row[idx]), kind, low, high, mode)
            self._set_dotted(overrides, self._param_names[idx], val)
            sample_row[idx] = val
        return overrides

    def _apply_cf_coupling(self, overrides: Dict[str, Any]) -> Dict[str, Any]:
        """Scale per-tech capacity factors with a swept project.capacity_factor (hybrid).

        Keeps the in-cashflow ±1% reconciliation valid (per-tech Σ cap·cf == project cap·cf)
        by scaling every per-tech CF by the same shock ratio, so the headline CF driver
        actually moves combined-plant production instead of raising. Mirrors the coupled
        override in analytics.portfolio.multi_tech_tornado.
        """
        if self._cf_coupling is None:
            return overrides
        base_proj_cf, base_tech_cfs = self._cf_coupling
        proj = overrides.get("project")
        cf = proj.get("capacity_factor") if isinstance(proj, Mapping) else None
        if cf is None or base_proj_cf == 0:
            return overrides
        ratio = float(cf) / base_proj_cf
        for tech, base_cf in base_tech_cfs.items():
            self._set_dotted(
                overrides,
                f"generation.technologies.{tech}.capacity_factor",
                base_cf * ratio,
            )
        return overrides

    @staticmethod
    def _refuse_native_capex_conflicts(
        cfg: Mapping[str, Any], names: List[str], kinds: List[str]
    ) -> None:
        """Refuse sweeps that every trial of a native-CAPEX scenario would reject.

        A scenario authored with ``capex.input`` (or already resolved to
        ``capex.native_input_applied``) owns its USD CAPEX. On an authored config,
        ``fx.start_lkr_per_usd`` and ``fx_calibrated`` sweeps are supported because
        ``normalize_native_capex`` derives the LKR conversion rate from
        ``fx.start_lkr_per_usd`` (DOM-1645-03). On an already-resolved config
        (``capex.native_input_applied``), FX sweeps would fail every trial with
        stale provenance, so they remain refused before sampling. The ``capex``
        alias, ``capex.usd_total``, ``capex.contingency_pct``, and
        ``capex.input.conversion.rate_lkr_per_usd`` are always refused (#1629,
        DOM-1645-R5-01).
        """
        capex = cfg.get("capex") if isinstance(cfg, Mapping) else None
        if not isinstance(capex, Mapping) or not (
            "input" in capex or "native_input_applied" in capex
        ):
            return
        is_resolved = "native_input_applied" in capex
        blocked = {
            "capex",
            "capex.usd_total",
            "capex.contingency_pct",
            "capex.input.conversion.rate_lkr_per_usd",
        }
        for name, kind in zip(names, kinds, strict=True):
            lowered = name.strip().lower()
            if lowered in blocked:
                raise MonteCarloConfigError(
                    f"monte_carlo parameter {name!r} cannot be swept on a native-CAPEX "
                    "scenario (capex.input): every trial would refuse it. Sweep "
                    "capex.input.amount for CAPEX or fx.start_lkr_per_usd for FX (#1629)."
                )
            if is_resolved and (
                kind == "fx_calibrated" or lowered == "fx.start_lkr_per_usd"
            ):
                raise MonteCarloConfigError(
                    f"monte_carlo parameter {name!r} cannot be swept on an already-resolved "
                    "native-CAPEX scenario (capex.native_input_applied): every trial would "
                    "refuse stale provenance. Start from the authored config (#1629)."
                )

    @staticmethod
    def _refuse_bare_capex_on_full_scenario(
        cfg: Mapping[str, Any], names: Sequence[str]
    ) -> None:
        """Refuse a bare ``capex`` parameter on a scenario that carries a capex section (#1793).

        A parameter named ``capex`` (any case or padding) overrides the whole capex section
        with one number. On a full scenario every trial then refuses it (a cost section that
        is not a mapping, #1767), so the run could only report toy KPIs or fail late. The
        native-CAPEX guard already refuses the name on ``capex.input`` scenarios; this covers
        the USD ones. A config with no capex mapping in any spelling is the minimal smoke
        config, whose toy metric reads ``capex`` directly, so the name stays accepted there.
        """
        if not isinstance(cfg, Mapping):
            return
        if not any(
            isinstance(key, str)
            and key.strip().lower() == "capex"
            and isinstance(value, Mapping)
            for key, value in cfg.items()
        ):
            return
        for name in names:
            if name.strip().lower() == "capex":
                raise MonteCarloConfigError(
                    f"monte_carlo parameter {name!r} is refused before sampling (#1793): it "
                    "overrides the whole capex section with one number, which every trial "
                    "of a full scenario refuses (the #1629 trial-path check). Sweep "
                    "capex.usd_total on a USD scenario, or capex.input.amount on a "
                    "native-CAPEX scenario."
                )

    @staticmethod
    def _extract_breakdown_reconciliation(cfg: Mapping[str, Any]) -> Dict[str, str]:
        """Read and validate each parameter's opt-in ``reconcile_breakdown`` (#1762).

        The declaration is read by the one shared helper the tornado and global SA also
        use (``analytics.sensitivity.engine.declared_breakdown_reconciliation``, #1817);
        an invalid declaration is a :class:`MonteCarloConfigError` here.
        """
        from analytics.sensitivity.engine import declared_breakdown_reconciliation

        try:
            return declared_breakdown_reconciliation(cfg)
        except ValueError as exc:
            raise MonteCarloConfigError(str(exc)) from exc

    def _apply_breakdown_reconciliation(
        self, overrides: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Scale ``capex.breakdown`` pro rata to a sampled ``capex.usd_total`` (#1762).

        Only for a parameter that declared ``reconcile_breakdown: pro_rata``. Each numeric
        breakdown line is multiplied by ``sampled total / base breakdown sum``, so the
        lines sum to the sampled total and the trial path's cross-check holds.
        """
        if "capex.usd_total" not in self._breakdown_reconciliation:
            return overrides
        capex_ov = overrides.get("capex")
        sampled = (
            _finite(capex_ov.get("usd_total"))
            if isinstance(capex_ov, Mapping)
            else None
        )
        if sampled is None:
            return overrides
        from analytics.sensitivity.engine import pro_rata_breakdown

        for key, value in pro_rata_breakdown(self._base_config, sampled).items():
            self._set_dotted(overrides, f"capex.breakdown.{key}", value)
        return overrides

    def _dry_run_capex_resolution(self) -> None:
        """Refuse, before sampling, a sweep whose trials the CAPEX resolution would refuse.

        #1629: a hand-kept list of refused names drifts out of step with the code that
        refuses. Instead, merge the base config with each parameter's low and then its
        high bound, exactly as a trial builds its overrides, and run the trial path's own
        config checks: the strict pre-flight ``run_v14_pipeline`` runs on every trial
        (native CAPEX normalisation, then ``validate_config_for_v14`` for the cashflow and
        debt modules) and the CAPEX resolution (``finance.debt.capex._extract_capex_usd``:
        cost-currency checks, the breakdown reconciliation and the import levies). A bound
        that fails there fails the trials near it, so the run is refused with the
        parameter, the bound and the reason named. It runs no cashflow, so it costs a
        small fraction of one trial.

        When the base config itself does not resolve (a minimal smoke config), there is
        nothing to attribute to a parameter and the dry run stands aside; the trials then
        behave exactly as before. The FX-calibrated driver samples a unit draw, not a
        config value, so it is not dry-run.
        """
        from analytics.evaluation_v14 import _deep_merge_config
        from analytics.schema_guard import validate_config_for_v14
        from finance.capex_price_basis import apply_capex_price_basis
        from finance.debt_v14 import _extract_capex_usd
        from finance.native_cost_inputs import normalize_native_capex

        def _check(overrides: Mapping[str, Any]) -> None:
            # As each trial's pipeline run does: a declared capex.price_basis is
            # applied before capex is read (#1899).
            cfg = apply_capex_price_basis(
                normalize_native_capex(_deep_merge_config(self._base_config, overrides))
            )
            validate_config_for_v14(
                raw_config=cfg,
                config_path="<monte_carlo dry run>",
                modules=["cashflow", "debt"],
            )
            _extract_capex_usd(cfg)

        try:
            _check({})
        except Exception:  # noqa: BLE001 - the base's own failure is reported elsewhere
            return

        for idx, (name, kind) in enumerate(
            zip(self._param_names, self._param_kinds, strict=True)
        ):
            if kind == "fx_calibrated":
                continue
            low, high = self._param_bounds[idx]
            failures: List[str] = []
            for label, value in (("low", low), ("high", high)):
                overrides = self._build_overrides_from_sample(
                    np.array([value], dtype=float), [name]
                )
                overrides = self._apply_breakdown_reconciliation(overrides)
                try:
                    _check(overrides)
                except Exception as exc:  # noqa: BLE001 - every refusal is reported
                    failures.append(f"{label} {value:.6g}: {exc}")
            if not failures:
                continue
            hint = ""
            capex = self._base_config.get("capex")
            if isinstance(capex, Mapping):
                if "native_input_applied" in capex and name.startswith("capex.input"):
                    hint = (
                        " This config is already resolved (capex.native_input_applied); "
                        "start the Monte Carlo from the authored config (capex.input)."
                    )
                elif capex.get("derive_from_breakdown") and name == "capex.usd_total":
                    hint = (
                        " The scenario derives CAPEX from capex.breakdown; declare "
                        "reconcile_breakdown: pro_rata on this parameter to scale the "
                        "breakdown with the sampled total."
                    )
            raise MonteCarloConfigError(
                f"monte_carlo.parameters[{idx}].name {name!r}: the trial path refuses "
                f"this sweep, so it is refused before sampling (#1629). "
                + "; ".join(failures)
                + "."
                + hint
            )

    @staticmethod
    def _extract_param_definitions(
        cfg: Mapping[str, Any],
    ) -> Tuple[List[str], List[Tuple[float, float]], List[str], List[str], List[str]]:
        mc = cfg.get("monte_carlo", {}) if isinstance(cfg, Mapping) else {}
        params = mc.get("parameters", []) or mc.get("params", [])

        # CESSPIT (schema strict): the engine contract is an explicit *list* of
        # ``{name, low, high[, distribution]}`` mappings. A bare mapping (e.g.
        # ``{capacity_factor_std: 0.05, ...}``) is a different, incompatible
        # schema; iterating it would yield string keys and ``p["name"]`` would
        # raise an opaque ``TypeError``. Reject it up-front with a clear message
        # naming the exact field and the expected shape.
        if isinstance(params, Mapping):
            raise MonteCarloConfigError(
                "monte_carlo.parameters must be a LIST of "
                "{name, low, high[, distribution]} mappings, but a mapping "
                f"(dict) was provided with keys {sorted(params)!r}. A dict of "
                "per-parameter scalars is not the engine contract — convert it "
                "to an explicit list of parameter definitions with dotted "
                "config paths as `name` (e.g. "
                "[{name: project.capacity_factor, low: 0.276, high: 0.338}])."
            )

        param_names: List[str] = []
        bounds: List[Tuple[float, float]] = []
        kinds: List[str] = []
        dead_names: List[str] = []
        base_outside: List[str] = []

        for idx, p in enumerate(params):
            if not isinstance(p, Mapping) or "name" not in p:
                raise MonteCarloConfigError(
                    f"monte_carlo.parameters[{idx}] must be a mapping with a "
                    f"'name' key (a dotted config path), got {type(p).__name__}: "
                    f"{p!r}."
                )
            name = str(p["name"])
            kind = str(p.get("distribution", p.get("kind", "uniform")))

            # Market-calibrated FX spot driver: the LHS samples a UNIT uniform [0,1]
            # for this dimension; _apply_fx_calibration maps it through the regime-mixture
            # inverse-CDF (analytics.fx.fx_calibration) to a spot and also injects the
            # data-derived fx.annual_depr. low/high are engine-set (not authored) and the
            # name resolves (fx.start_lkr_per_usd), so the dead-key check does not apply.
            if kind == "fx_calibrated":
                param_names.append(name)
                bounds.append((0.0, 1.0))
                kinds.append(kind)
                continue

            # A declared distribution shape the sampler can't produce must FAIL LOUD, not be
            # silently sampled uniform (the shape was decorative before this guard).
            if kind not in _SUPPORTED_DISTRIBUTIONS:
                raise MonteCarloConfigError(
                    f"monte_carlo.parameters[{idx}].name {name!r}: unsupported distribution "
                    f"{kind!r}. Use one of {sorted(_SUPPORTED_DISTRIBUTIONS)} (or fx_calibrated)."
                )

            low = float(p.get("low", p.get("min", 0.0)))
            high = float(p.get("high", p.get("max", 1.0)))

            # Bounds must be well-ordered — a transposed/typo'd band is a hard config error.
            if low > high:
                raise MonteCarloConfigError(
                    f"monte_carlo.parameters[{idx}].name {name!r}: low ({low}) > high ({high}) "
                    "— MC bounds must be well-ordered (low <= high)."
                )

            # #1898: an FX depreciation band must cite its source.
            if name in _SOURCED_BAND_PARAMS:
                source = p.get("source")
                if not isinstance(source, str) or not source.strip():
                    raise MonteCarloConfigError(
                        f"monte_carlo.parameters[{idx}].name {name!r}: an FX depreciation "
                        "band must declare a non-empty 'source' naming where its low and "
                        "high come from (#1898). Refusing to sample an unsourced band."
                    )

            # A param name that does not resolve to an EXISTING dotted path in the base
            # config is a likely DEAD lever. Contrary to the toy-fallback story, the
            # sampled override is NOT rejected: _build_overrides_from_sample expands it and
            # _deep_merge_config silently ADDS it as a brand-new config key the v14 pipeline
            # never reads, so full evaluation SUCCEEDS on every trial with REAL KPIs — but
            # the swept value moves NOTHING. The result is a fake-stable, zero-variance risk
            # distribution with toy_fallback_count == 0, which the prior warning mis-described
            # (it claimed trials fall to the toy metric — they do not). We WARN rather than
            # raise because non-dotted ALIASES are an accepted legacy input and DO move
            # outputs; the genuinely dead names are caught downstream by the post-run
            # zero-dispersion check (metadata['degenerate_sweep']) and recorded in
            # metadata['dead_param_names'].
            from analytics.sensitivity.engine import _resolves_in_config

            if not _resolves_in_config(cfg, name):
                dead_names.append(name)
                logger.warning(
                    "monte_carlo.parameters[%d].name %r does not resolve to an existing "
                    "config path; its sampled override may be merged as an UNREAD key, so "
                    "trials succeed with real KPIs but the lever moves nothing -> a possibly "
                    "DEGENERATE (zero-variance) risk distribution. Prefer a valid dotted "
                    "path (e.g. capex.usd_total, project.capacity_factor). The post-run "
                    "degenerate_sweep flag confirms whether dispersion actually collapsed.",
                    idx,
                    name,
                )
            else:
                # Distribution-integrity check: the sampled band SHOULD contain the
                # scenario's own deterministic base, so MC P50 reconciles to the base case.
                # A band that excludes its base (a stale/copy-pasted spread) yields real-
                # looking percentiles that are silently mis-centered. Warn loudly + record
                # in metadata (mirrors dead_param_names); not a hard raise, since an
                # intentionally one-sided downside band (e.g. curtailment_pct base 0.0 in
                # [0.0, 0.13]) legitimately sits at an edge.
                base_val = _resolve_config_value(cfg, name)
                if base_val is not None and not (low <= base_val <= high):
                    base_outside.append(name)
                    logger.warning(
                        "monte_carlo.parameters[%d].name %r deterministic base %.6g is OUTSIDE "
                        "its MC band [%.6g, %.6g]; the sampled distribution does not contain the "
                        "base case, so MC P50 will not reconcile to the deterministic run.",
                        idx,
                        name,
                        base_val,
                        low,
                        high,
                    )

            param_names.append(name)
            bounds.append((low, high))
            kinds.append(kind)

        if not param_names:
            raise MonteCarloConfigError(
                "Monte Carlo config has no parameters "
                "(monte_carlo.parameters is empty)."
            )

        return param_names, bounds, kinds, dead_names, base_outside

    @staticmethod
    def _resolve_sampler(mc_cfg: Any) -> str:
        """Resolve the validated sampler identity ("lhs"|"sobol") from the config block.

        The live selector is ``monte_carlo.sampler``. ``monte_carlo.sampling_method`` is a
        DEPRECATED ALIAS retained for back-compat (#648): historically it was a decorative,
        never-read key, so a scenario setting ``sampling_method: sobol`` silently ran LHS. It
        is now honored — mapped onto ``sampler`` with a ``DeprecationWarning`` — rather than
        removed, per CESSPIT (accept the config surface, fail loud only on genuine conflict)
        and the ask-before-delete directive. Precedence when BOTH are present:

        - identical values -> use it, warn to migrate to ``sampler``;
        - different values -> ``sampler`` wins (the live key is authoritative), warn that the
          alias is being ignored — never silently pick the deprecated one.

        Every committed scenario carries ``sampling_method: lhs`` (== the ``sampler`` default),
        so this resolution is byte-identical for all of them (guarded by the KPI oracle).
        """
        if not isinstance(mc_cfg, Mapping):
            return "lhs"

        def _norm(raw: Any) -> str:
            value = str(raw).strip().lower()
            if value not in ("lhs", "sobol"):
                raise MonteCarloConfigError(
                    f"monte_carlo.sampler must be 'lhs' or 'sobol', got {value!r}."
                )
            return value

        has_sampler = "sampler" in mc_cfg
        has_alias = "sampling_method" in mc_cfg
        sampler = _norm(mc_cfg.get("sampler", "lhs"))

        if has_alias:
            alias = _norm(mc_cfg.get("sampling_method"))
            if has_sampler and alias != sampler:
                msg = (
                    "monte_carlo.sampling_method is a deprecated alias for "
                    f"monte_carlo.sampler and conflicts with it (alias={alias!r}, "
                    f"sampler={sampler!r}); the live 'sampler' key wins. Remove "
                    "'sampling_method' and set 'sampler' only."
                )
            else:
                # Alias-only (or agreeing) -> honor it so `sampling_method: sobol` no longer
                # silently runs LHS. When sampler is absent the alias becomes the selection.
                msg = (
                    "monte_carlo.sampling_method is a deprecated alias for "
                    "monte_carlo.sampler; rename the key to 'sampler'."
                )
                if not has_sampler:
                    sampler = alias
            # Dual channel: warnings.warn for tooling/pytest, AND logger.warning so a real
            # CLI/pipeline user actually SEES it — Python's default filters suppress
            # library-code DeprecationWarnings outside __main__, so the warnings.warn alone
            # is invisible to the very user setting the dead key (the conflict case worst of
            # all, where their key is being ignored). Mirrors the engine's sobol+CRN caveat.
            warnings.warn(msg, DeprecationWarning, stacklevel=2)
            logger.warning(msg)

        return sampler

    def run(self, *, n_trials: int) -> MonteCarloResult:
        n_requested = int(n_trials)
        if n_requested <= 0:
            raise ValueError("n_trials must be > 0")

        if self._sampler == "sobol":
            # Sobol rounds n up to the next power of two (balance is only kept at 2**m); ALL
            # 2**m points are used, so the effective trial count may exceed the request. n is
            # re-derived from the returned sample count below so the loop, aggregator and
            # metadata all agree on the number of trials actually evaluated.
            samples = generate_sobol_samples(
                n_trials=n_requested,
                bounds=self._param_bounds,
                seed=self._seed,
            )
        else:
            samples = generate_lhs_samples(
                n_trials=n_requested,
                bounds=self._param_bounds,
                seed=self._seed,
                # Sampler-level name (#586): the engine-level CRN flag maps onto the
                # sampler's permutation-stream selector (see samplers.py docstring).
                shared_permutation_stream=self._crn,
            )

        n = int(samples.shape[0])  # effective trial count (Sobol may round up to 2**m)
        # Refresh the provenance stamp with the EFFECTIVE trial count now that sampling has
        # fixed it (Sobol may round the request up to a power of two) — replacing the
        # config-time n_trials=0 placeholder with a truthful record (#649).
        self._meta = self._build_run_meta(n_trials=n)

        if self._correlation is not None and self._correlation.enabled:
            if self._sampler == "sobol":
                # Correlation-induced rank-reordering (Iman-Conover and the opt-in Gaussian
                # copula alike, #601) preserves each driver's marginal but destroys the JOINT
                # low-discrepancy structure Sobol was chosen for — the balance benefit then
                # only accrues to the marginals. Warn once so an opted-in user is not misled.
                logger.warning(
                    "monte_carlo.sampler='sobol' with an enabled correlation block: "
                    "the '%s' rank-reordering preserves marginals but destroys the joint "
                    "Sobol low-discrepancy structure (the QMC benefit is limited to the "
                    "marginals). Disable correlation to retain the full QMC balance.",
                    self._correlation.method,
                )
            samples = apply_correlation_structure(
                lhs_samples=samples,
                correlation=self._correlation,
                seed=self._seed,
            )

        trial_metrics: List[Mapping[str, Any]] = []

        # Fixed-debt covenant-stress: size debt ONCE on the base (financial-close) schedule,
        # then test each trial's CFADS against that committed service (a committed loan cannot
        # shrink when production disappoints), on the covenant's dscr_by_year basis (#1728).
        # Off by default -> no base eval, full results not requested, byte-identical.
        base_debt_result: Mapping[str, Any] = {}
        fixed_dscr_vals: List[float] = []
        stress_unavailable: Optional[str] = None
        if self._fixed_debt_stress:
            base_full = evaluate_with_overrides(
                config_path=None,
                raw_config=self._base_config,
                overrides={},
                return_full_result=True,
            )
            if isinstance(base_full, Mapping):
                _bdr: Any = base_full.get("debt_result", {})
                if isinstance(_bdr, Mapping):
                    base_debt_result = _bdr
            if _trial_fixed_debt_min_dscr(base_debt_result, base_debt_result) is None:
                stress_unavailable = (
                    "the base case has no operating period with committed debt service, "
                    "so there is no covenant to stress"
                )
                self._fixed_debt_stress_unavailable(stress_unavailable)

        for i in range(n):
            overrides = self._build_overrides_from_sample(samples[i], self._param_names)
            overrides = self._apply_distribution_shapes(overrides, samples[i])
            overrides = self._apply_breakdown_reconciliation(overrides)
            overrides = self._apply_cf_coupling(overrides)
            overrides = self._apply_fx_calibration(overrides, samples[i])
            overrides = apply_degradation_if_enabled(
                base_cfg=self._base_config, overrides=overrides
            )

            try:
                out = evaluate_with_overrides(
                    config_path=None,
                    raw_config=self._base_config,
                    overrides=overrides,
                    return_full_result=self._fixed_debt_stress,
                )
                if isinstance(out, Mapping):
                    kpis = out.get("kpis", out)
                    trial_metrics.append(kpis if isinstance(kpis, Mapping) else out)
                else:
                    trial_metrics.append({})
            except Exception as exc:
                # MC-9 (#473): fail loud when the scenario has opted out of the fallback —
                # a production run must not silently report fabricated toy KPIs.
                if not self._allow_toy_fallback:
                    raise RuntimeError(
                        f"MC trial {i} failed full v14 evaluation and "
                        "effective monte_carlo.allow_toy_fallback is false, so the toy-metric fallback "
                        "is disabled (a production run must not report fabricated KPIs). Fix "
                        "the underlying scenario/config error. Toy fallback is permitted only "
                        "outside lender/IC modes with allow_toy_fallback enabled, for smoke "
                        f"runs. Underlying error: {exc}"
                    ) from exc
                # WARNING, not DEBUG: on a production scenario a toy fallback
                # means real evaluation FAILED for this trial; silently swallowing
                # it at DEBUG let an all-failing run report success_rate=100% with
                # fabricated KPIs. aggregate_trials surfaces toy_fallback_count.
                logger.warning(
                    "MC trial %d used toy fallback because full v14 evaluation failed: %s",
                    i,
                    exc,
                )
                trial_metrics.append(_toy_metric_fallback(overrides))
                continue

            # Outside the trial's fail-soft handler, so a missing stress result can never be
            # mistaken for a failed evaluation and turned into a toy trial.
            if self._fixed_debt_stress and stress_unavailable is None:
                _tdr: Any = (
                    out.get("debt_result", {}) if isinstance(out, Mapping) else {}
                )
                mfd = _trial_fixed_debt_min_dscr(
                    base_debt_result, _tdr if isinstance(_tdr, Mapping) else {}
                )
                if mfd is not None:
                    fixed_dscr_vals.append(mfd)
                elif not self._allow_toy_fallback:
                    self._fixed_debt_stress_unavailable(
                        f"MC trial {i} published no CFADS for the base case's covenant "
                        "periods"
                    )

        # Honor the scenario's monte_carlo reporting config (previously ignored): the
        # requested percentiles drive the aggregator, and var_confidence / cvar_confidence
        # compute downside VaR/CVaR per metric from the raw trial arrays.
        mc_cfg = self._base_config.get("monte_carlo", {})
        if not isinstance(mc_cfg, Mapping):
            mc_cfg = {}
        percentiles = _resolve_percentiles(mc_cfg.get("percentiles"))

        meta: Dict[str, Any] = {
            "seed": self._seed,
            "sampler": self._sampler,
            # CRN is a property of the pseudo-random LHS draw; it is inapplicable to a
            # deterministic Sobol' net, so record null rather than a misleading flag there.
            "common_random_numbers": (self._crn if self._sampler != "sobol" else None),
            "n_trials": n,
            "config_hash": self._meta.config_hash,
            "param_names": list(self._param_names),
            "dead_param_names": list(self._dead_param_names),
            "base_outside_bounds": list(self._base_outside_bounds),
            "correlation_enabled": bool(
                self._correlation and self._correlation.enabled
            ),
            "allow_toy_fallback": self._allow_toy_fallback,
        }
        if self._sampler == "sobol" and n != n_requested:
            # Surface that Sobol rounded the request up to a power of two so a downstream
            # consumer never silently mistakes the effective trial count for the requested one.
            meta["sobol_n_requested"] = n_requested
            meta["sobol_n_used"] = n
        if self._fixed_debt_stress and not fixed_dscr_vals:
            # Permissive runs only (a lender-posture run raised above): record why there is
            # no stress result instead of leaving the key silently absent (#1728).
            reason = stress_unavailable or "no trial produced a covenant observation"
            logger.warning("monte_carlo.fixed_debt_stress is on but %s.", reason)
            meta["fixed_debt_stress"] = {"status": "unavailable", "reason": reason}
        if self._fixed_debt_stress and fixed_dscr_vals:
            arr = sorted(fixed_dscr_vals)
            cov = float(self._fixed_debt_covenant)

            def _q(p: float) -> float:
                k = (len(arr) - 1) * p
                lo = math.floor(k)
                hi = math.ceil(k)
                return arr[lo] if lo == hi else arr[lo] * (hi - k) + arr[hi] * (k - lo)

            meta["fixed_debt_stress"] = {
                "status": "ok",
                # dscr_by_year: the per-year covenant table, bridge service folded into
                # operating year 1, against the committed debt service and senior fee.
                "basis": "dscr_by_year",
                "covenant": cov,
                # Delegate probability classification to the noise-tolerant covenant SSOT.
                "breach_probability": prob_breach(np.asarray(arr, dtype=float), cov),
                "n": len(arr),
                "min_dscr_p10": _q(0.10),
                "min_dscr_p50": _q(0.50),
                "min_dscr_p90": _q(0.90),
                "min_dscr_min": arr[0],
                "min_dscr_max": arr[-1],
            }
        var_conf = float(mc_cfg.get("var_confidence", 0.0) or 0.0)
        cvar_conf = float(mc_cfg.get("cvar_confidence", 0.0) or 0.0)
        if var_conf > 0.0:
            meta["var_confidence"] = var_conf
            meta["var_cvar"] = _tail_risk(trial_metrics, var_conf)
        if cvar_conf > 0.0 and cvar_conf != var_conf:
            meta["cvar_confidence"] = cvar_conf
            meta["cvar_at_cvar_confidence"] = _tail_risk(trial_metrics, cvar_conf)
        elif cvar_conf > 0.0:
            meta["cvar_confidence"] = cvar_conf

        kwargs: Dict[str, Any] = dict(
            trial_metrics=trial_metrics,
            base_config=self._base_config,
            param_names=self._param_names,
            samples=samples,
            meta=meta,
        )
        if percentiles is not None:
            kwargs["percentiles"] = percentiles
        result = aggregate_trials(**kwargs)
        self._flag_degenerate_sweep(result)
        # Read-only convergence diagnostic (running mean + CI half-width vs n) so a reader
        # can see whether n_trials sufficed for THIS scenario. Additive metadata only — it
        # never changes n_trials or the reported bands (#590).
        result.metadata["convergence"] = convergence_diagnostic(result.trials or {})
        # The mean CI above does NOT certify the tails, but a lender reads the P90/P95 band
        # (and the DSCR breach probability), not the mean. Add a distribution-free order-
        # statistic CI for those percentiles plus a Wilson CI for the covenant breach
        # probability on dscr_min. Read-only/additive — same KPI-neutral contract as #590.
        result.metadata["percentile_ci"] = percentile_ci_diagnostic(
            result.trials or {},
            breach_thresholds={"dscr_min": float(self._fixed_debt_covenant)},
        )
        # Wire the now-truthful provenance stamp onto the result surface (#649): a JSON-safe
        # dict of (n_trials, seed, sampler, common_random_numbers, param_names, config_hash),
        # so a run manifest carries a first-class record of HOW the bands were generated
        # instead of that record living only as a semi-vestigial n_trials=0 placeholder object.
        # param_names is emitted as a list for JSON round-tripping. Additive/read-only —
        # same KPI-neutral contract as the convergence/percentile_ci diagnostics above.
        run_meta = asdict(self._meta)
        run_meta["param_names"] = list(self._meta.param_names)
        result.metadata["run_meta"] = run_meta
        return result

    def _fixed_debt_stress_unavailable(self, reason: str) -> None:
        """Fail loud when a lender-posture run cannot produce its fixed-debt stress (#1728).

        The stress is ruled on for lender runs (#962 item 4). A lender-posture run is one
        whose effective ``allow_toy_fallback`` is false: the lender scenarios declare it,
        lender and IC run modes force it, and the capital-risk report forces it. Such a run
        raises rather than report a Monte Carlo with the stress silently missing
        (FRAMEWORK-02). A permissive run records the reason in the metadata instead.
        """
        if not self._allow_toy_fallback:
            raise RuntimeError(
                "monte_carlo.fixed_debt_stress is on for a run with the toy fallback off, "
                f"but the stress cannot be computed: {reason}. Fix the scenario, or turn "
                "the stress off explicitly."
            )

    @staticmethod
    def _flag_degenerate_sweep(result: MonteCarloResult) -> None:
        """Detect (and record) a no-op sweep: a sampled run whose outputs never moved.

        A swept Monte Carlo over more than one real trial that produces ZERO dispersion
        in every canonical metric is degenerate — the sampled lever(s) touched nothing.
        That is the silent symptom of a DEAD param name (a non-resolving dotted path
        merged as an unread config key): real evaluation succeeds on every trial with
        identical KPIs, so toy_fallback_count stays 0 and the percentiles look rock-stable
        while being meaningless. A transient WARNING is not enough — it never reaches the
        result object or any report — so we record ``degenerate_sweep`` (bool) and the
        flat ``zero_variance_metrics`` list in ``result.metadata`` and re-warn loudly.
        """
        real_trials = int(result.iterations) - int(result.failed_iterations)
        flat_metrics: List[str] = []
        any_measured = False
        for metric, values in (result.trials or {}).items():
            vals = [float(v) for v in values if v is not None]
            if len(vals) <= 1:
                continue
            any_measured = True
            arr = np.asarray(vals, dtype=float)
            mean = float(arr.mean())
            std = float(arr.std(ddof=1))
            if std <= 1e-9 * (abs(mean) + 1e-9):
                flat_metrics.append(metric)
        degenerate = bool(
            real_trials > 1
            and any_measured
            and len(flat_metrics)
            == sum(
                1
                for v in (result.trials or {}).values()
                if len([x for x in v if x is not None]) > 1
            )
        )
        result.metadata["degenerate_sweep"] = degenerate
        result.metadata["zero_variance_metrics"] = flat_metrics if degenerate else []
        if degenerate:
            logger.warning(
                "Monte Carlo sweep is DEGENERATE: %d real trials produced ZERO dispersion "
                "in every metric %r — the sampled parameter(s) moved no output (dead key(s): "
                "%r). The percentiles are NOT a real risk distribution.",
                real_trials,
                flat_metrics,
                list(result.metadata.get("dead_param_names", [])),
            )

    @staticmethod
    def _build_overrides_from_sample(
        sample_row: np.ndarray, param_names: Sequence[str]
    ) -> Dict[str, Any]:
        """Build a nested override dict from a flat LHS sample row.

        Dot-notation parameter names (e.g. ``"project.capacity_factor"``) are
        expanded into nested dicts so that ``_deep_merge_config`` in
        ``evaluation_v14`` can correctly merge them into the base scenario
        config.  Flat (non-dotted) names are placed at the top level as
        before.

        Example
        -------
        param_names = ["project.capacity_factor", "Financing_Terms.rates.lkr_nominal"]
        sample_row  = [0.42, 0.075]

        Returns
        -------
        {
            "project": {"capacity_factor": 0.42},
            "Financing_Terms": {"rates": {"lkr_nominal": 0.075}},
        }

        Dolphin Strategy note: this is a self-contained static method fix.
        No shim is required because ``_build_overrides_from_sample`` is a
        private helper with no external callers; the public API
        (``MonteCarloEngine.run`` and ``run_monte_carlo_analysis``) is
        unchanged.  Bug: MC trials all fell back to toy-metric fallback
        because flat keys were never found in the nested config and the
        schema guard raised ValidationError on every trial.
        """
        overrides: Dict[str, Any] = {}
        for name, val in zip(param_names, sample_row.tolist(), strict=True):
            keys = name.split(".")
            if len(keys) == 1:
                # Non-dotted name: place at top level (backward-compatible)
                overrides[name] = val
            else:
                # Dot-notation: expand into nested dict
                d = overrides
                for k in keys[:-1]:
                    d = d.setdefault(k, {})
                d[keys[-1]] = val
        return overrides


def run_monte_carlo_analysis(
    *,
    base_config: Mapping[str, Any],
    n_trials: int,
    seed: int = 123,
    common_random_numbers: bool = True,
    correlation: Optional[CorrelationSpec] = None,
) -> MonteCarloResult:
    """Stable functional entrypoint for the canonical MC engine."""
    engine = MonteCarloEngine(
        base_config=base_config,
        seed=seed,
        common_random_numbers=common_random_numbers,
        correlation=correlation,
    )
    return engine.run(n_trials=int(n_trials))
