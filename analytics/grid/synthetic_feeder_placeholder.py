"""Deterministic, explicitly synthetic feeder package for Issue #923.

This module is Dolphin #923-B1 only.  It creates a minimal OpenDSS package and an
hourly generation profile so the software wiring can be exercised while the real CEB
feeder remains unavailable.  The package is deliberately incapable of representing
observed, site-representative, bankable, canonical, or lender evidence.

The hourly chronology is synthetic.  It is generated with a pinned PCG64 seed and
calibrated to the repository's hashed ERA5-derived summary and scenario Weibull inputs;
it is not a reconstruction of actual 2021 ERA5 hours.  Wake, availability, electrical,
environmental, grid-curtailment, and P50 deductions remain outside the QSTS gross
injection boundary so the later counterfactual can exercise an export-cap breach.

Runtime loading and propagation of the package manifest belong to Dolphin #923-B2.
Per-step convergence and telemetry belong to #923-C.  Finance belongs to #923-D,
presentation/release controls to #923-E, and real-data replacement to #923-R.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
import re
import shutil
import tempfile
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence, cast

import numpy as np
import pandas as pd
import yaml
from numpy.typing import NDArray
from scipy.special import ndtr

from analytics.run_manifest import engine_version, git_sha
from wind_resource.energy_calculator import EnergyCalculator

ISSUE = 923
GENERATOR_VERSION = "issue923-synthetic-feeder-v1"
RANDOM_SEED = 92320260818
RNG_ALGORITHM = "pcg64_ar1_weibull_era5_summary_calibrated_v1"
MANIFEST_SCHEMA = "dutchbay.issue923.synthetic_feeder_manifest.v1"
INPUT_KIND = "synthetic_placeholder"
SOURCE_KIND = "synthetic_era5_summary_calibrated"
SYNTHETIC_CASE = "issue923_placeholder_v1"
CONVERGENCE_STATUS = "not_examined_deferred_issue_923_C"
FINANCE_STATUS = "not_run_scope_923_B"
FROZEN_SPEC_SHA256 = "7b8ff2cc52661ddd98efcdd4c56a4ad563f38317441ecddfa1dfa5d30af3ce0a"
SYNTHETIC_CHRONOLOGY_DECISION_SHA256 = (
    "0b09e9bb8bbb6c07bbf3ad87ed9212c507f1a04b9393342a5ba275c4a8cd6787"
)
EXPECTED_PROFILE_START_UTC = "2021-01-01T00:00:00Z"
EXPECTED_PROFILE_END_UTC = "2021-12-31T23:00:00Z"
GOVERNED_OUTPUT_DIR = "outputs/synthetic_placeholders/issue_923"

PINNED_REPOSITORY_SOURCE_TRIPLES = (
    (
        "scenario",
        "scenarios/dutchbay_lendercase_2025Q4.yaml",
        "bb83a662c754ef1376201818c2e294c660d4e9cc4cae0947ba091cdb62f53c39",
    ),
    (
        "era5_summary",
        "feasibility_reproduce/cache/expected/era5_result.json",
        "b2d6fd4a4373d3634383d5aec215e4c2dadd2e0b6a3db6d4139a4c850b4578d0",
    ),
    (
        "era5_request",
        "wind_resource/config/era5_request_kalpitiya.yaml",
        "6916e13b6f8b11bb062a81c6508edf4438a7a23d17c1372c6170888adeb0fe72",
    ),
    (
        "power_curves",
        "wind_resource/config/power_curves.yaml",
        "c17528e544df0586331497fe5ffc4659e49bdbcf5280fcd2f23113965fb5b1dc",
    ),
    (
        "era5_calculator_config",
        "wind_resource/config/era5_config.yaml",
        "fb9298b4d4e319b84da5a2725277d6f70567dd124f289f9e5eedfcc22cd1718b",
    ),
    (
        "version_file",
        "VERSION",
        "959e72b86645360fe0e50d549fbd14d1ad9eca6d9cc6ec321fdd1d3967a8a2c3",
    ),
)

FROZEN_PAYLOAD_SHA256 = {
    "feeder/Master.dss": "27d4660ac61655ea850c6d72c6a58292d510f24baaef40a92d9d0ab8cde50d53",
    "feeder/Source.dss": "3c9113cac626a0d97d0cd37b884ecf7c7f34f562fcbb69e6e0009b315471b7af",
    "feeder/Transformer.dss": "d73f535e77154c133e008710d8e1ce60d5c00520888e65e6c7478ae4936a8823",
    "feeder/Connection.dss": "a3aaf7701c25fc13391267df4522acbda1ebe742a18f41278859c14d7b9a1502",
    "feeder/Plant.dss": "7ef945edca01ef90191e102b78abacba89bfa98a73dfc7bb0e671438a690a3d0",
    "profile/generation_profile.csv": "cefa4b9e37f85e5f7774a14727bf35a43c9c3bd8b3219bd730a35aff4f36ab76",
}

PACKAGE_RELATIVE_PATHS = (
    "feeder/Master.dss",
    "feeder/Source.dss",
    "feeder/Transformer.dss",
    "feeder/Connection.dss",
    "feeder/Plant.dss",
    "profile/generation_profile.csv",
    "manifest.json",
    "MANIFEST.sha256",
)
PAYLOAD_RELATIVE_PATHS = PACKAGE_RELATIVE_PATHS[:6]

CSV_COLUMNS = (
    "timestamp_utc",
    "gross_generation_mw",
    "source_kind",
    "synthetic_feeder_case",
    "observed_feeder_response",
    "generated_input",
    "site_representative",
    "bankable",
    "canonical",
    "publishable",
)

HEADER_LINES = (
    "! SYNTHETIC PLACEHOLDER FOR ISSUE #923",
    "! NOT THE CEB KALPITIYA/PUTTALAM FEEDER",
    "! WIRING-ONLY; NOT SITE-REPRESENTATIVE; NOT BANKABLE",
    f"! generator={GENERATOR_VERSION} seed={RANDOM_SEED}",
)
HEADER = "\n".join(HEADER_LINES) + "\n"

CLASSIFICATION = {
    "input_kind": INPUT_KIND,
    "purpose": "wiring_only",
    "generated_input": True,
    "observed_network_data": False,
    "utility_provided": False,
    "site_representative": False,
    "engineering_validated": False,
    "utility_accepted": False,
    "bankable": False,
    "canonical": False,
    "canonical_finance_eligible": False,
    "publishable": False,
    "lender_eligible": False,
    "board_eligible": False,
    "finance_executed": False,
}

LABELS = (
    "SYNTHETIC FEEDER PLACEHOLDER",
    "Issue #923 wiring-only counterfactual",
    "Not the CEB Kalpitiya/Puttalam feeder",
    "No observed or utility-provided network data",
    "Not site-representative",
    "Not engineering-validated",
    "Not utility-accepted",
    "Not bankable",
    "Not canonical",
)

REPLACEMENT_GATE = (
    "CEB 33 kV feeder or accepted equivalent model at the actual DutchBay POC",
    "OpenDSS master file and every redirected component file",
    "Feeder topology and exact POC bus naming",
    "Positive- and zero-sequence line/cable impedances with units and length basis",
    "Transformer ratings, vector groups, taps, impedances, losses, grounding, and controls",
    "Upstream GSS fault level or Thevenin equivalent with minimum/maximum cases and source date",
    "Existing loads, generation, capacitors, regulators, and relevant operating states",
    "Thermal ratings and voltage limits used for the QSTS decision rule",
    "Utility/operator feeder-limit or dispatch schedule for any deemed-paid treatment",
    "Site generation profile with resource provenance and timestep definition",
    "OEM/PPC active and reactive control assumptions relevant to the QSTS",
    "File-level provenance, access date, confidentiality status, and SHA-256 hashes",
    "Independent electrical-engineering review of model interpretation and solver setup",
    "Successful QSTS convergence and reconciliation against available utility results",
    "Before/after KPI-oracle diff against then-current canon",
    "Explicit user sign-off on the real-data KPI movement",
    "Single real-enablement PR that changes the target scenario and only genuine canon surfaces",
)

MANIFEST_TOP_LEVEL_KEYS = frozenset(
    {
        "schema",
        "issue",
        "artifact_kind",
        "generator",
        "classification",
        "labels",
        "source_snapshots",
        "electrical_parameters",
        "profile",
        "artifacts",
        "validation",
        "kpi_treatment",
        "limitations",
        "replacement_gate",
        "control_cross_checks",
    }
)

DSS_REQUIRED_IDENTIFIERS = {
    "feeder/Master.dss": 'Redirect "Plant.dss"',
    "feeder/Source.dss": "New Circuit.synthetic923_circuit ",
    "feeder/Transformer.dss": "New Transformer.synthetic923_gss_transformer ",
    "feeder/Connection.dss": "New Line.synthetic923_equivalent_connection ",
    "feeder/Plant.dss": "New Generator.synthetic923_poc_generator ",
}

LIMITATIONS = (
    "The feeder is generated and contains no observed or utility-provided topology.",
    "The hourly chronology is synthetic and is not actual 2021 ERA5 data.",
    "The hashed ERA5 artefact is a summary, not the absent raw hourly snapshot.",
    "The source fault level and positive-sequence connection values are unbankable screening estimates.",
    "Source zero sequence, transformer, grounding, and ampacity are explicit synthetic assumptions.",
    "OpenDSS compilation is not an 8,760-step convergence or hosting-capacity result.",
    "No operator instruction data were supplied; none may be inferred from this package.",
    "No finance, lender, Board, engineering, utility-acceptance, or canonical claim is permitted.",
)

CALIBRATION_BASIS = (
    "Seeded AR(1)-Weibull chronology calibrated to the scenario mean and the "
    "hashed ERA5-derived recent-period summary; no raw hourly ERA5 snapshot "
    "was available or claimed."
)
GROSS_QSTS_INJECTION_BOUNDARY = (
    "Density-corrected fleet power-curve output before wake, availability, "
    "electrical, environmental, grid-curtailment, or P50 deductions."
)

PROFILE_KEYS = frozenset(
    {
        "path",
        "timestamp_column",
        "value_column",
        "columns",
        "source_kind",
        "chronology_kind",
        "calibration_basis",
        "does_not_claim_actual_2021_conditions",
        "reference_year_for_timestamp_shape_only",
        "weibull_a",
        "weibull_k",
        "scenario_mean_wind_speed_ms",
        "era5_recent_mean_wind_speed_ms",
        "era5_full_mean_wind_speed_ms",
        "ar1_phi",
        "seasonal_amplitude",
        "seasonal_peak_day",
        "diurnal_amplitude",
        "diurnal_peak_hour_utc",
        "maximum_wind_speed_ms",
        "turbine_model",
        "turbine_count",
        "air_density_site_kgm3",
        "air_density_reference_kgm3",
        "scenario_rounded_capacity_mw",
        "gross_qsts_injection_boundary",
        "excluded_loss_stack",
        "export_cap_mw_for_future_counterfactual",
        "row_count",
        "start_utc",
        "end_utc",
        "minimum_gross_generation_mw",
        "maximum_gross_generation_mw",
        "mean_gross_generation_mw",
        "gross_aep_mwh_from_rounded_csv",
        "energy_calculator_gross_aep_mwh",
        "energy_calculator_parity_delta_mwh",
        "synthetic_wind_mean_ms",
        "synthetic_wind_minimum_ms",
        "synthetic_wind_maximum_ms",
        "density_velocity_factor",
        "hours_above_140_mw",
        "hours_above_150_mw",
        "hours_above_159_6_mw",
    }
)

COPIED_ELECTRICAL_KEYS = frozenset(
    {
        "collector_voltage_kv",
        "source_fault_level_mva",
        "source_rx",
        "connection_r1_ohm_per_km",
        "connection_x1_ohm_per_km",
        "plant_rating_mva",
        "source_path",
        "classification",
    }
)
SYNTHETIC_ELECTRICAL_KEYS = frozenset(
    {
        "source_voltage_kv",
        "source_zero_sequence_r_multiplier",
        "source_zero_sequence_x_multiplier",
        "transformer_mva",
        "transformer_vector_group",
        "transformer_xhl_pct",
        "transformer_r_pct_per_winding",
        "connection_length_km",
        "connection_zero_sequence_r_multiplier",
        "connection_zero_sequence_x_multiplier",
        "connection_norm_amps",
        "connection_emerg_amps",
        "classification",
    }
)
DERIVED_ELECTRICAL_KEYS = frozenset(
    {
        "source_z1_ohm",
        "source_x1_ohm",
        "source_r1_ohm",
        "source_r0_ohm",
        "source_x0_ohm",
        "connection_r0_ohm_per_km",
        "connection_x0_ohm_per_km",
        "aggregate_generator_kva",
        "formulas",
        "classification",
    }
)

PROFILE_V1_FIXED_NUMBERS = {
    "weibull_a": 8.199,
    "weibull_k": 2.665,
    "scenario_mean_wind_speed_ms": 7.29,
    "era5_recent_mean_wind_speed_ms": 7.294,
    "era5_full_mean_wind_speed_ms": 7.46,
    "ar1_phi": 0.92,
    "seasonal_amplitude": 0.18,
    "diurnal_amplitude": 0.03,
    "diurnal_peak_hour_utc": 10.0,
    "maximum_wind_speed_ms": 40.0,
    "air_density_site_kgm3": 1.15,
    "air_density_reference_kgm3": 1.225,
    "scenario_rounded_capacity_mw": 159.6,
    "export_cap_mw_for_future_counterfactual": 150.0,
    "synthetic_wind_minimum_ms": 0.4611936397603918,
    "synthetic_wind_mean_ms": 7.289999999999999,
    "synthetic_wind_maximum_ms": 20.39251289209873,
    "density_velocity_factor": 0.979160571690375,
    "energy_calculator_gross_aep_mwh": 554674.3580436552,
    "energy_calculator_parity_delta_mwh": -4.655215889215469e-06,
}
PROFILE_V1_FIXED_INTS = {
    "seasonal_peak_day": 200,
    "turbine_count": 15,
}
PROFILE_V1_FIXED_STRINGS = {"turbine_model": "iea_reference_10mw"}
PROFILE_V1_EXCLUDED_LOSSES = {
    "wake_loss_pct": 7.28,
    "availability_pct": 97.0,
    "electrical_loss_pct": 2.0,
    "curtailment_pct": 2.0,
    "other_pct": 1.0,
}

COPIED_ELECTRICAL_V1 = {
    "collector_voltage_kv": 33.0,
    "source_fault_level_mva": 900.0,
    "source_rx": 0.083,
    "connection_r1_ohm_per_km": 0.6,
    "connection_x1_ohm_per_km": 6.0,
    "plant_rating_mva": 159.6,
}
SYNTHETIC_ELECTRICAL_V1 = {
    "source_voltage_kv": 220.0,
    "source_zero_sequence_r_multiplier": 3.0,
    "source_zero_sequence_x_multiplier": 3.0,
    "transformer_mva": 200.0,
    "transformer_xhl_pct": 12.0,
    "transformer_r_pct_per_winding": 0.5,
    "connection_length_km": 1.0,
    "connection_zero_sequence_r_multiplier": 3.0,
    "connection_zero_sequence_x_multiplier": 3.0,
    "connection_norm_amps": 3000.0,
    "connection_emerg_amps": 3300.0,
}
ELECTRICAL_FORMULAS = {
    "source_z1": "source_voltage_kv^2 / source_fault_level_mva",
    "source_x1": "source_z1 / sqrt(1 + source_rx^2)",
    "source_r1": "source_rx * source_x1",
}

PINNED_CONFIG_NUMERIC_CONTROLS = (
    ("export_cap_mw", "profile.export_cap_mw", 150.0),
    ("ar1_phi", "profile.ar1_phi", 0.92),
    ("seasonal_amplitude", "profile.seasonal_amplitude", 0.18),
    ("diurnal_amplitude", "profile.diurnal_amplitude", 0.03),
    ("diurnal_peak_hour_utc", "profile.diurnal_peak_hour_utc", 10.0),
    ("maximum_wind_speed_ms", "profile.maximum_wind_speed_ms", 40.0),
    ("source_voltage_kv", "electrical.source_voltage_kv", 220.0),
    ("transformer_mva", "electrical.transformer_mva", 200.0),
    ("transformer_xhl_pct", "electrical.transformer_xhl_pct", 12.0),
    (
        "transformer_r_pct_per_winding",
        "electrical.transformer_r_pct_per_winding",
        0.5,
    ),
    (
        "source_zero_sequence_r_multiplier",
        "electrical.source_zero_sequence_r_multiplier",
        3.0,
    ),
    (
        "source_zero_sequence_x_multiplier",
        "electrical.source_zero_sequence_x_multiplier",
        3.0,
    ),
    (
        "connection_zero_sequence_r_multiplier",
        "electrical.connection_zero_sequence_r_multiplier",
        3.0,
    ),
    (
        "connection_zero_sequence_x_multiplier",
        "electrical.connection_zero_sequence_x_multiplier",
        3.0,
    ),
    ("connection_norm_amps", "electrical.connection_norm_amps", 3000.0),
    ("connection_emerg_amps", "electrical.connection_emerg_amps", 3300.0),
    ("frequency_hz", "electrical.frequency_hz", 50.0),
)

_SHA256_RE = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True)
class SourceSnapshot:
    """One pinned repository input used by the generator.

    Attributes:
        logical_id: Stable source identifier used in the manifest.
        relative_path: Traversal-free path relative to the repository root.
        expected_sha256: Required lowercase SHA-256 digest of the source bytes.
    """

    logical_id: str
    relative_path: str
    expected_sha256: str


@dataclass(frozen=True)
class SyntheticFeederPlaceholderConfig:
    """Strict, config-first settings for the #923-B1 package."""

    output_dir: str
    allow_existing_identical: bool
    validate_opendss_compile: bool
    random_seed: int
    reference_year: int
    export_cap_mw: float
    frozen_spec_sha256: str
    synthetic_chronology_decision_sha256: str
    sources: tuple[SourceSnapshot, ...]
    ar1_phi: float
    seasonal_amplitude: float
    seasonal_peak_day: int
    diurnal_amplitude: float
    diurnal_peak_hour_utc: float
    maximum_wind_speed_ms: float
    source_voltage_kv: float
    transformer_mva: float
    transformer_xhl_pct: float
    transformer_r_pct_per_winding: float
    source_zero_sequence_r_multiplier: float
    source_zero_sequence_x_multiplier: float
    connection_zero_sequence_r_multiplier: float
    connection_zero_sequence_x_multiplier: float
    connection_norm_amps: float
    connection_emerg_amps: float
    frequency_hz: float

    def __post_init__(self) -> None:
        """Reject direct-constructor attempts to bypass the governed parser."""

        _validate_config_instance(self)

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> SyntheticFeederPlaceholderConfig:
        """Parse and fail loudly on every controlled field (CESSPIT).

        Args:
            raw: Resolved Hydra/YAML configuration mapping.

        Returns:
            A strictly validated immutable generator configuration.

        Raises:
            ValueError: If a field is missing, unknown, mistyped, or out of bounds.
        """

        _require_exact_keys(
            raw,
            {
                "defaults",
                "artifact",
                "generator",
                "source",
                "profile",
                "electrical",
                "classification",
                "hydra",
            },
            "config",
            required={
                "artifact",
                "generator",
                "source",
                "profile",
                "electrical",
                "classification",
            },
        )

        artifact = _require_mapping(raw.get("artifact"), "artifact")
        generator = _require_mapping(raw.get("generator"), "generator")
        source = _require_mapping(raw.get("source"), "source")
        profile = _require_mapping(raw.get("profile"), "profile")
        electrical = _require_mapping(raw.get("electrical"), "electrical")
        classification = _require_mapping(raw.get("classification"), "classification")

        _require_exact_keys(
            artifact,
            {"output_dir", "allow_existing_identical", "validate_opendss_compile"},
            "artifact",
        )
        _require_exact_keys(
            generator,
            {"version", "random_seed", "algorithm"},
            "generator",
        )
        _require_exact_keys(
            source,
            {
                "frozen_spec_sha256",
                "synthetic_chronology_decision_sha256",
                "scenario",
                "era5_summary",
                "era5_request",
                "power_curves",
                "era5_calculator_config",
                "version_file",
            },
            "source",
        )
        _require_exact_keys(
            profile,
            {
                "reference_year",
                "export_cap_mw",
                "ar1_phi",
                "seasonal_amplitude",
                "seasonal_peak_day",
                "diurnal_amplitude",
                "diurnal_peak_hour_utc",
                "maximum_wind_speed_ms",
            },
            "profile",
        )
        _require_exact_keys(
            electrical,
            {
                "source_voltage_kv",
                "transformer_mva",
                "transformer_xhl_pct",
                "transformer_r_pct_per_winding",
                "source_zero_sequence_r_multiplier",
                "source_zero_sequence_x_multiplier",
                "connection_zero_sequence_r_multiplier",
                "connection_zero_sequence_x_multiplier",
                "connection_norm_amps",
                "connection_emerg_amps",
                "frequency_hz",
            },
            "electrical",
        )
        _require_exact_classification(classification)
        source_entries: list[SourceSnapshot] = []
        for logical_id in (
            "scenario",
            "era5_summary",
            "era5_request",
            "power_curves",
            "era5_calculator_config",
            "version_file",
        ):
            entry = _require_mapping(source.get(logical_id), f"source.{logical_id}")
            _require_exact_keys(entry, {"path", "sha256"}, f"source.{logical_id}")
            source_entries.append(
                SourceSnapshot(
                    logical_id=logical_id,
                    relative_path=_require_safe_relative_path(
                        entry.get("path"), f"source.{logical_id}.path"
                    ),
                    expected_sha256=_require_sha256(
                        entry.get("sha256"), f"source.{logical_id}.sha256"
                    ),
                )
            )

        output_dir = _require_safe_relative_path(
            artifact.get("output_dir"), "artifact.output_dir"
        )
        if output_dir != GOVERNED_OUTPUT_DIR:
            raise ValueError(
                f"artifact.output_dir must remain exactly {GOVERNED_OUTPUT_DIR!r}."
            )

        random_seed = _require_int(
            generator.get("random_seed"), "generator.random_seed"
        )
        if random_seed != RANDOM_SEED:
            raise ValueError(
                f"generator.random_seed must be the frozen {RANDOM_SEED}, got {random_seed}."
            )
        version = _require_string(generator.get("version"), "generator.version")
        if version != GENERATOR_VERSION:
            raise ValueError(
                f"generator.version must be {GENERATOR_VERSION!r}, got {version!r}."
            )
        algorithm = _require_string(generator.get("algorithm"), "generator.algorithm")
        if algorithm != RNG_ALGORITHM:
            raise ValueError(
                f"generator.algorithm must be {RNG_ALGORITHM!r}, got {algorithm!r}."
            )

        reference_year = _require_int(
            profile.get("reference_year"), "profile.reference_year"
        )
        if reference_year != 2021:
            raise ValueError(
                "profile.reference_year must remain the frozen non-leap year 2021."
            )
        if _hours_in_year(reference_year) != 8760:
            raise ValueError(
                "profile.reference_year must contain exactly 8,760 UTC hours."
            )

        ar1_phi = _require_number(profile.get("ar1_phi"), "profile.ar1_phi")
        if not 0.0 <= ar1_phi < 1.0:
            raise ValueError("profile.ar1_phi must be within [0, 1).")
        seasonal_amplitude = _require_number(
            profile.get("seasonal_amplitude"), "profile.seasonal_amplitude"
        )
        if not 0.0 <= seasonal_amplitude <= 0.5:
            raise ValueError("profile.seasonal_amplitude must be within [0, 0.5].")
        diurnal_amplitude = _require_number(
            profile.get("diurnal_amplitude"), "profile.diurnal_amplitude"
        )
        if not 0.0 <= diurnal_amplitude <= 0.2:
            raise ValueError("profile.diurnal_amplitude must be within [0, 0.2].")
        seasonal_peak_day = _require_int(
            profile.get("seasonal_peak_day"), "profile.seasonal_peak_day"
        )
        if not 1 <= seasonal_peak_day <= 365:
            raise ValueError("profile.seasonal_peak_day must be within 1..365.")
        diurnal_peak_hour = _require_number(
            profile.get("diurnal_peak_hour_utc"), "profile.diurnal_peak_hour_utc"
        )
        if not 0.0 <= diurnal_peak_hour < 24.0:
            raise ValueError("profile.diurnal_peak_hour_utc must be within [0, 24).")

        return cls(
            output_dir=output_dir,
            allow_existing_identical=_require_bool(
                artifact.get("allow_existing_identical"),
                "artifact.allow_existing_identical",
            ),
            validate_opendss_compile=_require_bool(
                artifact.get("validate_opendss_compile"),
                "artifact.validate_opendss_compile",
            ),
            random_seed=random_seed,
            reference_year=reference_year,
            export_cap_mw=_require_positive(
                profile.get("export_cap_mw"), "profile.export_cap_mw"
            ),
            frozen_spec_sha256=_require_sha256(
                source.get("frozen_spec_sha256"), "source.frozen_spec_sha256"
            ),
            synthetic_chronology_decision_sha256=_require_sha256(
                source.get("synthetic_chronology_decision_sha256"),
                "source.synthetic_chronology_decision_sha256",
            ),
            sources=tuple(source_entries),
            ar1_phi=ar1_phi,
            seasonal_amplitude=seasonal_amplitude,
            seasonal_peak_day=seasonal_peak_day,
            diurnal_amplitude=diurnal_amplitude,
            diurnal_peak_hour_utc=diurnal_peak_hour,
            maximum_wind_speed_ms=_require_positive(
                profile.get("maximum_wind_speed_ms"),
                "profile.maximum_wind_speed_ms",
            ),
            source_voltage_kv=_require_positive(
                electrical.get("source_voltage_kv"), "electrical.source_voltage_kv"
            ),
            transformer_mva=_require_positive(
                electrical.get("transformer_mva"), "electrical.transformer_mva"
            ),
            transformer_xhl_pct=_require_positive(
                electrical.get("transformer_xhl_pct"),
                "electrical.transformer_xhl_pct",
            ),
            transformer_r_pct_per_winding=_require_positive(
                electrical.get("transformer_r_pct_per_winding"),
                "electrical.transformer_r_pct_per_winding",
            ),
            source_zero_sequence_r_multiplier=_require_positive(
                electrical.get("source_zero_sequence_r_multiplier"),
                "electrical.source_zero_sequence_r_multiplier",
            ),
            source_zero_sequence_x_multiplier=_require_positive(
                electrical.get("source_zero_sequence_x_multiplier"),
                "electrical.source_zero_sequence_x_multiplier",
            ),
            connection_zero_sequence_r_multiplier=_require_positive(
                electrical.get("connection_zero_sequence_r_multiplier"),
                "electrical.connection_zero_sequence_r_multiplier",
            ),
            connection_zero_sequence_x_multiplier=_require_positive(
                electrical.get("connection_zero_sequence_x_multiplier"),
                "electrical.connection_zero_sequence_x_multiplier",
            ),
            connection_norm_amps=_require_positive(
                electrical.get("connection_norm_amps"),
                "electrical.connection_norm_amps",
            ),
            connection_emerg_amps=_require_positive(
                electrical.get("connection_emerg_amps"),
                "electrical.connection_emerg_amps",
            ),
            frequency_hz=_require_positive(
                electrical.get("frequency_hz"), "electrical.frequency_hz"
            ),
        )


