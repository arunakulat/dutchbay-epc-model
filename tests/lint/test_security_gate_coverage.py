"""VERIFY-01 guard: the security gate audits the whole lock, and main reports its own state.

Three independent blind spots in the dependency audit. The first two were measured at the
objects on 2026-10-25 against ``main`` ``9b2b51e0``, the third on 2026-10-27 against the
gate's own job logs, each before anything was changed.

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

**3. The gate could answer from a cache and a single feed, and nothing showed it could
fail.** ``pip_audit._service.pypi``
builds its HTTP session with ``caching_session(cache_dir)``, taking the default
``use_pip=True``, which ``pip_audit._cache._get_cache_dir`` resolves to
``$(pip cache dir)/http``. Both jobs that run ``make security`` set
``actions/setup-python``'s ``cache: 'pip'``, so each audit read advisory responses out of a
restored cache whose key is the runner, the Python version and the lock hash - shared across
branches. On 2026-10-27 a cache saved at 16:50:20Z by job 122331742996, 18 minutes before
``GHSA-wf6j-7hvr-gr93`` published at 17:08:41Z, was restored byte-identical (31,413,483 B)
by five later runs, and the required gate reported a lock pinning the vulnerable
``hydra-core==1.3.7`` clean at 17:19:24Z (job 122348327291) two minutes after the same
workflow redded the same two lock lines (jobs 122346893695, 122347443951); another run
reported one of two live advisories (job 122353695670). The cause is NOT established: the
same restored bytes gave both answers, and PyPI-side consistency or edge caching, a partial
response accepted as complete, and runner egress remain open candidates beside the cache
(residual D-10 on #1353). So the rest of the remedy does not depend on the cache. A single
feed's answer, stale or partial for whatever reason, no longer decides the verdict alone,
because the OSV pass asks a different database and ``pip_audit._service.osv`` passes
``use_pip=False``; and a canary step makes every feed report two known advisories in the
same job before its clean verdict is trusted. Both jobs also installed ``bandit pip-audit``
UNPINNED, so the tool that decides a merge drifted with PyPI and its version reached no
receipt. Hardened under #1464.

What this module pins is the REMEDY, not the measurements: all three audit passes present
and sharing one suppression list, ``make audit`` left as the canonical single-command
spelling, a daily main-branch workflow running the same ``make security``, no cache key
on either audit job, the audit canary running unconditionally before the gate in both, and
both tools installed from one pins file held to the lock. The third blind spot's remedy is
deliberately HARDENING and names no root cause: whether the cache caused any particular
verdict is not asserted here. It cannot re-measure
coverage - that needs the network and a resolve - so the numbers above stay in the pull
request's receipts and in the ``Makefile``'s own comment, where a reviewer reads them.

Per VERIFY-01(5) every assertion in the ``Makefile`` and workflow guards ships the negative
control that observes it firing: both are pure functions over text, exercised against mutated
copies rather than trusted - 66 controls: 15 over the ``Makefile``, 21 over the main-audit
workflow, 24 over the two audit jobs' hygiene (twelve shapes against each workflow file:
cache, pins and canary), and 6 over the tooling pins against the lock. The canary's own
verdict function carries its negative controls inline in one test, against crafted
pip-audit reports. The claim is deliberately not made of the tests with no text to mutate:
three are oracles against live objects (one re-runs ``make -n``, two interrogate the installed
``pip_audit``), one asserts an equality across two workflow files, one asserts the live pins
file agrees with the lock, and two assert that the fail-closed checks still accept what they
must - the values that mean "always run", and an unrelated install standing beside the
pinned tooling.

That claim was once wider than the set. #1388's independent domain lane probed
``audit_workflow`` key by key and found six shapes it passed: ``continue-on-error: true`` on
the job or on the gate step, and an ``if:`` on either — ``if: false`` or a real condition like
``if: github.event_name == 'push'``, which honours the triggers in the YAML and silences the
daily run they promise, while every other assertion here stays green. ``continue-on-error``
was worse than silence: it would let a RED audit report success, so the status on ``main``
would say the opposite of what it measured. Both are now rejected, each with the lane's own
probe as its control.

The ``Makefile`` half had the same reach problem, and the independent assurance lane found it:
appending ``--ignore-vuln`` to ``security``'s resolve line, or ``|| true`` to either pass, left
every containment check passing. An earlier draft of this docstring claimed
``test_make_expansion_agrees_with_the_makefile_source`` was a backstop against exactly that.
It is not, and the claim is withdrawn: that test asks GNU Make what ``security`` expands to and
checks the answer agrees with the source, so a weakening WRITTEN INTO the source passes both
sides of the comparison. ``make -n audit`` is untouched by any of it, so #1386's fence does not
see it either. Both ``security`` audit lines are therefore pinned by equality to their
canonical spelling, with the lane's two shapes and a third as their controls. One nuance from
that lane is worth keeping: ``make -n`` is no backstop against an appended token, but it is
not inert - a duplicated ``security:`` target (Make honours the LAST recipe while ``_recipe``
returns on the first) and an extra ``exit 0`` recipe line are caught there and nowhere else.
Asking the tool what it will do, rather than out-parsing the file, still earns its place.

The same lane then found the sixth and seventh shapes, in the two checks written to close its
fifth. ``continue-on-error`` was an allowlist of two bad literals, so ``${{ true }}``,
``"True"`` and ``${{ github.event_name == 'schedule' }}`` all passed - the last of which
neuters the daily run while the push run keeps failing normally, which is gap 2 reopened
behind a healthy-looking workflow. And a ``paths:`` filter on the ``push`` trigger left
``main`` in ``branches`` while silencing the run for any commit that missed it. Both now fail
CLOSED: a value is rejected unless it can be proved harmless, which is the shape the ``if``
check had from the start. The lesson, recorded because it has now recurred four times on this
repository in two days: controls drawn from the list of shapes a reviewer handed over will
cover exactly those shapes. Derive them from the construct's grammar instead - every value
GitHub Actions accepts in that field, every key it accepts in that trigger.
"""

