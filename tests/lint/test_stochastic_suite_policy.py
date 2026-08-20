"""Executable guards for GWTF TEST-03's stochastic pytest budget."""

from __future__ import annotations

import ast
import csv
import re
from pathlib import Path
from typing import Iterator

import pytest
import yaml
from conftest import (
    STOCHASTIC_TEST_POLICY_PATH,
    StochasticTestBudgetError,
    _enforce_stochastic_model_budget,
    _load_stochastic_test_policy,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
RULESET = REPO_ROOT / "go_with_the_flow_rules_v3_0_clean.csv"
ORDINARY_CAP = 200


def _decorator_name(node: ast.expr) -> str:
    """Return a dotted decorator name for simple Name/Attribute expressions."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _decorator_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    if isinstance(node, ast.Call):
        return _decorator_name(node.func)
    return ""


def _integer_constants(nodes: list[ast.stmt]) -> dict[str, int]:
    """Collect simple integer assignments used as local trial-count aliases."""
    constants: dict[str, int] = {}
    for node in nodes:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            value = node.value
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if isinstance(value, ast.Constant) and isinstance(value.value, int):
                for target in targets:
                    if isinstance(target, ast.Name):
                        constants[target.id] = value.value
    return constants


def _resolved_int(node: ast.expr, constants: dict[str, int]) -> int | None:
    """Resolve a literal or simple named integer trial count."""
    if isinstance(node, ast.Constant) and isinstance(node.value, int):
        return node.value
    if isinstance(node, ast.Name):
        return constants.get(node.id)
    return None


def _test_functions(tree: ast.Module) -> Iterator[tuple[ast.FunctionDef, bool]]:
    """Yield test functions with class/function qualification-marker inheritance."""
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("test_") and isinstance(node, ast.FunctionDef):
                marked = any(
                    _decorator_name(dec).endswith("stochastic_qualification")
                    for dec in node.decorator_list
                )
                yield node, marked
        elif isinstance(node, ast.ClassDef):
            class_marked = any(
                _decorator_name(dec).endswith("stochastic_qualification")
                for dec in node.decorator_list
            )
            for member in node.body:
                if isinstance(member, ast.FunctionDef) and member.name.startswith(
                    "test_"
                ):
                    method_marked = any(
                        _decorator_name(dec).endswith("stochastic_qualification")
                        for dec in member.decorator_list
                    )
                    yield member, class_marked or method_marked


def _model_trial_keyword(call: ast.Call) -> tuple[str, ast.expr] | None:
    """Return the governed count keyword for known model-evaluation entrypoints."""
    func_name = _decorator_name(call.func)
    keyword_name: str | None = None
    if func_name.endswith("run_monte_carlo_analysis") or func_name.endswith(".run"):
        keyword_name = "n_trials"
    elif func_name.endswith("run_capex_mc"):
        keyword_name = "n_samples"
    if keyword_name is None:
        return None
    for keyword in call.keywords:
        if keyword.arg == keyword_name:
            return keyword_name, keyword.value
    return None


def test_test03_is_active_and_pins_the_evidence_boundary() -> None:
    """Keep the canonical GWTF row explicit about the cap and non-claims."""
    with RULESET.open(encoding="utf-8", newline="") as handle:
        rules = {row["rule_id"]: row for row in csv.DictReader(handle)}

    rule = rules["TEST-03"]
    policy = " ".join((rule["title"], rule["description"], rule["enforcement"]))
    assert rule["status"] == "active"
    assert "200" in policy
    assert "stochastic_qualification" in policy
    for prohibited_claim in ("convergence", "bankability", "lender", "release"):
        assert prohibited_claim in policy.lower()


def test_policy_is_strict_and_pins_the_ordinary_cap() -> None:
    """Validate the canonical YAML and its fail-closed unknown-key behavior."""
    policy = _load_stochastic_test_policy()
    assert policy.fast_model_evaluations == 20
    assert policy.full_model_evaluations == ORDINARY_CAP
    assert policy.hard_max_model_evaluations == ORDINARY_CAP
    assert policy.qualification_test_mode == "qualification"
    assert policy.qualification_marker == "stochastic_qualification"


def test_policy_rejects_unknown_keys(tmp_path: Path) -> None:
    """A typo or undeclared policy switch must fail before collection proceeds."""
    raw = yaml.safe_load(STOCHASTIC_TEST_POLICY_PATH.read_text(encoding="utf-8"))
    raw["ordinary_suite"]["silent_override"] = True
    bad = tmp_path / "bad_policy.yaml"
    bad.write_text(yaml.safe_dump(raw), encoding="utf-8")

    with pytest.raises(ValueError, match=r"unknown=\['silent_override'\]"):
        _load_stochastic_test_policy(bad)


def test_budget_counts_sobol_effective_evaluations() -> None:
    """Sobol requests that expand above 200 are refused in ordinary modes."""
    policy = _load_stochastic_test_policy()
    assert (
        _enforce_stochastic_model_budget(200, sampler="lhs", mode="full", policy=policy)
        == 200
    )
    assert (
        _enforce_stochastic_model_budget(
            128, sampler="sobol", mode="full", policy=policy
        )
        == 128
    )
    with pytest.raises(StochasticTestBudgetError, match="effective=256"):
        _enforce_stochastic_model_budget(
            129, sampler="sobol", mode="full", policy=policy
        )
    with pytest.raises(StochasticTestBudgetError, match="requested=201"):
        _enforce_stochastic_model_budget(201, sampler="lhs", mode="fast", policy=policy)
    assert (
        _enforce_stochastic_model_budget(
            10_000, sampler="lhs", mode="qualification", policy=policy
        )
        == 10_000
    )


def test_ordinary_tests_do_not_hardcode_model_runs_above_200() -> None:
    """Require explicit qualification marking for known model-evaluation calls."""
    violations: list[str] = []
    for path in sorted((REPO_ROOT / "tests").rglob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        module_constants = _integer_constants(tree.body)
        for function, qualified in _test_functions(tree):
            constants = {**module_constants, **_integer_constants(function.body)}
            for node in ast.walk(function):
                if not isinstance(node, ast.Call):
                    continue
                governed = _model_trial_keyword(node)
                if governed is None:
                    continue
                keyword, value_node = governed
                value = _resolved_int(value_node, constants)
                if value is not None and value > ORDINARY_CAP and not qualified:
                    relative = path.relative_to(REPO_ROOT)
                    violations.append(
                        f"{relative}:{node.lineno} {function.name} "
                        f"uses {keyword}={value} without stochastic_qualification"
                    )

    assert not violations, "\n".join(violations)


def test_full_gate_and_qualification_target_select_explicit_modes() -> None:
    """Keep local and CI entrypoints bound to the intended TEST-03 modes."""
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
    workflows_dir = REPO_ROOT / ".github" / "workflows"
    workflow = (workflows_dir / "test-suite.yml").read_text(encoding="utf-8")
    assert "DUTCHBAY_TEST_MODE=full $(PYTEST)" in makefile
    assert "test-stochastic-qualification:" in makefile
    assert "DUTCHBAY_TEST_MODE=qualification $(PYTEST)" in makefile
    assert "DUTCHBAY_TEST_MODE: full" in workflow
    assert "stochastic-qualification:" in workflow
    assert "DUTCHBAY_TEST_MODE: qualification" in workflow

    for name in (
        "test-suite.yml",
        "regression-smoke.yml",
        "fx-tests.yml",
        "release-run.yml",
    ):
        content = (workflows_dir / name).read_text(encoding="utf-8")
        assert re.search(r"(?m)^env:\n  DUTCHBAY_TEST_MODE: full$", content), name


def test_github_ci_test_interpreters_are_python312_only() -> None:
    """Reject any GitHub Actions Python test leg that reintroduces 3.11/3.13."""
    workflows_dir = REPO_ROOT / ".github" / "workflows"
    seen_versions: list[tuple[str, str]] = []
    paths = sorted([*workflows_dir.glob("*.yml"), *workflows_dir.glob("*.yaml")])
    for path in paths:
        workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(workflow, dict):
            continue
        jobs = workflow.get("jobs", {})
        if not isinstance(jobs, dict):
            continue
        for job_name, job in jobs.items():
            if not isinstance(job, dict):
                continue
            matrix = job.get("strategy", {}).get("matrix", {})
            for step in job.get("steps", []):
                if not isinstance(step, dict) or not str(
                    step.get("uses", "")
                ).startswith("actions/setup-python@"):
                    continue
                configured = step.get("with", {}).get("python-version")
                sources = [configured]
                if isinstance(configured, str) and "matrix." in configured:
                    match = re.search(r"matrix\.([A-Za-z0-9_-]+)", configured)
                    if match and isinstance(matrix, dict):
                        sources.append(matrix.get(match.group(1)))
                versions = {
                    version
                    for source in sources
                    for version in re.findall(r"\d+\.\d+", str(source))
                }
                assert versions, (
                    f"{path.name}:{job_name} setup-python must resolve an explicit "
                    "Python version"
                )
                assert versions == {"3.12"}, (
                    f"{path.name}:{job_name} configures Python versions "
                    f"{sorted(versions)} instead of only 3.12"
                )
                seen_versions.extend((path.name, version) for version in versions)

    assert seen_versions, "no explicit GitHub Actions Python versions were found"
