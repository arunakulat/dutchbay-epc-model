"""VERIFY-01 guard: the security gate audits the whole lock, and main reports its own state.

Two independent blind spots in the dependency audit, both measured at the objects on
2026-10-25 against ``main`` ``9b2b51e0`` before anything was changed.

**1. Two lock pins were never audited.** ``make security`` ran a single
``pip-audit -r requirements.txt``. In that mode pip-audit builds a temporary virtual
environment and audits what ``pip install --dry-run --report`` says it would install -
transitive packages included, which is why an unpinned ``cloudpickle`` was audited all along
(see #1387). But ``VirtualEnv.post_setup`` runs ``pip install --upgrade pip wheel setuptools``
inside that environment *before* the resolve, and that prologue lands ``packaging`` and
``wheel`` at exactly the versions this lock pins. pip therefore reports neither as
to-install, and pip-audit audited 310 of 312 pins: ``packaging==26.3`` and ``wheel==0.48.0``
were invisible to the gate. Nobody excluded them. The auditor's own environment hid them, and
the omission is version-coincidental - it would appear and disappear as upstream moved, with
nothing announcing either way. ``--no-deps --disable-pip`` takes pip-audit's pre-resolved
path, skips the environment and audits all 312.

**2. Nothing reported main's own audit state between Mondays.** ``Security Scan`` in
``test-suite.yml`` runs on ``pull_request`` and on that workflow's weekly Monday schedule,
never on a push to ``main``. The last scheduled run before 2026-10-25 was Monday 2026-10-19
(run 39226566738, ``8c4d0761``, success). Seven advisories landed against the UNCHANGED lock
on 2026-10-23/24 and the next run was not due until Monday 2026-10-26. The gate audits the
whole lock rather than the diff, so the only signal was every open pull request going red at
once, arriving as though it were somebody's change.

What this module pins is the REMEDY, not the measurements: both audit passes present and
sharing one suppression list, ``make audit`` left as the canonical single-command spelling,
and a daily main-branch workflow running the same ``make security``. It cannot re-measure
coverage - that needs the network and a resolve - so the numbers above stay in the pull
request's receipts and in the ``Makefile``'s own comment, where a reviewer reads them.

Per VERIFY-01(5) every assertion here ships the negative control that observes it firing: the
checks are pure functions over text, exercised against mutated copies rather than trusted. 22
controls, 7 over the ``Makefile`` and 15 over the workflow.

That claim was once wider than the set. #1388's independent domain lane probed
``audit_workflow`` key by key and found six shapes it passed: ``continue-on-error: true`` on
the job or on the gate step, and an ``if:`` on either — ``if: false`` or a real condition like
``if: github.event_name == 'push'``, which honours the triggers in the YAML and silences the
daily run they promise, while every other assertion here stays green. ``continue-on-error``
was worse than silence: it would let a RED audit report success, so the status on ``main``
would say the opposite of what it measured. Both are now rejected, each with the lane's own
probe as its control. The ``Makefile`` half had a backstop the workflow half cannot have —
``test_make_expansion_agrees_with_the_makefile_source`` re-runs ``make -n security``, which
catches a ``|| true`` or an appended weaker target that the text function alone would pass;
a workflow has no ``make -n`` to interrogate, so its shapes must be named here explicitly.
"""

from __future__ import annotations

import importlib
import inspect
import re
import shlex
import subprocess
import tempfile
import warnings
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
MAKEFILE = REPO_ROOT / "Makefile"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "security-audit.yml"
TEST_SUITE_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "test-suite.yml"

LOCK = "requirements.txt"
ALLOWLIST = "$(PIP_AUDIT_IGNORES)"
RESOLVE_RECIPE = f"pip-audit -r {LOCK} {ALLOWLIST}"
DECLARED_RECIPE = f"pip-audit --no-deps --disable-pip -r {LOCK} {ALLOWLIST}"
# The two pins resolve mode omitted, and the flags that make them visible again.
DECLARED_FLAGS = ("--no-deps", "--disable-pip")
UNAUDITED_IN_RESOLVE_MODE = ("packaging", "wheel")
# PyYAML parses a bare `on:` key as the boolean True (YAML 1.1 truthiness).
ON_KEYS = (True, "on")

# A parsed workflow is genuinely heterogeneous - PyYAML hands back a bool for the `on`
# key alongside string keys - so the mapping is not narrowable to anything useful.
Workflow = dict[Any, Any]


