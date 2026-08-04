"""Frozen resource-assessment contract (#996 D4).

A read-only, self-validating projection of a wind resource assessment's
P50/P75/P90 energy basis, so downstream consumers (finance P-level selection,
downside-debt sizing, the immutable auditable case snapshot) can read one
versioned object instead of loose, possibly-inconsistent scalars.

Constructing a ``ResourceAssessment`` validates two invariants and fails loud on
violation (CESSPIT — config-explicit, schema-strict, pre-flight integrity):

* the ``AEP = capacity_mw x hours_per_year x capacity_factor`` identity, for
  EVERY P-level present (a superset of #996's "active selected P-level"), and
* the ``P90 <= P75 <= P50`` exceedance monotonicity (AEP and capacity factor).

This module is deliberately dependency-light (standard library only) so that
``analytics.contracts_v14`` can re-export it without a circular import and
without dragging ``wind_resource`` / ``numpy`` into the contract layer. It
therefore does NOT subclass ``analytics.contracts_v14.ContractMixin`` (that
would be the cycle); it provides an equivalent ``model_dump()`` / ``dict()``
surface via :func:`dataclasses.asdict`.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Mapping, Optional

#: Hours in a (non-leap) year. Must match
#: ``analytics.wind.losses_model.HOURS_PER_YEAR`` and
#: ``wind_resource.bankable_aep.HOURS_PER_YEAR`` (both 8760.0) so the identity
#: check is consistent with how the pipeline derives the capacity factor.
HOURS_PER_YEAR = 8760.0

#: Valid P-level labels, best-exceedance (highest energy) first.
P_LEVELS = ("P50", "P75", "P90")

#: Default relative tolerance for the AEP = capacity x hours x CF identity.
#: Generous enough to absorb the pipeline's per-field rounding (<0.1%), tight
#: enough to catch a genuinely inconsistent (capacity, CF, AEP) triple.
DEFAULT_IDENTITY_RTOL = 0.02

#: Absolute slack (GWh / CF) for the monotonicity comparisons, to tolerate
#: float noise on otherwise-equal levels without allowing a real inversion.
_MONO_EPS = 1e-6


class ResourceAssessmentError(ValueError):
    """Raised when a :class:`ResourceAssessment` fails its consistency checks."""


@dataclass(frozen=True)
class ResourceAssessment:
    """Immutable P50/P75/P90 resource-energy basis for a wind assessment.

    All AEP values are farm-level net GWh/year; capacity factors are decimals in
    ``[0, 1]``; ``capacity_mw`` is the farm nameplate. ``run_manifest`` (when
    provided) is the :class:`analytics.run_manifest.RunManifest` dict, so an
    instance is a self-identifying snapshot of the resource basis.
    """

    capacity_mw: float
    n_turbines: int
    net_aep_p50_gwh: float
    net_aep_p75_gwh: float
    net_aep_p90_gwh: float
    capacity_factor_p50: float
    capacity_factor_p75: float
    capacity_factor_p90: float
    selected_p_level: str
    report_grade: str
    run_manifest: Optional[Dict[str, Any]] = None
    source_id: Optional[str] = None
    power_curve_key: Optional[str] = None
    hours_per_year: float = HOURS_PER_YEAR
    identity_rtol: float = DEFAULT_IDENTITY_RTOL

    # -- serialisation (ContractMixin-equivalent, no import cycle) -----------
    def model_dump(self) -> Dict[str, Any]:
        """Return a plain-dict projection (parity with ``ContractMixin``)."""
        return asdict(self)

    def dict(self) -> Dict[str, Any]:
        return self.model_dump()

    # -- accessors ----------------------------------------------------------
    def net_aep_gwh(self, p_level: str) -> float:
        """Net AEP (GWh) for ``p_level`` (case-insensitive P50/P75/P90)."""
        return {
            "P50": self.net_aep_p50_gwh,
            "P75": self.net_aep_p75_gwh,
            "P90": self.net_aep_p90_gwh,
        }[self._norm(p_level)]

    def capacity_factor(self, p_level: str) -> float:
        """Net capacity factor (decimal) for ``p_level``."""
        return {
            "P50": self.capacity_factor_p50,
            "P75": self.capacity_factor_p75,
            "P90": self.capacity_factor_p90,
        }[self._norm(p_level)]

    @property
    def selected_net_aep_gwh(self) -> float:
        return self.net_aep_gwh(self.selected_p_level)

    @property
    def selected_capacity_factor(self) -> float:
        return self.capacity_factor(self.selected_p_level)

    @property
    def p90_p50_ratio(self) -> float:
        """Bankable downside ratio (P90/P50 net AEP) — the debt-sizing scale."""
        return self.net_aep_p90_gwh / self.net_aep_p50_gwh

    # -- validation ---------------------------------------------------------
    def __post_init__(self) -> None:
        self._validate()

    @staticmethod
    def _norm(p_level: str) -> str:
        norm = str(p_level).strip().upper()
        if norm not in P_LEVELS:
            raise ResourceAssessmentError(
                f"p_level must be one of {P_LEVELS}; got {p_level!r}"
            )
        return norm

    def _validate(self) -> None:
        self._norm(self.selected_p_level)  # rejects an unknown selected level

        if self.capacity_mw <= 0.0:
            raise ResourceAssessmentError(
                f"capacity_mw must be > 0; got {self.capacity_mw}"
            )
        if self.n_turbines <= 0:
            raise ResourceAssessmentError(
                f"n_turbines must be > 0; got {self.n_turbines}"
            )
        if self.hours_per_year <= 0.0:
            raise ResourceAssessmentError(
                f"hours_per_year must be > 0; got {self.hours_per_year}"
            )

        aep = {
            "P50": self.net_aep_p50_gwh,
            "P75": self.net_aep_p75_gwh,
            "P90": self.net_aep_p90_gwh,
        }
        cf = {
            "P50": self.capacity_factor_p50,
            "P75": self.capacity_factor_p75,
            "P90": self.capacity_factor_p90,
        }
        for level in P_LEVELS:
            if aep[level] < 0.0:
                raise ResourceAssessmentError(
                    f"net_aep_{level.lower()}_gwh must be >= 0; got {aep[level]}"
                )
            if not 0.0 <= cf[level] <= 1.0:
                raise ResourceAssessmentError(
                    f"capacity_factor_{level.lower()} must be in [0, 1]; got {cf[level]}"
                )

        # Exceedance monotonicity: higher exceedance prob => lower energy.
        if not (aep["P50"] + _MONO_EPS >= aep["P75"] >= aep["P90"] - _MONO_EPS):
            raise ResourceAssessmentError(
                "net AEP must be monotone P90 <= P75 <= P50; got "
                f"P50={aep['P50']}, P75={aep['P75']}, P90={aep['P90']}"
            )
        if not (cf["P50"] + _MONO_EPS >= cf["P75"] >= cf["P90"] - _MONO_EPS):
            raise ResourceAssessmentError(
                "capacity factor must be monotone P90 <= P75 <= P50; got "
                f"P50={cf['P50']}, P75={cf['P75']}, P90={cf['P90']}"
            )

        # AEP = capacity_mw x hours x CF identity, for every level (GWh<->MWh).
        for level in P_LEVELS:
            implied_gwh = self.capacity_mw * self.hours_per_year * cf[level] / 1000.0
            reference = aep[level]
            # Scale the relative error by the larger of the two magnitudes so a
            # zero net AEP paired with a non-zero CF (implied > 0) still fails the
            # identity, while a genuinely-uncomputed (0 AEP, 0 CF) level is skipped.
            denom = max(abs(reference), abs(implied_gwh))
            if denom <= 1e-9:
                continue
            rel = abs(implied_gwh - reference) / denom
            if rel > self.identity_rtol:
                raise ResourceAssessmentError(
                    f"AEP identity violated at {level}: capacity_mw*hours*CF/1000 = "
                    f"{implied_gwh:.4f} GWh vs net_aep = {reference:.4f} GWh "
                    f"(rel {rel:.4f} > {self.identity_rtol})"
                )

    # -- construction from the async assessment result ----------------------
    @classmethod
    def from_assessment(
        cls,
        full_results: Mapping[str, Any],
        selected_p_level: str,
        *,
        report_grade: str,
        run_manifest: Optional[Dict[str, Any]] = None,
        identity_rtol: float = DEFAULT_IDENTITY_RTOL,
    ) -> "ResourceAssessment":
        """Project a ``WindPipeline.run_complete_assessment`` result.

        Reads ``full_results["energy_production"]["net_aep"]`` (net_aep_p{50,75,90}_mwh
        + capacity_factor_net_p{50,75,90}) and
        ``full_results["metadata"]["configuration"]`` (num_turbines, total_capacity_mw,
        source_id / power_curve_key when present). AEP is converted MWh -> GWh, and the
        capacity factors — which the pipeline stores as PERCENT (e.g. 35.33, see
        ``wind_resource.energy_calculator``) — are converted percent -> decimal, matching
        ``wind_resource.era5_retrieval``. Constructing the instance runs the identity +
        monotonicity validation.
        """
        try:
            net_aep = full_results["energy_production"]["net_aep"]
            config = full_results["metadata"]["configuration"]
        except (KeyError, TypeError) as exc:  # malformed assessment result
            raise ResourceAssessmentError(
                "assessment result is missing energy_production.net_aep or "
                f"metadata.configuration: {exc}"
            ) from exc

        def _mwh_to_gwh(key: str) -> float:
            return float(net_aep[key]) / 1000.0

        def _pct_to_decimal(key: str) -> float:
            return float(net_aep[key]) / 100.0

        return cls(
            capacity_mw=float(config["total_capacity_mw"]),
            n_turbines=int(config["num_turbines"]),
            net_aep_p50_gwh=_mwh_to_gwh("net_aep_p50_mwh"),
            net_aep_p75_gwh=_mwh_to_gwh("net_aep_p75_mwh"),
            net_aep_p90_gwh=_mwh_to_gwh("net_aep_p90_mwh"),
            capacity_factor_p50=_pct_to_decimal("capacity_factor_net_p50"),
            capacity_factor_p75=_pct_to_decimal("capacity_factor_net_p75"),
            capacity_factor_p90=_pct_to_decimal("capacity_factor_net_p90"),
            selected_p_level=cls._norm(selected_p_level),
            report_grade=str(report_grade),
            run_manifest=run_manifest,
            source_id=(
                str(config["turbine_model"]) if "turbine_model" in config else None
            ),
            power_curve_key=(
                str(config["power_curve_key"]) if "power_curve_key" in config else None
            ),
            identity_rtol=identity_rtol,
        )