@dataclass(frozen=True)
class VerifiedSyntheticFeederPackage:
    """Validated package identity, safe for B2 to consume as synthetic evidence."""

    output_root: Path
    master_path: Path
    profile_path: Path
    manifest_path: Path
    checksum_path: Path
    manifest_sha256: str
    file_sha256: Mapping[str, str]
    profile_rows: int
    profile_start_utc: str
    profile_end_utc: str
    generation_profile_mw: tuple[float, ...]
    export_cap_mw: float
    maximum_gross_generation_mw: float
    opendss_compile_status: str
    convergence_status: str


SyntheticFeederPackage = VerifiedSyntheticFeederPackage


def _require_mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be a mapping, got {type(value).__name__}.")
    return cast(Mapping[str, Any], value)


def _require_exact_keys(
    value: Mapping[str, Any],
    allowed: set[str],
    field: str,
    *,
    required: set[str] | None = None,
) -> None:
    """Reject undeclared keys and require the controlled schema subset."""

    unexpected = sorted(set(value) - allowed)
    if unexpected:
        raise ValueError(f"{field} contains unexpected keys: {unexpected}.")
    required_keys = allowed if required is None else required
    if not required_keys <= allowed:
        raise ValueError(
            f"{field} required-key schema is not a subset of allowed keys."
        )
    missing = sorted(required_keys - set(value))
    if missing:
        raise ValueError(f"{field} is missing required keys: {missing}.")