def _recipe(makefile_text: str, target: str) -> list[str]:
    """Return the recipe lines of ``target`` as written in the Makefile."""
    lines = makefile_text.splitlines()
    recipe: list[str] = []
    for index, line in enumerate(lines):
        if not re.match(rf"^{re.escape(target)}\s*:(?!=)", line):
            continue
        for candidate in lines[index + 1 :]:
            if candidate.startswith("\t"):
                recipe.append(candidate[1:].strip())
            elif candidate.strip():
                break
        return recipe
    return []


def audit_makefile(makefile_text: str) -> list[str]:
    """Return one message per security-coverage violation; empty means compliant."""
    violations: list[str] = []

    security = _recipe(makefile_text, "security")
    if not security:
        violations.append("Makefile: no `security` target recipe found")
    bandit = [line for line in security if line.startswith("bandit ")]
    if not bandit:
        violations.append("`security` must still run the bandit SAST pass")

    pip_audits = [line for line in security if line.startswith("pip-audit ")]
    resolve = [
        line for line in pip_audits if not any(f in line for f in DECLARED_FLAGS)
    ]
    declared = [
        line for line in pip_audits if all(flag in line for flag in DECLARED_FLAGS)
    ]
    if len(resolve) != 1:
        violations.append(
            "`security` must run exactly one resolve-mode pass "
            f"(`{RESOLVE_RECIPE}`), got {resolve!r}"
        )
    if len(declared) != 1:
        violations.append(
            "`security` must run the declared-pin pass "
            f"(`{DECLARED_RECIPE}`) so `packaging` and `wheel` are audited, got "
            f"{declared!r}"
        )
    for line in pip_audits:
        if ALLOWLIST not in line:
            violations.append(
                f"every audit pass must carry {ALLOWLIST} so a suppression cannot hold "
                f"in one mode and not the other, got {line!r}"
            )
        if f"-r {LOCK}" not in line:
            violations.append(f"audit pass must read {LOCK}, got {line!r}")

    # `make audit` stays the canonical one-command spelling of the effective suppression
    # set. #1386 proposes a SECDEP-01 fence that reads `make -n audit` as its oracle, and
    # added coverage belongs in `audit-declared`, so a second line or an extra flag here is
    # a violation even though it would widen coverage.
    alias = _recipe(makefile_text, "audit")
    if alias != [RESOLVE_RECIPE]:
        violations.append(
            f"`audit` must stay exactly [{RESOLVE_RECIPE!r}], got {alias!r}"
        )

    declared_alias = _recipe(makefile_text, "audit-declared")
    if declared_alias != [DECLARED_RECIPE]:
        violations.append(
            f"`audit-declared` must be exactly [{DECLARED_RECIPE!r}], got "
            f"{declared_alias!r}"
        )

    phony = next(
        (line for line in makefile_text.splitlines() if line.startswith(".PHONY:")), ""
    )
    for target in ("security", "audit", "audit-declared"):
        if target not in phony.split():
            violations.append(f".PHONY must list `{target}`")

    return violations


