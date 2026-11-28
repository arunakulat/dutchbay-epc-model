"""Lint controls for #1413: pinned security-gate tooling, invocation surface, and ruleset note."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml
from packaging.utils import canonicalize_name

REPO_ROOT = Path(__file__).resolve().parents[2]
SECURITY_AUDIT_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "security-audit.yml"
TEST_SUITE_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "test-suite.yml"
TOOLING_PINS_FILE = REPO_ROOT / ".github" / "requirements-security-tooling.txt"
LOCK_FILE = REPO_ROOT / "requirements.txt"
RULESET_DOC = REPO_ROOT / "docs" / "governance" / "security_gate_ruleset_dependency.md"

EXPECTED_TOOLING_REF = ".github/requirements-security-tooling.txt"
EXPECTED_CONSTRAINT = "-c ../requirements.txt"
REQUIRED_TOOLS = ("bandit", "pip-audit")


def _parse_lock_pins(lock_text: str) -> dict[str, str]:
    """Return canonicalized exact ``==`` pins from ``requirements.txt``."""
    pins: dict[str, str] = {}
    for raw_line in lock_text.splitlines():
        cleaned = raw_line.split("#", 1)[0].strip()
        if not cleaned or cleaned.startswith("-"):
            continue
        name, sep, version = cleaned.partition("==")
        if sep:
            pins[canonicalize_name(name)] = version.split(";", 1)[0].strip()
    return pins


def check_tooling_pins_surface(pins_text: str, lock_text: str) -> list[str]:
    """Validate that ``requirements-security-tooling.txt`` pins both tools to the lock."""
    violations: list[str] = []
    lines = [
        line.strip()
        for line in pins_text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if EXPECTED_CONSTRAINT not in lines:
        violations.append(
            f"Missing lock constraint `{EXPECTED_CONSTRAINT}` in {EXPECTED_TOOLING_REF}"
        )

    parsed_pins: dict[str, str] = {}
    for line in lines:
        if line.startswith("-"):
            continue
        name, sep, version = line.partition("==")
        if not sep or not re.fullmatch(r"[0-9][0-9A-Za-z.!+\-]*", version):
            violations.append(
                f"Unpinned or non-exact requirement `{line}` in {EXPECTED_TOOLING_REF}"
            )
            continue
        parsed_pins[canonicalize_name(name)] = version

    for tool in REQUIRED_TOOLS:
        canonical = canonicalize_name(tool)
        if canonical not in parsed_pins:
            violations.append(
                f"Missing exact pin for `{tool}` in {EXPECTED_TOOLING_REF}"
            )

    lock_pins = _parse_lock_pins(lock_text)
    for tool in REQUIRED_TOOLS:
        canonical = canonicalize_name(tool)
        if (
            canonical in parsed_pins
            and lock_pins.get(canonical) != parsed_pins[canonical]
        ):
            violations.append(
                f"{EXPECTED_TOOLING_REF} pins {tool}=={parsed_pins[canonical]} "
                f"but requirements.txt pins {lock_pins.get(canonical)}"
            )
    return violations


def check_workflow_security_surface(
    workflow_text: str, *, job_id: str, label: str
) -> list[str]:
    """Validate tooling installation and invocation surface for a security-gate job."""
    violations: list[str] = []
    data = yaml.safe_load(workflow_text)
    jobs = data.get("jobs", {})
    if job_id not in jobs:
        return [f"{label}: missing job `{job_id}`"]
    steps = jobs[job_id].get("steps", [])

    install_runs = [
        str(step.get("run", ""))
        for step in steps
        if isinstance(step, dict) and "pip install" in str(step.get("run", ""))
    ]
    if not any(f"-r {EXPECTED_TOOLING_REF}" in run for run in install_runs):
        violations.append(
            f"{label}: job `{job_id}` must install from `-r {EXPECTED_TOOLING_REF}`"
        )
    for run in install_runs:
        for line in run.splitlines():
            stripped = line.strip()
            if "pip install" in stripped and EXPECTED_TOOLING_REF not in stripped:
                if re.search(r"\b(bandit|pip-audit)\b", stripped):
                    violations.append(
                        f"{label}: unpinned or direct pip install of security tooling: `{stripped}`"
                    )

    gate_runs = [
        str(step.get("run", "")).strip()
        for step in steps
        if isinstance(step, dict)
        and "make" in str(step.get("run", ""))
        and "security" in str(step.get("run", ""))
    ]
    if gate_runs != ["make security"]:
        violations.append(
            f"{label}: job `{job_id}` must invoke exact `make security`, got {gate_runs!r}"
        )
    return violations


def test_committed_tooling_pins_match_lock() -> None:
    """Committed tooling pins must be exact and match requirements.txt."""
    violations = check_tooling_pins_surface(
        TOOLING_PINS_FILE.read_text(encoding="utf-8"),
        LOCK_FILE.read_text(encoding="utf-8"),
    )
    assert not violations, "\n".join(violations)


@pytest.mark.parametrize(
    ("workflow_path", "job_id"),
    [
        (SECURITY_AUDIT_WORKFLOW, "audit"),
        (TEST_SUITE_WORKFLOW, "security"),
    ],
)
def test_committed_workflows_pin_tooling_and_invocation(
    workflow_path: Path, job_id: str
) -> None:
    """Both security-gate workflows must install pinned tooling and run exact `make security`."""
    violations = check_workflow_security_surface(
        workflow_path.read_text(encoding="utf-8"),
        job_id=job_id,
        label=workflow_path.name,
    )
    assert not violations, "\n".join(violations)


@pytest.mark.parametrize(
    "mutated_pins",
    [
        pytest.param(
            "-c ../requirements.txt\nbandit\npip-audit==2.10.1\n", id="unpinned-bandit"
        ),
        pytest.param(
            "-c ../requirements.txt\nbandit==1.9.4\npip-audit\n",
            id="unpinned-pip-audit",
        ),
        pytest.param(
            "-c ../requirements.txt\nbandit>=1.7\npip-audit==2.10.1\n",
            id="range-bandit",
        ),
        pytest.param(
            "-c ../requirements.txt\nbandit==1.9.4\npip-audit>=2.7\n",
            id="range-pip-audit",
        ),
        pytest.param(
            "bandit==1.9.4\npip-audit==2.10.1\n", id="missing-lock-constraint"
        ),
    ],
)
def test_negative_control_rejects_unpinned_tooling(mutated_pins: str) -> None:
    """Negative control: unpinned, range-pinned, or unconstrained tooling must fail loudly."""
    lock_text = LOCK_FILE.read_text(encoding="utf-8")
    violations = check_tooling_pins_surface(mutated_pins, lock_text)
    assert (
        violations
    ), "Expected tooling pin guard to reject unpinned/unconstrained spec"


@pytest.mark.parametrize(
    ("install_cmd", "gate_cmd"),
    [
        pytest.param(
            "pip install bandit pip-audit",
            "make security",
            id="unpinned-workflow-install",
        ),
        pytest.param(
            f"pip install -r {EXPECTED_TOOLING_REF}",
            "make -i security",
            id="make-ignore-errors",
        ),
        pytest.param(
            f"pip install -r {EXPECTED_TOOLING_REF}",
            "make security PIP_AUDIT_IGNORES=--ignore-vuln=GHSA-0000-0000-0000",
            id="make-ignores-override",
        ),
    ],
)
def test_negative_control_rejects_workflow_bypasses(
    install_cmd: str, gate_cmd: str
) -> None:
    """Negative control: unpinned workflow install or bypassed `make security` must fail loudly."""
    crafted = yaml.safe_dump(
        {
            "jobs": {
                "audit": {
                    "steps": [
                        {"run": install_cmd},
                        {"run": gate_cmd},
                    ]
                }
            }
        }
    )
    violations = check_workflow_security_surface(
        crafted, job_id="audit", label="crafted.yml"
    )
    assert (
        violations
    ), "Expected workflow guard to reject unpinned install or bypassed invocation"


def test_ruleset_17414541_dependency_recorded() -> None:
    """Governance doc must record ruleset 17414541 and its GitHub Actions integration binding."""
    text = RULESET_DOC.read_text(encoding="utf-8")
    assert "17414541" in text
    assert "15368" in text
    assert "Test Summary" in text
    assert "no in-tree test" in text.lower()
