"""Dolphin #923-B1: deterministic synthetic feeder-package controls.

The generated package is software-wiring evidence only.  These tests deliberately
refuse any claim that it is observed, site-representative, bankable, canonical, or
sufficient to close Issue #923.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any, Iterator

import pytest
import yaml

import analytics.grid.synthetic_feeder_placeholder as synthetic_feeder_module
from analytics.grid.synthetic_feeder_placeholder import (
    CLASSIFICATION,
    CONVERGENCE_STATUS,
    CSV_COLUMNS,
    GENERATOR_VERSION,
    HEADER,
    PACKAGE_RELATIVE_PATHS,
    RANDOM_SEED,
    RNG_ALGORITHM,
    SourceSnapshot,
    SyntheticFeederPackage,
    SyntheticFeederPlaceholderConfig,
    cli_summary,
    generate_synthetic_feeder_placeholder,
    verify_synthetic_feeder_package,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / "conf" / "synthetic_feeder_placeholder.yaml"

EXPECTED_PAYLOAD_SHA256 = {
    "feeder/Master.dss": "27d4660ac61655ea850c6d72c6a58292d510f24baaef40a92d9d0ab8cde50d53",
    "feeder/Source.dss": "3c9113cac626a0d97d0cd37b884ecf7c7f34f562fcbb69e6e0009b315471b7af",
    "feeder/Transformer.dss": "d73f535e77154c133e008710d8e1ce60d5c00520888e65e6c7478ae4936a8823",
    "feeder/Connection.dss": "a3aaf7701c25fc13391267df4522acbda1ebe742a18f41278859c14d7b9a1502",
    "feeder/Plant.dss": "7ef945edca01ef90191e102b78abacba89bfa98a73dfc7bb0e671438a690a3d0",
    "profile/generation_profile.csv": "cefa4b9e37f85e5f7774a14727bf35a43c9c3bd8b3219bd730a35aff4f36ab76",
}
EXPECTED_PRODUCTION_MANIFEST_SHA256 = (
    # Re-pinned under #961. The manifest digest rolls up the pinned source
    # digests, and retracting the fabricated met-mast provenance from
    # scenarios/dutchbay_lendercase_2025Q4.yaml changed that scenario's bytes.
    # The per-file artefact digests above are UNCHANGED - the generated feeder
    # and profile are byte-identical - so this moved only because the manifest
    # records which sources produced them, which is the guard working, not
    # drifting. Verified deterministic across repeated runs (MRM-01).
    "24a723f33e13035def1f3fa68140bf6dc22f1b380d230b44331caadde5b25b2f"
)

MASTER_REDIRECT_MUTATIONS = [
    (target, mutation)
    for target in ("Source.dss", "Transformer.dss", "Connection.dss", "Plant.dss")
    for mutation in ("delete", "duplicate", "substitute", "traversal")
]

DSS_EXECUTABLE_MUTATIONS = [
    (
        "feeder/Plant.dss",
        "\nNew Load.CEB_observed_load bus1=synthetic923_poc_33kv.1.2.3 "
        "phases=3 kv=33 kw=1\n",
    ),
    (
        "feeder/Plant.dss",
        "\nnew load.CEB_observed_lowercase "
        "bus1=synthetic923_poc_33kv.1.2.3 phases=3 kv=33 kw=1\n",
    ),
    (
        "feeder/Plant.dss",
        "\nEdit Generator.synthetic923_poc_generator kw=1\n",
    ),
    (
        "feeder/Plant.dss",
        "\nClone Generator.synthetic923_poc_generator " "Generator.CEB_actual_poc\n",
    ),
    (
        "feeder/Plant.dss",
        "\nBatchEdit Generator..* kw=1\n",
    ),
]

FIXED_MANIFEST_FIELD_MUTATIONS: list[tuple[tuple[str, ...], object]] = [
    *(
        (("profile", key), False)
        for key in synthetic_feeder_module.PROFILE_V1_FIXED_NUMBERS
    ),
    *(
        (("profile", key), False)
        for key in synthetic_feeder_module.PROFILE_V1_FIXED_INTS
    ),
    *(
        (("profile", key), "forged")
        for key in synthetic_feeder_module.PROFILE_V1_FIXED_STRINGS
    ),
    *(
        (("profile", "excluded_loss_stack", key), False)
        for key in synthetic_feeder_module.PROFILE_V1_EXCLUDED_LOSSES
    ),
    *(
        (
            (
                "electrical_parameters",
                "copied_screening_estimates",
                key,
            ),
            False,
        )
        for key in synthetic_feeder_module.COPIED_ELECTRICAL_V1
    ),
    *(
        (
            (
                "electrical_parameters",
                "synthetic_assumptions",
                key,
            ),
            False,
        )
        for key in synthetic_feeder_module.SYNTHETIC_ELECTRICAL_V1
    ),
    *(
        (
            (
                "electrical_parameters",
                "derived_values",
                key,
            ),
            False,
        )
        for key in sorted(
            synthetic_feeder_module.DERIVED_ELECTRICAL_KEYS
            - {"classification", "formulas"}
        )
    ),
    *(
        (
            (
                "electrical_parameters",
                "derived_values",
                "formulas",
                key,
            ),
            "forged",
        )
        for key in synthetic_feeder_module.ELECTRICAL_FORMULAS
    ),
]

PINNED_CONFIG_FIELD_MUTATIONS: list[tuple[tuple[str, str], object]] = [
    *(
        (tuple(field.split(".", maxsplit=1)), expected + 0.001)
        for _, field, expected in synthetic_feeder_module.PINNED_CONFIG_NUMERIC_CONTROLS
    ),
    (("profile", "seasonal_peak_day"), 201),
    (("profile", "reference_year"), 2023),
    (("generator", "version"), "issue923-synthetic-feeder-v2"),
    (("generator", "algorithm"), "uncontrolled_rng"),
]


def _config() -> SyntheticFeederPlaceholderConfig:
    raw = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    assert isinstance(raw, dict)
    return SyntheticFeederPlaceholderConfig.from_mapping(raw)


def _sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _reseal_package(root: Path, manifest: dict[str, object]) -> str:
    artifacts = manifest["artifacts"]
    assert isinstance(artifacts, list)
    checksum_lines: list[str] = []
    for raw_record in artifacts:
        assert isinstance(raw_record, dict)
        relative = raw_record["path"]
        assert isinstance(relative, str)
        payload_path = root / relative
        payload = payload_path.read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        raw_record["sha256"] = digest
        raw_record["byte_length"] = len(payload)
        checksum_lines.append(f"{digest}  {relative}")

    manifest_payload = (
        json.dumps(
            manifest,
            sort_keys=True,
            indent=2,
            allow_nan=False,
            ensure_ascii=False,
        )
        + "\n"
    ).encode("utf-8")
    manifest_path = root / "manifest.json"
    manifest_path.write_bytes(manifest_payload)
    manifest_sha256 = hashlib.sha256(manifest_payload).hexdigest()
    checksum_lines.append(f"{manifest_sha256}  manifest.json")
    (root / "MANIFEST.sha256").write_text(
        "\n".join(sorted(checksum_lines)) + "\n", encoding="ascii"
    )
    return manifest_sha256


def _reseal_manifest_only(root: Path, manifest: dict[str, object]) -> str:
    manifest_payload = (
        json.dumps(
            manifest,
            sort_keys=True,
            indent=2,
            allow_nan=False,
            ensure_ascii=False,
        )
        + "\n"
    ).encode("utf-8")
    manifest_path = root / "manifest.json"
    manifest_path.write_bytes(manifest_payload)
    manifest_sha256 = hashlib.sha256(manifest_payload).hexdigest()
    checksum_lines = [
        f"{_sha256_path(root / relative)}  {relative}"
        for relative in synthetic_feeder_module.PAYLOAD_RELATIVE_PATHS
    ]
    checksum_lines.append(f"{manifest_sha256}  manifest.json")
    (root / "MANIFEST.sha256").write_text(
        "\n".join(sorted(checksum_lines)) + "\n", encoding="ascii"
    )
    return manifest_sha256


def _set_nested(mapping: dict[str, Any], path: tuple[str, ...], value: object) -> None:
    cursor: dict[str, Any] = mapping
    for key in path[:-1]:
        nested = cursor[key]
        assert isinstance(nested, dict)
        cursor = nested
    cursor[path[-1]] = value


@pytest.fixture(scope="module")
def package(
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[SyntheticFeederPackage]:
    output = tmp_path_factory.mktemp("issue923-package") / "issue_923"
    config = replace(_config(), validate_opendss_compile=False)
    yield generate_synthetic_feeder_placeholder(
        config, repo_root=REPO_ROOT, output_dir_override=output
    )


def test_config_is_explicitly_synthetic_and_finance_free() -> None:
    config = _config()
    assert config.random_seed == RANDOM_SEED
    assert config.output_dir == "outputs/synthetic_placeholders/issue_923"
    raw = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    assert raw["classification"] == CLASSIFICATION
    assert raw["generator"] == {
        "version": GENERATOR_VERSION,
        "random_seed": RANDOM_SEED,
        "algorithm": RNG_ALGORITHM,
    }
    assert "finance_wiring" not in raw
    assert "scenario" not in raw.get("artifact", {})


def test_source_yaml_retains_exact_hydra_no_log_no_output_controls() -> None:
    raw = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    assert set(raw) == {
        "defaults",
        "artifact",
        "generator",
        "source",
        "profile",
        "electrical",
        "classification",
        "hydra",
    }
    assert raw["defaults"] == [
        "_self_",
        {"override hydra/job_logging": "disabled"},
        {"override hydra/hydra_logging": "disabled"},
    ]
    assert raw["hydra"] == {
        "run": {"dir": "."},
        "sweep": {"dir": ".", "subdir": "."},
        "job": {"chdir": False},
        "output_subdir": None,
    }


def test_generated_package_has_only_eight_governed_files(
    package: SyntheticFeederPackage,
) -> None:
    actual = {
        path.relative_to(package.output_root).as_posix()
        for path in package.output_root.rglob("*")
        if path.is_file()
    }
    assert actual == set(PACKAGE_RELATIVE_PATHS)
    assert package.profile_rows == 8760
    assert package.profile_start_utc == "2021-01-01T00:00:00Z"
    assert package.profile_end_utc == "2021-12-31T23:00:00Z"
    assert len(package.generation_profile_mw) == 8760
    assert sum(package.generation_profile_mw) == pytest.approx(554674.358039)
    assert package.export_cap_mw == pytest.approx(150.0)
    assert package.maximum_gross_generation_mw == pytest.approx(159.5745)
    assert package.convergence_status == CONVERGENCE_STATUS
    assert package.opendss_compile_status == "not_examined_explicit_test_configuration"


def test_payload_hashes_are_exact_for_the_pinned_sources(
    package: SyntheticFeederPackage,
) -> None:
    assert {
        relative: package.file_sha256[relative] for relative in EXPECTED_PAYLOAD_SHA256
    } == EXPECTED_PAYLOAD_SHA256


def test_second_generation_is_byte_identical(
    tmp_path: Path, package: SyntheticFeederPackage
) -> None:
    second = generate_synthetic_feeder_placeholder(
        replace(_config(), validate_opendss_compile=False),
        repo_root=REPO_ROOT,
        output_dir_override=tmp_path / "issue_923_second",
    )
    assert second.manifest_sha256 == package.manifest_sha256
    for relative in PACKAGE_RELATIVE_PATHS:
        assert (second.output_root / relative).read_bytes() == (
            package.output_root / relative
        ).read_bytes()


def test_identical_existing_package_is_a_noop(
    package: SyntheticFeederPackage,
) -> None:
    before = {
        relative: (package.output_root / relative).read_bytes()
        for relative in PACKAGE_RELATIVE_PATHS
    }
    repeated = generate_synthetic_feeder_placeholder(
        replace(_config(), validate_opendss_compile=False),
        repo_root=REPO_ROOT,
        output_dir_override=package.output_root,
    )
    assert repeated.manifest_sha256 == package.manifest_sha256
    assert before == {
        relative: (package.output_root / relative).read_bytes()
        for relative in PACKAGE_RELATIVE_PATHS
    }


def test_differing_existing_package_is_not_overwritten(
    tmp_path: Path, package: SyntheticFeederPackage
) -> None:
    target = tmp_path / "differing"
    shutil.copytree(package.output_root, target)
    master = target / "feeder" / "Master.dss"
    master.write_text(
        master.read_text(encoding="utf-8") + "! altered\n", encoding="utf-8"
    )
    with pytest.raises(FileExistsError, match="differing #923 synthetic package"):
        generate_synthetic_feeder_placeholder(
            replace(_config(), validate_opendss_compile=False),
            repo_root=REPO_ROOT,
            output_dir_override=target,
        )
    assert master.read_text(encoding="utf-8").endswith("! altered\n")


def test_source_hash_drift_fails_before_generation(tmp_path: Path) -> None:
    config = _config()
    drifted_sources = list(config.sources)
    first = drifted_sources[0]
    drifted_sources[0] = SourceSnapshot(
        logical_id=first.logical_id,
        relative_path=first.relative_path,
        expected_sha256="0" * 64,
    )
    with pytest.raises(ValueError, match="immutable generator-v1"):
        generate_synthetic_feeder_placeholder(
            replace(
                config,
                sources=tuple(drifted_sources),
                validate_opendss_compile=False,
            ),
            repo_root=REPO_ROOT,
            output_dir_override=tmp_path / "never_published",
        )
    assert not (tmp_path / "never_published").exists()


def test_source_symlink_fails_before_generation(tmp_path: Path) -> None:
    config = replace(_config(), validate_opendss_compile=False)
    first = config.sources[0]
    synthetic_repo = tmp_path / "synthetic_repo"
    linked_source = synthetic_repo / first.relative_path
    linked_source.parent.mkdir(parents=True)
    linked_source.symlink_to(REPO_ROOT / first.relative_path)

    with pytest.raises(FileNotFoundError, match="is a symlink"):
        generate_synthetic_feeder_placeholder(
            config,
            repo_root=synthetic_repo,
            output_dir_override=tmp_path / "never_published_symlink",
        )
    assert not (tmp_path / "never_published_symlink").exists()


def test_direct_config_construction_cannot_change_frozen_seed() -> None:
    with pytest.raises(ValueError, match="random_seed must be the frozen"):
        replace(_config(), random_seed=RANDOM_SEED + 1)


def test_output_symlink_fails_before_generation(tmp_path: Path) -> None:
    real_output = tmp_path / "real_output"
    real_output.mkdir()
    output_link = tmp_path / "linked_output"
    output_link.symlink_to(real_output, target_is_directory=True)
    with pytest.raises(ValueError, match="output root may not be a symlink"):
        generate_synthetic_feeder_placeholder(
            replace(_config(), validate_opendss_compile=False),
            repo_root=REPO_ROOT,
            output_dir_override=output_link,
        )


def test_every_dss_file_begins_with_the_frozen_warning(
    package: SyntheticFeederPackage,
) -> None:
    for relative in EXPECTED_PAYLOAD_SHA256:
        if relative.endswith(".dss"):
            text = (package.output_root / relative).read_text(encoding="utf-8")
            assert text.startswith(HEADER)
            assert "package_id=synthetic923_placeholder" in text
            assert "bankable=false" in text
            assert "canonical=false" in text


def test_detached_csv_retains_machine_readable_anti_laundering_flags(
    package: SyntheticFeederPackage,
) -> None:
    lines = package.profile_path.read_text(encoding="utf-8").splitlines()
    assert tuple(lines[0].split(",")) == CSV_COLUMNS
    assert len(lines) == 8761
    first = lines[1].split(",")
    last = lines[-1].split(",")
    assert first[0] == "2021-01-01T00:00:00Z"
    assert last[0] == "2021-12-31T23:00:00Z"
    assert first[2:] == [
        "synthetic_era5_summary_calibrated",
        "issue923_placeholder_v1",
        "false",
        "true",
        "false",
        "false",
        "false",
        "false",
    ]


def test_manifest_discloses_synthetic_chronology_and_gross_boundary(
    package: SyntheticFeederPackage,
) -> None:
    manifest = json.loads(package.manifest_path.read_text(encoding="utf-8"))
    assert manifest["classification"] == CLASSIFICATION
    assert manifest["generator"]["random_draws_used"] is True
    assert manifest["profile"]["chronology_kind"] == "synthetic_not_observed_2021"
    assert manifest["profile"]["source_kind"] == "synthetic_era5_summary_calibrated"
    assert manifest["profile"]["does_not_claim_actual_2021_conditions"] is True
    assert "no raw hourly ERA5" in manifest["profile"]["calibration_basis"]
    assert manifest["profile"]["hours_above_150_mw"] > 0
    assert manifest["profile"]["hours_above_159_6_mw"] == 0
    assert manifest["profile"]["energy_calculator_parity_delta_mwh"] == pytest.approx(
        0.0, abs=0.01
    )
    assert (
        manifest["source_snapshots"]["synthetic_chronology_decision"]["sha256"]
        == _config().synthetic_chronology_decision_sha256
    )
    assert set(manifest["profile"]["excluded_loss_stack"]) == {
        "wake_loss_pct",
        "availability_pct",
        "electrical_loss_pct",
        "curtailment_pct",
        "other_pct",
    }
    assert manifest["kpi_treatment"] == {
        "canon_repin_permitted": False,
        "canonical_kpi_changed": False,
        "finance_executed": False,
        "finance_status": "not_run_scope_923_B",
        "finding_closure_weight": 0,
        "issue_923_closable": False,
    }


def test_source_impedance_is_derived_on_the_declared_220kv_side(
    package: SyntheticFeederPackage,
) -> None:
    manifest = json.loads(package.manifest_path.read_text(encoding="utf-8"))
    derived = manifest["electrical_parameters"]["derived_values"]
    synthetic = manifest["electrical_parameters"]["synthetic_assumptions"]
    assert synthetic["source_voltage_kv"] == pytest.approx(220.0)
    assert derived["source_z1_ohm"] == pytest.approx(220.0**2 / 900.0)
    assert derived["source_x1_ohm"] == pytest.approx(53.59349183686337)
    assert derived["source_r1_ohm"] == pytest.approx(4.44825982245966)
    assert synthetic["transformer_vector_group"] == "delta_grounded_wye_placeholder"


def test_verifier_refuses_payload_tampering(
    tmp_path: Path, package: SyntheticFeederPackage
) -> None:
    tampered = tmp_path / "tampered_payload"
    shutil.copytree(package.output_root, tampered)
    source = tampered / "feeder" / "Source.dss"
    source.write_text(
        source.read_text(encoding="utf-8") + "! forged\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="Payload SHA-256 mismatch"):
        verify_synthetic_feeder_package(
            manifest_path=tampered / "manifest.json",
            expected_manifest_sha256=package.manifest_sha256,
        )


def test_verifier_refuses_manifest_classification_laundering(
    tmp_path: Path, package: SyntheticFeederPackage
) -> None:
    tampered = tmp_path / "tampered_manifest"
    shutil.copytree(package.output_root, tampered)
    manifest_path = tampered / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["classification"]["canonical"] = True
    manifest_path.write_text(
        json.dumps(manifest, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match=r"classification\.canonical"):
        verify_synthetic_feeder_package(
            manifest_path=manifest_path,
            expected_manifest_sha256=_sha256_path(manifest_path),
        )


def test_verifier_refuses_generator_provenance_laundering(
    tmp_path: Path, package: SyntheticFeederPackage
) -> None:
    tampered = tmp_path / "tampered_generator"
    shutil.copytree(package.output_root, tampered)
    manifest_path = tampered / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["generator"]["seed"] = RANDOM_SEED + 1
    manifest_path.write_text(
        json.dumps(manifest, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="generator seed"):
        verify_synthetic_feeder_package(
            manifest_path=manifest_path,
            expected_manifest_sha256=_sha256_path(manifest_path),
        )


@pytest.mark.parametrize("invalid_seed", [float(RANDOM_SEED), True])
def test_verifier_requires_literal_integer_generator_seed(
    tmp_path: Path,
    package: SyntheticFeederPackage,
    invalid_seed: object,
) -> None:
    tampered = tmp_path / f"invalid_seed_{type(invalid_seed).__name__}"
    shutil.copytree(package.output_root, tampered)
    manifest = json.loads((tampered / "manifest.json").read_text(encoding="utf-8"))
    manifest["generator"]["seed"] = invalid_seed
    resealed_sha256 = _reseal_manifest_only(tampered, manifest)

    with pytest.raises(ValueError, match="manifest.generator.seed must be an integer"):
        verify_synthetic_feeder_package(
            manifest_path=tampered / "manifest.json",
            expected_manifest_sha256=resealed_sha256,
        )


@pytest.mark.parametrize("mutation", ["float", "boolean", "negative", "wrong"])
def test_verifier_requires_exact_nonnegative_integer_artifact_byte_length(
    tmp_path: Path,
    package: SyntheticFeederPackage,
    mutation: str,
) -> None:
    tampered = tmp_path / f"invalid_byte_length_{mutation}"
    shutil.copytree(package.output_root, tampered)
    manifest = json.loads((tampered / "manifest.json").read_text(encoding="utf-8"))
    record = manifest["artifacts"][0]
    exact_length = record["byte_length"]
    assert isinstance(exact_length, int)
    record["byte_length"] = {
        "float": float(exact_length),
        "boolean": True,
        "negative": -1,
        "wrong": exact_length + 1,
    }[mutation]
    resealed_sha256 = _reseal_manifest_only(tampered, manifest)

    with pytest.raises(ValueError, match="integer|byte length mismatch"):
        verify_synthetic_feeder_package(
            manifest_path=tampered / "manifest.json",
            expected_manifest_sha256=resealed_sha256,
        )


def test_verifier_requires_an_external_manifest_hash(
    package: SyntheticFeederPackage,
) -> None:
    with pytest.raises(ValueError, match="Manifest SHA-256 mismatch"):
        verify_synthetic_feeder_package(
            manifest_path=package.manifest_path,
            expected_manifest_sha256="0" * 64,
        )


def test_verifier_refuses_resealed_generator_identifier_laundering(
    tmp_path: Path, package: SyntheticFeederPackage
) -> None:
    tampered = tmp_path / "renamed_generator"
    shutil.copytree(package.output_root, tampered)
    plant_path = tampered / "feeder" / "Plant.dss"
    plant_path.write_text(
        plant_path.read_text(encoding="utf-8").replace(
            "New Generator.synthetic923_poc_generator ",
            "New Generator.utility_poc_generator ",
        )
        + "! New Generator.synthetic923_poc_generator retained only in a comment\n",
        encoding="utf-8",
    )
    manifest = json.loads((tampered / "manifest.json").read_text(encoding="utf-8"))
    resealed_sha256 = _reseal_package(tampered, manifest)

    with pytest.raises(ValueError, match="frozen generator-v1 bytes"):
        verify_synthetic_feeder_package(
            manifest_path=tampered / "manifest.json",
            expected_manifest_sha256=resealed_sha256,
        )


def test_verifier_refuses_resealed_unknown_claims(
    tmp_path: Path, package: SyntheticFeederPackage
) -> None:
    tampered = tmp_path / "unknown_claims"
    shutil.copytree(package.output_root, tampered)
    manifest = json.loads((tampered / "manifest.json").read_text(encoding="utf-8"))
    manifest["claims"] = {
        "bankable": True,
        "engineering_validated": True,
        "utility_accepted": True,
    }
    resealed_sha256 = _reseal_package(tampered, manifest)

    with pytest.raises(ValueError, match="manifest contains unexpected keys"):
        verify_synthetic_feeder_package(
            manifest_path=tampered / "manifest.json",
            expected_manifest_sha256=resealed_sha256,
        )


def test_verifier_refuses_resealed_missing_top_level_field(
    tmp_path: Path, package: SyntheticFeederPackage
) -> None:
    tampered = tmp_path / "missing_electrical_parameters"
    shutil.copytree(package.output_root, tampered)
    manifest = json.loads((tampered / "manifest.json").read_text(encoding="utf-8"))
    del manifest["electrical_parameters"]
    resealed_sha256 = _reseal_package(tampered, manifest)

    with pytest.raises(ValueError, match="manifest is missing required keys"):
        verify_synthetic_feeder_package(
            manifest_path=tampered / "manifest.json",
            expected_manifest_sha256=resealed_sha256,
        )


def test_verifier_refuses_resealed_missing_generator_field(
    tmp_path: Path, package: SyntheticFeederPackage
) -> None:
    tampered = tmp_path / "missing_engine_version"
    shutil.copytree(package.output_root, tampered)
    manifest = json.loads((tampered / "manifest.json").read_text(encoding="utf-8"))
    del manifest["generator"]["engine_version"]
    resealed_sha256 = _reseal_package(tampered, manifest)

    with pytest.raises(ValueError, match="manifest.generator is missing required keys"):
        verify_synthetic_feeder_package(
            manifest_path=tampered / "manifest.json",
            expected_manifest_sha256=resealed_sha256,
        )


def test_verifier_refuses_resealed_nested_profile_claims(
    tmp_path: Path, package: SyntheticFeederPackage
) -> None:
    tampered = tmp_path / "nested_profile_claims"
    shutil.copytree(package.output_root, tampered)
    manifest = json.loads((tampered / "manifest.json").read_text(encoding="utf-8"))
    manifest["profile"]["claims"] = {"observed_era5": True, "bankable": True}
    resealed_sha256 = _reseal_package(tampered, manifest)

    with pytest.raises(ValueError, match="manifest.profile contains unexpected keys"):
        verify_synthetic_feeder_package(
            manifest_path=tampered / "manifest.json",
            expected_manifest_sha256=resealed_sha256,
        )


def test_verifier_refuses_resealed_timestamp_year_laundering(
    tmp_path: Path, package: SyntheticFeederPackage
) -> None:
    tampered = tmp_path / "shifted_timestamps"
    shutil.copytree(package.output_root, tampered)
    profile_path = tampered / "profile" / "generation_profile.csv"
    profile_path.write_text(
        profile_path.read_text(encoding="utf-8").replace("2021-", "2022-"),
        encoding="utf-8",
    )
    manifest = json.loads((tampered / "manifest.json").read_text(encoding="utf-8"))
    manifest["profile"]["start_utc"] = "2022-01-01T00:00:00Z"
    manifest["profile"]["end_utc"] = "2022-12-31T23:00:00Z"
    resealed_sha256 = _reseal_package(tampered, manifest)

    with pytest.raises(ValueError, match="frozen generator-v1 bytes"):
        verify_synthetic_feeder_package(
            manifest_path=tampered / "manifest.json",
            expected_manifest_sha256=resealed_sha256,
        )


def test_verifier_refuses_resealed_frozen_spec_hash_laundering(
    tmp_path: Path, package: SyntheticFeederPackage
) -> None:
    tampered = tmp_path / "forged_spec_hash"
    shutil.copytree(package.output_root, tampered)
    manifest = json.loads((tampered / "manifest.json").read_text(encoding="utf-8"))
    manifest["source_snapshots"]["frozen_issue_923_spec"]["sha256"] = "0" * 64
    resealed_sha256 = _reseal_package(tampered, manifest)

    with pytest.raises(ValueError, match="frozen #923 specification hash"):
        verify_synthetic_feeder_package(
            manifest_path=tampered / "manifest.json",
            expected_manifest_sha256=resealed_sha256,
        )


def test_verifier_refuses_symlinked_package_ancestor(
    tmp_path: Path, package: SyntheticFeederPackage
) -> None:
    real_package = tmp_path / "real_synthetic_package"
    shutil.copytree(package.output_root, real_package)
    misleading_alias = tmp_path / "AUTHENTICATED_CEB_FEEDER"
    misleading_alias.symlink_to(real_package, target_is_directory=True)

    with pytest.raises(ValueError, match="symlinked ancestor"):
        verify_synthetic_feeder_package(
            manifest_path=misleading_alias / "manifest.json",
            master_path=misleading_alias / "feeder" / "Master.dss",
            expected_manifest_sha256=package.manifest_sha256,
        )


def test_verifier_refuses_manifest_symlink(
    tmp_path: Path, package: SyntheticFeederPackage
) -> None:
    manifest_link = tmp_path / "manifest.json"
    manifest_link.symlink_to(package.manifest_path)
    with pytest.raises(ValueError, match="manifest must not be a symlink"):
        verify_synthetic_feeder_package(
            manifest_path=manifest_link,
            expected_manifest_sha256=package.manifest_sha256,
        )


@pytest.mark.parametrize(
    ("target", "mutation"),
    MASTER_REDIRECT_MUTATIONS,
    ids=[f"{target}-{mutation}" for target, mutation in MASTER_REDIRECT_MUTATIONS],
)
def test_verifier_refuses_every_master_redirect_mutation(
    tmp_path: Path,
    package: SyntheticFeederPackage,
    target: str,
    mutation: str,
) -> None:
    tampered = tmp_path / f"master_{target}_{mutation}"
    shutil.copytree(package.output_root, tampered)
    master_path = tampered / "feeder" / "Master.dss"
    redirect = f'Redirect "{target}"'
    original = master_path.read_text(encoding="utf-8")
    if mutation == "delete":
        changed = original.replace(f"{redirect}\n", "", 1)
    elif mutation == "duplicate":
        changed = original.replace(redirect, f"{redirect}\n{redirect}", 1)
    elif mutation == "substitute":
        changed = original.replace(target, "Forged.dss", 1)
    else:
        changed = original.replace(target, f"../{target}", 1)
    assert changed != original
    master_path.write_text(changed, encoding="utf-8")
    manifest = json.loads((tampered / "manifest.json").read_text(encoding="utf-8"))
    resealed_sha256 = _reseal_package(tampered, manifest)

    with pytest.raises(ValueError, match="frozen generator-v1 bytes"):
        verify_synthetic_feeder_package(
            manifest_path=tampered / "manifest.json",
            expected_manifest_sha256=resealed_sha256,
        )


@pytest.mark.parametrize(
    ("relative", "addition"),
    DSS_EXECUTABLE_MUTATIONS,
    ids=[
        "extra-load",
        "lowercase-extra-load",
        "edit-command",
        "clone-command",
        "batchedit-command",
    ],
)
def test_verifier_refuses_extra_or_mutating_dss_commands(
    tmp_path: Path,
    package: SyntheticFeederPackage,
    relative: str,
    addition: str,
) -> None:
    tampered = tmp_path / f"dss_command_{relative.replace('/', '_')}"
    shutil.copytree(package.output_root, tampered)
    payload_path = tampered / relative
    payload_path.write_text(
        payload_path.read_text(encoding="utf-8") + addition,
        encoding="utf-8",
    )
    manifest = json.loads((tampered / "manifest.json").read_text(encoding="utf-8"))
    resealed_sha256 = _reseal_package(tampered, manifest)

    with pytest.raises(ValueError, match="frozen generator-v1 bytes"):
        verify_synthetic_feeder_package(
            manifest_path=tampered / "manifest.json",
            expected_manifest_sha256=resealed_sha256,
        )


@pytest.mark.parametrize(
    ("relative", "old", "new"),
    [
        (
            "feeder/Plant.dss",
            "bus1=synthetic923_poc_33kv",
            "bus1=CEB_actual_poc_33kv",
        ),
        (
            "feeder/Connection.dss",
            "bus1=synthetic923_collector_33kv",
            "bus1=CEB_actual_collector_33kv",
        ),
        (
            "feeder/Connection.dss",
            "bus2=synthetic923_poc_33kv",
            "bus2=CEB_actual_poc_33kv",
        ),
        (
            "feeder/Transformer.dss",
            "bus=synthetic923_collector_33kv.1.2.3.0",
            "bus=CEB_actual_collector_33kv.1.2.3.0",
        ),
    ],
    ids=["generator-bus", "line-bus1", "line-bus2", "transformer-bus"],
)
def test_verifier_refuses_every_unprefixed_bus_position(
    tmp_path: Path,
    package: SyntheticFeederPackage,
    relative: str,
    old: str,
    new: str,
) -> None:
    tampered = tmp_path / f"unprefixed_{relative.replace('/', '_')}"
    shutil.copytree(package.output_root, tampered)
    payload_path = tampered / relative
    original = payload_path.read_text(encoding="utf-8")
    changed = original.replace(old, new, 1)
    assert changed != original
    payload_path.write_text(changed, encoding="utf-8")
    manifest = json.loads((tampered / "manifest.json").read_text(encoding="utf-8"))
    resealed_sha256 = _reseal_package(tampered, manifest)

    with pytest.raises(ValueError, match="frozen generator-v1 bytes"):
        verify_synthetic_feeder_package(
            manifest_path=tampered / "manifest.json",
            expected_manifest_sha256=resealed_sha256,
        )


@pytest.mark.parametrize(
    ("field_path", "invalid_value"),
    FIXED_MANIFEST_FIELD_MUTATIONS,
    ids=[".".join(path) for path, _ in FIXED_MANIFEST_FIELD_MUTATIONS],
)
def test_verifier_refuses_every_frozen_profile_and_electrical_field_mutation(
    tmp_path: Path,
    package: SyntheticFeederPackage,
    field_path: tuple[str, ...],
    invalid_value: object,
) -> None:
    tampered = tmp_path / ("manifest_" + "_".join(field_path))
    shutil.copytree(package.output_root, tampered)
    manifest = json.loads((tampered / "manifest.json").read_text(encoding="utf-8"))
    _set_nested(manifest, field_path, invalid_value)
    resealed_sha256 = _reseal_package(tampered, manifest)

    with pytest.raises(ValueError):
        verify_synthetic_feeder_package(
            manifest_path=tampered / "manifest.json",
            expected_manifest_sha256=resealed_sha256,
        )


@pytest.mark.parametrize(
    ("logical_id", "field"),
    [
        (logical_id, field)
        for logical_id, _, _ in synthetic_feeder_module.PINNED_REPOSITORY_SOURCE_TRIPLES
        for field in ("path", "sha256")
    ],
)
def test_verifier_refuses_each_resealed_repository_source_identity_change(
    tmp_path: Path,
    package: SyntheticFeederPackage,
    logical_id: str,
    field: str,
) -> None:
    tampered = tmp_path / f"source_{logical_id}_{field}"
    shutil.copytree(package.output_root, tampered)
    manifest = json.loads((tampered / "manifest.json").read_text(encoding="utf-8"))
    source_snapshot = manifest["source_snapshots"][logical_id]
    source_snapshot[field] = (
        "0" * 64 if field == "sha256" else f"forged/{logical_id}.yaml"
    )
    resealed_sha256 = _reseal_package(tampered, manifest)

    with pytest.raises(ValueError, match="immutable generator-v1 source control"):
        verify_synthetic_feeder_package(
            manifest_path=tampered / "manifest.json",
            expected_manifest_sha256=resealed_sha256,
        )


def test_verifier_refuses_coordinated_scenario_source_resealing(
    tmp_path: Path, package: SyntheticFeederPackage
) -> None:
    tampered = tmp_path / "coordinated_scenario_reseal"
    shutil.copytree(package.output_root, tampered)
    manifest = json.loads((tampered / "manifest.json").read_text(encoding="utf-8"))
    forged_hash = "0" * 64
    manifest["source_snapshots"]["scenario"]["sha256"] = forged_hash
    manifest["control_cross_checks"]["scenario_source_sha256"] = forged_hash
    resealed_sha256 = _reseal_package(tampered, manifest)

    with pytest.raises(ValueError, match="immutable generator-v1 source control"):
        verify_synthetic_feeder_package(
            manifest_path=tampered / "manifest.json",
            expected_manifest_sha256=resealed_sha256,
        )


@pytest.mark.parametrize("mutation", ["wind-extrema", "energy-parity"])
def test_verifier_refuses_coordinated_derived_profile_claim_resealing(
    tmp_path: Path,
    package: SyntheticFeederPackage,
    mutation: str,
) -> None:
    tampered = tmp_path / f"derived_profile_{mutation}"
    shutil.copytree(package.output_root, tampered)
    manifest = json.loads((tampered / "manifest.json").read_text(encoding="utf-8"))
    profile = manifest["profile"]
    if mutation == "wind-extrema":
        profile["synthetic_wind_minimum_ms"] = 0.1
        profile["synthetic_wind_maximum_ms"] = 30.0
    else:
        changed_aep = profile["energy_calculator_gross_aep_mwh"] + 0.005
        profile["energy_calculator_gross_aep_mwh"] = changed_aep
        profile["energy_calculator_parity_delta_mwh"] = (
            profile["gross_aep_mwh_from_rounded_csv"] - changed_aep
        )
    resealed_sha256 = _reseal_manifest_only(tampered, manifest)

    with pytest.raises(ValueError, match="frozen generator-v1 value"):
        verify_synthetic_feeder_package(
            manifest_path=tampered / "manifest.json",
            expected_manifest_sha256=resealed_sha256,
        )


def test_verifier_reruns_claimed_opendss_compile_before_acceptance(
    tmp_path: Path,
    package: SyntheticFeederPackage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tampered = tmp_path / "claimed_compile"
    shutil.copytree(package.output_root, tampered)
    manifest = json.loads((tampered / "manifest.json").read_text(encoding="utf-8"))
    manifest["validation"][
        "opendss_compile_status"
    ] = "passed_compile_only_no_convergence_claim"
    resealed_sha256 = _reseal_package(tampered, manifest)

    def _fail_compile(_: Path) -> str:
        raise RuntimeError("sentinel detached compile failure")

    monkeypatch.setattr(synthetic_feeder_module, "_compile_opendss", _fail_compile)
    with pytest.raises(RuntimeError, match="sentinel detached compile failure"):
        verify_synthetic_feeder_package(
            manifest_path=tampered / "manifest.json",
            expected_manifest_sha256=resealed_sha256,
        )


def test_cli_receipt_is_concise_and_keeps_wall_clock_out_of_manifest(
    package: SyntheticFeederPackage,
) -> None:
    receipt = cli_summary(package, replace(_config(), validate_opendss_compile=False))
    assert receipt["status"] == "PASS"
    assert receipt["generated_at_utc"]
    assert receipt["finding_closure_weight"] == 0
    assert receipt["issue_923_closable"] is False
    assert receipt["profile"]["chronology_kind"] == "synthetic_not_observed_2021"
    manifest = json.loads(package.manifest_path.read_text(encoding="utf-8"))
    assert manifest["generator"]["wall_clock_generation_time_in_manifest"] is False
    assert "generated_at_utc" not in manifest
    rendered = json.dumps(receipt)
    assert str(package.output_root) not in rendered
    assert "/Users/" not in rendered


@pytest.mark.grid
def test_production_configuration_compiles_opendss_and_has_exact_manifest_hash(
    tmp_path: Path,
) -> None:
    pytest.importorskip("opendssdirect")
    generated = generate_synthetic_feeder_placeholder(
        _config(),
        repo_root=REPO_ROOT,
        output_dir_override=tmp_path / "compiled_issue_923",
    )
    assert (
        generated.opendss_compile_status == "passed_compile_only_no_convergence_claim"
    )
    assert generated.convergence_status == CONVERGENCE_STATUS
    assert generated.manifest_sha256 == EXPECTED_PRODUCTION_MANIFEST_SHA256


@pytest.mark.parametrize(
    ("field_path", "invalid_value", "message"),
    [
        (("classification", "bankable"), True, "classification.bankable"),
        (("classification", "generated_input"), 1, "literal boolean"),
        (("generator", "random_seed"), True, "must be an integer"),
        (("artifact", "output_dir"), "/tmp/issue923", "repository-relative"),
        (("artifact", "validate_opendss_compile"), "true", "literal boolean"),
    ],
)
def test_config_refuses_adversarial_values(
    field_path: tuple[str, str], invalid_value: object, message: str
) -> None:
    raw = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    raw[field_path[0]][field_path[1]] = invalid_value
    with pytest.raises(ValueError, match=message):
        SyntheticFeederPlaceholderConfig.from_mapping(raw)


@pytest.mark.parametrize(
    ("field_path", "alternate_value"),
    PINNED_CONFIG_FIELD_MUTATIONS,
    ids=[".".join(path) for path, _ in PINNED_CONFIG_FIELD_MUTATIONS],
)
def test_config_preflight_refuses_every_alternate_generator_v1_control(
    field_path: tuple[str, str], alternate_value: object
) -> None:
    raw = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    raw[field_path[0]][field_path[1]] = alternate_value

    with pytest.raises(ValueError, match="must remain|must be"):
        SyntheticFeederPlaceholderConfig.from_mapping(raw)


@pytest.mark.parametrize(
    "invalid_output_dir",
    [
        "outputs/synthetic_placeholders/issue_923/descendant",
        "outputs/synthetic_placeholders",
        "../outputs/synthetic_placeholders/issue_923",
        "/tmp/outputs/synthetic_placeholders/issue_923",
    ],
    ids=["descendant", "ancestor", "traversal", "absolute"],
)
def test_config_requires_the_exact_governed_output_path(
    invalid_output_dir: str,
) -> None:
    raw = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    raw["artifact"]["output_dir"] = invalid_output_dir

    with pytest.raises(ValueError, match="artifact.output_dir"):
        SyntheticFeederPlaceholderConfig.from_mapping(raw)


def test_production_generation_refuses_compile_disabled_before_source_loading(
    tmp_path: Path,
) -> None:
    nonexistent_repo = tmp_path / "nonexistent_repo"
    with pytest.raises(ValueError, match="requires OpenDSS compile validation"):
        generate_synthetic_feeder_placeholder(
            replace(_config(), validate_opendss_compile=False),
            repo_root=nonexistent_repo,
        )
    assert not nonexistent_repo.exists()


@pytest.mark.parametrize(
    "relation",
    [
        "equal",
        "descendant",
        "ancestor",
        "case-exact",
        "case-descendant",
        "case-ancestor",
        "mixed-case",
    ],
)
def test_library_output_override_cannot_overlap_the_governed_target(
    tmp_path: Path,
    relation: str,
) -> None:
    synthetic_repo = tmp_path / "synthetic_repo"
    synthetic_repo.mkdir()
    governed_target = synthetic_repo / synthetic_feeder_module.GOVERNED_OUTPUT_DIR
    target = {
        "equal": governed_target,
        "descendant": governed_target / "nested",
        "ancestor": synthetic_repo / "outputs",
        "case-exact": governed_target.with_name("ISSUE_923"),
        "case-descendant": governed_target.with_name("ISSUE_923") / "child",
        "case-ancestor": synthetic_repo / "OUTPUTS" / "synthetic_placeholders",
        "mixed-case": synthetic_repo
        / "OuTpUtS"
        / "SYNTHETIC_PLACEHOLDERS"
        / "Issue_923",
    }[relation]

    with pytest.raises(ValueError, match="must be outside"):
        generate_synthetic_feeder_placeholder(
            replace(_config(), validate_opendss_compile=False),
            repo_root=synthetic_repo,
            output_dir_override=target,
        )
    assert list(synthetic_repo.iterdir()) == []


def test_library_output_override_allows_a_nonoverlapping_casefolded_sibling(
    tmp_path: Path,
) -> None:
    synthetic_repo = tmp_path / "synthetic_repo"
    synthetic_repo.mkdir()
    for _, relative, _ in synthetic_feeder_module.PINNED_REPOSITORY_SOURCE_TRIPLES:
        source = REPO_ROOT / relative
        destination = synthetic_repo / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    sibling = (
        synthetic_repo / "outputs" / "synthetic_placeholders" / "issue_923_test_fixture"
    )

    generated = generate_synthetic_feeder_placeholder(
        replace(_config(), validate_opendss_compile=False),
        repo_root=synthetic_repo,
        output_dir_override=sibling,
    )

    assert generated.output_root == sibling.resolve()
    assert generated.opendss_compile_status == (
        "not_examined_explicit_test_configuration"
    )
    assert {
        path.relative_to(sibling).as_posix()
        for path in sibling.rglob("*")
        if path.is_file()
    } == set(PACKAGE_RELATIVE_PATHS)


def test_generation_refuses_a_symlinked_output_ancestor_before_source_loading(
    tmp_path: Path,
) -> None:
    synthetic_repo = tmp_path / "synthetic_repo"
    synthetic_repo.mkdir()
    real_outputs = tmp_path / "real_outputs"
    real_outputs.mkdir()
    (synthetic_repo / "outputs").symlink_to(real_outputs, target_is_directory=True)

    with pytest.raises(ValueError, match="symlinked ancestor"):
        generate_synthetic_feeder_placeholder(_config(), repo_root=synthetic_repo)
    assert list(real_outputs.iterdir()) == []


@pytest.mark.parametrize(
    "override",
    [
        "artifact.validate_opendss_compile=false",
        "artifact.output_dir=outputs/synthetic_placeholders/issue_923/descendant",
    ],
    ids=["compile-disabled", "descendant-output"],
)
def test_actual_hydra_cli_refuses_unsafe_production_overrides(
    tmp_path: Path,
    override: str,
) -> None:
    mirror = tmp_path / "cli_mirror"
    (mirror / "conf").mkdir(parents=True)
    (mirror / "scripts").mkdir()
    shutil.copy2(
        REPO_ROOT / "scripts" / "run_synthetic_feeder_placeholder_v14.py",
        mirror / "scripts" / "run_synthetic_feeder_placeholder_v14.py",
    )
    shutil.copy2(CONFIG_PATH, mirror / "conf" / CONFIG_PATH.name)
    environment = os.environ.copy()
    existing_pythonpath = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = (
        str(REPO_ROOT)
        if not existing_pythonpath
        else f"{REPO_ROOT}{os.pathsep}{existing_pythonpath}"
    )
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["HYDRA_FULL_ERROR"] = "1"

    completed = subprocess.run(
        [
            sys.executable,
            str(mirror / "scripts" / "run_synthetic_feeder_placeholder_v14.py"),
            override,
        ],
        cwd=mirror,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
    assert completed.stdout == ""
    assert "ValueError" in completed.stderr
    assert not (mirror / "outputs").exists()
    assert not (mirror / ".hydra").exists()
    assert list(mirror.rglob("*.log")) == []


@pytest.mark.parametrize(
    ("section", "unexpected_key"),
    [
        (None, "finance_wiring"),
        ("classification", "authenticated_feeder"),
        ("source", "untracked_source"),
        ("profile", "silent_default"),
    ],
)
def test_config_refuses_undeclared_keys(
    section: str | None, unexpected_key: str
) -> None:
    raw = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    if section is None:
        raw[unexpected_key] = {"enabled": True}
        message = "config contains unexpected keys"
    else:
        raw[section][unexpected_key] = True
        message = rf"{section} contains unexpected keys"
    with pytest.raises(ValueError, match=message):
        SyntheticFeederPlaceholderConfig.from_mapping(raw)
