#!/usr/bin/env python3
"""tests/conftest.py

Shared pytest configuration and utilities for DutchBay v14 test suite.

Go-with-the-Flow Compliance:
- CST-01: LibCST Banned APIs enforcement (shared visitor base)
- CST-02: Safe code inspection without touching runtime
- Automated integration with pytest tests/ directory
- R3: No argparse (uses env vars for test mode config)

This module provides:
1. PATH SETUP - Ensures repository root is on sys.path (CRITICAL for imports)
2. BaseSensitivityVisitor - Shared LibCST visitor for import/call inspection
3. load_sensitivity_source() - Unified file loading from multiple locations
4. Shared fixtures and configuration for all test suites
5. TEST PERFORMANCE - CESSPIT-governed stochastic evaluation budgets
"""

from __future__ import annotations

import importlib
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, List, Mapping, Set

import libcst as cst
import pytest
import yaml

# =============================================================================
# PATH SETUP (CRITICAL - Must be first)
# =============================================================================
# Resolve repository root (one level above tests/)
REPO_ROOT = Path(__file__).resolve().parents[1]
root_str = str(REPO_ROOT)

# 1) Make sure repo root is FIRST on sys.path
if not sys.path or sys.path[0] != root_str:
    # Remove any existing occurrences and re-insert at front
    sys.path = [p for p in sys.path if p != root_str]
    sys.path.insert(0, root_str)

# 2) Force `analytics` to be the repo package, not tests/analytics
if "analytics" in sys.modules:
    del sys.modules["analytics"]

analytics = importlib.import_module("analytics")


@dataclass(frozen=True)
class StochasticTestPolicy:
    """Strict test-harness policy loaded from the canonical YAML control."""

    fast_model_evaluations: int
    full_model_evaluations: int
    hard_max_model_evaluations: int
    qualification_test_mode: str
    qualification_marker: str
    requires_explicit_seed: bool
    required_receipt_fields: tuple[str, ...]


@dataclass(frozen=True)
class ReportSensitivityProfilePolicy:
    """One config-declared report sensitivity execution profile."""

    name: str
    tornado_evaluations: int
    morris_trajectories: int
    pawn_evaluations: int
    pawn_slices: int


@dataclass(frozen=True)
class ReportQualificationDurationEvidence:
    """Observed qualification timing, separate from pytest-split weights."""

    nodeid: str
    command: str
    python_version: str
    profile: str
    outcome: str
    measured_at: str
    observed_scope: str
    observed_seconds: float


@dataclass(frozen=True)
class ReportTestPolicy:
    """Strict report-test architecture loaded from the canonical YAML control."""

    api_transport_context: str
    renderer_context: str
    representative_live_e2e_required: bool
    claim_classification: str
    ordinary_sensitivity_profile: ReportSensitivityProfilePolicy
    qualification_test_mode: str
    qualification_marker: str
    required_live_paths: tuple[str, ...]
    production_sensitivity_profile: ReportSensitivityProfilePolicy
    duration_history_path: str
    duration_review_threshold_seconds: float
    ordinary_duration_exceptions: tuple[tuple[str, str], ...]
    qualification_duration_evidence: ReportQualificationDurationEvidence


STOCHASTIC_TEST_POLICY_PATH = REPO_ROOT / "config" / "stochastic_test_policy.yaml"
REPORT_TEST_POLICY_PATH = REPO_ROOT / "config" / "report_test_policy.yaml"
_STOCHASTIC_POLICY_SCHEMA = "dutchbay_stochastic_test_policy_v1"
_REPORT_POLICY_SCHEMA = "dutchbay_report_test_policy_v2"
_TEST_MODES = {"fast", "full", "qualification"}


class StochasticTestBudgetError(ValueError):
    """Raised when an ordinary test requests too many model evaluations."""


def _require_exact_keys(
    value: object, expected: set[str], *, context: str
) -> Mapping[str, object]:
    """Return a mapping only when its keys exactly match the policy schema."""
    if not isinstance(value, Mapping):
        raise ValueError(f"{context} must be a mapping")
    actual = {str(key) for key in value}
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        raise ValueError(
            f"{context} keys do not match the strict schema; "
            f"missing={missing}, unknown={unknown}"
        )
    return value


def _positive_int(value: object, *, context: str) -> int:
    """Parse a positive integer without admitting bool as an integer."""
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{context} must be a positive integer")
    return value