def _require_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a non-empty string, got {value!r}.")
    return value


def _require_bool(value: Any, field: str) -> bool:
    if type(value) is not bool:
        raise ValueError(f"{field} must be a literal boolean, got {value!r}.")
    return bool(value)


def _require_int(value: Any, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{field} must be an integer, got {value!r}.")
    return value


def _require_number(value: Any, field: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{field} must be a finite number, got {value!r}.")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{field} must be finite, got {value!r}.")
    return result


def _require_positive(value: Any, field: str) -> float:
    result = _require_number(value, field)
    if result <= 0.0:
        raise ValueError(f"{field} must be > 0, got {value!r}.")
    return result


def _require_frozen_numbers(
    value: Mapping[str, Any], expected: Mapping[str, float], field: str
) -> dict[str, float]:
    """Require exact finite non-boolean generator-v1 numeric controls."""

    result: dict[str, float] = {}
    for key, expected_value in expected.items():
        actual = _require_number(value.get(key), f"{field}.{key}")
        if actual != expected_value:
            raise ValueError(
                f"{field}.{key} must remain the frozen generator-v1 value "
                f"{expected_value}, got {actual}."
            )
        result[key] = actual
    return result


def _require_close(actual: float, expected: float, field: str) -> None:
    """Require deterministic floating-point formula parity."""

    if not math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12):
        raise ValueError(
            f"{field} does not reconcile to its frozen generator-v1 formula: "
            f"expected {expected}, got {actual}."
        )


def _require_sha256(value: Any, field: str) -> str:
    result = _require_string(value, field)
    if _SHA256_RE.fullmatch(result) is None:
        raise ValueError(f"{field} must be 64 lowercase hexadecimal characters.")
    return result


def _require_safe_relative_path(value: Any, field: str) -> str:
    text = _require_string(value, field)
    if "\\" in text:
        raise ValueError(f"{field} must use POSIX separators, got {text!r}.")
    path = PurePosixPath(text)
    if path.is_absolute() or ".." in path.parts or "." in path.parts:
        raise ValueError(f"{field} must be a traversal-free repository-relative path.")
    return path.as_posix()


def _reject_symlink_ancestors(path: Path, field: str) -> None:
    """Reject provenance paths that traverse an existing symlinked directory."""

    absolute = Path(os.path.abspath(os.fspath(path)))
    for ancestor in absolute.parents:
        if ancestor.is_symlink():
            raise ValueError(
                f"{field} must not traverse a symlinked ancestor: {ancestor}."
            )


def _normalized_path_identity_parts(path: Path) -> tuple[str, ...]:
    """Return conservative cross-platform filesystem-identity components."""

    return tuple(
        unicodedata.normalize("NFC", component).casefold()
        for component in path.resolve().parts
    )


def _nearest_existing_ancestor(path: Path) -> tuple[Path, tuple[str, ...]]:
    """Return the nearest existing ancestor and its normalized remaining suffix."""

    cursor = path.resolve()
    missing_components: list[str] = []
    while not cursor.exists() and cursor.parent != cursor:
        missing_components.append(unicodedata.normalize("NFC", cursor.name).casefold())
        cursor = cursor.parent
    return cursor, tuple(reversed(missing_components))


def _publication_paths_overlap(left: Path, right: Path) -> bool:
    """Detect equal, ancestor, or descendant publication paths conservatively."""

    left_parts = _normalized_path_identity_parts(left)
    right_parts = _normalized_path_identity_parts(right)
    lexical_overlap = (
        left_parts[: len(right_parts)] == right_parts
        or right_parts[: len(left_parts)] == left_parts
    )
    if lexical_overlap:
        return True

    left_anchor, left_suffix = _nearest_existing_ancestor(left)
    right_anchor, right_suffix = _nearest_existing_ancestor(right)
    try:
        same_existing_anchor = left_anchor.samefile(right_anchor)
    except OSError:
        same_existing_anchor = False
    return same_existing_anchor and (
        left_suffix[: len(right_suffix)] == right_suffix
        or right_suffix[: len(left_suffix)] == left_suffix
    )


def _require_exact_classification(value: Mapping[str, Any]) -> None:
    _require_exact_keys(value, set(CLASSIFICATION), "classification")
    for key, expected in CLASSIFICATION.items():
        actual = value.get(key)
        if type(expected) is bool and type(actual) is not bool:
            raise ValueError(
                f"classification.{key} must be the literal boolean {expected}, got {actual!r}."
            )
        if actual != expected:
            raise ValueError(
                f"classification.{key} must be {expected!r}, got {actual!r}."
            )


def _validate_config_instance(config: SyntheticFeederPlaceholderConfig) -> None:
    """Apply fail-loud invariants to parsed and directly constructed configs."""

    output_dir = _require_safe_relative_path(config.output_dir, "artifact.output_dir")
    if output_dir != GOVERNED_OUTPUT_DIR:
        raise ValueError(
            f"artifact.output_dir must remain exactly {GOVERNED_OUTPUT_DIR!r}."
        )
    _require_bool(config.allow_existing_identical, "artifact.allow_existing_identical")
    _require_bool(config.validate_opendss_compile, "artifact.validate_opendss_compile")
    if _require_int(config.random_seed, "generator.random_seed") != RANDOM_SEED:
        raise ValueError(f"generator.random_seed must be the frozen {RANDOM_SEED}.")
    if _require_int(config.reference_year, "profile.reference_year") != 2021:
        raise ValueError("profile.reference_year must remain the frozen year 2021.")
    frozen_spec_sha256 = _require_sha256(
        config.frozen_spec_sha256, "source.frozen_spec_sha256"
    )
    if frozen_spec_sha256 != FROZEN_SPEC_SHA256:
        raise ValueError(
            "source.frozen_spec_sha256 does not match the frozen #923 specification."
        )
    chronology_decision_sha256 = _require_sha256(
        config.synthetic_chronology_decision_sha256,
        "source.synthetic_chronology_decision_sha256",
    )
    if chronology_decision_sha256 != SYNTHETIC_CHRONOLOGY_DECISION_SHA256:
        raise ValueError(
            "source.synthetic_chronology_decision_sha256 does not match the "
            "controlled B1 chronology decision."
        )

    if not isinstance(config.sources, tuple) or not all(
        isinstance(source, SourceSnapshot) for source in config.sources
    ):
        raise ValueError("Every source snapshot must be a SourceSnapshot instance.")
    actual_source_triples = tuple(
        (source.logical_id, source.relative_path, source.expected_sha256)
        for source in config.sources
    )
    if actual_source_triples != PINNED_REPOSITORY_SOURCE_TRIPLES:
        raise ValueError(
            "source snapshots must exactly match the immutable generator-v1 "
            "logical-id/path/SHA-256 mapping."
        )
    for source in config.sources:
        _require_safe_relative_path(
            source.relative_path, f"source.{source.logical_id}.path"
        )
        _require_sha256(source.expected_sha256, f"source.{source.logical_id}.sha256")

    for attribute, field, expected_value in PINNED_CONFIG_NUMERIC_CONTROLS:
        actual_value = _require_number(getattr(config, attribute), field)
        if actual_value != expected_value:
            raise ValueError(
                f"{field} must remain the frozen generator-v1 value "
                f"{expected_value}, got {actual_value}."
            )

    ar1_phi = _require_number(config.ar1_phi, "profile.ar1_phi")
    if not 0.0 <= ar1_phi < 1.0:
        raise ValueError("profile.ar1_phi must be within [0, 1).")
    seasonal_amplitude = _require_number(
        config.seasonal_amplitude, "profile.seasonal_amplitude"
    )
    if not 0.0 <= seasonal_amplitude <= 0.5:
        raise ValueError("profile.seasonal_amplitude must be within [0, 0.5].")
    diurnal_amplitude = _require_number(
        config.diurnal_amplitude, "profile.diurnal_amplitude"
    )
    if not 0.0 <= diurnal_amplitude <= 0.2:
        raise ValueError("profile.diurnal_amplitude must be within [0, 0.2].")
    seasonal_peak_day = _require_int(
        config.seasonal_peak_day, "profile.seasonal_peak_day"
    )
    if not 1 <= seasonal_peak_day <= 365:
        raise ValueError("profile.seasonal_peak_day must be within 1..365.")
    if seasonal_peak_day != PROFILE_V1_FIXED_INTS["seasonal_peak_day"]:
        raise ValueError(
            "profile.seasonal_peak_day must remain the frozen generator-v1 value "
            f"{PROFILE_V1_FIXED_INTS['seasonal_peak_day']}."
        )
    diurnal_peak_hour = _require_number(
        config.diurnal_peak_hour_utc, "profile.diurnal_peak_hour_utc"
    )
    if not 0.0 <= diurnal_peak_hour < 24.0:
        raise ValueError("profile.diurnal_peak_hour_utc must be within [0, 24).")

    for value, field in (
        (config.export_cap_mw, "profile.export_cap_mw"),
        (config.maximum_wind_speed_ms, "profile.maximum_wind_speed_ms"),
        (config.source_voltage_kv, "electrical.source_voltage_kv"),
        (config.transformer_mva, "electrical.transformer_mva"),
        (config.transformer_xhl_pct, "electrical.transformer_xhl_pct"),
        (
            config.transformer_r_pct_per_winding,
            "electrical.transformer_r_pct_per_winding",
        ),
        (
            config.source_zero_sequence_r_multiplier,
            "electrical.source_zero_sequence_r_multiplier",
        ),
        (
            config.source_zero_sequence_x_multiplier,
            "electrical.source_zero_sequence_x_multiplier",
        ),
        (
            config.connection_zero_sequence_r_multiplier,
            "electrical.connection_zero_sequence_r_multiplier",
        ),
        (
            config.connection_zero_sequence_x_multiplier,
            "electrical.connection_zero_sequence_x_multiplier",
        ),
        (config.connection_norm_amps, "electrical.connection_norm_amps"),
        (config.connection_emerg_amps, "electrical.connection_emerg_amps"),
        (config.frequency_hz, "electrical.frequency_hz"),
    ):
        _require_positive(value, field)


