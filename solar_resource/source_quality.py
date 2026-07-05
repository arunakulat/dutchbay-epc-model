"""Solar resource source-quality grading (pure metadata; bills off NOTHING).

The photovoltaic analogue of the wind ``provenance.aep`` block
(:func:`analytics.loader.aep_loader.build_provenance_aep_block`): it grades *how good the
resource evidence is* behind a modelled solar P50, so a lender energy-yield assessment can
see at a glance whether a capacity factor rests on a ground-measured multi-year record or on
a single satellite year. Wind has a certified-power-curve manifest with an
``is_placeholder`` flag; solar's evidence lives in the irradiance dataset (TMY / satellite /
ground station), so this module grades *that*.

Deliberately metadata-only (the #587 P50-haircut lesson)
--------------------------------------------------------
This grade is emitted into the ``solar_resource`` provenance block ONLY. It is NOT wired to
``compute_solar_aep``, the exceedance ``p50_haircut_pct``, or any billed field. Applying a
grade-driven P50 haircut is a producer-driven re-baseline (moves a reported number) and is a
deliberate user/policy decision of the same class as #587 (the wind no-EYA haircut) and #529
(SOLAR-6/12) — it is intentionally NOT done here. A scenario that adds no ``source_quality``
config is byte-identical: the block simply records the frozen export's own metadata at the
default grade.

Grading (config-first, evidence-driven)
---------------------------------------
Four evidence axes, each scored on documented rubrics, combined into a single 0-1
``quality_score`` and an A/B/C/D letter ``grade``:

* ``measurement_type`` — ground_measured (best) > satellite_calibrated > satellite > modelled
  (clear-sky, worst). This is the dominant axis (IEA-PVPS Task 13: on-site pyranometer data
  is the gold standard; satellite GHI carries a larger bias/uncertainty).
* ``years_of_record`` — more years shrink the interannual-variability contribution
  (score saturates at the ``_YEARS_SATURATION`` long record).
* ``tmy_source`` — a named, reputable dataset (PVGIS / NSRDB / Solargis / Meteonorm) scores
  above an unnamed / unknown one.
* ``ghi_dataset`` — free text recorded for the audit trail (does not move the score; it is
  provenance, not a rubric axis, to avoid double-counting ``tmy_source``).

The rubric weights and the score->letter thresholds are module constants (documented,
lender-auditable); a caller may override any axis via the scenario's OPTIONAL
``resource.solar.source_quality`` block. Absent that block, a default (candid, low) grade is
recorded so an ungraded frozen export never silently reads as investment-grade.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional

__all__ = [
    "MEASUREMENT_TYPE_SCORES",
    "TMY_SOURCE_SCORES",
    "AXIS_WEIGHTS",
    "SolarSourceQuality",
    "grade_solar_source_quality",
    "solar_source_quality_from_config",
]

#: Measurement-type evidence score (0-1). Ground-measured on-site pyranometry is the
#: gold standard; a bare satellite year (or a clear-sky ``modelled`` fallback) is weakest.
#: IEA-PVPS Task 13 "Uncertainties in Yield Assessments".
MEASUREMENT_TYPE_SCORES: Dict[str, float] = {
    "ground_measured": 1.0,
    "satellite_calibrated": 0.75,  # satellite bias-corrected against a ground station
    "satellite": 0.55,
    "modelled": 0.30,  # clear-sky / reanalysis with no measured irradiance
    "unknown": 0.0,
}

#: Named-dataset reputability score (0-1). A recognised, documented dataset scores above an
#: unnamed or unknown source. Free-form; unlisted names fall back to ``_UNNAMED_SOURCE_SCORE``.
TMY_SOURCE_SCORES: Dict[str, float] = {
    "solargis": 1.0,
    "meteonorm": 0.9,
    "nsrdb": 0.9,
    "pvgis": 0.85,
    "era5": 0.5,
    "unknown": 0.0,
}

#: Score used when ``tmy_source`` is a non-empty but unlisted name (recorded, mildly credited).
_UNNAMED_SOURCE_SCORE: float = 0.4

#: Years-of-record at which the record-length axis saturates (a long multi-year record no
#: longer improves the interannual-variability evidence materially).
_YEARS_SATURATION: float = 10.0

#: Relative weights of the three scored axes (must sum to 1.0). ``measurement_type`` dominates
#: because it drives the GHI-dataset uncertainty far more than record length or dataset name.
AXIS_WEIGHTS: Dict[str, float] = {
    "measurement_type": 0.6,
    "years_of_record": 0.25,
    "tmy_source": 0.15,
}

#: Score -> letter thresholds (inclusive lower bound). A grade is investment-quality only on
#: strong ground-truthed evidence; the default (no config) grade lands at D.
_GRADE_THRESHOLDS: tuple[tuple[float, str], ...] = (
    (0.85, "A"),
    (0.65, "B"),
    (0.45, "C"),
    (0.0, "D"),
)


@dataclass(frozen=True)
class SolarSourceQuality:
    """A graded assessment of the evidence behind a modelled solar P50 (pure metadata).

    Attributes:
        quality_score: Weighted 0-1 evidence score (see :data:`AXIS_WEIGHTS`).
        grade: A/B/C/D letter from :data:`_GRADE_THRESHOLDS`.
        measurement_type: The (normalised) measurement axis value scored.
        years_of_record: Years of irradiance record behind the resource.
        tmy_source: The (normalised) named dataset scored.
        ghi_dataset: Free-text GHI dataset identifier for the audit trail (unscored).
        measurement_score / years_score / tmy_source_score: The per-axis sub-scores, exposed
            so the audit trail shows exactly how ``quality_score`` was built up.
    """

    quality_score: float
    grade: str
    measurement_type: str
    years_of_record: float
    tmy_source: str
    ghi_dataset: Optional[str]
    measurement_score: float
    years_score: float
    tmy_source_score: float

    def to_provenance(self) -> Dict[str, Any]:
        """Serialise into the ``solar_resource.source_quality`` provenance sub-block."""
        block: Dict[str, Any] = {
            "quality_score": round(self.quality_score, 4),
            "grade": self.grade,
            "measurement_type": self.measurement_type,
            "years_of_record": self.years_of_record,
            "tmy_source": self.tmy_source,
            "measurement_score": round(self.measurement_score, 4),
            "years_score": round(self.years_score, 4),
            "tmy_source_score": round(self.tmy_source_score, 4),
        }
        if self.ghi_dataset is not None:
            block["ghi_dataset"] = self.ghi_dataset
        return block


def _score_to_grade(score: float) -> str:
    for lower, letter in _GRADE_THRESHOLDS:
        if score >= lower:
            return letter
    return "D"  # pragma: no cover - the 0.0 floor above always matches


def grade_solar_source_quality(
    *,
    measurement_type: str = "modelled",
    years_of_record: float = 1.0,
    tmy_source: str = "unknown",
    ghi_dataset: Optional[str] = None,
) -> SolarSourceQuality:
    """Grade the resource evidence behind a modelled solar P50 (pure; no economics).

    Combines the three scored evidence axes with :data:`AXIS_WEIGHTS` into a single 0-1
    ``quality_score`` and an A/B/C/D ``grade``. Nothing about the returned value feeds a
    capacity factor, a haircut, or any billed field — it is provenance only.

    Args:
        measurement_type: One of :data:`MEASUREMENT_TYPE_SCORES` (case-insensitive; an
            unrecognised value scores as ``unknown`` = 0.0, i.e. fails candid, not silently).
        years_of_record: Years of irradiance record (>= 0); the axis saturates at
            :data:`_YEARS_SATURATION`.
        tmy_source: Dataset name; scored via :data:`TMY_SOURCE_SCORES` (case-insensitive), a
            non-empty unlisted name credited at :data:`_UNNAMED_SOURCE_SCORE`.
        ghi_dataset: Optional free-text GHI dataset identifier (recorded, unscored).

    Returns:
        A :class:`SolarSourceQuality`.

    Raises:
        ValueError: if ``years_of_record`` is negative.
    """
    if years_of_record < 0.0:
        raise ValueError(f"years_of_record must be >= 0; got {years_of_record}")

    mtype = str(measurement_type).strip().lower()
    measurement_score = MEASUREMENT_TYPE_SCORES.get(
        mtype, MEASUREMENT_TYPE_SCORES["unknown"]
    )

    years_score = min(float(years_of_record) / _YEARS_SATURATION, 1.0)

    tsource = str(tmy_source).strip().lower()
    if tsource in TMY_SOURCE_SCORES:
        tmy_source_score = TMY_SOURCE_SCORES[tsource]
    elif tsource and tsource != "unknown":
        tmy_source_score = _UNNAMED_SOURCE_SCORE
    else:
        tmy_source_score = TMY_SOURCE_SCORES["unknown"]

    quality_score = (
        AXIS_WEIGHTS["measurement_type"] * measurement_score
        + AXIS_WEIGHTS["years_of_record"] * years_score
        + AXIS_WEIGHTS["tmy_source"] * tmy_source_score
    )
    return SolarSourceQuality(
        quality_score=quality_score,
        grade=_score_to_grade(quality_score),
        measurement_type=mtype,
        years_of_record=float(years_of_record),
        tmy_source=tsource,
        ghi_dataset=ghi_dataset,
        measurement_score=measurement_score,
        years_score=years_score,
        tmy_source_score=tmy_source_score,
    )


#: Valid keys in a ``resource.solar.source_quality`` block (CESSPIT typo protection).
_CONFIG_KEYS: frozenset[str] = frozenset(
    {"measurement_type", "years_of_record", "tmy_source", "ghi_dataset"}
)


def solar_source_quality_from_config(
    block: Optional[Mapping[str, Any]],
) -> SolarSourceQuality:
    """Grade from a scenario's OPTIONAL ``resource.solar.source_quality`` mapping (#743).

    With ``block=None`` (the committed hybrid declares none) this returns the DEFAULT grade
    (``modelled`` / 1 year / unknown source = grade D), so an ungraded frozen export is
    recorded candidly rather than silently reading as investment-grade. It never affects any
    KPI.

    Args:
        block: The ``resource.solar.source_quality`` mapping, or None.

    Returns:
        A :class:`SolarSourceQuality`.

    Raises:
        KeyError: an unknown key is present (CESSPIT — a typo fails loud, not silently reverts).
        TypeError: ``block`` is not a mapping.
    """
    if block is None:
        return grade_solar_source_quality()
    if not isinstance(block, Mapping):
        raise TypeError(
            "resource.solar.source_quality must be a mapping; got "
            f"{type(block).__name__}"
        )
    unknown = [k for k in block if k not in _CONFIG_KEYS]
    if unknown:
        raise KeyError(
            f"resource.solar.source_quality has unknown field(s): {sorted(unknown)}; "
            f"valid keys: {sorted(_CONFIG_KEYS)}"
        )
    kwargs: Dict[str, Any] = {}
    if "measurement_type" in block:
        kwargs["measurement_type"] = block["measurement_type"]
    if "years_of_record" in block:
        kwargs["years_of_record"] = float(block["years_of_record"])
    if "tmy_source" in block:
        kwargs["tmy_source"] = block["tmy_source"]
    if "ghi_dataset" in block:
        kwargs["ghi_dataset"] = block["ghi_dataset"]
    return grade_solar_source_quality(**kwargs)
