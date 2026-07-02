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
from dataclasses import dataclass
from statistics import NormalDist
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np

from analytics.contracts_v14 import MonteCarloResult
from analytics.evaluation_v14 import evaluate_with_overrides
from analytics.mc.aggregate import aggregate_trials
from analytics.mc.convergence import convergence_diagnostic
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
from analytics.mc.samplers import generate_lhs_samples, generate_sobol_samples

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

    Returns None (so the aggregator's documented default applies) when the key is absent
    or malformed, rather than silently ignoring a well-formed request.
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


def _trial_fixed_debt_min_dscr(
    base_debt_service: Sequence[float], trial_debt_result: Mapping[str, Any]
) -> Optional[float]:
    """Min DSCR of a trial's CFADS against the FIXED (financial-close) debt service.

    A committed loan cannot retroactively shrink when a production year disappoints, yet the
    per-trial pipeline RE-SIZES debt (DSCR sculpting), pinning every trial's min_dscr at the
    covenant target and reporting ZERO breach probability. The trial's actual CFADS per
    period is recovered exactly from its own outputs as ``raw_dscr_series[i] * debt_service
    _total[i]`` (independent of how that trial sized debt), then divided by the BASE committed
    debt service to give the honest fixed-debt DSCR. Returns the min over operating periods.
    """
    rd = trial_debt_result.get("raw_dscr_series") or []
    ds = trial_debt_result.get("debt_service_total") or []
    vals: List[float] = []
    for i, bds in enumerate(base_debt_service):
        if bds and bds > 0 and i < len(rd) and i < len(ds):
            try:
                vals.append((float(rd[i]) * float(ds[i])) / float(bds))
            except (TypeError, ValueError, ZeroDivisionError):
                continue
    return min(vals) if vals else None


#: Distribution shapes the sampler can honor (besides the calibrated FX driver). A declared
#: shape outside this set is a config error (previously silently sampled uniform — decorative).
_SUPPORTED_DISTRIBUTIONS = frozenset({"uniform", "triangular", "normal", "lognormal"})
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

    Toy fallback (MC-9, #473): when a trial's full v14 evaluation raises, the engine appends a
    deterministic toy-metric stand-in so a smoke run still yields an array; the trial is tagged
    ``_toy_fallback`` and counted in ``toy_fallback_count``. Set
    ``monte_carlo.allow_toy_fallback: false`` to fail loud instead — a production run then
    RAISES on the first failed trial rather than reporting fabricated KPIs.
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
        _sampler = (
            str(_mc_cfg.get("sampler", "lhs")).strip().lower()
            if isinstance(_mc_cfg, Mapping)
            else "lhs"
        )
        if _sampler not in ("lhs", "sobol"):
            raise MonteCarloConfigError(
                f"monte_carlo.sampler must be 'lhs' or 'sobol', got {_sampler!r}."
            )
        self._sampler: str = _sampler

        # Fixed-debt covenant-stress (opt-in via monte_carlo.fixed_debt_stress: true).
        self._fixed_debt_stress: bool = (
            bool(_mc_cfg.get("fixed_debt_stress", False))
            if isinstance(_mc_cfg, Mapping)
            else False
        )
        # MC-9 (#473): the toy-metric fallback exists so a smoke/integration run on a minimal
        # config still produces an array. On a REAL run a fallback means full v14 evaluation
        # FAILED for that trial — the toy KPIs are fabricated, not real, and (though tagged and
        # counted) could be consumed downstream as if real. Opt in to fail-loud via
        # monte_carlo.allow_toy_fallback: false, which RAISES on the first failed trial instead
        # of substituting toy metrics. Default true keeps smoke tests and back-compat identical.
        self._allow_toy_fallback: bool = (
            bool(_mc_cfg.get("allow_toy_fallback", True))
            if isinstance(_mc_cfg, Mapping)
            else True
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

        self._meta = MonteCarloRunMeta(
            n_trials=0,
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
        per-tech generation capacity factors (multi-tech). Wind-only scenarios have no
        generation.technologies block, so the project.capacity_factor override drives
        production directly and no coupling is needed (self._cf_coupling stays None).
        """
        if "project.capacity_factor" not in self._param_names:
            return
        gen = self._base_config.get("generation")
        techs = gen.get("technologies") if isinstance(gen, Mapping) else None
        if not isinstance(techs, Mapping):
            return
        base_tech_cfs: Dict[str, float] = {}
        for name, blk in techs.items():
            if isinstance(blk, Mapping) and blk.get("capacity_factor") is not None:
                try:
                    base_tech_cfs[str(name)] = float(blk["capacity_factor"])
                except (TypeError, ValueError):
                    continue
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

        if self._correlation is not None and self._correlation.enabled:
            if self._sampler == "sobol":
                # Iman-Conover rank-reordering preserves each driver's marginal but destroys the
                # JOINT low-discrepancy structure Sobol was chosen for — the balance benefit then
                # only accrues to the marginals. Warn once so an opted-in user is not misled.
                logger.warning(
                    "monte_carlo.sampler='sobol' with an enabled correlation block: "
                    "Iman-Conover rank-reordering preserves marginals but destroys the joint "
                    "Sobol low-discrepancy structure (the QMC benefit is limited to the "
                    "marginals). Disable correlation to retain the full QMC balance."
                )
            samples = apply_correlation_structure(
                lhs_samples=samples,
                correlation=self._correlation,
                seed=self._seed,
            )

        trial_metrics: List[Mapping[str, Any]] = []

        # Fixed-debt covenant-stress: size debt ONCE on the base (financial-close) schedule,
        # then test each trial's CFADS against that committed service (a committed loan cannot
        # shrink when production disappoints). Off by default -> no base eval, full results not
        # requested, byte-identical.
        base_debt_service: List[float] = []
        fixed_dscr_vals: List[float] = []
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
                    base_debt_service = [
                        float(x) for x in (_bdr.get("debt_service_total") or [])
                    ]

        for i in range(n):
            overrides = self._build_overrides_from_sample(samples[i], self._param_names)
            overrides = self._apply_distribution_shapes(overrides, samples[i])
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
                    if self._fixed_debt_stress and base_debt_service:
                        _tdr: Any = out.get("debt_result", {})
                        mfd = _trial_fixed_debt_min_dscr(
                            base_debt_service, _tdr if isinstance(_tdr, Mapping) else {}
                        )
                        if mfd is not None:
                            fixed_dscr_vals.append(mfd)
                else:
                    trial_metrics.append({})
            except Exception as exc:
                # MC-9 (#473): fail loud when the scenario has opted out of the fallback —
                # a production run must not silently report fabricated toy KPIs.
                if not self._allow_toy_fallback:
                    raise RuntimeError(
                        f"MC trial {i} failed full v14 evaluation and "
                        "monte_carlo.allow_toy_fallback is false, so the toy-metric fallback "
                        "is disabled (a production run must not report fabricated KPIs). Fix "
                        "the underlying scenario/config error, or set allow_toy_fallback: true "
                        f"for a smoke run. Underlying error: {exc}"
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
        if self._fixed_debt_stress and fixed_dscr_vals:
            arr = sorted(fixed_dscr_vals)
            cov = float(self._fixed_debt_covenant)

            def _q(p: float) -> float:
                k = (len(arr) - 1) * p
                lo = math.floor(k)
                hi = math.ceil(k)
                return arr[lo] if lo == hi else arr[lo] * (hi - k) + arr[hi] * (k - lo)

            meta["fixed_debt_stress"] = {
                "covenant": cov,
                "breach_probability": sum(1 for v in arr if v < cov) / len(arr),
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
        return result

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
        for name, val in zip(param_names, sample_row.tolist()):
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