def _hours_in_year(year: int) -> int:
    start = datetime(year, 1, 1, tzinfo=timezone.utc)
    end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    return int((end - start).total_seconds() // 3600)


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical_json(value: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(value, sort_keys=True, indent=2, allow_nan=False, ensure_ascii=False)
        + "\n"
    ).encode("utf-8")


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    try:
        temporary.write_bytes(payload)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _source_paths(
    config: SyntheticFeederPlaceholderConfig, repo_root: Path
) -> dict[str, Path]:
    root = repo_root.resolve()
    resolved: dict[str, Path] = {}
    for source in config.sources:
        relative_parts = PurePosixPath(source.relative_path).parts
        candidate = root.joinpath(*relative_parts)
        cursor = root
        for part in relative_parts:
            cursor /= part
            if cursor.is_symlink():
                raise FileNotFoundError(
                    f"Pinned source {source.logical_id!r} is a symlink: "
                    f"{source.relative_path}"
                )
        path = candidate.resolve()
        if not path.is_relative_to(root):
            raise ValueError(
                f"source.{source.logical_id}.path escapes the repository root."
            )
        if not path.is_file():
            raise FileNotFoundError(
                f"Pinned source {source.logical_id!r} is absent or a symlink: "
                f"{source.relative_path}"
            )
        actual = _sha256_path(path)
        if actual != source.expected_sha256:
            raise ValueError(
                f"Pinned source hash mismatch for {source.logical_id}: expected "
                f"{source.expected_sha256}, got {actual}. Refuse silent source drift."
            )
        resolved[source.logical_id] = path
    return resolved


def _load_yaml_mapping(path: Path, field: str) -> Mapping[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    return _require_mapping(value, field)


def _load_json_mapping(path: Path, field: str) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    return _require_mapping(value, field)


def _nested_mapping(root: Mapping[str, Any], key: str, field: str) -> Mapping[str, Any]:
    return _require_mapping(root.get(key), field)


def _extract_inputs(
    config: SyntheticFeederPlaceholderConfig,
    source_paths: Mapping[str, Path],
) -> dict[str, Any]:
    scenario = _load_yaml_mapping(source_paths["scenario"], "scenario")
    era5_summary = _load_json_mapping(source_paths["era5_summary"], "era5_summary")
    era5_request = _load_yaml_mapping(source_paths["era5_request"], "era5_request")
    power_curves = _load_yaml_mapping(source_paths["power_curves"], "power_curves")

    project = _nested_mapping(scenario, "project", "scenario.project")
    turbine = _nested_mapping(scenario, "turbine", "scenario.turbine")
    wind_resource = _nested_mapping(scenario, "wind_resource", "scenario.wind_resource")
    resource = _nested_mapping(scenario, "resource", "scenario.resource")
    resource_losses = _nested_mapping(resource, "losses", "scenario.resource.losses")
    resource_power_curve = _nested_mapping(
        resource, "power_curve", "scenario.resource.power_curve"
    )
    grid = _nested_mapping(scenario, "grid", "scenario.grid")
    request_project = _nested_mapping(era5_request, "project", "era5_request.project")
    request_download = _nested_mapping(
        era5_request, "download", "era5_request.download"
    )
    request_reference = _nested_mapping(
        request_download, "reference", "era5_request.download.reference"
    )
    request_turbine = _nested_mapping(era5_request, "turbine", "era5_request.turbine")

    latitude = _require_number(request_project.get("latitude"), "era5 latitude")
    longitude = _require_number(request_project.get("longitude"), "era5 longitude")
    if latitude != 8.27 or longitude != 79.75:
        raise ValueError("#923 source location must remain exactly 8.27, 79.75.")
    if request_reference.get("mode") != "fixed":
        raise ValueError("ERA5 request reference.mode must be fixed.")
    if _require_int(request_reference.get("start"), "ERA5 start") != 2005:
        raise ValueError("ERA5 request start must be 2005.")
    if _require_int(request_reference.get("end"), "ERA5 end") != 2024:
        raise ValueError("ERA5 request end must be 2024.")
    if request_download.get("strict_coverage") is not True:
        raise ValueError("ERA5 request strict_coverage must be literal true.")

    summary_hours = _require_int(era5_summary.get("hours"), "ERA5 summary hours")
    if summary_hours != 175_320:
        raise ValueError(f"ERA5 summary must cover 175,320 hours, got {summary_hours}.")
    coverage = _nested_mapping(era5_summary, "coverage", "era5_summary.coverage")
    if coverage.get("coverage_complete") is not True:
        raise ValueError("ERA5 summary coverage_complete must be literal true.")
    if _require_int(coverage.get("missing_hours"), "ERA5 missing_hours") != 0:
        raise ValueError("ERA5 summary must have zero missing hours.")

    turbine_model = _require_string(
        request_turbine.get("model"), "era5_request.turbine.model"
    )
    curve_key = _require_string(
        resource_power_curve.get("curve_key"), "resource.power_curve.curve_key"
    )
    if turbine_model != curve_key:
        raise ValueError(
            f"ERA5 request turbine model {turbine_model!r} does not match scenario "
            f"curve_key {curve_key!r}."
        )
    curve = _nested_mapping(power_curves, curve_key, f"power_curves.{curve_key}")

    n_turbines = _require_int(turbine.get("n_turbines"), "turbine.n_turbines")
    if n_turbines != _require_int(
        request_turbine.get("num_turbines"), "era5_request.turbine.num_turbines"
    ):
        raise ValueError("Scenario and ERA5 request turbine counts do not match.")
    hub_height_m = _require_number(turbine.get("hub_height_m"), "turbine.hub_height_m")
    if hub_height_m != _require_number(
        request_turbine.get("hub_height_m"), "era5_request.turbine.hub_height_m"
    ):
        raise ValueError("Scenario and ERA5 request hub heights do not match.")

    recent_mean = None
    period_aep = era5_summary.get("long_term_trend")
    if isinstance(period_aep, Mapping):
        rows = period_aep.get("period_aep")
        if isinstance(rows, Sequence) and not isinstance(rows, (str, bytes)):
            for row in rows:
                if isinstance(row, Mapping) and row.get("key") == "recent_5yr":
                    recent_mean = _require_number(
                        row.get("mean_ws_ms"), "ERA5 recent_5yr mean_ws_ms"
                    )
                    break
    if recent_mean is None:
        raise ValueError("ERA5 summary lacks the recent_5yr mean wind speed.")
    scenario_mean = _require_positive(
        wind_resource.get("mean_wind_speed_ms"), "wind_resource.mean_wind_speed_ms"
    )
    if abs(scenario_mean - recent_mean) > 0.05:
        raise ValueError(
            "Scenario mean wind speed does not reconcile within 0.05 m/s to the "
            "hashed ERA5 recent-period summary."
        )

    copied_grid = {
        "collector_voltage_kv": _require_positive(
            grid.get("poc_voltage_kv"), "grid.poc_voltage_kv"
        ),
        "source_fault_level_mva": _require_positive(
            grid.get("source_fault_level_mva"), "grid.source_fault_level_mva"
        ),
        "source_rx": _require_positive(grid.get("source_rx"), "grid.source_rx"),
        "connection_r1_ohm_per_km": _require_positive(
            grid.get("connection_r_ohm"), "grid.connection_r_ohm"
        ),
        "connection_x1_ohm_per_km": _require_positive(
            grid.get("connection_x_ohm"), "grid.connection_x_ohm"
        ),
        "plant_rating_mva": _require_positive(
            grid.get("plant_rating_mva"), "grid.plant_rating_mva"
        ),
    }

    return {
        "scenario": scenario,
        "era5_summary": era5_summary,
        "turbine_model": turbine_model,
        "curve": curve,
        "n_turbines": n_turbines,
        "hub_height_m": hub_height_m,
        "weibull_a": _require_positive(
            wind_resource.get("weibull_a"), "wind_resource.weibull_a"
        ),
        "weibull_k": _require_positive(
            wind_resource.get("weibull_k"), "wind_resource.weibull_k"
        ),
        "scenario_mean_wind_speed_ms": scenario_mean,
        "era5_recent_mean_wind_speed_ms": recent_mean,
        "era5_full_mean_wind_speed_ms": _require_positive(
            era5_summary.get("mean_ws_hub_ms"), "era5_summary.mean_ws_hub_ms"
        ),
        "air_density_site_kgm3": _require_positive(
            wind_resource.get("air_density_kgm3"), "wind_resource.air_density_kgm3"
        ),
        "air_density_ref_kgm3": _require_positive(
            wind_resource.get("air_density_ref_kgm3"),
            "wind_resource.air_density_ref_kgm3",
        ),
        "scenario_capacity_mw": _require_positive(
            project.get("capacity_mw"), "project.capacity_mw"
        ),
        "curve_rated_capacity_kw": _require_positive(
            curve.get("rated_capacity_kw"), "power curve rated_capacity_kw"
        ),
        "copied_grid": copied_grid,
        "excluded_losses": dict(resource_losses),
    }


def _synthetic_wind_speeds(
    config: SyntheticFeederPlaceholderConfig, inputs: Mapping[str, Any]
) -> NDArray[np.float64]:
    """Create a seeded synthetic chronology calibrated to summary statistics only."""

    n_hours = _hours_in_year(config.reference_year)
    rng = np.random.Generator(np.random.PCG64(config.random_seed))
    innovations = rng.standard_normal(n_hours)
    latent = np.empty(n_hours, dtype=float)
    latent[0] = innovations[0]
    innovation_scale = math.sqrt(1.0 - config.ar1_phi**2)
    for index in range(1, n_hours):
        latent[index] = (
            config.ar1_phi * latent[index - 1] + innovation_scale * innovations[index]
        )

    uniforms = np.clip(ndtr(latent), 1e-12, 1.0 - 1e-12)
    weibull_a = float(inputs["weibull_a"])
    weibull_k = float(inputs["weibull_k"])
    speeds = weibull_a * np.power(-np.log1p(-uniforms), 1.0 / weibull_k)

    hours = np.arange(n_hours, dtype=float)
    day_of_year = np.floor(hours / 24.0) + 1.0
    hour_of_day = np.mod(hours, 24.0)
    seasonal = 1.0 + config.seasonal_amplitude * np.cos(
        2.0 * math.pi * (day_of_year - config.seasonal_peak_day) / 365.0
    )
    diurnal = 1.0 + config.diurnal_amplitude * np.cos(
        2.0 * math.pi * (hour_of_day - config.diurnal_peak_hour_utc) / 24.0
    )
    speeds = np.clip(speeds * seasonal * diurnal, 0.0, config.maximum_wind_speed_ms)

    target_mean = float(inputs["scenario_mean_wind_speed_ms"])
    for _ in range(4):
        observed_mean = float(np.mean(speeds))
        if observed_mean <= 0.0:
            raise ValueError("Synthetic wind generator produced a non-positive mean.")
        speeds = np.clip(
            speeds * (target_mean / observed_mean),
            0.0,
            config.maximum_wind_speed_ms,
        )
    if not np.isfinite(speeds).all() or np.any(speeds < 0.0):
        raise ValueError("Synthetic wind profile contains invalid values.")
    return np.asarray(speeds, dtype=np.float64)


def _generation_profile(
    config: SyntheticFeederPlaceholderConfig,
    inputs: Mapping[str, Any],
    source_paths: Mapping[str, Path],
) -> tuple[bytes, dict[str, Any]]:
    speeds = _synthetic_wind_speeds(config, inputs)
    calculator = EnergyCalculator(
        pd.DataFrame({"ws_150m": speeds}),
        ws_column="ws_150m",
        turbine_model=str(inputs["turbine_model"]),
        num_turbines=int(inputs["n_turbines"]),
        config_path=str(source_paths["era5_calculator_config"]),
        power_curves_path=str(source_paths["power_curves"]),
        air_density_site_kgm3=float(inputs["air_density_site_kgm3"]),
        air_density_ref_kgm3=float(inputs["air_density_ref_kgm3"]),
    )
    density_factor = float(calculator.density_velocity_factor)
    power_per_turbine_kw = np.asarray(
        calculator.power_curve_func(speeds * density_factor), dtype=float
    )
    gross_mw = power_per_turbine_kw * int(inputs["n_turbines"]) / 1000.0
    if not np.isfinite(gross_mw).all() or np.any(gross_mw < 0.0):
        raise ValueError("Power-curve conversion produced invalid gross generation.")
    scenario_capacity = float(inputs["scenario_capacity_mw"])
    if np.any(gross_mw > scenario_capacity + 1e-9):
        raise ValueError("Gross generation exceeds the scenario plant rating.")

    rounded_mw = np.round(gross_mw, 6)
    start = datetime(config.reference_year, 1, 1, tzinfo=timezone.utc)
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(CSV_COLUMNS)
    for index, generation_mw in enumerate(rounded_mw):
        timestamp = start + timedelta(hours=index)
        writer.writerow(
            (
                timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
                f"{generation_mw:.6f}",
                SOURCE_KIND,
                SYNTHETIC_CASE,
                "false",
                "true",
                "false",
                "false",
                "false",
                "false",
            )
        )
    payload = stream.getvalue().encode("utf-8")

    gross = calculator.calculate_gross_aep()
    rounded_aep_mwh = float(np.sum(rounded_mw))
    parity_delta = rounded_aep_mwh - float(gross["windfarm_aep_mwh"])
    if abs(parity_delta) > 0.01:
        raise ValueError(
            "Generated CSV no longer reconciles to EnergyCalculator.calculate_gross_aep()."
        )

    stats: dict[str, Any] = {
        "row_count": len(rounded_mw),
        "start_utc": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "end_utc": (start + timedelta(hours=len(rounded_mw) - 1)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "minimum_gross_generation_mw": float(np.min(rounded_mw)),
        "maximum_gross_generation_mw": float(np.max(rounded_mw)),
        "mean_gross_generation_mw": float(np.mean(rounded_mw)),
        "gross_aep_mwh_from_rounded_csv": rounded_aep_mwh,
        "energy_calculator_gross_aep_mwh": float(gross["windfarm_aep_mwh"]),
        "energy_calculator_parity_delta_mwh": parity_delta,
        "synthetic_wind_mean_ms": float(np.mean(speeds)),
        "synthetic_wind_minimum_ms": float(np.min(speeds)),
        "synthetic_wind_maximum_ms": float(np.max(speeds)),
        "density_velocity_factor": density_factor,
        "hours_above_140_mw": int(np.sum(rounded_mw > 140.0)),
        "hours_above_150_mw": int(np.sum(rounded_mw > 150.0)),
        "hours_above_159_6_mw": int(np.sum(rounded_mw > 159.6)),
    }
    if stats["hours_above_150_mw"] <= 0:
        raise ValueError(
            "Gross synthetic profile must exercise the 150 MW export-cap boundary; "
            "do not apply downstream loss deductions before QSTS."
        )
    return payload, stats


def _dss_payloads(
    config: SyntheticFeederPlaceholderConfig, inputs: Mapping[str, Any]
) -> tuple[dict[str, bytes], dict[str, Any]]:
    copied = cast(Mapping[str, float], inputs["copied_grid"])
    source_fault_mva = float(copied["source_fault_level_mva"])
    source_rx = float(copied["source_rx"])
    source_z1_ohm = config.source_voltage_kv**2 / source_fault_mva
    source_x1_ohm = source_z1_ohm / math.sqrt(1.0 + source_rx**2)
    source_r1_ohm = source_rx * source_x1_ohm
    source_r0_ohm = source_r1_ohm * config.source_zero_sequence_r_multiplier
    source_x0_ohm = source_x1_ohm * config.source_zero_sequence_x_multiplier
    connection_r1 = float(copied["connection_r1_ohm_per_km"])
    connection_x1 = float(copied["connection_x1_ohm_per_km"])
    connection_r0 = connection_r1 * config.connection_zero_sequence_r_multiplier
    connection_x0 = connection_x1 * config.connection_zero_sequence_x_multiplier
    collector_kv = float(copied["collector_voltage_kv"])
    rated_kva = float(inputs["curve_rated_capacity_kw"]) * int(inputs["n_turbines"])

    common = (
        HEADER + "! input_kind=synthetic_placeholder generated=true observed=false "
        "site_representative=false bankable=false canonical=false publishable=false\n"
        "! package_id=synthetic923_placeholder\n"
    )
    payloads = {
        "feeder/Master.dss": (
            common
            + "Clear\n"
            + 'Redirect "Source.dss"\n'
            + 'Redirect "Transformer.dss"\n'
            + 'Redirect "Connection.dss"\n'
            + 'Redirect "Plant.dss"\n'
            + f"Set VoltageBases=[{config.source_voltage_kv:.6f}, {collector_kv:.6f}]\n"
            + "CalcVoltageBases\n"
            + "Set ControlMode=OFF\n"
            + "Set MaxIterations=50\n"
            + "! COMPILE ONLY IN #923-B; Solve/convergence evidence is deferred to #923-C.\n"
        ).encode("utf-8"),
        "feeder/Source.dss": (
            common
            + "! 900 MVA and R/X are screening estimates copied from the lender scenario.\n"
            + "! The 220 kV side and zero-sequence multipliers are synthetic assumptions.\n"
            + "New Circuit.synthetic923_circuit "
            + "bus1=synthetic923_source_220kv "
            + f"basekv={config.source_voltage_kv:.6f} pu=1.000000 phases=3 "
            + f"frequency={config.frequency_hz:.6f} "
            + f"r1={source_r1_ohm:.10f} x1={source_x1_ohm:.10f} "
            + f"r0={source_r0_ohm:.10f} x0={source_x0_ohm:.10f}\n"
        ).encode("utf-8"),
        "feeder/Transformer.dss": (
            common
            + "! Vector group, grounding, rating, and impedance are synthetic assumptions.\n"
            + "New Transformer.synthetic923_gss_transformer phases=3 windings=2 "
            + f"xhl={config.transformer_xhl_pct:.6f}\n"
            + "~ wdg=1 bus=synthetic923_source_220kv conn=delta "
            + f"kv={config.source_voltage_kv:.6f} kva={config.transformer_mva * 1000.0:.6f} "
            + f"%r={config.transformer_r_pct_per_winding:.6f}\n"
            + "~ wdg=2 bus=synthetic923_collector_33kv.1.2.3.0 conn=wye "
            + f"kv={collector_kv:.6f} kva={config.transformer_mva * 1000.0:.6f} "
            + f"%r={config.transformer_r_pct_per_winding:.6f}\n"
        ).encode("utf-8"),
        "feeder/Connection.dss": (
            common
            + "! Positive sequence is a scenario screening estimate; zero sequence and "
            + "ampacity are synthetic assumptions.\n"
            + "New Line.synthetic923_equivalent_connection "
            + "bus1=synthetic923_collector_33kv "
            + "bus2=synthetic923_poc_33kv phases=3 length=1.000000 units=km "
            + f"r1={connection_r1:.10f} x1={connection_x1:.10f} "
            + f"r0={connection_r0:.10f} x0={connection_x0:.10f} "
            + f"c1=0.000000 c0=0.000000 normamps={config.connection_norm_amps:.6f} "
            + f"emergamps={config.connection_emerg_amps:.6f}\n"
        ).encode("utf-8"),
        "feeder/Plant.dss": (
            common
            + "! Aggregate generator is a software-wiring equivalent, not an OEM or POC model.\n"
            + "New Generator.synthetic923_poc_generator "
            + "bus1=synthetic923_poc_33kv phases=3 conn=wye "
            + f"kv={collector_kv:.6f} kw=0.000000 kvar=0.000000 "
            + f"kva={rated_kva:.6f} pf=1.000000 model=1 enabled=true\n"
        ).encode("utf-8"),
    }

    electrical = {
        "copied_screening_estimates": {
            **dict(copied),
            "source_path": "scenarios/dutchbay_lendercase_2025Q4.yaml:grid",
            "classification": "existing_scenario_screening_estimate_not_bankable",
        },
        "synthetic_assumptions": {
            "source_voltage_kv": config.source_voltage_kv,
            "source_zero_sequence_r_multiplier": config.source_zero_sequence_r_multiplier,
            "source_zero_sequence_x_multiplier": config.source_zero_sequence_x_multiplier,
            "transformer_mva": config.transformer_mva,
            "transformer_vector_group": "delta_grounded_wye_placeholder",
            "transformer_xhl_pct": config.transformer_xhl_pct,
            "transformer_r_pct_per_winding": config.transformer_r_pct_per_winding,
            "connection_length_km": 1.0,
            "connection_zero_sequence_r_multiplier": config.connection_zero_sequence_r_multiplier,
            "connection_zero_sequence_x_multiplier": config.connection_zero_sequence_x_multiplier,
            "connection_norm_amps": config.connection_norm_amps,
            "connection_emerg_amps": config.connection_emerg_amps,
            "classification": "synthetic_assumption_not_project_fact",
        },
        "derived_values": {
            "source_z1_ohm": source_z1_ohm,
            "source_x1_ohm": source_x1_ohm,
            "source_r1_ohm": source_r1_ohm,
            "source_r0_ohm": source_r0_ohm,
            "source_x0_ohm": source_x0_ohm,
            "connection_r0_ohm_per_km": connection_r0,
            "connection_x0_ohm_per_km": connection_x0,
            "aggregate_generator_kva": rated_kva,
            "formulas": {
                "source_z1": "source_voltage_kv^2 / source_fault_level_mva",
                "source_x1": "source_z1 / sqrt(1 + source_rx^2)",
                "source_r1": "source_rx * source_x1",
            },
            "classification": "derived_from_screening_estimates_and_synthetic_assumptions",
        },
    }
    return payloads, electrical


def _compile_opendss(master_path: Path) -> str:
    try:
        import opendssdirect as dss
    except ImportError as exc:  # pragma: no cover - depends on optional extra
        raise ImportError(
            "#923-B OpenDSS compilation requires the [grid] extra: "
            "PIP_CONSTRAINT=constraints.txt pip install -e '.[grid]'. "
            "No package was published."
        ) from exc

    try:
        dss.Basic.ClearAll()
        dss.Command(f'Redirect "{master_path}"')
        error_number = int(dss.Error.Number())
        error_description = str(dss.Error.Description())
        circuit_name = str(dss.Circuit.Name())
        generator_count = int(dss.Generators.Count())
    except Exception as exc:  # pragma: no cover - dependency-specific failure
        raise RuntimeError(
            f"OpenDSS compile failed for the synthetic package: {exc}"
        ) from exc
    finally:
        try:
            dss.Basic.ClearAll()
        except Exception:
            pass

    if error_number != 0:
        raise RuntimeError(
            f"OpenDSS compile error {error_number}: {error_description or 'no description'}"
        )
    if not circuit_name or "synthetic923" not in circuit_name.lower():
        raise RuntimeError(
            f"OpenDSS did not activate the synthetic923 circuit, got {circuit_name!r}."
        )
    if generator_count != 1:
        raise RuntimeError(
            f"OpenDSS package must compile exactly one POC generator, got {generator_count}."
        )
    return "passed_compile_only_no_convergence_claim"


def _artifact_record(relative_path: str, payload: bytes) -> dict[str, Any]:
    suffix = PurePosixPath(relative_path).suffix.lower()
    media_type = {
        ".dss": "text/plain; charset=utf-8",
        ".csv": "text/csv; charset=utf-8",
    }.get(suffix, "application/octet-stream")
    return {
        "path": relative_path,
        "sha256": _sha256_bytes(payload),
        "byte_length": len(payload),
        "media_type": media_type,
    }


def _build_manifest(
    config: SyntheticFeederPlaceholderConfig,
    inputs: Mapping[str, Any],
    source_paths: Mapping[str, Path],
    payloads: Mapping[str, bytes],
    profile_stats: Mapping[str, Any],
    electrical: Mapping[str, Any],
    compile_status: str,
) -> dict[str, Any]:
    source_by_id = {item.logical_id: item for item in config.sources}
    source_snapshots: dict[str, dict[str, Any]] = {
        item.logical_id: {
            "logical_id": item.logical_id,
            "path": item.relative_path,
            "sha256": item.expected_sha256,
        }
        for item in config.sources
    }
    source_snapshots["frozen_issue_923_spec"] = {
        "logical_id": "frozen_issue_923_spec",
        "path": None,
        "sha256": config.frozen_spec_sha256,
        "note": "Controlled external specification hash; no machine-local path persisted.",
    }
    source_snapshots["synthetic_chronology_decision"] = {
        "logical_id": "synthetic_chronology_decision",
        "path": None,
        "sha256": config.synthetic_chronology_decision_sha256,
        "note": (
            "User-authorised controlled addendum for an explicitly synthetic chronology; "
            "no machine-local path persisted."
        ),
    }
    generator_path = Path(__file__).resolve()
    module_relative = generator_path.relative_to(generator_path.parents[2]).as_posix()
    source_snapshots["generator_source"] = {
        "logical_id": "generator_source",
        "path": module_relative,
        "sha256": _sha256_path(generator_path),
    }

    excluded_losses = cast(Mapping[str, Any], inputs["excluded_losses"])
    return {
        "schema": MANIFEST_SCHEMA,
        "issue": ISSUE,
        "artifact_kind": "synthetic_feeder_and_generation_profile_placeholder",
        "generator": {
            "version": GENERATOR_VERSION,
            "engine_version": engine_version(),
            "seed": config.random_seed,
            "algorithm": RNG_ALGORITHM,
            "random_draws_used": True,
            "wall_clock_generation_time_in_manifest": False,
        },
        "classification": dict(CLASSIFICATION),
        "labels": list(LABELS),
        "source_snapshots": source_snapshots,
        "electrical_parameters": dict(electrical),
        "profile": {
            "path": "profile/generation_profile.csv",
            "timestamp_column": "timestamp_utc",
            "value_column": "gross_generation_mw",
            "columns": list(CSV_COLUMNS),
            "source_kind": SOURCE_KIND,
            "chronology_kind": "synthetic_not_observed_2021",
            "calibration_basis": CALIBRATION_BASIS,
            "does_not_claim_actual_2021_conditions": True,
            "reference_year_for_timestamp_shape_only": config.reference_year,
            "weibull_a": float(inputs["weibull_a"]),
            "weibull_k": float(inputs["weibull_k"]),
            "scenario_mean_wind_speed_ms": float(inputs["scenario_mean_wind_speed_ms"]),
            "era5_recent_mean_wind_speed_ms": float(
                inputs["era5_recent_mean_wind_speed_ms"]
            ),
            "era5_full_mean_wind_speed_ms": float(
                inputs["era5_full_mean_wind_speed_ms"]
            ),
            "ar1_phi": config.ar1_phi,
            "seasonal_amplitude": config.seasonal_amplitude,
            "seasonal_peak_day": config.seasonal_peak_day,
            "diurnal_amplitude": config.diurnal_amplitude,
            "diurnal_peak_hour_utc": config.diurnal_peak_hour_utc,
            "maximum_wind_speed_ms": config.maximum_wind_speed_ms,
            "turbine_model": str(inputs["turbine_model"]),
            "turbine_count": int(inputs["n_turbines"]),
            "air_density_site_kgm3": float(inputs["air_density_site_kgm3"]),
            "air_density_reference_kgm3": float(inputs["air_density_ref_kgm3"]),
            "scenario_rounded_capacity_mw": float(inputs["scenario_capacity_mw"]),
            "gross_qsts_injection_boundary": GROSS_QSTS_INJECTION_BOUNDARY,
            "excluded_loss_stack": dict(excluded_losses),
            "export_cap_mw_for_future_counterfactual": config.export_cap_mw,
            **dict(profile_stats),
        },
        "artifacts": [
            _artifact_record(relative_path, payloads[relative_path])
            for relative_path in PAYLOAD_RELATIVE_PATHS
        ],
        "validation": {
            "source_hashes_verified": True,
            "package_hashes_verified_before_publication": True,
            "opendss_compile_status": compile_status,
            "convergence_status": CONVERGENCE_STATUS,
            "timestep_convergence_checked": False,
            "telemetry_checked": False,
            "generator_activation_each_step_checked": False,
        },
        "kpi_treatment": {
            "finance_executed": False,
            "finance_status": FINANCE_STATUS,
            "canonical_kpi_changed": False,
            "canon_repin_permitted": False,
            "finding_closure_weight": 0,
            "issue_923_closable": False,
        },
        "limitations": list(LIMITATIONS),
        "replacement_gate": {
            "status": "open",
            "requirements": list(REPLACEMENT_GATE),
            "issue_923_closable": False,
        },
        "control_cross_checks": {
            "scenario_source_sha256": source_by_id["scenario"].expected_sha256,
            "era5_summary_source_sha256": source_by_id["era5_summary"].expected_sha256,
            "source_files_resolved_inside_repo": all(
                path.is_relative_to(source_paths["scenario"].parents[1])
                for path in source_paths.values()
            ),
        },
    }


def _write_package(stage: Path, payloads: Mapping[str, bytes], manifest: bytes) -> None:
    for relative_path in PAYLOAD_RELATIVE_PATHS:
        _atomic_write(stage / relative_path, payloads[relative_path])
    _atomic_write(stage / "manifest.json", manifest)
    checksum_lines = [
        f"{_sha256_bytes(payloads[path])}  {path}" for path in PAYLOAD_RELATIVE_PATHS
    ]
    checksum_lines.append(f"{_sha256_bytes(manifest)}  manifest.json")
    checksum = ("\n".join(sorted(checksum_lines)) + "\n").encode("ascii")
    _atomic_write(stage / "MANIFEST.sha256", checksum)


def _package_bytes(root: Path) -> dict[str, bytes]:
    return {
        relative: (root / relative).read_bytes() for relative in PACKAGE_RELATIVE_PATHS
    }


def _publish_stage(
    stage: Path, target: Path, *, allow_existing_identical: bool
) -> None:
    if not target.exists():
        os.replace(stage, target)
        return
    if not target.is_dir() or target.is_symlink():
        raise FileExistsError(
            f"Refuse to replace non-directory or symlink output target: {target}"
        )
    if not allow_existing_identical:
        raise FileExistsError(f"Output package already exists: {target}")
    try:
        existing = _package_bytes(target)
        candidate = _package_bytes(stage)
    except (FileNotFoundError, OSError) as exc:
        raise FileExistsError(
            "Existing synthetic package is incomplete; refuse implicit overwrite."
        ) from exc
    if existing != candidate:
        raise FileExistsError(
            "A differing #923 synthetic package already exists. Refuse implicit overwrite; "
            "preserve or explicitly remove the prior governed package first."
        )
    shutil.rmtree(stage)


def generate_synthetic_feeder_placeholder(
    config: SyntheticFeederPlaceholderConfig,
    *,
    repo_root: Path,
    output_dir_override: Path | None = None,
) -> SyntheticFeederPackage:
    """Generate, validate, compile, and atomically publish the B1 package.

    ``output_dir_override`` exists only so tests can write outside the repository while
    exercising the exact production configuration.  It is not exposed by the Hydra CLI
    and never changes the repository-relative paths persisted inside the package.

    Args:
        config: Strict synthetic-package configuration.
        repo_root: Repository root against which pinned sources are resolved.
        output_dir_override: Test-only output target outside the configured package path.

    Returns:
        The verified identity and bounded metadata of the published package.

    Raises:
        FileNotFoundError: If a pinned input is absent or resolves through a symlink.
        ValueError: If configuration, provenance, profile, or package validation fails.
        FileExistsError: If a different package already occupies the output target.
        ImportError: If compile validation is enabled without the OpenDSS dependency.
        RuntimeError: If the generated OpenDSS package does not compile as required.
    """

    _validate_config_instance(config)
    if output_dir_override is None and config.validate_opendss_compile is not True:
        raise ValueError(
            "The governed #923-B1 production target requires OpenDSS compile "
            "validation; compile-disabled runs require an explicit isolated "
            "output_dir_override."
        )
    repo = repo_root.resolve()
    if not repo.is_dir():
        raise FileNotFoundError(f"Repository root does not exist: {repo}")
    governed_target = repo.joinpath(*PurePosixPath(GOVERNED_OUTPUT_DIR).parts).resolve()
    target_input = (
        output_dir_override
        if output_dir_override is not None
        else repo.joinpath(*PurePosixPath(config.output_dir).parts)
    )
    if target_input.is_symlink():
        raise ValueError("Synthetic package output root may not be a symlink.")
    _reject_symlink_ancestors(target_input, "Synthetic package output root")
    target = target_input.resolve()
    if output_dir_override is None and not target.is_relative_to(repo):
        raise ValueError("Configured output directory escapes the repository root.")
    if output_dir_override is not None and _publication_paths_overlap(
        target, governed_target
    ):
        raise ValueError(
            "Test-only output_dir_override must be outside, and must not contain, "
            "the governed #923-B1 production target."
        )

    source_paths = _source_paths(config, repo)
    inputs = _extract_inputs(config, source_paths)
    profile_payload, profile_stats = _generation_profile(config, inputs, source_paths)
    dss_payloads, electrical = _dss_payloads(config, inputs)
    payloads = {**dss_payloads, "profile/generation_profile.csv": profile_payload}

    target.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(
        tempfile.mkdtemp(prefix=".issue923-stage-", dir=str(target.parent))
    ).resolve()
    try:
        for relative_path, payload in payloads.items():
            _atomic_write(stage / relative_path, payload)
        compile_status = (
            _compile_opendss(stage / "feeder" / "Master.dss")
            if config.validate_opendss_compile
            else "not_examined_explicit_test_configuration"
        )
        manifest_dict = _build_manifest(
            config,
            inputs,
            source_paths,
            payloads,
            profile_stats,
            electrical,
            compile_status,
        )
        manifest_payload = _canonical_json(manifest_dict)
        _write_package(stage, payloads, manifest_payload)
        verify_synthetic_feeder_package(
            manifest_path=stage / "manifest.json",
            expected_manifest_sha256=_sha256_bytes(manifest_payload),
        )
        _publish_stage(
            stage,
            target,
            allow_existing_identical=config.allow_existing_identical,
        )
    except Exception:
        if stage.exists():
            shutil.rmtree(stage)
        raise

    return verify_synthetic_feeder_package(
        manifest_path=target / "manifest.json",
        expected_manifest_sha256=_sha256_bytes(manifest_payload),
    )


def verify_synthetic_feeder_package(
    *,
    manifest_path: str | Path,
    expected_manifest_sha256: str,
    master_path: str | Path | None = None,
) -> VerifiedSyntheticFeederPackage:
    """Verify a detached package without granting it finance or evidence status.

    Args:
        manifest_path: Path to the package's canonical ``manifest.json``.
        master_path: Optional feeder path that must match the packaged ``Master.dss``.
        expected_manifest_sha256: Required externally pinned manifest digest. An
            embedded checksum cannot authenticate a self-consistently resealed package.

    Returns:
        Verified package identity and its bounded validation metadata.

    Raises:
        FileNotFoundError: If the manifest or a governed payload is absent.
        ValueError: If provenance, classification, hashes, schema, or profile checks fail.
    """

    manifest_input = Path(manifest_path)
    if manifest_input.is_symlink():
        raise ValueError("Synthetic package manifest must not be a symlink.")
    _reject_symlink_ancestors(manifest_input, "Synthetic package manifest")
    manifest_file = manifest_input.resolve()
    output_root = manifest_file.parent
    if manifest_file.name != "manifest.json" or not manifest_file.is_file():
        raise FileNotFoundError("Synthetic package manifest.json is absent.")
    actual_manifest_sha = _sha256_path(manifest_file)
    expected = _require_sha256(expected_manifest_sha256, "expected_manifest_sha256")
    if actual_manifest_sha != expected:
        raise ValueError(
            f"Manifest SHA-256 mismatch: expected {expected}, got {actual_manifest_sha}."
        )

    manifest_raw = manifest_file.read_bytes()
    manifest_value = json.loads(manifest_raw.decode("utf-8"))
    manifest = _require_mapping(manifest_value, "manifest")
    if manifest_raw != _canonical_json(manifest):
        raise ValueError(
            "manifest.json is not canonical sorted two-space UTF-8/LF JSON."
        )
    _require_exact_keys(manifest, set(MANIFEST_TOP_LEVEL_KEYS), "manifest")
    if (
        manifest.get("schema") != MANIFEST_SCHEMA
        or _require_int(manifest.get("issue"), "manifest.issue") != ISSUE
    ):
        raise ValueError("Manifest schema or issue identifier is invalid.")
    if (
        manifest.get("artifact_kind")
        != "synthetic_feeder_and_generation_profile_placeholder"
    ):
        raise ValueError("Manifest artifact kind is invalid.")
    classification = _require_mapping(
        manifest.get("classification"), "manifest.classification"
    )
    _require_exact_classification(classification)
    generator = _require_mapping(manifest.get("generator"), "manifest.generator")
    _require_exact_keys(
        generator,
        {
            "version",
            "engine_version",
            "seed",
            "algorithm",
            "random_draws_used",
            "wall_clock_generation_time_in_manifest",
        },
        "manifest.generator",
    )
    if generator.get("version") != GENERATOR_VERSION:
        raise ValueError("Manifest generator version is invalid.")
    if generator.get("engine_version") != engine_version():
        raise ValueError("Manifest generator engine version is invalid.")
    if _require_int(generator.get("seed"), "manifest.generator.seed") != RANDOM_SEED:
        raise ValueError("Manifest generator seed is invalid.")
    if generator.get("algorithm") != RNG_ALGORITHM:
        raise ValueError("Manifest generator algorithm is invalid.")
    if (
        generator.get("random_draws_used") is not True
        or generator.get("wall_clock_generation_time_in_manifest") is not False
    ):
        raise ValueError("Manifest generator reproducibility flags are invalid.")
    if manifest.get("labels") != list(LABELS):
        raise ValueError("Manifest synthetic labels are absent or altered.")
    if manifest.get("limitations") != list(LIMITATIONS):
        raise ValueError("Manifest limitations are absent or altered.")
    source_snapshots = _require_mapping(
        manifest.get("source_snapshots"), "manifest.source_snapshots"
    )
    expected_snapshot_ids = {
        "scenario",
        "era5_summary",
        "era5_request",
        "power_curves",
        "era5_calculator_config",
        "version_file",
        "frozen_issue_923_spec",
        "synthetic_chronology_decision",
        "generator_source",
    }
    if set(source_snapshots) != expected_snapshot_ids:
        raise ValueError("Manifest source-snapshot set is incomplete or unexpected.")
    pinned_repository_sources = {
        logical_id: (relative_path, sha256)
        for logical_id, relative_path, sha256 in PINNED_REPOSITORY_SOURCE_TRIPLES
    }
    for logical_id, raw_snapshot in source_snapshots.items():
        snapshot = _require_mapping(
            raw_snapshot, f"manifest.source_snapshots.{logical_id}"
        )
        external_control = logical_id in {
            "frozen_issue_923_spec",
            "synthetic_chronology_decision",
        }
        _require_exact_keys(
            snapshot,
            (
                {"logical_id", "path", "sha256", "note"}
                if external_control
                else {"logical_id", "path", "sha256"}
            ),
            f"manifest.source_snapshots.{logical_id}",
        )
        if snapshot.get("logical_id") != logical_id:
            raise ValueError(f"Manifest source logical_id mismatch: {logical_id}.")
        snapshot_sha256 = _require_sha256(
            snapshot.get("sha256"),
            f"manifest.source_snapshots.{logical_id}.sha256",
        )
        snapshot_path = snapshot.get("path")
        if external_control:
            if snapshot_path is not None:
                raise ValueError("Controlled external evidence paths must remain null.")
        else:
            _require_safe_relative_path(
                snapshot_path, f"manifest.source_snapshots.{logical_id}.path"
            )
        if logical_id == "frozen_issue_923_spec":
            if snapshot_sha256 != FROZEN_SPEC_SHA256:
                raise ValueError("Manifest frozen #923 specification hash is invalid.")
            if snapshot.get("note") != (
                "Controlled external specification hash; no machine-local path persisted."
            ):
                raise ValueError("Manifest frozen #923 specification note is invalid.")
        elif logical_id == "synthetic_chronology_decision":
            if snapshot_sha256 != SYNTHETIC_CHRONOLOGY_DECISION_SHA256:
                raise ValueError(
                    "Manifest synthetic chronology decision hash is invalid."
                )
            if snapshot.get("note") != (
                "User-authorised controlled addendum for an explicitly synthetic "
                "chronology; no machine-local path persisted."
            ):
                raise ValueError(
                    "Manifest synthetic chronology decision note is invalid."
                )
        elif logical_id == "generator_source":
            if snapshot_path != "analytics/grid/synthetic_feeder_placeholder.py":
                raise ValueError("Manifest generator source path is invalid.")
            if snapshot_sha256 != _sha256_path(Path(__file__).resolve()):
                raise ValueError("Manifest generator source hash is not current.")
        elif logical_id in pinned_repository_sources:
            expected_path, expected_sha256 = pinned_repository_sources[logical_id]
            if snapshot_path != expected_path or snapshot_sha256 != expected_sha256:
                raise ValueError(
                    f"Manifest source snapshot {logical_id!r} does not match the "
                    "immutable generator-v1 source control."
                )
    kpi_treatment = _require_mapping(
        manifest.get("kpi_treatment"), "manifest.kpi_treatment"
    )
    _require_exact_keys(
        kpi_treatment,
        {
            "finance_executed",
            "finance_status",
            "canonical_kpi_changed",
            "canon_repin_permitted",
            "finding_closure_weight",
            "issue_923_closable",
        },
        "manifest.kpi_treatment",
    )
    if (
        kpi_treatment.get("finance_executed") is not False
        or kpi_treatment.get("finance_status") != FINANCE_STATUS
        or kpi_treatment.get("canonical_kpi_changed") is not False
        or kpi_treatment.get("canon_repin_permitted") is not False
        or _require_int(
            kpi_treatment.get("finding_closure_weight"),
            "manifest.kpi_treatment.finding_closure_weight",
        )
        != 0
        or kpi_treatment.get("issue_923_closable") is not False
    ):
        raise ValueError("Manifest attempts to grant finance or closure credit.")

    electrical_parameters = _require_mapping(
        manifest.get("electrical_parameters"), "manifest.electrical_parameters"
    )
    _require_exact_keys(
        electrical_parameters,
        {"copied_screening_estimates", "synthetic_assumptions", "derived_values"},
        "manifest.electrical_parameters",
    )
    copied_electrical = _require_mapping(
        electrical_parameters.get("copied_screening_estimates"),
        "manifest.electrical_parameters.copied_screening_estimates",
    )
    synthetic_electrical = _require_mapping(
        electrical_parameters.get("synthetic_assumptions"),
        "manifest.electrical_parameters.synthetic_assumptions",
    )
    derived_electrical = _require_mapping(
        electrical_parameters.get("derived_values"),
        "manifest.electrical_parameters.derived_values",
    )
    _require_exact_keys(
        copied_electrical,
        set(COPIED_ELECTRICAL_KEYS),
        "manifest.electrical_parameters.copied_screening_estimates",
    )
    _require_exact_keys(
        synthetic_electrical,
        set(SYNTHETIC_ELECTRICAL_KEYS),
        "manifest.electrical_parameters.synthetic_assumptions",
    )
    _require_exact_keys(
        derived_electrical,
        set(DERIVED_ELECTRICAL_KEYS),
        "manifest.electrical_parameters.derived_values",
    )
    formulas = _require_mapping(
        derived_electrical.get("formulas"),
        "manifest.electrical_parameters.derived_values.formulas",
    )
    _require_exact_keys(
        formulas,
        {"source_z1", "source_x1", "source_r1"},
        "manifest.electrical_parameters.derived_values.formulas",
    )
    if (
        copied_electrical.get("classification")
        != "existing_scenario_screening_estimate_not_bankable"
        or copied_electrical.get("source_path")
        != "scenarios/dutchbay_lendercase_2025Q4.yaml:grid"
        or synthetic_electrical.get("classification")
        != "synthetic_assumption_not_project_fact"
        or derived_electrical.get("classification")
        != "derived_from_screening_estimates_and_synthetic_assumptions"
    ):
        raise ValueError("Manifest electrical provenance classification is invalid.")
    copied_numbers = _require_frozen_numbers(
        copied_electrical,
        COPIED_ELECTRICAL_V1,
        "manifest.electrical_parameters.copied_screening_estimates",
    )
    synthetic_numbers = _require_frozen_numbers(
        synthetic_electrical,
        SYNTHETIC_ELECTRICAL_V1,
        "manifest.electrical_parameters.synthetic_assumptions",
    )
    if (
        synthetic_electrical.get("transformer_vector_group")
        != "delta_grounded_wye_placeholder"
    ):
        raise ValueError("Manifest transformer vector group is invalid.")
    if dict(formulas) != ELECTRICAL_FORMULAS:
        raise ValueError("Manifest electrical formulas are absent or altered.")

    derived_numbers = {
        key: _require_positive(
            derived_electrical.get(key),
            f"manifest.electrical_parameters.derived_values.{key}",
        )
        for key in DERIVED_ELECTRICAL_KEYS
        if key not in {"formulas", "classification"}
    }
    source_z1 = (
        synthetic_numbers["source_voltage_kv"] ** 2
        / copied_numbers["source_fault_level_mva"]
    )
    source_x1 = source_z1 / math.sqrt(1.0 + copied_numbers["source_rx"] ** 2)
    source_r1 = copied_numbers["source_rx"] * source_x1
    expected_derived = {
        "source_z1_ohm": source_z1,
        "source_x1_ohm": source_x1,
        "source_r1_ohm": source_r1,
        "source_r0_ohm": source_r1
        * synthetic_numbers["source_zero_sequence_r_multiplier"],
        "source_x0_ohm": source_x1
        * synthetic_numbers["source_zero_sequence_x_multiplier"],
        "connection_r0_ohm_per_km": copied_numbers["connection_r1_ohm_per_km"]
        * synthetic_numbers["connection_zero_sequence_r_multiplier"],
        "connection_x0_ohm_per_km": copied_numbers["connection_x1_ohm_per_km"]
        * synthetic_numbers["connection_zero_sequence_x_multiplier"],
        "aggregate_generator_kva": 159_574.5,
    }
    for key, expected_value in expected_derived.items():
        _require_close(
            derived_numbers[key],
            expected_value,
            f"manifest.electrical_parameters.derived_values.{key}",
        )
    if (
        synthetic_numbers["connection_emerg_amps"]
        < synthetic_numbers["connection_norm_amps"]
    ):
        raise ValueError("Emergency ampacity must not be below normal ampacity.")

    package_entries = list(output_root.rglob("*"))
    for path in package_entries:
        if path.is_symlink():
            raise ValueError(
                "Synthetic package must not contain symlinks: "
                f"{path.relative_to(output_root).as_posix()}"
            )
    actual_files = {
        path.relative_to(output_root).as_posix()
        for path in package_entries
        if path.is_file()
    }
    if actual_files != set(PACKAGE_RELATIVE_PATHS):
        raise ValueError(
            "Synthetic package must contain exactly the governed eight files; "
            f"got {sorted(actual_files)}."
        )
    for relative in PACKAGE_RELATIVE_PATHS:
        path = output_root / relative
        if path.is_symlink():
            raise ValueError(
                f"Synthetic package payload may not be a symlink: {relative}"
            )

    artifacts_value = manifest.get("artifacts")
    if not isinstance(artifacts_value, list):
        raise ValueError("manifest.artifacts must be a list.")
    artifacts: dict[str, Mapping[str, Any]] = {}
    for raw_record in artifacts_value:
        record = _require_mapping(raw_record, "manifest.artifacts[]")
        _require_exact_keys(
            record,
            {"path", "sha256", "byte_length", "media_type"},
            "manifest.artifacts[]",
        )
        relative = _require_safe_relative_path(
            record.get("path"), "manifest.artifacts[].path"
        )
        if relative in artifacts:
            raise ValueError(f"Duplicate manifest artifact path: {relative}")
        artifacts[relative] = record
    if set(artifacts) != set(PAYLOAD_RELATIVE_PATHS):
        raise ValueError("Manifest payload list does not match the governed package.")

    file_hashes: dict[str, str] = {}
    for relative in PAYLOAD_RELATIVE_PATHS:
        path = output_root / relative
        payload = path.read_bytes()
        actual_sha = _sha256_bytes(payload)
        record = artifacts[relative]
        expected_sha = _require_sha256(
            record.get("sha256"), f"artifact {relative} sha256"
        )
        if actual_sha != expected_sha:
            raise ValueError(f"Payload SHA-256 mismatch: {relative}")
        if actual_sha != FROZEN_PAYLOAD_SHA256[relative]:
            raise ValueError(
                f"Payload differs from the frozen generator-v1 bytes: {relative}"
            )
        byte_length = _require_int(
            record.get("byte_length"), f"artifact {relative} byte_length"
        )
        if byte_length < 0 or byte_length != len(payload):
            raise ValueError(f"Payload byte length mismatch: {relative}")
        expected_media_type = (
            "text/csv; charset=utf-8"
            if relative.endswith(".csv")
            else "text/plain; charset=utf-8"
        )
        if record.get("media_type") != expected_media_type:
            raise ValueError(f"Payload media type mismatch: {relative}")
        file_hashes[relative] = actual_sha

    checksum_path = output_root / "MANIFEST.sha256"
    expected_checksum_lines = [
        f"{file_hashes[relative]}  {relative}" for relative in PAYLOAD_RELATIVE_PATHS
    ]
    expected_checksum_lines.append(f"{actual_manifest_sha}  manifest.json")
    expected_checksum = "\n".join(sorted(expected_checksum_lines)) + "\n"
    if checksum_path.read_text(encoding="ascii") != expected_checksum:
        raise ValueError(
            "MANIFEST.sha256 is missing, altered, unsorted, or incomplete."
        )
    file_hashes["manifest.json"] = actual_manifest_sha
    file_hashes["MANIFEST.sha256"] = _sha256_path(checksum_path)

    executable_by_path: dict[str, list[str]] = {}
    for relative in DSS_REQUIRED_IDENTIFIERS:
        dss_text = (output_root / relative).read_text(encoding="utf-8")
        if not dss_text.startswith(HEADER):
            raise ValueError(f"Mandatory synthetic DSS header is absent: {relative}")
        executable_by_path[relative] = [
            line.strip()
            for line in dss_text.splitlines()
            if line.strip() and not line.lstrip().startswith("!")
        ]

    master_redirects: list[str] = []
    for line in executable_by_path["feeder/Master.dss"]:
        redirect_match = re.fullmatch(
            r'redirect\s+(?:"([^"]+)"|(\S+))', line, flags=re.IGNORECASE
        )
        if redirect_match is not None:
            master_redirects.append(redirect_match.group(1) or redirect_match.group(2))
    if master_redirects != [
        "Source.dss",
        "Transformer.dss",
        "Connection.dss",
        "Plant.dss",
    ]:
        raise ValueError(
            "Master.dss must contain exactly the four frozen component redirects."
        )

    expected_objects = {
        ("circuit", "synthetic923_circuit"),
        ("transformer", "synthetic923_gss_transformer"),
        ("line", "synthetic923_equivalent_connection"),
        ("generator", "synthetic923_poc_generator"),
    }
    actual_objects: set[tuple[str, str]] = set()
    for relative, executable_lines in executable_by_path.items():
        for line in executable_lines:
            if re.match(r"^(?:edit|clone|batchedit)\b", line, flags=re.IGNORECASE):
                raise ValueError(
                    f"Synthetic package contains an object-mutating command: {relative}"
                )
            object_match = re.match(
                r"^new\s+([A-Za-z]+)\.([^\s]+)", line, flags=re.IGNORECASE
            )
            if object_match is not None:
                actual_objects.add(
                    (object_match.group(1).lower(), object_match.group(2))
                )
            for bus_match in re.finditer(
                r"(?:^|\s)bus(?:1|2)?=([^\s]+)", line, flags=re.IGNORECASE
            ):
                base_bus = bus_match.group(1).split(".", maxsplit=1)[0]
                if not base_bus.startswith("synthetic923_"):
                    raise ValueError(
                        f"Synthetic package contains an unprefixed bus token: {relative}"
                    )
    if actual_objects != expected_objects:
        raise ValueError(
            "Synthetic package executable object set does not match the four frozen "
            "synthetic923 objects."
        )

    expected_master = output_root / "feeder" / "Master.dss"
    if master_path is not None and Path(master_path).is_symlink():
        raise ValueError("Configured feeder_model_path must not be a symlink.")
    if master_path is not None:
        _reject_symlink_ancestors(Path(master_path), "Configured feeder_model_path")
    if (
        master_path is not None
        and Path(master_path).resolve() != expected_master.resolve()
    ):
        raise ValueError(
            "Configured feeder_model_path does not match the package Master.dss."
        )

    profile_mapping = _require_mapping(manifest.get("profile"), "manifest.profile")
    _require_exact_keys(profile_mapping, set(PROFILE_KEYS), "manifest.profile")
    if (
        profile_mapping.get("path") != "profile/generation_profile.csv"
        or profile_mapping.get("timestamp_column") != "timestamp_utc"
        or profile_mapping.get("value_column") != "gross_generation_mw"
        or profile_mapping.get("columns") != list(CSV_COLUMNS)
        or profile_mapping.get("source_kind") != SOURCE_KIND
        or profile_mapping.get("chronology_kind") != "synthetic_not_observed_2021"
        or profile_mapping.get("calibration_basis") != CALIBRATION_BASIS
        or profile_mapping.get("does_not_claim_actual_2021_conditions") is not True
        or _require_int(
            profile_mapping.get("reference_year_for_timestamp_shape_only"),
            "manifest.profile.reference_year_for_timestamp_shape_only",
        )
        != 2021
        or profile_mapping.get("gross_qsts_injection_boundary")
        != GROSS_QSTS_INJECTION_BOUNDARY
    ):
        raise ValueError("Manifest profile provenance classification is invalid.")
    excluded_loss_stack = _require_mapping(
        profile_mapping.get("excluded_loss_stack"),
        "manifest.profile.excluded_loss_stack",
    )
    _require_exact_keys(
        excluded_loss_stack,
        {
            "wake_loss_pct",
            "availability_pct",
            "electrical_loss_pct",
            "curtailment_pct",
            "other_pct",
        },
        "manifest.profile.excluded_loss_stack",
    )
    fixed_profile_numbers = _require_frozen_numbers(
        profile_mapping, PROFILE_V1_FIXED_NUMBERS, "manifest.profile"
    )
    export_cap_mw = _require_positive(
        profile_mapping.get("export_cap_mw_for_future_counterfactual"),
        "manifest.profile.export_cap_mw_for_future_counterfactual",
    )
    for key, expected_integer in PROFILE_V1_FIXED_INTS.items():
        if (
            _require_int(profile_mapping.get(key), f"manifest.profile.{key}")
            != expected_integer
        ):
            raise ValueError(
                f"manifest.profile.{key} must remain the frozen generator-v1 value "
                f"{expected_integer}."
            )
    for key, expected_string in PROFILE_V1_FIXED_STRINGS.items():
        if (
            _require_string(profile_mapping.get(key), f"manifest.profile.{key}")
            != expected_string
        ):
            raise ValueError(
                f"manifest.profile.{key} must remain the frozen generator-v1 value "
                f"{expected_string!r}."
            )
    _require_frozen_numbers(
        excluded_loss_stack,
        PROFILE_V1_EXCLUDED_LOSSES,
        "manifest.profile.excluded_loss_stack",
    )

    energy_calculator_aep = _require_positive(
        profile_mapping.get("energy_calculator_gross_aep_mwh"),
        "manifest.profile.energy_calculator_gross_aep_mwh",
    )
    parity_delta = _require_number(
        profile_mapping.get("energy_calculator_parity_delta_mwh"),
        "manifest.profile.energy_calculator_parity_delta_mwh",
    )
    if abs(parity_delta) > 0.01:
        raise ValueError("Manifest EnergyCalculator parity exceeds 0.01 MWh.")
    synthetic_wind_minimum = _require_number(
        profile_mapping.get("synthetic_wind_minimum_ms"),
        "manifest.profile.synthetic_wind_minimum_ms",
    )
    synthetic_wind_mean = _require_positive(
        profile_mapping.get("synthetic_wind_mean_ms"),
        "manifest.profile.synthetic_wind_mean_ms",
    )
    synthetic_wind_maximum = _require_positive(
        profile_mapping.get("synthetic_wind_maximum_ms"),
        "manifest.profile.synthetic_wind_maximum_ms",
    )
    if not (
        0.0
        <= synthetic_wind_minimum
        <= synthetic_wind_mean
        <= synthetic_wind_maximum
        <= fixed_profile_numbers["maximum_wind_speed_ms"]
    ):
        raise ValueError("Manifest synthetic wind statistics are out of bounds.")
    _require_close(
        synthetic_wind_mean,
        fixed_profile_numbers["scenario_mean_wind_speed_ms"],
        "manifest.profile.synthetic_wind_mean_ms",
    )
    density_factor = _require_positive(
        profile_mapping.get("density_velocity_factor"),
        "manifest.profile.density_velocity_factor",
    )
    expected_density_factor = (
        fixed_profile_numbers["air_density_site_kgm3"]
        / fixed_profile_numbers["air_density_reference_kgm3"]
    ) ** (1.0 / 3.0)
    _require_close(
        density_factor,
        expected_density_factor,
        "manifest.profile.density_velocity_factor",
    )
    profile_path = output_root / "profile" / "generation_profile.csv"
    start_expected = _require_string(
        profile_mapping.get("start_utc"), "profile.start_utc"
    )
    end_expected = _require_string(profile_mapping.get("end_utc"), "profile.end_utc")
    if (
        start_expected != EXPECTED_PROFILE_START_UTC
        or end_expected != EXPECTED_PROFILE_END_UTC
    ):
        raise ValueError(
            "Generation profile timestamps must retain the frozen 2021 UTC shape."
        )
    rows_expected = _require_int(profile_mapping.get("row_count"), "profile.row_count")
    maximum_allowed = _require_positive(
        profile_mapping.get("scenario_rounded_capacity_mw"),
        "profile.scenario_rounded_capacity_mw",
    )
    minimum_seen = math.inf
    maximum_seen = 0.0
    total_generation_mwh = 0.0
    hours_above_140_mw = 0
    hours_above_150_mw = 0
    hours_above_159_6_mw = 0
    row_count = 0
    generation_profile_mw: list[float] = []
    previous: datetime | None = None
    first_timestamp: str | None = None
    last_timestamp: str | None = None
    with profile_path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != CSV_COLUMNS:
            raise ValueError(
                "Generation profile CSV columns do not match the frozen schema."
            )
        for row in reader:
            row_count += 1
            timestamp_text = row["timestamp_utc"]
            try:
                timestamp = datetime.strptime(
                    timestamp_text, "%Y-%m-%dT%H:%M:%SZ"
                ).replace(tzinfo=timezone.utc)
            except ValueError as exc:
                raise ValueError(
                    f"Invalid generation-profile UTC timestamp: {timestamp_text!r}"
                ) from exc
            if previous is not None and timestamp - previous != timedelta(hours=1):
                raise ValueError(
                    "Generation profile timestamps are not unique hourly steps."
                )
            previous = timestamp
            first_timestamp = first_timestamp or timestamp_text
            last_timestamp = timestamp_text
            generation = _require_number(
                float(row["gross_generation_mw"]), "gross_generation_mw"
            )
            if generation < 0.0 or generation > maximum_allowed + 1e-9:
                raise ValueError(
                    "Generation profile contains an out-of-range MW value."
                )
            generation_profile_mw.append(generation)
            minimum_seen = min(minimum_seen, generation)
            maximum_seen = max(maximum_seen, generation)
            total_generation_mwh += generation
            hours_above_140_mw += int(generation > 140.0)
            hours_above_150_mw += int(generation > 150.0)
            hours_above_159_6_mw += int(generation > 159.6)
            expected_constants = {
                "source_kind": SOURCE_KIND,
                "synthetic_feeder_case": SYNTHETIC_CASE,
                "observed_feeder_response": "false",
                "generated_input": "true",
                "site_representative": "false",
                "bankable": "false",
                "canonical": "false",
                "publishable": "false",
            }
            for column, expected_csv_value in expected_constants.items():
                if row[column] != expected_csv_value:
                    raise ValueError(
                        f"Generation profile anti-laundering field {column} is invalid."
                    )
    if row_count != rows_expected or row_count != 8760:
        raise ValueError(
            f"Generation profile must contain exactly 8,760 rows, got {row_count}."
        )
    if first_timestamp != start_expected or last_timestamp != end_expected:
        raise ValueError(
            "Generation profile start/end timestamps do not match the manifest."
        )
    if (
        abs(
            maximum_seen
            - _require_number(
                profile_mapping.get("maximum_gross_generation_mw"),
                "profile.maximum_gross_generation_mw",
            )
        )
        > 1e-9
    ):
        raise ValueError("Generation profile maximum does not match the manifest.")
    expected_statistics = {
        "minimum_gross_generation_mw": minimum_seen,
        "mean_gross_generation_mw": total_generation_mwh / row_count,
        "gross_aep_mwh_from_rounded_csv": total_generation_mwh,
    }
    for field, actual_value in expected_statistics.items():
        expected_statistic = _require_number(
            profile_mapping.get(field), f"profile.{field}"
        )
        if abs(actual_value - expected_statistic) > 1e-6:
            raise ValueError(f"Generation profile {field} does not match the manifest.")
    _require_close(
        _require_number(
            profile_mapping.get("gross_aep_mwh_from_rounded_csv"),
            "manifest.profile.gross_aep_mwh_from_rounded_csv",
        )
        - energy_calculator_aep,
        parity_delta,
        "manifest.profile.energy_calculator_parity_delta_mwh",
    )
    expected_counts = {
        "hours_above_140_mw": hours_above_140_mw,
        "hours_above_150_mw": hours_above_150_mw,
        "hours_above_159_6_mw": hours_above_159_6_mw,
    }
    for field, actual_value in expected_counts.items():
        expected_count = _require_int(profile_mapping.get(field), f"profile.{field}")
        if actual_value != expected_count:
            raise ValueError(f"Generation profile {field} does not match the manifest.")
    if hours_above_150_mw <= 0 or hours_above_159_6_mw != 0:
        raise ValueError(
            "Generation profile does not exercise the governed export cap."
        )

    validation = _require_mapping(manifest.get("validation"), "manifest.validation")
    _require_exact_keys(
        validation,
        {
            "source_hashes_verified",
            "package_hashes_verified_before_publication",
            "opendss_compile_status",
            "convergence_status",
            "timestep_convergence_checked",
            "telemetry_checked",
            "generator_activation_each_step_checked",
        },
        "manifest.validation",
    )
    compile_status = _require_string(
        validation.get("opendss_compile_status"),
        "validation.opendss_compile_status",
    )
    if compile_status not in {
        "passed_compile_only_no_convergence_claim",
        "not_examined_explicit_test_configuration",
    }:
        raise ValueError("Manifest OpenDSS compile status is invalid for B1.")
    convergence_status = _require_string(
        validation.get("convergence_status"), "validation.convergence_status"
    )
    if convergence_status != CONVERGENCE_STATUS:
        raise ValueError("B1 must defer convergence explicitly to #923-C.")
    if (
        validation.get("source_hashes_verified") is not True
        or validation.get("package_hashes_verified_before_publication") is not True
        or validation.get("timestep_convergence_checked") is not False
        or validation.get("telemetry_checked") is not False
        or validation.get("generator_activation_each_step_checked") is not False
    ):
        raise ValueError("Manifest B1 validation boundaries are invalid.")
    if compile_status == "passed_compile_only_no_convergence_claim":
        observed_compile_status = _compile_opendss(expected_master)
        if observed_compile_status != compile_status:
            raise ValueError(
                "Detached OpenDSS compile result does not match the manifest claim."
            )

    replacement_gate = _require_mapping(
        manifest.get("replacement_gate"), "manifest.replacement_gate"
    )
    _require_exact_keys(
        replacement_gate,
        {"status", "requirements", "issue_923_closable"},
        "manifest.replacement_gate",
    )
    if (
        replacement_gate.get("status") != "open"
        or replacement_gate.get("requirements") != list(REPLACEMENT_GATE)
        or replacement_gate.get("issue_923_closable") is not False
    ):
        raise ValueError("Manifest real-data replacement gate is invalid.")

    control_cross_checks = _require_mapping(
        manifest.get("control_cross_checks"), "manifest.control_cross_checks"
    )
    _require_exact_keys(
        control_cross_checks,
        {
            "scenario_source_sha256",
            "era5_summary_source_sha256",
            "source_files_resolved_inside_repo",
        },
        "manifest.control_cross_checks",
    )
    if (
        control_cross_checks.get("scenario_source_sha256")
        != pinned_repository_sources["scenario"][1]
        or control_cross_checks.get("era5_summary_source_sha256")
        != pinned_repository_sources["era5_summary"][1]
        or control_cross_checks.get("source_files_resolved_inside_repo") is not True
    ):
        raise ValueError("Manifest source control cross-checks are invalid.")

    return VerifiedSyntheticFeederPackage(
        output_root=output_root,
        master_path=expected_master,
        profile_path=profile_path,
        manifest_path=manifest_file,
        checksum_path=checksum_path,
        manifest_sha256=actual_manifest_sha,
        file_sha256=file_hashes,
        profile_rows=row_count,
        profile_start_utc=start_expected,
        profile_end_utc=end_expected,
        generation_profile_mw=tuple(generation_profile_mw),
        export_cap_mw=export_cap_mw,
        maximum_gross_generation_mw=maximum_seen,
        opendss_compile_status=compile_status,
        convergence_status=convergence_status,
    )


def cli_summary(
    package: SyntheticFeederPackage, config: SyntheticFeederPlaceholderConfig
) -> dict[str, Any]:
    """Build the single concise, non-durable JSON receipt emitted by the CLI.

    Args:
        package: Successfully generated and verified package.
        config: Configuration that produced the package.

    Returns:
        JSON-serializable receipt with hashes, boundaries, and zero-closure controls.
    """

    return {
        "status": "PASS",
        "issue": ISSUE,
        "classification": dict(CLASSIFICATION),
        "labels": list(LABELS),
        "generator_version": GENERATOR_VERSION,
        "random_seed": config.random_seed,
        "algorithm": RNG_ALGORITHM,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "repository_commit": git_sha(),
        "engine_version": engine_version(),
        "output_dir": config.output_dir,
        "manifest_sha256": package.manifest_sha256,
        "generated_files": [
            {"path": relative, "sha256": package.file_sha256[relative]}
            for relative in PACKAGE_RELATIVE_PATHS
        ],
        "profile": {
            "row_count": package.profile_rows,
            "start_utc": package.profile_start_utc,
            "end_utc": package.profile_end_utc,
            "maximum_gross_generation_mw": package.maximum_gross_generation_mw,
            "chronology_kind": "synthetic_not_observed_2021",
        },
        "opendss_compile_status": package.opendss_compile_status,
        "convergence_status": package.convergence_status,
        "finance_status": FINANCE_STATUS,
        "finding_closure_weight": 0,
        "issue_923_closable": False,
    }


__all__ = [
    "CLASSIFICATION",
    "CONVERGENCE_STATUS",
    "CSV_COLUMNS",
    "GENERATOR_VERSION",
    "HEADER",
    "INPUT_KIND",
    "LABELS",
    "MANIFEST_SCHEMA",
    "PACKAGE_RELATIVE_PATHS",
    "RANDOM_SEED",
    "RNG_ALGORITHM",
    "SOURCE_KIND",
    "SourceSnapshot",
    "SyntheticFeederPackage",
    "SyntheticFeederPlaceholderConfig",
    "VerifiedSyntheticFeederPackage",
    "cli_summary",
    "generate_synthetic_feeder_placeholder",
    "verify_synthetic_feeder_package",
]