from __future__ import annotations

import importlib
import importlib.util
import inspect
import json
import re
import shlex
import subprocess
import tempfile
import warnings
from pathlib import Path
from typing import Any

import pytest
import yaml
from packaging.utils import canonicalize_name

REPO_ROOT = Path(__file__).resolve().parents[2]
MAKEFILE = REPO_ROOT / "Makefile"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "security-audit.yml"
TEST_SUITE_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "test-suite.yml"
TOOLING_PINS = REPO_ROOT / ".github" / "requirements-security-tooling.txt"
TOOLING_PINS_REF = ".github/requirements-security-tooling.txt"
TOOLING_INSTALL = f"pip install -r {TOOLING_PINS_REF}"
PINNED_TOOLS = ("bandit", "pip-audit")
# Holds the auditor's transitive dependencies to the lock as well; pip resolves the path
# relative to the pins file.
TOOLING_CONSTRAINT = "-c ../requirements.txt"
# Any pip invocation, however spelled: `pip install`, `pip3 install`, `python -m pip install`.
PIP_INSTALL = re.compile(r"(?<![\w.-])pip3?\s+install(?![\w-])")
# The negative control a clean verdict needs (#1464): every feed must report known
# advisories, in the same job, before the gate's own verdict is trusted.
CANARY_RUN = "python scripts/ci/check_audit_canary.py"

