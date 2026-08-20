"""Dolphin #923-B3: verified package-to-QSTS runtime adaptation.

The adapter removes manual CSV/config glue while preserving the Issue #923 evidence
firewall. It cannot manufacture convergence, operator instructions, bankability, canonical
eligibility, or finance enablement.
"""

from __future__ import annotations

import shutil
from dataclasses import replace
from pathlib import Path

import pytest
import yaml

import analytics.grid.curtailment_qsts as qsts_module
from analytics.contracts_v14 import (
    QSTS_SYNTHETIC_OUTPUT_CLASS,
    SYNTHETIC_PROCESS_PROVENANCE_WARNING,
    QSTSSolveTelemetry,
)
from analytics.grid.curtailment_qsts import run_qsts_curtailment
from analytics.grid.grid_interface_schema import validate_grid_block
from analytics.grid.synthetic_feeder_placeholder import (
    SyntheticFeederPackage,
    SyntheticFeederPlaceholderConfig,
    generate_synthetic_feeder_placeholder,
)
from analytics.grid.synthetic_feeder_qsts_adapter import (
    build_verified_synthetic_qsts_overlay,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / "conf" / "synthetic_feeder_placeholder.yaml"


def _generator_config() -> SyntheticFeederPlaceholderConfig:
    raw = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    assert isinstance(raw, dict)
    return SyntheticFeederPlaceholderConfig.from_mapping(raw)


@pytest.fixture(scope="module")
def compiled_package(
    tmp_path_factory: pytest.TempPathFactory,
) -> SyntheticFeederPackage:
    pytest.importorskip("opendssdirect")
    return generate_synthetic_feeder_placeholder(
        _generator_config(),
        repo_root=REPO_ROOT,
        output_dir_override=(
            tmp_path_factory.mktemp("issue923-b3-compiled") / "issue_923"
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
            tmp_path_factory.mktemp("issue923-b3-no-compile") / "issue_923"
        ),
    )


@pytest.mark.grid
def test_adapter_builds_exact_safe_qsts_overlay(
    compiled_package: SyntheticFeederPackage,
) -> None:
    overlay = build_verified_synthetic_qsts_overlay(
        manifest_path=compiled_package.manifest_path,
        expected_manifest_sha256=compiled_package.manifest_sha256,
    )

    assert set(overlay) == {
        "enabled",
        "input_kind",
        "feeder_model_path",
        "source_manifest_sha256",
        "export_cap_mw",
        "generation_profile_mw",
        "finance_wiring",
    }
    assert overlay["enabled"] is True
    assert overlay["input_kind"] == "synthetic_placeholder"
    assert overlay["feeder_model_path"] == str(compiled_package.master_path)
    assert overlay["source_manifest_sha256"] == compiled_package.manifest_sha256
    assert overlay["export_cap_mw"] == pytest.approx(150.0)
    assert len(overlay["generation_profile_mw"]) == 8760
    assert tuple(overlay["generation_profile_mw"]) == (
        compiled_package.generation_profile_mw
    )
    assert overlay["finance_wiring"] == {
        "enabled": False,
        "mode": "synthetic_counterfactual",
        "canonical_eligible": False,
    }

    forbidden = {
        "grid_instructed_profile_mw",
        "convergence_status",
        "timestep_convergence_checked",
        "telemetry_checked",
        "bankable",
        "site_representative",
        "issue_923_closable",
    }
    assert forbidden.isdisjoint(overlay)


@pytest.mark.grid
def test_adapter_output_passes_schema_and_runtime_verification(
    compiled_package: SyntheticFeederPackage,
) -> None:
    overlay = build_verified_synthetic_qsts_overlay(
        manifest_path=compiled_package.manifest_path,
        expected_manifest_sha256=compiled_package.manifest_sha256,
    )
    config = {"grid": {"qsts": overlay}}
    errors: list[str] = []

    validate_grid_block(config, errors)
    assert errors == []

    result = run_qsts_curtailment(
        config,
        generation_mwh=overlay["generation_profile_mw"],
        grid_instructed_mwh=[0.0] * len(overlay["generation_profile_mw"]),
    )
    assert result.ran is True
    assert result.hours_total == 8760
    assert result.gross_energy_mwh == pytest.approx(
        sum(compiled_package.generation_profile_mw)
    )
    assert result.source_manifest_sha256 == compiled_package.manifest_sha256
    assert result.generated_input is True
    assert result.site_representative is False
    assert result.canonical_finance_eligible is False
    assert result.bankable is False
    receipt = result.qsts_run_manifest
    assert receipt is not None
    assert receipt.output_class == QSTS_SYNTHETIC_OUTPUT_CLASS
    assert receipt.required_warning == SYNTHETIC_PROCESS_PROVENANCE_WARNING
    assert receipt.finance_wiring_mode == "synthetic_counterfactual"
    assert receipt.finance_wiring_enabled is False
    assert receipt.canonical_finance_eligible is False
    assert receipt.lender_eligible is False
    assert receipt.board_approval_eligible is False
    assert receipt.release_eligible is False
    serialized = result.model_dump()
    assert serialized["qsts_run_manifest"]["required_warning"] == (
        SYNTHETIC_PROCESS_PROVENANCE_WARNING
    )


@pytest.mark.grid
def test_adapter_returns_profile_copy_not_mutable_verified_state(
    compiled_package: SyntheticFeederPackage,
) -> None:
    overlay = build_verified_synthetic_qsts_overlay(
        manifest_path=compiled_package.manifest_path,
        expected_manifest_sha256=compiled_package.manifest_sha256,
    )
    verified_first = compiled_package.generation_profile_mw[0]

    overlay["generation_profile_mw"][0] = verified_first + 1.0

    assert compiled_package.generation_profile_mw[0] == verified_first


@pytest.mark.grid
@pytest.mark.parametrize("substitution", ["profile", "export-cap"])
def test_runtime_refuses_substituted_adapter_values(
    compiled_package: SyntheticFeederPackage,
    substitution: str,
) -> None:
    overlay = build_verified_synthetic_qsts_overlay(
        manifest_path=compiled_package.manifest_path,
        expected_manifest_sha256=compiled_package.manifest_sha256,
    )
    if substitution == "profile":
        overlay["generation_profile_mw"] = [151.0, 149.0]
        message = "generation_profile_mw.*8760 timesteps"
    else:
        overlay["export_cap_mw"] = 149.0
        message = "must match the manifest-verified QSTS package export cap"

    with pytest.raises(ValueError, match=message):
        run_qsts_curtailment({"grid": {"qsts": overlay}})


@pytest.mark.grid
@pytest.mark.parametrize("substitution", ["profile", "export-cap"])
def test_runtime_refuses_substituted_explicit_overrides(
    compiled_package: SyntheticFeederPackage,
    substitution: str,
) -> None:
    overlay = build_verified_synthetic_qsts_overlay(
        manifest_path=compiled_package.manifest_path,
        expected_manifest_sha256=compiled_package.manifest_sha256,
    )
    kwargs: dict[str, object] = {
        "generation_mwh": overlay["generation_profile_mw"],
        "grid_instructed_mwh": [0.0] * len(overlay["generation_profile_mw"]),
    }
    if substitution == "profile":
        kwargs["generation_mwh"] = [151.0, 149.0]
        message = "generation_mwh override.*8760 timesteps"
    else:
        kwargs["export_cap_mw"] = 149.0
        message = "must match the manifest-verified QSTS package export cap"

    with pytest.raises(ValueError, match=message):
        run_qsts_curtailment({"grid": {"qsts": overlay}}, **kwargs)


@pytest.mark.grid
def test_runtime_solver_receives_verifier_derived_profile(
    compiled_package: SyntheticFeederPackage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    overlay = build_verified_synthetic_qsts_overlay(
        manifest_path=compiled_package.manifest_path,
        expected_manifest_sha256=compiled_package.manifest_sha256,
    )
    captured_profile: tuple[float, ...] | None = None

    def _capture_solver_profile(
        grid: object,
        *,
        feeder_path: str,
        timestep_hours: float,
        generation_profile_mw: object = None,
        grid_instructed_profile_mw: object = None,
    ) -> tuple[list[float], list[float], QSTSSolveTelemetry]:
        del grid, feeder_path, timestep_hours, grid_instructed_profile_mw
        nonlocal captured_profile
        assert isinstance(generation_profile_mw, tuple)
        captured_profile = generation_profile_mw
        return (
            [0.0],
            [0.0],
            QSTSSolveTelemetry(
                attempted_steps=1,
                converged_steps=1,
                nonconverged_steps=0,
                first_nonconverged_step=None,
                last_nonconverged_step=None,
                monitoring_configured=False,
            ),
        )

    monkeypatch.setattr(qsts_module, "_solve_qsts", _capture_solver_profile)

    result = run_qsts_curtailment({"grid": {"qsts": overlay}})

    assert result.ran is True
    assert captured_profile == compiled_package.generation_profile_mw


def test_adapter_refuses_wrong_external_manifest_digest(
    compile_disabled_package: SyntheticFeederPackage,
) -> None:
    with pytest.raises(ValueError, match="Manifest SHA-256 mismatch"):
        build_verified_synthetic_qsts_overlay(
            manifest_path=compile_disabled_package.manifest_path,
            expected_manifest_sha256="0" * 64,
        )


@pytest.mark.parametrize(
    "relative_path",
    [
        "profile/generation_profile.csv",
        "feeder/Master.dss",
        "manifest.json",
        "MANIFEST.sha256",
    ],
)
def test_adapter_refuses_tampered_governed_package_file(
    compiled_package: SyntheticFeederPackage,
    tmp_path: Path,
    relative_path: str,
) -> None:
    copied_package = tmp_path / "issue_923"
    shutil.copytree(compiled_package.manifest_path.parent, copied_package)
    tampered_path = copied_package / relative_path
    tampered_path.write_bytes(tampered_path.read_bytes() + b"\n")

    with pytest.raises(ValueError):
        build_verified_synthetic_qsts_overlay(
            manifest_path=copied_package / "manifest.json",
            expected_manifest_sha256=compiled_package.manifest_sha256,
        )


def test_adapter_refuses_compile_disabled_test_package(
    compile_disabled_package: SyntheticFeederPackage,
) -> None:
    with pytest.raises(ValueError, match="compile-disabled packages are not runtime"):
        build_verified_synthetic_qsts_overlay(
            manifest_path=compile_disabled_package.manifest_path,
            expected_manifest_sha256=compile_disabled_package.manifest_sha256,
        )