def _positive_number(value: object, *, context: str) -> float:
    """Parse a finite positive real number without admitting bool."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{context} must be a positive number")
    parsed = float(value)
    if not (parsed > 0.0 and parsed < float("inf")):
        raise ValueError(f"{context} must be a positive finite number")
    return parsed


def _load_stochastic_test_policy(
    path: Path = STOCHASTIC_TEST_POLICY_PATH,
) -> StochasticTestPolicy:
    """Load and strictly validate the stochastic pytest policy."""
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"cannot load stochastic test policy {path}: {exc}") from exc

    root = _require_exact_keys(
        raw,
        {"schema_version", "ordinary_suite", "qualification_suite"},
        context="stochastic test policy",
    )
    if root["schema_version"] != _STOCHASTIC_POLICY_SCHEMA:
        raise ValueError(
            "stochastic test policy schema_version must be "
            f"{_STOCHASTIC_POLICY_SCHEMA!r}"
        )

    ordinary = _require_exact_keys(
        root["ordinary_suite"],
        {
            "fast_model_evaluations",
            "full_model_evaluations",
            "hard_max_model_evaluations",
            "claim_classification",
        },
        context="ordinary_suite",
    )
    qualification = _require_exact_keys(
        root["qualification_suite"],
        {
            "test_mode",
            "marker",
            "requires_explicit_seed",
            "required_receipt_fields",
        },
        context="qualification_suite",
    )

    fast = _positive_int(
        ordinary["fast_model_evaluations"],
        context="ordinary_suite.fast_model_evaluations",
    )
    full = _positive_int(
        ordinary["full_model_evaluations"],
        context="ordinary_suite.full_model_evaluations",
    )
    hard_max = _positive_int(
        ordinary["hard_max_model_evaluations"],
        context="ordinary_suite.hard_max_model_evaluations",
    )
    if ordinary["claim_classification"] != "regression_and_coverage_only":
        raise ValueError(
            "ordinary_suite.claim_classification must be 'regression_and_coverage_only'"
        )
    if not (fast <= full == hard_max == 200):
        raise ValueError(
            "ordinary stochastic budgets must satisfy fast <= full == hard_max == 200"
        )

    test_mode = qualification["test_mode"]
    marker = qualification["marker"]
    explicit_seed = qualification["requires_explicit_seed"]
    receipt_fields = qualification["required_receipt_fields"]
    if test_mode != "qualification":
        raise ValueError("qualification_suite.test_mode must be 'qualification'")
    if marker != "stochastic_qualification":
        raise ValueError(
            "qualification_suite.marker must be 'stochastic_qualification'"
        )
    if explicit_seed is not True:
        raise ValueError("qualification_suite.requires_explicit_seed must be true")
    if (
        not isinstance(receipt_fields, list)
        or not receipt_fields
        or not all(isinstance(field, str) and field for field in receipt_fields)
    ):
        raise ValueError(
            "qualification_suite.required_receipt_fields must be a non-empty string list"
        )
    required = {
        "requested_evaluations",
        "effective_evaluations",
        "seed",
        "config_sha256",
        "git_sha",
        "result_sha256",
        "limitations",
    }
    if set(receipt_fields) != required:
        raise ValueError(
            "qualification_suite.required_receipt_fields must contain the governed set"
        )

    return StochasticTestPolicy(
        fast_model_evaluations=fast,
        full_model_evaluations=full,
        hard_max_model_evaluations=hard_max,
        qualification_test_mode=str(test_mode),
        qualification_marker=str(marker),
        requires_explicit_seed=explicit_seed,
        required_receipt_fields=tuple(receipt_fields),
    )


def _load_report_test_policy(
    path: Path = REPORT_TEST_POLICY_PATH,
) -> ReportTestPolicy:
    """Load and strictly validate the report/API pytest architecture."""
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"cannot load report test policy {path}: {exc}") from exc

    root = _require_exact_keys(
        raw,
        {
            "schema_version",
            "ordinary_suite",
            "qualification_suite",
            "duration_history",
        },
        context="report test policy",
    )
    if root["schema_version"] != _REPORT_POLICY_SCHEMA:
        raise ValueError(
            f"report test policy schema_version must be {_REPORT_POLICY_SCHEMA!r}"
        )

    ordinary = _require_exact_keys(
        root["ordinary_suite"],
        {
            "api_transport_context",
            "renderer_context",
            "representative_live_e2e",
            "claim_classification",
            "sensitivity_profile",
        },
        context="report ordinary_suite",
    )
    qualification = _require_exact_keys(
        root["qualification_suite"],
        {"test_mode", "marker", "required_live_paths", "sensitivity_profile"},
        context="report qualification_suite",
    )
    duration = _require_exact_keys(
        root["duration_history"],
        {
            "path",
            "review_threshold_seconds",
            "ordinary_exceptions",
            "qualification_evidence",
        },
        context="report duration_history",
    )

    expected_ordinary = {
        "api_transport_context": "deterministic_known_context",
        "renderer_context": "deterministic_known_context",
        "representative_live_e2e": "required",
        "claim_classification": "regression_and_coverage_only",
    }
    for key, expected in expected_ordinary.items():
        if ordinary[key] != expected:
            raise ValueError(f"report ordinary_suite.{key} must be {expected!r}")

    def _profile(value: object, *, context: str) -> ReportSensitivityProfilePolicy:
        profile = _require_exact_keys(
            value,
            {
                "name",
                "tornado_evaluations",
                "morris_trajectories",
                "pawn_evaluations",
                "pawn_slices",
            },
            context=context,
        )
        name = profile["name"]
        if not isinstance(name, str) or not name:
            raise ValueError(f"{context}.name must be a non-empty string")
        return ReportSensitivityProfilePolicy(
            name=name,
            tornado_evaluations=_positive_int(
                profile["tornado_evaluations"],
                context=f"{context}.tornado_evaluations",
            ),
            morris_trajectories=_positive_int(
                profile["morris_trajectories"],
                context=f"{context}.morris_trajectories",
            ),
            pawn_evaluations=_positive_int(
                profile["pawn_evaluations"],
                context=f"{context}.pawn_evaluations",
            ),
            pawn_slices=_positive_int(
                profile["pawn_slices"], context=f"{context}.pawn_slices"
            ),
        )

    ordinary_profile = _profile(
        ordinary["sensitivity_profile"],
        context="report ordinary_suite.sensitivity_profile",
    )
    production_profile = _profile(
        qualification["sensitivity_profile"],
        context="report qualification_suite.sensitivity_profile",
    )
    if ordinary_profile.name != "ordinary_bounded":
        raise ValueError(
            "report ordinary_suite.sensitivity_profile.name must be 'ordinary_bounded'"
        )
    if production_profile.name != "production_full":
        raise ValueError(
            "report qualification_suite.sensitivity_profile.name must be "
            "'production_full'"
        )

    test_mode = qualification["test_mode"]
    marker = qualification["marker"]
    required_live_paths = qualification["required_live_paths"]
    if test_mode != "qualification":
        raise ValueError("report qualification_suite.test_mode must be 'qualification'")
    if marker != "report_qualification":
        raise ValueError(
            "report qualification_suite.marker must be 'report_qualification'"
        )
    if (
        not isinstance(required_live_paths, list)
        or len(required_live_paths) != 2
        or not all(isinstance(value, str) and value for value in required_live_paths)
        or set(required_live_paths) != {"supplemental_sensitivity", "pdf_backend"}
    ):
        raise ValueError(
            "report qualification_suite.required_live_paths must contain "
            "supplemental_sensitivity and pdf_backend"
        )

    duration_path = duration["path"]
    if duration_path != ".test_durations":
        raise ValueError("report duration_history.path must be '.test_durations'")
    threshold = _positive_number(
        duration["review_threshold_seconds"],
        context="report duration_history.review_threshold_seconds",
    )
    if threshold != 5.0:
        raise ValueError(
            "report duration_history.review_threshold_seconds must be exactly 5.0"
        )
    exceptions = duration["ordinary_exceptions"]
    if not isinstance(exceptions, Mapping) or not all(
        isinstance(nodeid, str)
        and nodeid
        and isinstance(reason, str)
        and reason.strip()
        for nodeid, reason in exceptions.items()
    ):
        raise ValueError(
            "report duration_history.ordinary_exceptions must map nodeids to "
            "non-empty written reasons"
        )
    evidence = _require_exact_keys(
        duration["qualification_evidence"],
        {
            "nodeid",
            "command",
            "python_version",
            "profile",
            "outcome",
            "measured_at",
            "observed_scope",
            "observed_seconds",
        },
        context="report duration_history.qualification_evidence",
    )
    for key in (
        "nodeid",
        "command",
        "python_version",
        "profile",
        "outcome",
        "measured_at",
        "observed_scope",
    ):
        if not isinstance(evidence[key], str) or not str(evidence[key]).strip():
            raise ValueError(
                f"report duration_history.qualification_evidence.{key} "
                "must be a non-empty string"
            )
    if evidence["profile"] != production_profile.name:
        raise ValueError(
            "report duration_history.qualification_evidence.profile must match "
            "the production sensitivity profile"
        )
    if evidence["outcome"] not in {"passed", "failed"}:
        raise ValueError(
            "report duration_history.qualification_evidence.outcome must be "
            "'passed' or 'failed'"
        )
    if evidence["observed_scope"] != "pytest_session":
        raise ValueError(
            "report duration_history.qualification_evidence.observed_scope must be "
            "'pytest_session'"
        )
    if not str(evidence["python_version"]).startswith("3.12."):
        raise ValueError(
            "report duration_history.qualification_evidence.python_version "
            "must identify Python 3.12"
        )
    if evidence["command"] != "make test-report-qualification":
        raise ValueError(
            "report duration_history.qualification_evidence.command must be "
            "'make test-report-qualification'"
        )
    observed = _positive_number(
        evidence["observed_seconds"],
        context="report duration_history.qualification_evidence.observed_seconds",
    )

    return ReportTestPolicy(
        api_transport_context=str(ordinary["api_transport_context"]),
        renderer_context=str(ordinary["renderer_context"]),
        representative_live_e2e_required=True,
        claim_classification=str(ordinary["claim_classification"]),
        ordinary_sensitivity_profile=ordinary_profile,
        qualification_test_mode=str(test_mode),
        qualification_marker=str(marker),
        required_live_paths=tuple(required_live_paths),
        production_sensitivity_profile=production_profile,
        duration_history_path=str(duration_path),
        duration_review_threshold_seconds=threshold,
        ordinary_duration_exceptions=tuple(
            sorted((str(nodeid), str(reason)) for nodeid, reason in exceptions.items())
        ),
        qualification_duration_evidence=ReportQualificationDurationEvidence(
            nodeid=str(evidence["nodeid"]),
            command=str(evidence["command"]),
            python_version=str(evidence["python_version"]),
            profile=str(evidence["profile"]),
            outcome=str(evidence["outcome"]),
            measured_at=str(evidence["measured_at"]),
            observed_scope=str(evidence["observed_scope"]),
            observed_seconds=observed,
        ),
    )


def _test_mode() -> str:
    """Return the validated DUTCHBAY_TEST_MODE value."""
    mode = os.environ.get("DUTCHBAY_TEST_MODE", "fast").strip().lower()
    if mode not in _TEST_MODES:
        raise ValueError(
            f"DUTCHBAY_TEST_MODE must be one of fast, full, qualification; got {mode!r}"
        )
    return mode


def _effective_stochastic_model_evaluations(requested: int, *, sampler: str) -> int:
    """Resolve the model count, including Sobol power-of-two expansion."""
    if isinstance(requested, bool) or not isinstance(requested, int) or requested <= 0:
        raise StochasticTestBudgetError("stochastic model evaluations must be > 0")
    if sampler == "sobol":
        return 1 << (requested - 1).bit_length()
    return requested


def _enforce_stochastic_model_budget(
    requested: int, *, sampler: str, mode: str, policy: StochasticTestPolicy
) -> int:
    """Fail closed when an ordinary test exceeds TEST-03's effective cap."""
    effective = _effective_stochastic_model_evaluations(requested, sampler=sampler)
    if mode != policy.qualification_test_mode and (
        effective > policy.hard_max_model_evaluations
    ):
        raise StochasticTestBudgetError(
            "TEST-03 refuses an ordinary pytest Monte Carlo run above "
            f"{policy.hard_max_model_evaluations} effective model evaluations "
            f"(requested={requested}, effective={effective}, sampler={sampler!r}). "
            "Mark a genuine scale test stochastic_qualification and run "
            "`make test-stochastic-qualification`."
        )
    return effective