LOCK = "requirements.txt"
ALLOWLIST = "$(PIP_AUDIT_IGNORES)"
RESOLVE_RECIPE = f"pip-audit -r {LOCK} {ALLOWLIST}"
DECLARED_RECIPE = f"pip-audit --no-deps --disable-pip -r {LOCK} {ALLOWLIST}"
# The feed cross-check: declared-pin coverage read from OSV instead of PyPI's API.
OSV_FLAGS = ("--vulnerability-service", "osv")
OSV_FLAG = " ".join(OSV_FLAGS)
OSV_RECIPE = f"pip-audit {OSV_FLAG} --no-deps --disable-pip -r {LOCK} {ALLOWLIST}"
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
    # Partition by FEED first. The OSV pass carries both declared flags too, so a
    # coverage-only split would count it as a second declared pass and red this guard
    # for the very line it is meant to pin.
    osv = [line for line in pip_audits if OSV_FLAG in line]
    pypi = [line for line in pip_audits if OSV_FLAG not in line]
    resolve = [line for line in pypi if not any(f in line for f in DECLARED_FLAGS)]
    declared = [line for line in pypi if all(flag in line for flag in DECLARED_FLAGS)]
    if len(osv) != 1:
        violations.append(
            "`security` must run exactly one OSV cross-check pass "
            f"(`{OSV_RECIPE}`) so one feed's stale or partial answer cannot produce a "
            f"clean verdict on its own (#1353 D-10), got {osv!r}"
        )
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

    # Pinned by EQUALITY, not by containment. #1388's independent assurance lane
    # demonstrated the hole the containment checks above leave: append
    # `--ignore-vuln GHSA-...` to `security`'s resolve line, or `|| true` to either pass,
    # and there is still exactly one line of each mode, each carrying the lock and the
    # shared allowlist. A suppression added to one pass alone is a suppression that holds
    # in one mode and not the other, which is the whole point of sharing
    # $(PIP_AUDIT_IGNORES); `|| true` makes a RED audit green. Neither `make -n` oracle
    # sees either shape - `make -n security` only agrees with whatever the source says,
    # and `make -n audit` is untouched - so equality here is the only check that does.
    for mode, lines, canonical in (
        ("resolve-mode", resolve, RESOLVE_RECIPE),
        ("declared-pin", declared, DECLARED_RECIPE),
        ("OSV cross-check", osv, OSV_RECIPE),
    ):
        if lines and lines != [canonical]:
            violations.append(
                f"`security`'s {mode} pass must be exactly `{canonical}` - an appended "
                "flag suppresses in one mode only and an appended `|| true` reports a red "
                f"audit as green, both invisible to `make -n`; got {lines!r}"
            )

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

    osv_alias = _recipe(makefile_text, "audit-osv")
    if osv_alias != [OSV_RECIPE]:
        violations.append(
            f"`audit-osv` must be exactly [{OSV_RECIPE!r}], got {osv_alias!r}"
        )

    phony = next(
        (line for line in makefile_text.splitlines() if line.startswith(".PHONY:")), ""
    )
    for target in ("security", "audit", "audit-declared", "audit-osv"):
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
    # A path filter leaves `main` in `branches` and silences the run for every commit
    # that misses the filter. `schedule:` cannot carry one, so the daily cadence would
    # survive, but the push run would be present in the YAML and absent in fact.
    for key in ("paths", "paths-ignore"):
        if isinstance(push, dict) and key in push:
            violations.append(
                f"the `push` trigger must not carry `{key}`: the audit is about the "
                f"whole lock, not the diff, so no commit to `main` is out of its scope, "
                f"got {push[key]!r}"
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
            # Fails CLOSED, like the `if` check above: only a value that can be proved
            # harmless is accepted. Actions takes an expression here, so an allowlist of
            # bad literals missed `${{ true }}`, `"True"` and
            # `${{ github.event_name == 'schedule' }}` — the last of which neuters the
            # DAILY run while the push run keeps failing normally, so the workflow looks
            # healthy and gap 2 reopens with every assertion here still green.
            cont = node.get("continue-on-error")
            if cont is not None and str(cont).strip().lower() not in {
                "false",
                "${{ false }}",
            }:
                violations.append(
                    f"the `make security` {owner} must not set `continue-on-error` — a "
                    f"red audit would report success on main, got {cont!r}"
                )

    names = {job.get("name") for job in jobs.values() if isinstance(job, dict)}
    if "Security Scan" in names:
        violations.append(
            "job name must differ from test-suite.yml's `Security Scan`, which is the "
            "required merge gate"
        )

    return violations


def audit_gate_hygiene(workflow: Workflow, label: str) -> list[str]:
    """Return one message per audit-hygiene violation in a job that runs `make security`.

    Two separate defects, both measured on 2026-10-27 and logged as residual D-10 on
    #1353, and both outside everything ``audit_makefile`` and ``audit_workflow`` can see,
    because neither lives in the Makefile or in a trigger.

    **The cache.** ``pip_audit._service.pypi`` builds its session with
    ``caching_session(cache_dir)``, taking the default ``use_pip=True``, which
    ``pip_audit._cache._get_cache_dir`` resolves to ``$(pip cache dir)/http``. A job that
    restores pip's cache therefore hands the auditor somebody else's advisory responses.
    The key is the runner, the Python version and the lock hash, so it is shared across
    branches: a cache saved at 16:50:20Z, 18 minutes before GHSA-wf6j-7hvr-gr93
    published, was restored byte-identical by five later runs, and the gate reported a
    lock pinning the vulnerable ``hydra-core==1.3.7`` clean (job 122348327291). Rejected
    fail-CLOSED - the key must be absent, not merely unequal to ``'pip'`` - because the
    field takes any value Actions accepts and a cache of any flavour is a directory the
    auditor may read.

    **The pins.** Both jobs installed ``bandit pip-audit`` unpinned, so the tool that
    decides a merge drifted with whatever PyPI served that morning and its version
    appeared in no receipt. Also fail-closed: any ``pip install`` naming either tool is a
    violation unless it is exactly the shared pinned-file install, so a drifting pin
    cannot be added beside the pinned one.
    """
    violations: list[str] = []

    jobs = workflow.get("jobs")
    if not isinstance(jobs, dict) or not jobs:
        return [f"{label}: no jobs"]

    gate_jobs = [
        job
        for job in jobs.values()
        if isinstance(job, dict)
        and any(
            isinstance(step, dict) and "make security" in str(step.get("run", ""))
            for step in (job.get("steps") or [])
        )
    ]
    if not gate_jobs:
        return [f"{label}: no job runs `make security`"]

    for job in gate_jobs:
        steps = [step for step in (job.get("steps") or []) if isinstance(step, dict)]
        for step in steps:
            if not str(step.get("uses", "")).startswith("actions/setup-python@"):
                continue
            configured = step.get("with")
            if isinstance(configured, dict) and "cache" in configured:
                violations.append(
                    f"{label}: a job running `make security` must not set setup-python "
                    "`cache` - pip-audit reads pip's HTTP cache by default, so a restored "
                    "cache hands the audit advisory responses saved by another branch's "
                    f"run (#1353 D-10, #1464), got {configured['cache']!r}"
                )

        runs = "\n".join(str(step.get("run", "")) for step in steps)
        if TOOLING_INSTALL not in runs:
            violations.append(
                f"{label}: must install the audit tooling from {TOOLING_PINS_REF} so the "
                "tool that decides a merge cannot drift with PyPI, and so both audit jobs "
                "install the same one"
            )
        for line in runs.splitlines():
            command = line.strip()
            if not PIP_INSTALL.search(command) or command == TOOLING_INSTALL:
                continue
            named = [
                tool
                for tool in PINNED_TOOLS
                if re.search(rf"(?<![\w.-]){re.escape(tool)}(?![\w.-])", command)
            ]
            if named:
                violations.append(
                    f"{label}: {named} must be installed only from {TOOLING_PINS_REF}, "
                    f"so a pin cannot drift beside the pinned one, got {command!r}"
                )

        violations.extend(_canary_violations(steps, label))

    return violations


def _canary_violations(steps: list[Workflow], label: str) -> list[str]:
    """Require the audit canary to run, unconditionally and failing, before the gate.

    A clean audit is evidence about the lock only if the feeds could have reported a
    finding at that moment. The canary step is that negative control: each service the
    gate consults must report two known advisories or the job fails. It is held to the
    same fail-closed `if` and `continue-on-error` rules as the gate step, because a canary
    that cannot fail is the defect it exists to catch, and it must come BEFORE the gate so
    a dead feed fails the job instead of being discovered after a green verdict.
    """
    violations: list[str] = []
    runs = [str(step.get("run", "")).strip() for step in steps]
    canaries = [index for index, run in enumerate(runs) if run == CANARY_RUN]
    gates = [index for index, run in enumerate(runs) if run == "make security"]
    if len(canaries) != 1:
        violations.append(
            f"{label}: a job running `make security` must run `{CANARY_RUN}` exactly "
            "once, so every feed is shown able to report a known advisory before its "
            f"clean verdict is trusted (#1464), got {len(canaries)}"
        )
        return violations
    if gates and canaries[0] > gates[0]:
        violations.append(
            f"{label}: the audit canary must run before `make security`, so a feed that "
            "cannot report fails the job rather than following a green verdict"
        )
    step = steps[canaries[0]]
    if "if" in step and str(step["if"]).strip().lower() not in {"true", "${{ true }}"}:
        violations.append(
            f"{label}: the audit canary must not be conditional, got {step['if']!r}"
        )
    cont = step.get("continue-on-error")
    if cont is not None and str(cont).strip().lower() not in {"false", "${{ false }}"}:
        violations.append(
            f"{label}: the audit canary must not set `continue-on-error` - a canary that "
            f"cannot fail proves nothing, got {cont!r}"
        )
    return violations


def audit_tooling_pins(pins_text: str, lock_text: str) -> list[str]:
    """Return one message per tooling-pin violation; empty means compliant.

    Both tools must be pinned exactly, to the same version the lock pins, and the file
    must carry the constraint that holds their transitive dependencies to the lock. A
    pure function over two texts, so each clause is observed failing on a mutated copy.
    """
    violations: list[str] = []
    lines = [
        line.strip()
        for line in pins_text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if TOOLING_CONSTRAINT not in lines:
        violations.append(
            f"{TOOLING_PINS_REF} must carry `{TOOLING_CONSTRAINT}` so the auditor's "
            "transitive dependencies are held to the lock"
        )
    requirements = [line for line in lines if not line.startswith("-")]
    pins: dict[str, str] = {}
    for line in requirements:
        name, separator, version = line.partition("==")
        if not separator or not re.fullmatch(r"[0-9][0-9A-Za-z.!+\-]*", version):
            violations.append(f"{TOOLING_PINS_REF}: `{line}` is not an exact pin")
            continue
        pins[canonicalize_name(name)] = version
    if set(pins) != set(PINNED_TOOLS):
        violations.append(
            f"{TOOLING_PINS_REF} must pin exactly {list(PINNED_TOOLS)}, got {sorted(pins)}"
        )

    lock: dict[str, str] = {}
    for line in lock_text.splitlines():
        name, separator, version = line.split("#", 1)[0].strip().partition("==")
        if separator:
            lock[canonicalize_name(name)] = version.split(";", 1)[0].strip()
    for tool, version in pins.items():
        if tool in PINNED_TOOLS and lock.get(tool) != version:
            violations.append(
                f"{TOOLING_PINS_REF} pins {tool}=={version} but {LOCK} pins "
                f"{tool}=={lock.get(tool)}: a local `make security` and CI would run "
                "different analysers"
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
    assert len(security) == 4, security
    assert security[0][0] == "bandit"
    assert security[1][:3] == ["pip-audit", "-r", LOCK]
    assert security[2][0] == "pip-audit"
    assert set(DECLARED_FLAGS) <= set(security[2])
    assert security[2][-2:] == ["-r", LOCK]
    # The feed cross-check: the same declared coverage, asked of OSV rather than PyPI.
    assert security[3][0] == "pip-audit"
    assert set(DECLARED_FLAGS) <= set(security[3])
    assert set(OSV_FLAGS) <= set(security[3])
    assert security[3][-2:] == ["-r", LOCK]
    assert set(OSV_FLAGS).isdisjoint(security[1] + security[2])

    # The alias stays a single unflagged command; `make -n audit` is SECDEP-01's oracle.
    assert _make_commands("audit") == [["pip-audit", "-r", LOCK]]
    declared = _make_commands("audit-declared")
    assert len(declared) == 1
    assert set(DECLARED_FLAGS) <= set(declared[0])
    osv = _make_commands("audit-osv")
    assert len(osv) == 1
    assert set(OSV_FLAGS) | set(DECLARED_FLAGS) <= set(osv[0])


def test_the_conditional_checks_do_not_over_reject() -> None:
    """Both fail-closed checks must still accept the values that mean "always run".

    A check that rejects everything is as useless as one that rejects nothing, and the
    `continue-on-error` rule was tightened from an allowlist of bad literals to a
    denylist-by-default. These are the spellings a maintainer may legitimately write.
    """
    for allowed in (False, "false", "${{ false }}"):
        assert audit_workflow(_mutate_gate_step(**{"continue-on-error": allowed})) == []
        assert audit_workflow(_mutate_job(**{"continue-on-error": allowed})) == []
    for allowed in (True, "true", "${{ true }}"):
        assert audit_workflow(_mutate_gate_step(**{"if": allowed})) == []
    assert (
        audit_workflow(_with_trigger("push", {"branches": ["main", "release/*"]})) == []
    )


def test_the_merge_gate_and_the_main_audit_run_the_same_command() -> None:
    """Both workflows must invoke `make security`, so neither can drift weaker."""
    test_suite = TEST_SUITE_WORKFLOW.read_text(encoding="utf-8")
    assert "run: make security" in test_suite
    assert "run: make security" in WORKFLOW.read_text(encoding="utf-8")


@pytest.mark.parametrize("path", [TEST_SUITE_WORKFLOW, WORKFLOW], ids=lambda p: p.name)
def test_neither_audit_job_lets_a_cache_answer_for_the_feed(path: Path) -> None:
    """Both live audit jobs must keep pip's cache out of the audit and pin the tools."""
    loaded: Workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert audit_gate_hygiene(loaded, path.name) == []


def test_the_audit_tooling_is_pinned_to_the_lock() -> None:
    """The shared pins file must pin both tools to the lock's own versions."""
    assert TOOLING_PINS.is_file(), f"missing {TOOLING_PINS}"
    assert (
        audit_tooling_pins(
            TOOLING_PINS.read_text(encoding="utf-8"),
            (REPO_ROOT / LOCK).read_text(encoding="utf-8"),
        )
        == []
    )


def test_the_audit_canary_runs_and_can_fail() -> None:
    """The canary's verdict function passes a full report and fails every gap.

    Hermetic: crafted pip-audit reports stand in for the network. The live run is the
    workflow step itself and the pull request's receipts.
    """
    spec = importlib.util.spec_from_file_location(
        "check_audit_canary", REPO_ROOT / "scripts" / "ci" / "check_audit_canary.py"
    )
    assert spec is not None and spec.loader is not None
    canary = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(canary)

    def report(*found: tuple[str, str, list[str]]) -> str:
        return json.dumps(
            {
                "dependencies": [
                    {
                        "name": name,
                        "version": "0",
                        "vulns": [{"id": vid, "aliases": al}],
                    }
                    for name, vid, al in found
                ]
            }
        )

    full = report(
        ("hydra-core", "GHSA-wf6j-7hvr-gr93", []),
        ("msgpack", "CVE-2026-114613", ["GHSA-j586-36cw-2gc2"]),
    )
    assert canary.missing_detections(1, full) == []
    # Either name of the msgpack advisory is a detection.
    assert (
        canary.missing_detections(
            1,
            report(
                ("hydra-core", "GHSA-wf6j-7hvr-gr93", []),
                ("msgpack", "GHSA-j586-36cw-2gc2", []),
            ),
        )
        == []
    )
    # Negative controls, one per way a feed can fail to answer.
    partial = report(("hydra-core", "GHSA-wf6j-7hvr-gr93", []))
    assert any("msgpack" in m for m in canary.missing_detections(1, partial))
    assert canary.missing_detections(0, report())
    assert canary.missing_detections(1, report())
    assert canary.missing_detections(2, full)
    assert canary.missing_detections(1, "not json")
    assert canary.missing_detections(1, json.dumps({"dependencies": None}))
    other = report(
        ("hydra-core", "GHSA-0000-0000-0000", []),
        ("msgpack", "CVE-2026-114613", []),
    )
    assert any("hydra-core" in m for m in canary.missing_detections(1, other))
    assert canary.canary_requirements() == "hydra-core==1.3.7\nmsgpack==1.2.1\n"


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
                f"\t{DECLARED_RECIPE}\n\t{OSV_RECIPE}",
                "\tpip-audit --no-deps --disable-pip -r requirements.txt\n"
                f"\t{OSV_RECIPE}",
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
            lambda text: text.replace(
                f"\t{RESOLVE_RECIPE}\n\t{DECLARED_RECIPE}",
                f"\t{RESOLVE_RECIPE} --ignore-vuln GHSA-0000-0000-0000"
                f"\n\t{DECLARED_RECIPE}",
                1,
            ),
            "resolve-mode pass must be exactly",
            id="suppression added to the resolve pass alone",
        ),
        pytest.param(
            lambda text: text.replace(
                f"\t{RESOLVE_RECIPE}\n\t{DECLARED_RECIPE}",
                f"\t{RESOLVE_RECIPE} || true\n\t{DECLARED_RECIPE}",
                1,
            ),
            "resolve-mode pass must be exactly",
            id="resolve pass made non-failing",
        ),
        pytest.param(
            lambda text: text.replace(
                f"\t{DECLARED_RECIPE}\n\t{OSV_RECIPE}",
                f"\t{DECLARED_RECIPE} || true\n\t{OSV_RECIPE}",
                1,
            ),
            "declared-pin pass must be exactly",
            id="declared pass made non-failing",
        ),
        pytest.param(
            lambda text: text.replace(
                " audit-declared audit-osv test", " audit-osv test", 1
            ),
            ".PHONY must list `audit-declared`",
            id="target left off PHONY",
        ),
        pytest.param(
            lambda text: text.replace(
                f"\t{OSV_RECIPE}\n\n# Convenience", "\n# Convenience", 1
            ),
            "must run exactly one OSV cross-check pass",
            id="feed cross-check dropped",
        ),
        pytest.param(
            lambda text: text.replace(
                f"\t{OSV_RECIPE}\n\n# Convenience",
                f"\t{OSV_RECIPE} || true\n\n# Convenience",
                1,
            ),
            "OSV cross-check pass must be exactly",
            id="feed cross-check made non-failing",
        ),
        pytest.param(
            lambda text: text.replace(
                f"\t{OSV_RECIPE}\n\n# Convenience",
                f"\t{OSV_RECIPE.replace(' ' + ALLOWLIST, '')}\n\n# Convenience",
                1,
            ),
            "every audit pass must carry",
            id="feed cross-check loses the shared allowlist",
        ),
        pytest.param(
            lambda text: text.replace(
                f"audit-osv:\n\t{OSV_RECIPE}", f"audit-osv:\n\t{OSV_RECIPE} --strict", 1
            ),
            "`audit-osv` must be exactly",
            id="osv alias widened",
        ),
        pytest.param(
            lambda text: text.replace(" audit-osv test", " test", 1),
            ".PHONY must list `audit-osv`",
            id="osv alias left off PHONY",
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
            lambda: _mutate_gate_step(**{"continue-on-error": "${{ true }}"}),
            "step must not set `continue-on-error`",
            id="step continue-on-error written as an expression",
        ),
        pytest.param(
            lambda: _mutate_gate_step(**{"continue-on-error": "True"}),
            "step must not set `continue-on-error`",
            id="step continue-on-error written as a capitalised string",
        ),
        pytest.param(
            lambda: _mutate_gate_step(
                **{"continue-on-error": "${{ github.event_name == 'schedule' }}"}
            ),
            "step must not set `continue-on-error`",
            id="step continue-on-error silences only the daily run",
        ),
        pytest.param(
            lambda: _mutate_job(**{"continue-on-error": "${{ true }}"}),
            "job must not set `continue-on-error`",
            id="job continue-on-error written as an expression",
        ),
        pytest.param(
            lambda: _with_trigger(
                "push", {"branches": ["main"], "paths": ["docs/never-touched/**"]}
            ),
            "must not carry `paths`",
            id="push to main narrowed by a path filter",
        ),
        pytest.param(
            lambda: _with_trigger(
                "push", {"branches": ["main"], "paths-ignore": ["**"]}
            ),
            "must not carry `paths-ignore`",
            id="push to main emptied by a paths-ignore filter",
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


def _hygiene_workflow(path: Path) -> Workflow:
    loaded: Workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
    return loaded


def _gate_jobs(workflow: Workflow) -> list[dict[str, Any]]:
    return [
        job
        for job in workflow["jobs"].values()
        if isinstance(job, dict)
        and any(
            "make security" in str(step.get("run", ""))
            for step in (job.get("steps") or [])
        )
    ]


def _with_python_cache(path: Path, value: object) -> Workflow:
    """Give the audit job's setup-python step a cache again, as it had before #1353 D-10."""
    workflow = _hygiene_workflow(path)
    for job in _gate_jobs(workflow):
        for step in job["steps"]:
            if str(step.get("uses", "")).startswith("actions/setup-python@"):
                step["with"] = {**(step.get("with") or {}), "cache": value}
    return workflow


def _with_tooling_install(path: Path, run: str) -> Workflow:
    """Replace the pinned-tooling install in the audit job with ``run``."""
    workflow = _hygiene_workflow(path)
    for job in _gate_jobs(workflow):
        for step in job["steps"]:
            if TOOLING_INSTALL in str(step.get("run", "")):
                step["run"] = run
    return workflow


def _mutate_canary(path: Path, **changes: Any) -> Workflow:
    """Apply ``changes`` to the audit-canary step of the audit job."""
    workflow = _hygiene_workflow(path)
    for job in _gate_jobs(workflow):
        job["steps"] = [
            (
                {**step, **changes}
                if str(step.get("run", "")).strip() == CANARY_RUN
                else step
            )
            for step in job["steps"]
        ]
    return workflow


def _without_canary(path: Path) -> Workflow:
    workflow = _hygiene_workflow(path)
    for job in _gate_jobs(workflow):
        job["steps"] = [
            step
            for step in job["steps"]
            if str(step.get("run", "")).strip() != CANARY_RUN
        ]
    return workflow


def _canary_after_gate(path: Path) -> Workflow:
    workflow = _hygiene_workflow(path)
    for job in _gate_jobs(workflow):
        steps = job["steps"]
        canary = [s for s in steps if str(s.get("run", "")).strip() == CANARY_RUN]
        job["steps"] = [s for s in steps if s not in canary] + canary
    return workflow


@pytest.mark.parametrize("path", [TEST_SUITE_WORKFLOW, WORKFLOW], ids=lambda p: p.name)
@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        pytest.param(
            _without_canary,
            f"must run `{CANARY_RUN}` exactly once",
            id="audit canary removed",
        ),
        pytest.param(
            _canary_after_gate,
            "must run before `make security`",
            id="audit canary moved after the gate",
        ),
        pytest.param(
            lambda path: _mutate_canary(path, **{"continue-on-error": True}),
            "audit canary must not set `continue-on-error`",
            id="audit canary allowed to fail",
        ),
        pytest.param(
            lambda path: _mutate_canary(
                path, **{"continue-on-error": "${{ github.event_name == 'schedule' }}"}
            ),
            "audit canary must not set `continue-on-error`",
            id="audit canary allowed to fail by expression",
        ),
        pytest.param(
            lambda path: _mutate_canary(path, **{"if": "github.event_name == 'push'"}),
            "audit canary must not be conditional",
            id="audit canary made conditional",
        ),
        pytest.param(
            lambda path: _mutate_canary(path, run=f"{CANARY_RUN} || true"),
            f"must run `{CANARY_RUN}` exactly once",
            id="audit canary swallowed by a shell or-true",
        ),
        pytest.param(
            lambda path: _with_tooling_install(
                path,
                f"{TOOLING_INSTALL}\npython -m pip install --upgrade pip-audit\n",
            ),
            "must be installed only from",
            id="a drifting pin added through python -m pip",
        ),
        pytest.param(
            lambda path: _with_python_cache(path, "pip"),
            "must not set setup-python `cache`",
            id="pip cache restored",
        ),
        pytest.param(
            lambda path: _with_python_cache(path, "poetry"),
            "must not set setup-python `cache`",
            id="another cache flavour restored",
        ),
        pytest.param(
            lambda path: _with_python_cache(path, ""),
            "must not set setup-python `cache`",
            id="empty cache value is still a cache key",
        ),
        pytest.param(
            lambda path: _with_tooling_install(
                path,
                "python -m pip install --upgrade pip\npip install bandit pip-audit\n",
            ),
            "must install the audit tooling from",
            id="tooling unpinned again",
        ),
        pytest.param(
            lambda path: _with_tooling_install(
                path, f"{TOOLING_INSTALL}\npip install --upgrade pip-audit\n"
            ),
            "must be installed only from",
            id="a drifting pin added beside the pinned one",
        ),
    ],
)
def test_the_hygiene_guard_rejects_a_cached_or_unpinned_audit(
    mutation: object, expected: str, path: Path
) -> None:
    violations = audit_gate_hygiene(mutation(path), path.name)  # type: ignore[operator]
    assert violations, "the guard passed an audit job that can read a stale cache"
    assert any(expected in violation for violation in violations), violations


_LIVE_PINS = TOOLING_PINS.read_text(encoding="utf-8")
_LIVE_LOCK = (REPO_ROOT / LOCK).read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("pins", "lock", "expected"),
    [
        pytest.param(
            _LIVE_PINS.replace("bandit==", "bandit>="),
            _LIVE_LOCK,
            "is not an exact pin",
            id="bandit loosened to a floor",
        ),
        pytest.param(
            _LIVE_PINS.replace("pip-audit==2.10.1", "pip-audit"),
            _LIVE_LOCK,
            "is not an exact pin",
            id="pip-audit unpinned",
        ),
        pytest.param(
            _LIVE_PINS.replace("pip-audit==2.10.1", "pip-audit==2.10.0"),
            _LIVE_LOCK,
            "but requirements.txt pins pip-audit",
            id="pip-audit drifts from the lock",
        ),
        pytest.param(
            _LIVE_PINS,
            _LIVE_LOCK.replace("bandit==1.9.4", "bandit==1.9.5"),
            "but requirements.txt pins bandit",
            id="lock bumps bandit and the pins file stays behind",
        ),
        pytest.param(
            _LIVE_PINS.replace(f"{TOOLING_CONSTRAINT}\n", ""),
            _LIVE_LOCK,
            f"must carry `{TOOLING_CONSTRAINT}`",
            id="transitive constraint dropped",
        ),
        pytest.param(
            _LIVE_PINS.replace("bandit==1.9.4\n", ""),
            _LIVE_LOCK,
            "must pin exactly",
            id="bandit dropped from the pins file",
        ),
    ],
)
def test_the_tooling_pin_guard_rejects_drift(
    pins: str, lock: str, expected: str
) -> None:
    assert pins != _LIVE_PINS or lock != _LIVE_LOCK, "the mutation did not apply"
    violations = audit_tooling_pins(pins, lock)
    assert violations, "the guard passed drifting audit tooling"
    assert any(expected in violation for violation in violations), violations


@pytest.mark.parametrize("path", [TEST_SUITE_WORKFLOW, WORKFLOW], ids=lambda p: p.name)
def test_the_hygiene_guard_does_not_over_reject(path: Path) -> None:
    """Installing something else alongside the pinned tooling is legitimate.

    The pin check fails closed on the two audit tools by name; it must not object to an
    unrelated install in the same job, or it would stop a maintainer adding one.
    """
    assert (
        audit_gate_hygiene(
            _with_tooling_install(path, f"{TOOLING_INSTALL}\npip install ruff\n"),
            path.name,
        )
        == []
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
