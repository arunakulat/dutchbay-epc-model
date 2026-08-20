"""Executable guards for GWTF TEST-04's report/API test architecture."""

from __future__ import annotations

import ast
import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

import pytest
import yaml
from conftest import REPORT_TEST_POLICY_PATH, _load_report_test_policy

from analytics.contracts_v14 import SYNTHETIC_PROCESS_PROVENANCE_WARNING

REPO_ROOT = Path(__file__).resolve().parents[2]
RULESET = REPO_ROOT / "go_with_the_flow_rules_v3_0_clean.csv"
API_TESTS = REPO_ROOT / "tests" / "app" / "test_api.py"
ORCHESTRATION_TESTS = REPO_ROOT / "tests" / "app" / "test_report_orchestration.py"
SURFACE_TESTS = REPO_ROOT / "tests" / "app" / "test_surface_contract.py"
E2E_TESTS = REPO_ROOT / "tests" / "integration" / "test_lender_report_e2e.py"
DURATION_HISTORY = REPO_ROOT / ".test_durations"

_QUALIFICATION_TEST = "test_complete_production_report_matrix_renders_html_and_pdf"
_REPORT_DURATION_PREFIXES = (
    "tests/app/test_api.py::test_run_case_report_",
    "tests/app/test_report_orchestration.py::",
    "tests/app/test_surface_contract.py::test_build_case_surface_projects_a_real_run",
    "tests/integration/test_lender_report_e2e.py::",
)