# 3) Headless matplotlib for the WHOLE suite. Without this, chart-emitting tests
# (e.g. plot_npv_distribution via the capital-risk report) instantiate the platform GUI
# backend on developer machines — on macOS the `macosx` backend hard-SEGFAULTS the pytest
# process when no window server is reachable (sandboxed shells, SSH, tmux). Linux CI was
# never affected (no DISPLAY → matplotlib already falls back to Agg), so this pins the
# same non-interactive backend everywhere. Must run BEFORE any test imports pyplot;
# os.environ is belt-and-braces for xdist workers and subprocesses spawned by tests.
os.environ.setdefault("MPLBACKEND", "Agg")
try:
    import matplotlib

    matplotlib.use("Agg", force=True)
except ImportError:  # pragma: no cover - matplotlib is a hard dependency, but stay safe
    pass

# Optional: Uncomment for debugging path resolution
# print("Pytest using analytics from:", analytics.__file__)
# print("Pytest sys.path[0]:", sys.path[0])


# =============================================================================
# TEST PERFORMANCE CONFIGURATION (GWTF-Compliant: No argparse)
# =============================================================================


@pytest.fixture(scope="session")
def fast_test_mode() -> bool:
    """
    Session-scoped fixture: determine if tests should run in fast mode.

    Fast mode reduces Monte Carlo and sensitivity test iterations for rapid
    development feedback. The ordinary full mode remains capped by TEST-03;
    production-scale work belongs to the explicit qualification mode.

    GWTF-Compliant:
        Uses environment variable instead of argparse-style CLI options.
        No pytest_addoption required, avoiding argparse.

    Returns
    -------
    bool
        True if fast mode enabled (default), False for full iterations.

    Usage
    -----
    Environment variable:
        DUTCHBAY_TEST_MODE=fast pytest    # Fast mode (20 iter, default)
        DUTCHBAY_TEST_MODE=full pytest    # Full regression mode (200 max)
        DUTCHBAY_TEST_MODE=qualification pytest -m stochastic_qualification
        pytest                             # Default: fast mode

    In test code:
        def test_monte_carlo(fast_test_mode):
            n_iter = 20 if fast_test_mode else 200
            result = run_monte_carlo(n_iterations=n_iter)
    """
    return _test_mode() == "fast"