def audit_workflow(workflow: Workflow) -> list[str]:
    """Return one message per main-branch-reporting violation; empty means compliant."""
    violations: list[str] = []

    triggers = next(
        (workflow[key] for key in ON_KEYS if key in workflow),
        None,
    )
    if not isinstance(triggers, dict):
        return ["security-audit.yml: no `on:` trigger mapping"]

    push = triggers.get("push")
    # `main` must be among the pushed branches. Deliberately not exact equality: adding
    # `release/*` later is legitimate and should not red this guard, while dropping
    # `main` — the branch whose audit state is the point — still fails closed.
    branches = push.get("branches") if isinstance(push, dict) else None
    if not isinstance(branches, list) or "main" not in branches:
        violations.append(
            "must trigger on `push` to `main` so main carries its own audit status, got "
            f"{push!r}"
        )

    schedule = triggers.get("schedule")
    if not isinstance(schedule, list) or not schedule:
        violations.append(
            "must carry a `schedule`: the weekly Test Suite cron is the window seven "
            f"advisories landed in unnoticed, got {schedule!r}"
        )
    else:
        for entry in schedule:
            cron = entry.get("cron") if isinstance(entry, dict) else None
            fields = str(cron).split()
            if len(fields) != 5:
                violations.append(f"malformed cron {cron!r}")
                continue
            # Day-of-month, month and day-of-week must all be unrestricted, or the run is
            # not daily and the blind window reopens.
            if fields[2:] != ["*", "*", "*"]:
                violations.append(
                    f"schedule must run DAILY - weekly was the gap - got {cron!r}"
                )

    if "workflow_dispatch" not in triggers:
        violations.append("must allow `workflow_dispatch` for an on-demand re-check")

    if "pull_request" in triggers:
        violations.append(
            "must NOT trigger on `pull_request`: `Security Scan` already gates every "
            "pull request, and a second audit check there duplicates the required one"
        )

    jobs = workflow.get("jobs")
    if not isinstance(jobs, dict) or not jobs:
        return [*violations, "security-audit.yml: no jobs"]

    # Locate the gate step with its job. Exact equality, so `make security || true` and
    # any reduced variant are not the gate.
    gate_steps = [
        (job, step)
        for job in jobs.values()
        if isinstance(job, dict)
        for step in (job.get("steps") or [])
        if isinstance(step, dict) and step.get("run", "").strip() == "make security"
    ]
    if not gate_steps:
        violations.append(
            "must run `make security` itself, not a reduced variant: a weaker audit on "
            "main than on a pull request reports green on bytes the gate would reject"
        )

    # A conditional or non-failing audit is not an audit. Without these, the triggers
    # above can be honoured in the YAML and neutered in the job: `if: false` or
    # `if: github.event_name == 'push'` silences the daily run the triggers promise,
    # and `continue-on-error: true` lets a RED audit report success — which would make
    # the status on `main` say the opposite of what it measured. Both shapes leave every
    # other assertion here passing, so the pinned remedy could be undone in silence.
    for owner, holder in (("job", 0), ("step", 1)):
        for gate in gate_steps:
            node = gate[holder]
            if "if" in node and str(node["if"]).strip().lower() not in {
                "true",
                "${{ true }}",
            }:
                violations.append(
                    f"the `make security` {owner} must not be conditional — an `if:` can "
                    f"silence the daily run the triggers promise, got {node['if']!r}"
                )
            if node.get("continue-on-error") in (True, "true"):
                violations.append(
                    f"the `make security` {owner} must not set `continue-on-error` — a "
                    "red audit would report success on main"
                )

    names = {job.get("name") for job in jobs.values() if isinstance(job, dict)}
    if "Security Scan" in names:
        violations.append(
            "job name must differ from test-suite.yml's `Security Scan`, which is the "
            "required merge gate"
        )

    return violations


