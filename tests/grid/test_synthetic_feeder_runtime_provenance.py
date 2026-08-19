"""Dolphin #923-B2 runtime manifest verification and provenance propagation.

These tests prove that the path-backed B1 synthetic package reaches QSTS accounting only
after detached verification against an externally pinned manifest digest. Execution never
upgrades the package to observed, site-representative, bankable, canonical, or finance
evidence; convergence remains the separate #923-C gate.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from analytics.grid.curtailment_qsts import run_qsts_curtailment
from analytics.grid.synthetic_feeder_placeholder import (
    SyntheticFeederPackage,
    SyntheticFeederPlaceholderConfig,
    generate_synthetic_feeder_placeholder,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / "conf" / "synthetic_feeder_placeholder.yaml"


def _generator_config() -> SyntheticFeederPlaceholderConfig:
    raw = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    assert isinstance(raw, dict)
    return SyntheticFeederPlaceholderConfig.from_mapping(raw)


def _runtime_config(
    package: SyntheticFeederPackage,
    *,
    manifest_sha256: object | None = None,
    feeder_model_path: Path | None = None,
) -> dict[str, object]:
    qsts: dict[str, object] = {
        "enabled": True,
        "input_kind": "synthetic_placeholder",
        "feeder_model_path": str(feeder_model_path or package.master_path),
        "source_manifest_sha256": (
            package.manifest_sha256 if manifest_sha256 is None else manifest_sha256
        ),
        "export_cap_mw": package.export_cap_mw,
        "generation_profile_mw": list(package.generation_profile_mw),
        "finance_wiring": {
            "enabled": False,
            "mode": "synthetic_counterfactual",
            "canonical_eligible": False,
        },
    }
    return {"grid": {"qsts": qsts}}


@pytest.fixture(scope="module")
def compiled_package(
    tmp_path_factory: pytest.TempPathFactory,
) -> SyntheticFeederPackage:
    pytest.importorskip("opendssdirect")
    return generate_synthetic_feeder_placeholder(
        _generator_config(),
        repo_root=REPO_ROOT,
        output_dir_override=(
            tmp_path_factory.mktemp("issue923-b2-compiled") / "issue_923"
        ),
    )


@pytest.fixture(scope="module")
def compile_disabled_package(
    tmp_path_factory: pytest.TempPathFactory,
) -> SyntheticFeederPackage:
    return generate_synthetic_feeder_placeholder(
        replace(_generator_config(), validate_opendss_compile=False),
        repo_root=REPO_ROOT,
        output_dir_override=(
            tmp_path_factory.mktemp("issue923-b2-no-compile") / "issue_923"
        ),
    )


@pytest.mark.grid
def test_verified_manifest_identity_is_propagated_without_evidence_upgrade(
    compiled_package: SyntheticFeederPackage,
) -> None:
    generation_mwh = list(compiled_package.generation_profile_mw)
    result = run_qsts_curtailment(
        _runtime_config(compiled_package),
        generation_mwh=generation_mwh,
        grid_instructed_mwh=[0.0] * len(generation_mwh),
    )

    assert result.ran is True
    assert result.feeder_source == str(compiled_package.master_path)
    assert result.feeder_input_kind == "synthetic_placeholder"
    assert result.source_manifest_sha256 == compiled_package.manifest_sha256
    assert result.generated_input is True
    assert result.observed_network_data is False
    assert result.site_representative is False
    assert result.canonical_finance_eligible is False
    assert result.bankable is False
    assert result.self_curtailed_energy_mwh == pytest.approx(
        sum(
            max(generation - compiled_package.export_cap_mw, 0.0)
            for generation in generation_mwh
        )
    )
    assert any("externally pinned SHA-256" in item for item in result.limitations)

    payload = result.model_dump()
    assert payload["source_manifest_sha256"] == compiled_package.manifest_sha256
    assert payload["generated_input"] is True
    assert payload["canonical_finance_eligible"] is False
    assert payload["bankable"] is False


@pytest.mark.grid
def test_wrong_external_digest_fails_before_accounting(
    compiled_package: SyntheticFeederPackage,
) -> None:
    with pytest.raises(ValueError, match="Manifest SHA-256 mismatch"):
        run_qsts_curtailment(
            _runtime_config(compiled_package, manifest_sha256="0" * 64),
            generation_mwh=[151.0],
            grid_instructed_mwh=[0.0],
        )


@pytest.mark.grid
def test_unrelated_feeder_path_cannot_borrow_package_manifest(
    compiled_package: SyntheticFeederPackage,
) -> None:
    plant_path = compiled_package.output_root / "feeder" / "Plant.dss"
    with pytest.raises(ValueError, match="does not match the package Master.dss"):
        run_qsts_curtailment(
            _runtime_config(compiled_package, feeder_model_path=plant_path),
            generation_mwh=[151.0],
            grid_instructed_mwh=[0.0],
        )


def test_compile_disabled_test_package_is_not_a_runtime_input(
    compile_disabled_package: SyntheticFeederPackage,
) -> None:
    with pytest.raises(ValueError, match="compile-disabled packages are not runtime"):
        run_qsts_curtailment(
            _runtime_config(compile_disabled_package),
            generation_mwh=[151.0],
            grid_instructed_mwh=[0.0],
        )


def test_default_off_does_not_load_or_authenticate_synthetic_package() -> None:
    result = run_qsts_curtailment(
        {
            "grid": {
                "qsts": {
                    "enabled": False,
                    "input_kind": "synthetic_placeholder",
                    "feeder_model_path": "/not/present/Master.dss",
                }
            }
        }
    )
    assert result.ran is False
    assert result.source_manifest_sha256 is None
    assert "default-off" in result.reason