@pytest.fixture(scope="session")
def test_iteration_config(fast_test_mode: bool) -> dict[str, int | str]:
    """
    Session-scoped fixture: iteration counts for different test types.

    Provides centralized configuration for test performance tuning.

    Parameters
    ----------
    fast_test_mode : bool
        Whether tests are running in fast mode.

    Returns
    -------
    dict[str, int]
        Configuration with keys:
        - monte_carlo_iterations: Number of MC simulations
        - sensitivity_parameters: Max parameters for sensitivity analysis
        - sensitivity_steps: Steps per parameter in tornado charts
        - timeout_seconds: Test timeout multiplier

    Examples
    --------
    >>> def test_monte_carlo(test_iteration_config):
    ...     n = test_iteration_config["monte_carlo_iterations"]
    ...     result = run_monte_carlo(n_iterations=n)
    """
    policy = _load_stochastic_test_policy()
    mode = _test_mode()
    if mode == policy.qualification_test_mode:
        raise StochasticTestBudgetError(
            "stochastic_qualification tests must declare their scale explicitly; "
            "the ordinary test_iteration_config fixture is unavailable"
        )
    if fast_test_mode:
        return {
            "monte_carlo_iterations": policy.fast_model_evaluations,
            "sensitivity_parameters": 3,  # Limit to 3 params (was 8+)
            "sensitivity_steps": 3,  # 3-point sensitivity (was 5)
            "timeout_seconds": 30,  # Short timeout for dev
            "mode": "fast",
        }
    else:
        return {
            "monte_carlo_iterations": policy.full_model_evaluations,
            "sensitivity_parameters": 12,  # All parameters
            "sensitivity_steps": 5,  # Full 5-point tornado
            "timeout_seconds": 300,  # 5 min timeout
            "mode": "full",
        }