def _make_commands(target: str) -> list[list[str]]:
    """Return GNU Make's effective commands for ``target``, as argv lists."""
    completed = subprocess.run(
        ["make", "--no-print-directory", "-n", target],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [
        shlex.split(line.strip())
        for line in completed.stdout.splitlines()
        if line.strip()
    ]


def _workflow() -> Workflow:
    loaded: Workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    return loaded


def test_the_live_security_gate_audits_every_pin_in_the_lock() -> None:
    """The real Makefile must run both coverage modes over the same allowlist."""
    assert audit_makefile(MAKEFILE.read_text(encoding="utf-8")) == []


def test_main_reports_its_own_audit_state() -> None:
    """The real workflow must put a daily audit status on main."""
    assert WORKFLOW.is_file(), f"missing {WORKFLOW}"
    assert audit_workflow(_workflow()) == []


def test_make_expansion_agrees_with_the_makefile_source() -> None:
    """GNU Make's effective commands, not just the source text, carry both passes."""
    security = _make_commands("security")
    assert len(security) == 3, security
    assert security[0][0] == "bandit"
    assert security[1][:3] == ["pip-audit", "-r", LOCK]
    assert security[2][0] == "pip-audit"
    assert set(DECLARED_FLAGS) <= set(security[2])
    assert security[2][-2:] == ["-r", LOCK]

    # The alias stays a single unflagged command; `make -n audit` is SECDEP-01's oracle.
    assert _make_commands("audit") == [["pip-audit", "-r", LOCK]]
    declared = _make_commands("audit-declared")
    assert len(declared) == 1
    assert set(DECLARED_FLAGS) <= set(declared[0])


def test_the_merge_gate_and_the_main_audit_run_the_same_command() -> None:
    """Both workflows must invoke `make security`, so neither can drift weaker."""
    test_suite = TEST_SUITE_WORKFLOW.read_text(encoding="utf-8")
    assert "run: make security" in test_suite
    assert "run: make security" in WORKFLOW.read_text(encoding="utf-8")


def test_declared_mode_really_audits_the_pins_resolve_mode_skips() -> None:
    """Oracle: the two flags we rely on select pip-audit's pre-resolved path.

    Hermetic - no network, no resolve. It proves the flags change the mode and that the
    two pins resolve mode omitted are collected under it.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        pip_audit_cli = importlib.import_module("pip_audit._cli")
    parsed = pip_audit_cli._parser().parse_args([*DECLARED_FLAGS, "-r", LOCK])
    assert parsed.no_deps is True
    assert parsed.disable_pip is True

    from pip_audit._dependency_source.requirement import RequirementSource

    with tempfile.TemporaryDirectory() as tmp:
        requirements = Path(tmp) / "requirements.txt"
        requirements.write_text("packaging==26.3\nwheel==0.48.0\n", encoding="utf-8")
        source = RequirementSource([requirements], no_deps=True, disable_pip=True)
        collected = {dependency.name for dependency in source.collect()}
    assert set(UNAUDITED_IN_RESOLVE_MODE) <= collected


def test_the_documented_reason_resolve_mode_skips_those_pins_still_holds() -> None:
    """Oracle: pip-audit's venv prologue is why `packaging` and `wheel` were invisible.

    ``pip_audit`` is a pinned lock entry, so this only moves on a deliberate bump - which
    is exactly when the coverage measurement in the Makefile comment needs re-taking.
    """
    from pip_audit._virtual_env import VirtualEnv

    prologue = inspect.getsource(VirtualEnv.post_setup)
    missing = [
        token
        for token in ('"--upgrade"', '"pip"', '"wheel"', '"setuptools"')
        if token not in prologue
    ]
    assert not missing, (
        "pip-audit no longer upgrades pip/wheel/setuptools inside its temporary "
        f"environment (missing {missing}). That prologue is the documented reason resolve "
        "mode omitted `packaging` and `wheel`. Re-measure both passes against the current "
        "lock and update the Makefile's `security` comment before trusting it."
    )


# --------------------------------------------------------------------------------------
# Negative controls. Every assertion above is observed failing on a mutated copy, rather
# than assumed to be load-bearing (VERIFY-01(5)).
# --------------------------------------------------------------------------------------

_LIVE_MAKEFILE = MAKEFILE.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        pytest.param(
            lambda text: text.replace(f"\t{DECLARED_RECIPE}\n", "", 1),
            "declared-pin pass",
            id="declared pass dropped from security",
        ),
        pytest.param(
            lambda text: text.replace(f"\t{RESOLVE_RECIPE}\n\t{DECLARED_RECIPE}", ""),
            "resolve-mode pass",
            id="both audit passes dropped",
        ),
        pytest.param(
            lambda text: text.replace(
                f"\t{DECLARED_RECIPE}\n\n# Convenience",
                "\tpip-audit --no-deps --disable-pip -r requirements.txt\n\n# Convenience",
                1,
            ),
            "must carry $(PIP_AUDIT_IGNORES)",
            id="declared pass loses the shared allowlist",
        ),
        pytest.param(
            lambda text: text.replace(
                f"audit:\n\t{RESOLVE_RECIPE}",
                f"audit:\n\t{RESOLVE_RECIPE}\n\t{DECLARED_RECIPE}",
                1,
            ),
            "`audit` must stay exactly",
            id="coverage smuggled into the SECDEP-01 oracle target",
        ),
        pytest.param(
            lambda text: text.replace(f"audit-declared:\n\t{DECLARED_RECIPE}\n", "", 1),
            "`audit-declared` must be exactly",
            id="declared alias removed",
        ),
        pytest.param(
            lambda text: text.replace(
                "bandit -c pyproject.toml", "# bandit -c pyproject.toml", 1
            ),
            "bandit SAST pass",
            id="bandit pass commented out",
        ),
        pytest.param(
            lambda text: text.replace(" audit-declared test", " test", 1),
            ".PHONY must list `audit-declared`",
            id="target left off PHONY",
        ),
    ],
)
def test_the_makefile_guard_rejects_narrowed_coverage(
    mutation: object, expected: str
) -> None:
    violations = audit_makefile(mutation(_LIVE_MAKEFILE))  # type: ignore[operator]
    assert violations, "the guard passed a narrowed security gate"
    assert any(expected in violation for violation in violations), violations


def _without(key: object) -> Workflow:
    workflow = _workflow()
    triggers = dict(next(workflow[k] for k in ON_KEYS if k in workflow))
    triggers.pop(key, None)
    for k in ON_KEYS:
        if k in workflow:
            workflow[k] = triggers
    return workflow


def _with_trigger(key: object, value: object) -> Workflow:
    workflow = _workflow()
    triggers = dict(next(workflow[k] for k in ON_KEYS if k in workflow))
    triggers[key] = value
    for k in ON_KEYS:
        if k in workflow:
            workflow[k] = triggers
    return workflow


def _mutate_job(**changes: Any) -> Workflow:
    workflow = _workflow()
    jobs = {name: {**job, **changes} for name, job in workflow["jobs"].items()}
    workflow["jobs"] = jobs
    return workflow


def _mutate_gate_step(**changes: Any) -> Workflow:
    """Apply ``changes`` to the step that runs `make security`, leaving the rest alone."""
    workflow = _workflow()
    for job in workflow["jobs"].values():
        job["steps"] = [
            (
                {**step, **changes}
                if step.get("run", "").strip() == "make security"
                else step
            )
            for step in job["steps"]
        ]
    return workflow


@pytest.mark.parametrize(
    ("workflow_factory", "expected"),
    [
        pytest.param(
            lambda: _without("schedule"),
            "must carry a `schedule`",
            id="schedule removed",
        ),
        pytest.param(
            lambda: _with_trigger("schedule", [{"cron": "17 3 * * 1"}]),
            "must run DAILY",
            id="schedule relaxed back to weekly",
        ),
        pytest.param(
            lambda: _without("push"),
            "must trigger on `push` to `main`",
            id="push to main removed",
        ),
        pytest.param(
            lambda: _with_trigger("push", {"branches": ["develop"]}),
            "must trigger on `push` to `main`",
            id="push pointed away from main",
        ),
        pytest.param(
            lambda: _without("workflow_dispatch"),
            "workflow_dispatch",
            id="manual re-check removed",
        ),
        pytest.param(
            lambda: _with_trigger("pull_request", {"branches": ["main"]}),
            "must NOT trigger on `pull_request`",
            id="duplicates the required pull-request gate",
        ),
        pytest.param(
            lambda: _mutate_job(steps=[{"name": "Weaker audit", "run": "make audit"}]),
            "must run `make security`",
            id="main audits less than the merge gate",
        ),
        pytest.param(
            lambda: _mutate_job(name="Security Scan"),
            "must differ from test-suite.yml's `Security Scan`",
            id="name collides with the required check",
        ),
        # F-2 on #1388: the six shapes the domain lane probed and found this guard
        # passing. Each one honours the triggers in the YAML and neuters the run.
        pytest.param(
            lambda: _mutate_job(**{"continue-on-error": True}),
            "job must not set `continue-on-error`",
            id="job continue-on-error lets a red audit report success",
        ),
        pytest.param(
            lambda: _mutate_gate_step(**{"continue-on-error": True}),
            "step must not set `continue-on-error`",
            id="step continue-on-error lets a red audit report success",
        ),
        pytest.param(
            lambda: _mutate_job(**{"if": False}),
            "job must not be conditional",
            id="job if false silences the whole audit",
        ),
        pytest.param(
            lambda: _mutate_job(**{"if": "github.event_name == 'push'"}),
            "job must not be conditional",
            id="job if drops the daily schedule",
        ),
        pytest.param(
            lambda: _mutate_gate_step(
                **{"if": "github.event_name == 'workflow_dispatch'"}
            ),
            "step must not be conditional",
            id="step if drops the daily schedule",
        ),
        pytest.param(
            lambda: _mutate_gate_step(**{"if": False}),
            "step must not be conditional",
            id="gate step if false silences the audit",
        ),
        pytest.param(
            lambda: _mutate_gate_step(run="make security || true"),
            "must run `make security` itself",
            id="gate swallowed by a shell or-true",
        ),
    ],
)
def test_the_workflow_guard_rejects_a_reopened_blind_spot(
    workflow_factory: object, expected: str
) -> None:
    violations = audit_workflow(workflow_factory())  # type: ignore[operator]
    assert violations, "the guard passed a workflow that reopens the gap"
    assert any(expected in violation for violation in violations), violations


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