def _function(path: Path, name: str) -> ast.FunctionDef:
    """Return one top-level test function from a source file."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{path.relative_to(REPO_ROOT)} has no function {name}")


def _function_source(path: Path, name: str) -> str:
    """Return the exact source segment for a top-level test function."""
    source = path.read_text(encoding="utf-8")
    segment = ast.get_source_segment(source, _function(path, name))
    assert segment is not None
    return segment


def _decorator_name(value: ast.expr) -> str:
    """Return a dotted decorator name without evaluating test code."""
    if isinstance(value, ast.Call):
        return _decorator_name(value.func)
    if isinstance(value, ast.Name):
        return value.id
    if isinstance(value, ast.Attribute):
        prefix = _decorator_name(value.value)
        return f"{prefix}.{value.attr}" if prefix else value.attr
    return ""


def _decorators(path: Path, name: str) -> set[str]:
    """Return normalized decorator names for one top-level test function."""
    return {_decorator_name(value) for value in _function(path, name).decorator_list}


def _has_qualification_marker(decorators: Iterable[ast.expr]) -> bool:
    """Return whether decorators carry the explicit TEST-04 marker."""
    return any(
        _decorator_name(value).endswith(".report_qualification")
        or _decorator_name(value) == "report_qualification"
        for value in decorators
    )


def _dotted(value: ast.expr) -> str:
    """Return a syntactic dotted name for a name or attribute expression."""
    if isinstance(value, ast.Name):
        return value.id
    if isinstance(value, ast.Attribute):
        prefix = _dotted(value.value)
        return f"{prefix}.{value.attr}" if prefix else value.attr
    return ""


def _module_aliases(tree: ast.Module) -> dict[str, str]:
    """Resolve imports and straightforward module-local name aliases."""
    aliases: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module:
            for imported in node.names:
                local = imported.asname or imported.name
                aliases[local] = f"{node.module}.{imported.name}"
        elif isinstance(node, ast.Import):
            for imported in node.names:
                local = imported.asname or imported.name.split(".")[0]
                aliases[local] = imported.name

    changed = True
    while changed:
        changed = False
        for node in tree.body:
            if isinstance(node, (ast.Assign, ast.AnnAssign)) and isinstance(
                node.value, (ast.Name, ast.Attribute)
            ):
                targets = (
                    node.targets if isinstance(node, ast.Assign) else [node.target]
                )
                resolved = _resolve_name(_dotted(node.value), aliases)
                for target in targets:
                    if (
                        isinstance(target, ast.Name)
                        and aliases.get(target.id) != resolved
                    ):
                        aliases[target.id] = resolved
                        changed = True
    return aliases


def _resolve_name(name: str, aliases: Mapping[str, str]) -> str:
    """Expand the first component of a dotted name through known aliases."""
    if not name:
        return ""
    head, separator, tail = name.partition(".")
    expanded = aliases.get(head, head)
    return f"{expanded}.{tail}" if separator else expanded


def _is_live_complete_composition(call: ast.Call, aliases: Mapping[str, str]) -> bool:
    """Recognize calls that perform unbounded production report composition."""
    name = _resolve_name(_dotted(call.func), aliases)
    leaf = name.rsplit(".", 1)[-1]
    if leaf == "_build_report_context":
        return True
    if leaf != "compute_report_sensitivity":
        return False

    # Explicit injected computers are typed doubles, not a live complete composition.
    injected = {"tornado_computer", "morris_computer", "pawn_computer"}
    if injected <= {keyword.arg for keyword in call.keywords}:
        return False

    profile = next(
        (keyword.value for keyword in call.keywords if keyword.arg == "profile"), None
    )
    if profile is None:
        return True
    profile_name = _resolve_name(_dotted(profile), aliases)
    return not profile_name.endswith("ORDINARY_REPORT_SENSITIVITY_PROFILE")


def _is_sensitive_compositor(name: str) -> bool:
    """Return whether a resolved binding names a complete report compositor."""
    return name.rsplit(".", 1)[-1] in {
        "_build_report_context",
        "compute_report_sensitivity",
    }


@dataclass(frozen=True)
class _StructuralViolation:
    """One unqualified complete report composition found by the AST policy."""

    path: Path
    test_name: str
    call_name: str
    line: int

    def display(self) -> str:
        return (
            f"{self.path.relative_to(REPO_ROOT)}::{self.test_name}:{self.line} "
            f"calls {self.call_name} without @pytest.mark.report_qualification"
        )


def _structural_violations(path: Path) -> list[_StructuralViolation]:
    """Find unmarked complete composition, following module-local helpers/aliases."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    aliases = _module_aliases(tree)
    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    def inspect(
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        *,
        seen: frozenset[str],
        inherited_stubbed: frozenset[str] = frozenset(),
        inherited_aliases: Mapping[str, str] | None = None,
        inherited_live_aliases: frozenset[str] = frozenset(),
        inherited_patchers: frozenset[str] = frozenset(),
    ) -> list[tuple[str, int]]:
        findings: list[tuple[str, int]] = []
        local_aliases = dict(aliases)
        local_aliases.update(inherited_aliases or {})
        stubbed = set(inherited_stubbed)
        # A direct import or module-level assignment captures the production
        # callable before any per-test monkeypatch runs. Keep that binding live
        # even when its canonical module attribute is patched later.
        live_aliases = {
            local
            for local, resolved in local_aliases.items()
            if _is_sensitive_compositor(resolved)
        }
        live_aliases.update(inherited_live_aliases)
        trusted_patchers = set(inherited_patchers)

        class _CallVisitor(ast.NodeVisitor):
            def _register_import(
                self, imported: ast.alias, *, module: str = ""
            ) -> None:
                local = imported.asname or imported.name.split(".")[0]
                target = f"{module}.{imported.name}" if module else imported.name
                local_aliases[local] = target
                trusted_patchers.discard(local)
                if _is_sensitive_compositor(target) and target not in stubbed:
                    live_aliases.add(local)
                else:
                    live_aliases.discard(local)

            def visit_ImportFrom(self, imported: ast.ImportFrom) -> None:  # noqa: N802
                if imported.module:
                    for name in imported.names:
                        self._register_import(name, module=imported.module)

            def visit_Import(self, imported: ast.Import) -> None:  # noqa: N802
                for name in imported.names:
                    self._register_import(name)

            def _register_assignment(
                self, targets: Iterable[ast.expr], value: ast.expr
            ) -> None:
                source = _dotted(value)
                resolved = _resolve_name(source, local_aliases)
                for target in targets:
                    if isinstance(target, ast.Name):
                        local_aliases.pop(target.id, None)
                        live_aliases.discard(target.id)
                        trusted_patchers.discard(target.id)
                        if isinstance(value, (ast.Name, ast.Attribute)):
                            local_aliases[target.id] = resolved
                            if source in trusted_patchers:
                                trusted_patchers.add(target.id)
                            if source in live_aliases or (
                                _is_sensitive_compositor(resolved)
                                and resolved not in stubbed
                            ):
                                live_aliases.add(target.id)

            def visit_Assign(self, assignment: ast.Assign) -> None:  # noqa: N802
                self.visit(assignment.value)
                self._register_assignment(assignment.targets, assignment.value)

            def visit_AnnAssign(self, assignment: ast.AnnAssign) -> None:  # noqa: N802
                if assignment.value is not None:
                    self.visit(assignment.value)
                    self._register_assignment([assignment.target], assignment.value)

            def _monkeypatch_target(self, call: ast.Call) -> str:
                """Resolve the binding replaced by a monkeypatch.setattr call."""
                if not call.args:
                    return ""
                first = call.args[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    return first.value
                if (
                    len(call.args) >= 2
                    and isinstance(call.args[1], ast.Constant)
                    and isinstance(call.args[1].value, str)
                ):
                    owner = _resolve_name(_dotted(first), local_aliases)
                    return f"{owner}.{call.args[1].value}" if owner else ""
                return ""

            def _is_trusted_setattr(self, call: ast.Call) -> bool:
                """Accept only setattr from a provenance-tracked pytest fixture."""
                return (
                    isinstance(call.func, ast.Attribute)
                    and call.func.attr == "setattr"
                    and _dotted(call.func.value) in trusted_patchers
                )

            def _helper_bindings(
                self,
                helper: ast.FunctionDef | ast.AsyncFunctionDef,
                call: ast.Call,
            ) -> tuple[dict[str, str], frozenset[str], frozenset[str]]:
                """Map caller binding provenance into a module-local helper."""
                parameters = [*helper.args.posonlyargs, *helper.args.args]
                parameter_names = [parameter.arg for parameter in parameters]
                arguments: dict[str, ast.expr] = {
                    name: value
                    for name, value in zip(parameter_names, call.args, strict=False)
                }
                arguments.update(
                    {
                        keyword.arg: keyword.value
                        for keyword in call.keywords
                        if keyword.arg is not None and keyword.arg in parameter_names
                    }
                )
                helper_aliases: dict[str, str] = {}
                helper_live: set[str] = set()
                helper_patchers: set[str] = set()
                for parameter, value in arguments.items():
                    source = _dotted(value)
                    resolved = _resolve_name(source, local_aliases)
                    if resolved:
                        helper_aliases[parameter] = resolved
                    if source in trusted_patchers:
                        helper_patchers.add(parameter)
                    if source in live_aliases or (
                        _is_sensitive_compositor(resolved) and resolved not in stubbed
                    ):
                        helper_live.add(parameter)
                return (
                    helper_aliases,
                    frozenset(helper_live),
                    frozenset(helper_patchers),
                )

            def visit_Call(self, call: ast.Call) -> None:  # noqa: N802
                call_name = _resolve_name(_dotted(call.func), local_aliases)
                # A monkeypatch declaration names a seam but does not execute it. Do
                # not descend into its replacement lambda and mistake setup for work;
                # remember the replaced binding so a subsequent stub call is not
                # misclassified as production composition.
                if self._is_trusted_setattr(call):
                    target = self._monkeypatch_target(call)
                    if target:
                        stubbed.add(target)
                    return
                raw_call_name = _dotted(call.func)
                captured_live = raw_call_name in live_aliases
                if _is_live_complete_composition(call, local_aliases) and (
                    captured_live or call_name not in stubbed
                ):
                    findings.append((call_name, call.lineno))
                helper_name = call_name.rsplit(".", 1)[-1]
                helper = functions.get(helper_name)
                if helper is not None and helper_name not in seen:
                    helper_aliases, helper_live, helper_patchers = (
                        self._helper_bindings(helper, call)
                    )
                    findings.extend(
                        inspect(
                            helper,
                            seen=seen | frozenset({helper_name}),
                            inherited_stubbed=frozenset(stubbed),
                            inherited_aliases=helper_aliases,
                            inherited_live_aliases=helper_live,
                            inherited_patchers=helper_patchers,
                        )
                    )
                self.generic_visit(call)

        visitor = _CallVisitor()
        for statement in node.body:
            visitor.visit(statement)
        return findings

    violations: list[_StructuralViolation] = []
    targets: list[tuple[ast.FunctionDef | ast.AsyncFunctionDef, str, bool]] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            targets.append(
                (node, node.name, _has_qualification_marker(node.decorator_list))
            )
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            class_qualified = _has_qualification_marker(node.decorator_list)
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    targets.append(
                        (
                            child,
                            f"{node.name}::{child.name}",
                            class_qualified
                            or _has_qualification_marker(child.decorator_list),
                        )
                    )

    for node, display_name, is_qualification in targets:
        if not node.name.startswith("test_") or is_qualification:
            continue
        patchers = (
            frozenset({"monkeypatch"})
            if any(argument.arg == "monkeypatch" for argument in node.args.args)
            else frozenset()
        )
        for call_name, line in inspect(
            node,
            seen=frozenset({node.name}),
            inherited_patchers=patchers,
        ):
            violations.append(_StructuralViolation(path, display_name, call_name, line))
    return violations


def _write_source(tmp_path: Path, source: str) -> Path:
    """Write one synthetic Python module used to qualify the structural scanner."""
    path = tmp_path / "test_sample.py"
    path.write_text(source, encoding="utf-8")
    return path


def _test_markers(path: Path) -> dict[str, set[str]]:
    """Return decorators for all top-level tests in one history-controlled file."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {
        node.name: {_decorator_name(value) for value in node.decorator_list}
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
    }


def _history_test_name(nodeid: str) -> str:
    """Extract the unparametrized function name from a pytest node id."""
    return nodeid.split("::")[-1].split("[", 1)[0]


def _governed_duration_tests() -> set[tuple[str, str]]:
    """Return report/API tests that must have duration-history coverage."""
    governed: set[tuple[str, str]] = set()
    for path in (API_TESTS, ORCHESTRATION_TESTS, SURFACE_TESTS, E2E_TESTS):
        relative_path = str(path.relative_to(REPO_ROOT))
        for test_name in _test_markers(path):
            if path == API_TESTS and not test_name.startswith("test_run_case_report_"):
                continue
            if (
                path == SURFACE_TESTS
                and test_name != "test_build_case_surface_projects_a_real_run"
            ):
                continue
            governed.add((relative_path, test_name))
    return governed


def test_test04_is_active_and_pins_the_assurance_boundary() -> None:
    """Keep TEST-04 explicit about retained assurance and prohibited claims."""
    with RULESET.open(encoding="utf-8", newline="") as handle:
        rules = {row["rule_id"]: row for row in csv.DictReader(handle)}

    rule = rules["TEST-04"]
    policy = " ".join((rule["title"], rule["description"], rule["enforcement"]))
    assert rule["status"] == "active"
    for required in (
        "deterministic",
        "representative live",
        "report_qualification",
        "supplemental-sensitivity",
        "PDF",
        "Python 3.12",
        "bankability",
        "release evidence",
    ):
        assert required.lower() in policy.lower()


def test_report_policy_is_strict_and_fail_closed(tmp_path: Path) -> None:
    """Validate the CESSPIT policy and reject undeclared execution switches."""
    policy = _load_report_test_policy()
    assert policy.api_transport_context == "deterministic_known_context"
    assert policy.renderer_context == "deterministic_known_context"
    assert policy.representative_live_e2e_required is True
    assert policy.claim_classification == "regression_and_coverage_only"
    assert policy.qualification_test_mode == "qualification"
    assert policy.qualification_marker == "report_qualification"
    assert set(policy.required_live_paths) == {
        "supplemental_sensitivity",
        "pdf_backend",
    }
    assert policy.duration_review_threshold_seconds == 5.0

    raw = yaml.safe_load(REPORT_TEST_POLICY_PATH.read_text(encoding="utf-8"))
    raw["ordinary_suite"]["silent_live_sweep"] = True
    bad = tmp_path / "bad_report_policy.yaml"
    bad.write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(ValueError, match=r"unknown=\['silent_live_sweep'\]"):
        _load_report_test_policy(bad)


def test_transport_tests_use_the_typed_orchestration_and_pdf_preflight_seams() -> None:
    """Response-only tests must not rerun finance or supplemental sensitivity."""
    names = (
        "test_run_case_report_html_renders",
        "test_run_case_report_pdf_503_without_weasyprint",
        "test_run_case_report_pdf_success_path",
    )
    for name in names:
        source = _function_source(API_TESTS, name)
        assert 'monkeypatch.setattr(api_main, "_build_report_context"' in source
        assert "pytest.mark.slow" not in _decorators(API_TESTS, name)

    missing = _function_source(
        API_TESTS, "test_run_case_report_pdf_503_without_weasyprint"
    )
    assert "ReportDependencyError" in missing
    assert 'monkeypatch.setattr(api_main, "require_pdf_backend"' in missing
    assert 'monkeypatch.setattr(api_main, "render_report_pdf"' not in missing
    assert 'calls == ["pdf_preflight"]' in missing

    validation = _function_source(
        API_TESTS, "test_run_case_report_html_maps_validation_error_to_400"
    )
    assert 'monkeypatch.setattr(api_main, "run_report_case"' in validation
    for name in (
        "test_run_case_report_html_renders",
        "test_run_case_report_html_maps_validation_error_to_400",
        "test_run_case_report_pdf_503_without_weasyprint",
        "test_run_case_report_pdf_success_path",
    ):
        assert (
            'monkeypatch.setattr(api_main, "run_finance_case"'
            not in _function_source(API_TESTS, name)
        )


def test_complete_live_matrix_remains_one_explicit_qualification_test() -> None:
    """Pin tornado, Morris, PAWN, HTML, and PDF to one production context."""
    assert "pytest.mark.report_qualification" in _decorators(
        E2E_TESTS, _QUALIFICATION_TEST
    )
    source = _function_source(E2E_TESTS, _QUALIFICATION_TEST)
    for required in (
        "run_report_case",
        "compute_report_sensitivity",
        "PRODUCTION_REPORT_SENSITIVITY_PROFILE",
        "build_report_context_from_case",
        'metadata["tornado"]',
        'metadata["morris"]',
        'metadata["pawn"]',
        "render_report_html(ctx)",
        "render_report_pdf(ctx)",
        'b"%PDF-"',
    ):
        assert required in source
    assert source.count("compute_report_sensitivity(") == 1
    assert source.count("build_report_context_from_case(") == 1


def test_unmarked_complete_report_composition_is_rejected_repo_wide() -> None:
    """Reject live full composition anywhere in ordinary repository tests."""
    violations = [
        violation
        for path in sorted((REPO_ROOT / "tests").rglob("test_*.py"))
        for violation in _structural_violations(path)
    ]
    assert not violations, "\n".join(violation.display() for violation in violations)


def test_structural_scan_follows_helpers_and_aliases(tmp_path: Path) -> None:
    """Qualify transitive, module-local, and function-local alias detection."""
    path = _write_source(
        tmp_path,
        """
from app.reports.report_orchestration import compute_report_sensitivity as compose

def _helper(scenario):
    return compose(scenario)

alias = _helper

def test_unmarked():
    alias({})

class TestClassComposition:
    def test_method(self):
        alias({})

def test_function_local_assignment():
    local_compose = compose
    local_compose({})

def test_function_local_import():
    from app.reports.report_orchestration import compute_report_sensitivity as local
    local({})
""",
    )
    violations = _structural_violations(path)
    assert len(violations) == 4
    assert {violation.test_name for violation in violations} == {
        "test_unmarked",
        "TestClassComposition::test_method",
        "test_function_local_assignment",
        "test_function_local_import",
    }
    assert all(
        violation.call_name.endswith("compute_report_sensitivity")
        for violation in violations
    )


def test_structural_scan_accepts_marked_bounded_and_monkeypatched_paths(
    tmp_path: Path,
) -> None:
    """Avoid false positives for explicit qualification, bounded calls, and patches."""
    path = _write_source(
        tmp_path,
        """
import pytest
import app.api.main as api_main
from app.reports.report_orchestration import (
    ORDINARY_REPORT_SENSITIVITY_PROFILE,
    compute_report_sensitivity,
)

@pytest.mark.report_qualification
def test_marked():
    api_main._build_report_context(object())

def test_bounded():
    compute_report_sensitivity({}, profile=ORDINARY_REPORT_SENSITIVITY_PROFILE)

def test_patch_only(monkeypatch):
    monkeypatch.setattr(api_main, "_build_report_context", lambda _inputs: object())
    api_main._build_report_context(object())

def test_patch_alias(monkeypatch):
    mp = monkeypatch
    mp.setattr(api_main, "_build_report_context", lambda _inputs: object())
    api_main._build_report_context(object())

def test_post_patch_alias(monkeypatch):
    monkeypatch.setattr(api_main, "_build_report_context", lambda _inputs: object())
    stubbed_builder = api_main._build_report_context
    stubbed_builder(object())

def _patched_helper(patcher, inputs):
    patcher.setattr(api_main, "_build_report_context", lambda _inputs: object())
    api_main._build_report_context(inputs)

def test_real_patch_propagates_to_helper(monkeypatch):
    _patched_helper(monkeypatch, object())
""",
    )
    assert _structural_violations(path) == []


def test_structural_scan_rejects_prepatch_aliases_and_fake_setattr(
    tmp_path: Path,
) -> None:
    """Preserve capture time and trust only the pytest monkeypatch fixture."""
    path = _write_source(
        tmp_path,
        """
import app.api.main as api_main

module_live = api_main._build_report_context

class NoOp:
    def setattr(self, *_args):
        return None

def test_module_prepatch_alias(monkeypatch):
    monkeypatch.setattr(api_main, "_build_report_context", lambda _inputs: object())
    module_live(object())

def test_local_prepatch_alias(monkeypatch):
    live = api_main._build_report_context
    monkeypatch.setattr(api_main, "_build_report_context", lambda _inputs: object())
    live(object())

def test_fake_setattr():
    fake = NoOp()
    fake.setattr(api_main, "_build_report_context", lambda _inputs: object())
    api_main._build_report_context(object())

def _fake_helper(patcher, inputs):
    patcher.setattr(api_main, "_build_report_context", lambda _inputs: object())
    api_main._build_report_context(inputs)

def test_fake_patcher_does_not_gain_helper_trust():
    _fake_helper(NoOp(), object())
""",
    )

    violations = _structural_violations(path)
    assert len(violations) == 4
    assert {violation.test_name for violation in violations} == {
        "test_module_prepatch_alias",
        "test_local_prepatch_alias",
        "test_fake_setattr",
        "test_fake_patcher_does_not_gain_helper_trust",
    }


def test_representative_http_e2e_uses_real_auth_and_only_typed_sensitivity_stub() -> (
    None
):
    """Keep one ordinary auth/token/HTTP/live-finance path with a bounded seam."""
    source = _function_source(
        E2E_TESTS, "test_lender_report_renders_through_the_auth_gated_http_route"
    )
    assert '"/v1/token"' in source
    assert '"Authorization": f"Bearer {token}"' in source
    assert "hash_password" in source
    assert "dependency_overrides" not in source
    assert 'api_main, "compute_report_sensitivity"' in source
    assert 'monkeypatch.setattr(api_main, "_build_report_context"' not in source
    assert 'monkeypatch.setattr(api_main, "run_finance_case"' not in source
    assert "pytest.mark.report_qualification" not in _decorators(
        E2E_TESTS, "test_lender_report_renders_through_the_auth_gated_http_route"
    )


def test_duration_history_applies_five_second_review_only_to_ordinary_tests() -> None:
    """Require written ordinary exceptions and separate real qualification evidence."""
    policy = _load_report_test_policy()
    history_raw = json.loads(DURATION_HISTORY.read_text(encoding="utf-8"))
    assert isinstance(history_raw, dict)
    history = {
        str(nodeid): float(seconds)
        for nodeid, seconds in history_raw.items()
        if str(nodeid).startswith(_REPORT_DURATION_PREFIXES)
    }
    exceptions = dict(policy.ordinary_duration_exceptions)
    marker_cache: dict[Path, dict[str, set[str]]] = {}
    ordinary_over_budget: set[str] = set()
    history_coverage = {
        (nodeid.split("::", 1)[0], _history_test_name(nodeid)) for nodeid in history
    }

    missing_history = _governed_duration_tests() - history_coverage
    assert not missing_history, (
        "governed report/API tests missing from .test_durations: "
        f"{sorted(missing_history)}"
    )

    for nodeid, seconds in history.items():
        relative_path = nodeid.split("::", 1)[0]
        path = REPO_ROOT / relative_path
        markers = marker_cache.setdefault(path, _test_markers(path))
        is_qualification = any(
            marker.endswith(".report_qualification")
            for marker in markers.get(_history_test_name(nodeid), set())
        )
        if not is_qualification and seconds > policy.duration_review_threshold_seconds:
            ordinary_over_budget.add(nodeid)

    assert ordinary_over_budget == set(exceptions)
    for nodeid, reason in exceptions.items():
        assert nodeid in history
        assert reason.strip()

    evidence = policy.qualification_duration_evidence
    assert evidence.nodeid in history
    assert evidence.profile == policy.production_sensitivity_profile.name
    assert evidence.outcome == "passed"
    assert evidence.observed_scope == "pytest_session"
    assert evidence.observed_seconds is not None
    assert evidence.observed_seconds > 0.0
    # Qualification entries are tiny scheduler weights in .test_durations; they are
    # not masquerading as observed end-to-end timing evidence.
    assert history[evidence.nodeid] < policy.duration_review_threshold_seconds
    assert evidence.observed_seconds != history[evidence.nodeid]
    assert evidence.measured_at != "pending_final_validation"


def test_issue1072_warning_routing_and_finance_refusals_remain_ordinary() -> None:
    """Keep the frozen provenance firewall in the always-run regression profile."""
    expected_warning = (
        "based on synthetic data - non-bankable - only for process provenance purposes"
    )
    assert SYNTHETIC_PROCESS_PROVENANCE_WARNING == expected_warning

    pinned: tuple[tuple[Path, Iterable[str]], ...] = (
        (
            REPO_ROOT / "tests" / "app" / "test_grid_screening_emit.py",
            (
                "test_executed_synthetic_curtailment_is_presented_with_structural_warning",
                "test_synthetic_warning_cannot_be_suppressed_by_config",
                "test_emit_routes_synthetic_qsts_to_segregated_output_namespace",
                "test_emit_refuses_synthetic_output_with_lender_token",
            ),
        ),
        (
            REPO_ROOT / "tests" / "finance" / "test_self_curtailment_finance.py",
            (
                "test_wiring_disabled_by_default_and_on_committed_lendercase",
                "test_resolver_refuses_synthetic_result_even_when_finance_flag_is_on",
            ),
        ),
    )
    for path, names in pinned:
        for name in names:
            assert "pytest.mark.report_qualification" not in _decorators(path, name)


def test_local_and_python312_ci_qualification_targets_are_explicit() -> None:
    """Pin the separate local, scheduled/manual, and release report gates."""
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
    workflow = (REPO_ROOT / ".github/workflows/test-suite.yml").read_text(
        encoding="utf-8"
    )
    release = (REPO_ROOT / ".github/workflows/release-run.yml").read_text(
        encoding="utf-8"
    )

    assert "test-report-qualification:" in makefile
    assert "DUTCHBAY_TEST_MODE=qualification $(PYTEST)" in makefile
    assert "-n 2 tests/integration/test_lender_report_e2e.py" in makefile
    assert "-m report_qualification" in makefile
    assert "report-qualification:" in workflow
    assert "Report Qualification (Python 3.12, scheduled/manual)" in workflow
    assert 'python-version: "3.12"' in workflow
    assert "-n 2 tests/integration/test_lender_report_e2e.py" in workflow
    assert "-m report_qualification" in workflow
    assert "Run report qualification tests" in release
    assert "DUTCHBAY_TEST_MODE: qualification" in release
    assert "-n 2 tests/integration/test_lender_report_e2e.py" in release
    assert "-m report_qualification" in release