@pytest.fixture(scope="session", autouse=True)
def _stochastic_model_evaluation_guard() -> Iterator[None]:
    """Enforce TEST-03 at the canonical Monte Carlo model-execution seam."""
    mode = _test_mode()
    policy = _load_stochastic_test_policy()
    if mode == policy.qualification_test_mode:
        yield
        return

    from analytics.mc.engine import MonteCarloEngine

    original_run = MonteCarloEngine.run

    def guarded_run(self: Any, *, n_trials: int) -> Any:
        _enforce_stochastic_model_budget(
            n_trials,
            sampler=str(getattr(self, "_sampler", "lhs")),
            mode=mode,
            policy=policy,
        )
        return original_run(self, n_trials=n_trials)

    MonteCarloEngine.run = guarded_run
    try:
        yield
    finally:
        MonteCarloEngine.run = original_run


# =============================================================================
# Shared LibCST Visitor Base Class
# =============================================================================


class BaseSensitivityVisitor(cst.CSTVisitor):
    """
    Base visitor for sensitivity_v14.py structural analysis via LibCST.

    Provides unified utilities for:
    - Safe module name extraction from CST nodes
    - Import tracking
    - Function call inspection
    - Error-safe visiting patterns

    Subclasses should override policy enforcement in visit_ImportFrom()
    and visit_Call() while inheriting utility methods.
    """

    def __init__(self) -> None:
        """Initialize visitor tracking collections."""
        self.forbidden_imports: List[str] = []
        self.direct_pipeline_calls: List[str] = []
        self.seen_imports: Set[str] = set()

    def _get_module_name(self, node: cst.Attribute | cst.Name) -> str:
        """Extract full module name from cst.Attribute or cst.Name node.

        Safely handles both:
        - Simple names: cst.Name (e.g., '__future__', 'os')
        - Dotted paths: cst.Attribute (e.g., 'analytics.evaluation_v14')

        Parameters
        ----------
        node : cst.Attribute | cst.Name
            The module node from an ImportFrom statement.

        Returns
        -------
        str
            Full module name (e.g., 'analytics.evaluation_v14') or empty string
            if extraction fails.
        """
        parts: List[str] = []
        current: cst.BaseExpression | None = node

        while current is not None:
            if isinstance(current, cst.Name):
                parts.insert(0, current.value)
                break
            elif isinstance(current, cst.Attribute):
                parts.insert(0, current.attr.value)
                current = current.value
            else:
                break

        return ".".join(parts) if parts else ""

    def visit_ImportFrom(self, node: cst.ImportFrom) -> None:
        """Base implementation: just track imports seen.

        Subclasses override to enforce specific policies.

        Parameters
        ----------
        node : cst.ImportFrom
            The ImportFrom node from the CST.
        """
        if node.module is None:
            return

        module_name = self._get_module_name(node.module)
        self.seen_imports.add(module_name)

    def visit_Call(self, node: cst.Call) -> None:
        """Base implementation: track function calls.

        Subclasses override to enforce specific policies.

        Parameters
        ----------
        node : cst.Call
            The Call node from the CST.
        """
        # Base implementation does nothing; subclasses override as needed


# =============================================================================
# Shared File Loading Utilities
# =============================================================================


def load_sensitivity_source() -> str:
    """Load sensitivity_v14.py source code from standard locations.

    Searches for the file in the following order:
    1. Current working directory: analytics/sensitivity_v14.py
    2. Parent directory: ../analytics/sensitivity_v14.py
    3. Finance directory: finance/sensitivity_v14.py

    Returns
    -------
    str
        Source code of sensitivity_v14.py.

    Raises
    ------
    pytest.skip
        If file not found in any standard location.
    """
    repo_root = Path.cwd()

    # Try direct path first
    sensitivity_path = repo_root / "analytics" / "sensitivity_v14.py"
    if sensitivity_path.exists():
        return sensitivity_path.read_text(encoding="utf-8")

    # Try parent directory
    sensitivity_path = repo_root.parent / "analytics" / "sensitivity_v14.py"
    if sensitivity_path.exists():
        return sensitivity_path.read_text(encoding="utf-8")

    # Try finance directory (alternate location)
    sensitivity_path = repo_root / "finance" / "sensitivity_v14.py"
    if sensitivity_path.exists():
        return sensitivity_path.read_text(encoding="utf-8")

    pytest.skip(
        "sensitivity_v14.py not found in expected locations "
        "(tried analytics/, finance/, and parent/analytics/)"
    )


def load_sensitivity_module() -> cst.Module:
    """Parse sensitivity_v14.py and return LibCST Module object.

    Returns
    -------
    cst.Module
        Parsed CST module.

    Raises
    ------
    pytest.fail
        If file cannot be parsed.
    """
    source = load_sensitivity_source()

    try:
        return cst.parse_module(source)
    except Exception as exc:
        pytest.fail(f"Failed to parse sensitivity_v14.py: {exc}")


# =============================================================================
# Shared Pytest Fixtures
# =============================================================================


@pytest.fixture(scope="session")
def sensitivity_source() -> str:
    """Session-scoped fixture: load sensitivity_v14.py source once.

    Returns
    -------
    str
        Source code of sensitivity_v14.py.
    """
    return load_sensitivity_source()


@pytest.fixture(scope="session")
def sensitivity_module(sensitivity_source: str) -> cst.Module:
    """Session-scoped fixture: parse sensitivity_v14.py once.

    Parameters
    ----------
    sensitivity_source : str
        Source code from sensitivity_source fixture.

    Returns
    -------
    cst.Module
        Parsed CST module (reused across all tests in session).
    """
    try:
        return cst.parse_module(sensitivity_source)
    except Exception as exc:
        pytest.fail(f"Failed to parse sensitivity_v14.py: {exc}")


@pytest.fixture
def visitor(sensitivity_module: cst.Module) -> BaseSensitivityVisitor:
    """Module-scoped fixture: create and populate BaseSensitivityVisitor.

    Subclasses in specific test modules can override this fixture
    to use their custom visitor implementation.

    Parameters
    ----------
    sensitivity_module : cst.Module
        Parsed module from sensitivity_module fixture.

    Returns
    -------
    BaseSensitivityVisitor
        Visitor with import/call data populated from sensitivity_v14.py.
    """
    v = BaseSensitivityVisitor()

    try:
        sensitivity_module.visit(v)
    except AttributeError as exc:
        pytest.fail(f"LibCST visitor AttributeError (unsupported CST node): {exc}")
    except Exception as exc:
        pytest.fail(f"LibCST visitor error: {exc}")

    return v


# =============================================================================
# Pytest Configuration (No argparse - GWTF R3 compliant)
# =============================================================================


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers for test categorization.

    Markers:
    - edge_case: Edge case and boundary condition stress tests
    - stress: Stress tests, failure scenarios, and load/performance edge cases
    - critical_error: Critical error handling and recovery tests
    - integration: Integration tests spanning multiple modules
    - unit: Unit tests for individual functions and classes
    - slow: Tests taking >5 seconds (skip with -m "not slow")
    - regression: Regression tests with frozen/expected output
    - monte_carlo: Monte Carlo simulation tests
    - sensitivity: Sensitivity analysis tests
    - stochastic_qualification: Explicit tests above the ordinary 200-run cap
    - report_qualification: Explicit live supplemental-sensitivity/PDF tests
    - lint: Static analysis and linting tests
    - analytics_layer: Functional/integration tests for analytics layer
    """
    config.addinivalue_line(
        "markers",
        "edge_case: Edge case and boundary condition stress tests",
    )
    config.addinivalue_line(
        "markers",
        "stress: Stress/failure/load scenario tests",
    )
    config.addinivalue_line(
        "markers",
        "critical_error: Critical error handling and recovery tests",
    )
    config.addinivalue_line(
        "markers",
        "integration: Integration tests spanning multiple modules",
    )
    config.addinivalue_line(
        "markers",
        "unit: Unit tests for individual functions and classes",
    )
    config.addinivalue_line(
        "markers",
        "slow: Tests with long runtime (>5s, use -m 'not slow' to skip)",
    )
    config.addinivalue_line(
        "markers",
        "regression: Regression tests with frozen/expected output",
    )
    config.addinivalue_line(
        "markers",
        "monte_carlo: Monte Carlo simulation tests",
    )
    config.addinivalue_line(
        "markers",
        "sensitivity: Sensitivity analysis tests",
    )
    config.addinivalue_line(
        "markers",
        "stochastic_qualification: explicit stochastic scale/qualification tests "
        "that are isolated from the ordinary full suite",
    )
    config.addinivalue_line(
        "markers",
        "report_qualification: explicit live supplemental-sensitivity and PDF "
        "backend tests isolated from the ordinary full suite",
    )
    config.addinivalue_line("markers", "lint: Static analysis and linting tests")
    config.addinivalue_line(
        "markers",
        "analytics_layer: Functional/integration tests for analytics layer",
    )
    config.addinivalue_line(
        "markers",
        "performance: Performance/throughput benchmark tests (subset of slow)",
    )

    try:
        policy = _load_stochastic_test_policy()
        report_policy = _load_report_test_policy()
        test_mode = _test_mode()
    except ValueError as exc:
        raise pytest.UsageError(str(exc)) from exc

    if test_mode == "full":
        print("\n" + "=" * 78)
        print("TEST MODE: FULL REGRESSION + COVERAGE")
        print(
            "Stochastic model-evaluation hard cap: "
            f"{policy.hard_max_model_evaluations} per test"
        )
        print(
            "Claim boundary: not convergence, lender, bankability, or release evidence"
        )
        print("=" * 78 + "\n")
    elif test_mode == policy.qualification_test_mode:
        print("\n" + "=" * 78)
        print("TEST MODE: QUALIFICATION (EXPLICITLY MARKED TESTS ONLY)")
        print(
            "Enabled markers: "
            f"{policy.qualification_marker}, {report_policy.qualification_marker}"
        )
        print("A green gate is not by itself a governed external-evidence receipt")
        print("=" * 78 + "\n")
    else:
        print("\n" + "=" * 78)
        print(
            "TEST MODE: FAST "
            f"({policy.fast_model_evaluations} recommended model evaluations)"
        )
        print(
            "Ordinary stochastic hard cap remains "
            f"{policy.hard_max_model_evaluations}; use `make test` for the full gate"
        )
        print("=" * 78 + "\n")


# =============================================================================
# Test Collection Hooks
# =============================================================================


def pytest_collection_modifyitems(
    config: pytest.Config, items: List[pytest.Item]
) -> None:
    """
    Automatically apply markers based on test file location and characteristics.

    Tests in:
    - tests/lint/ → lint marker
    - tests/analytics_layer/ → analytics_layer marker
    - Any test with 'sensitivity' in name → sensitivity marker
    - Tests with 'monte_carlo' in name → slow marker (can be skipped)
    - Tests with 'edge_case' or 'stress' in name → edge_case/stress markers
    """
    policy = _load_stochastic_test_policy()
    report_policy = _load_report_test_policy()
    mode = _test_mode()
    skip_qualification = pytest.mark.skip(
        reason=(
            "TEST-03/TEST-04 isolate qualification tests from the ordinary suite; "
            "run the matching make test-*-qualification target"
        )
    )
    skip_ordinary = pytest.mark.skip(
        reason="qualification mode executes only explicitly marked qualification tests"
    )
    qualification_markers = {
        policy.qualification_marker,
        report_policy.qualification_marker,
    }

    for item in items:
        # Mark by directory
        if "lint" in str(item.fspath):
            item.add_marker(pytest.mark.lint)
        if "analytics_layer" in str(item.fspath):
            item.add_marker(pytest.mark.analytics_layer)

        # Mark by name
        if "sensitivity" in item.nodeid:
            item.add_marker(pytest.mark.sensitivity)
        if "monte_carlo" in item.nodeid.lower():
            item.add_marker(pytest.mark.slow)
        if "edge_case" in item.nodeid.lower():
            item.add_marker(pytest.mark.edge_case)
        if "stress" in item.nodeid.lower():
            item.add_marker(pytest.mark.stress)

        is_qualification = any(
            item.get_closest_marker(marker) is not None
            for marker in qualification_markers
        )
        if mode == policy.qualification_test_mode:
            if not is_qualification:
                item.add_marker(skip_ordinary)
        elif is_qualification:
            item.add_marker(skip_qualification)


__all__ = [
    # Path setup
    "REPO_ROOT",
    "analytics",
    "REPORT_TEST_POLICY_PATH",
    "STOCHASTIC_TEST_POLICY_PATH",
    # Performance fixtures
    "fast_test_mode",
    "test_iteration_config",
    "ReportTestPolicy",
    "ReportSensitivityProfilePolicy",
    "ReportQualificationDurationEvidence",
    "StochasticTestBudgetError",
    "StochasticTestPolicy",
    "_effective_stochastic_model_evaluations",
    "_enforce_stochastic_model_budget",
    "_load_report_test_policy",
    "_load_stochastic_test_policy",
    # Visitors
    "BaseSensitivityVisitor",
    # Utilities
    "load_sensitivity_source",
    "load_sensitivity_module",
    # Fixtures
    "sensitivity_source",
    "sensitivity_module",
    "visitor",
]
