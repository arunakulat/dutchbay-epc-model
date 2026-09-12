"""CESSPIT pre-flight guard: every place a dependency pin is declared must agree.

A ``[report]`` package is declared in **five** places, and nothing until now
checked that they say the same thing:

* ``requirements.txt`` -- the reproducibility lock CI installs and ``pip-audit`` reads;
* ``constraints.txt`` -- the resolver ceiling, applied at image build
  (``Dockerfile`` ``pip install -c constraints.txt``);
* ``pyproject.toml`` ``[project.optional-dependencies]`` -- the specifier baked
  into the built distribution's metadata;
* a string literal in an integration guard, e.g.
  ``assert version("weasyprint") == "70.0"``;
* ``docs/MODULE_REFERENCE.md`` -- prose, and out of this file's reach.

The third is not documentation.  ``app.ops.extras.probe_extra`` reads
``declared_spec`` back out of that metadata and sets ``satisfies_spec``, and
``app.reports.dbpl.print_core.require_dbpl_stack`` raises
``DbplDependencyError`` when an installed package "violates its declared pin"
(DBPL-01).  So bumping the lock while leaving the ``pyproject`` ceiling behind
does not produce a version disagreement on paper -- it stops every DBPL PDF from
rendering at runtime, which is the deliverable itself.

The fourth is what actually broke CI on this change's first push: the three
dependency files were perfectly self-consistent and the disagreement was in a
literal, so it surfaced in a 40-minute integration shard rather than here.

**On what these controls do and do not cover.**  Three independent reviewers
defeated the first version of this parser, which matched only
``^name==version$``.  A marker (``pkg==1.0 ; python_version >= "3.12"``), an
extras group (``pkg[x]==1.0``), a ``--hash=`` suffix, or simply ``pkg == 1.0``
with spaces each yielded *no pin at all*, and a package absent from the lock is
skipped by every consumer here -- so a real disagreement passed silently.  Five
ceiling lines in ``constraints.txt`` (``pandas<3``, ``ruff<0.15`` and friends)
were dropped for the same reason, leaving a control named "constraints never
contradict the lock" covering 12 of its 17 lines.

Parsing now goes through :mod:`packaging`, and a line this file cannot parse is
a hard failure rather than a silent skip.  The prose declaration in
``docs/MODULE_REFERENCE.md`` remains outside any automated check.
"""

from __future__ import annotations

import ast
import tomllib
from pathlib import Path

import pytest
from packaging.requirements import InvalidRequirement, Requirement
from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name
from packaging.version import Version

REPO_ROOT = Path(__file__).resolve().parents[2]

#: The extra whose pins are load-bearing at runtime, not merely at install time.
DBPL_EXTRA = "report"

#: Logging-free stdlib helper: PEP 503 normalisation.  A hand-rolled
#: ``lower().replace("_","-")`` differs on ``opendssdirect.py`` and three other
#: locked names, which silently disabled a check.
_canonical = canonicalize_name


def _requirement_lines(filename: str) -> list[str]:
    """Return the requirement lines of a pip file, comments and hashes removed.

    An option or include line (anything starting with ``-``) raises rather than
    being skipped: ``-r extra-pins.txt`` moves pins somewhere this file does not
    look, which would quietly hollow out every control below.
    """
    lines: list[str] = []
    for raw in (REPO_ROOT / filename).read_text().splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("-"):
            raise AssertionError(
                f"{filename}: option/include line {line!r} can hide pins from these "
                "controls; teach this parser about it before introducing it"
            )
        # ``--hash=`` options bind to the preceding requirement; drop them and
        # keep the pin, rather than failing to parse the whole line.
        lines.append(line.split("--hash", 1)[0].strip())
    return lines


def _parse_requirements(
    filename: str,
) -> tuple[dict[str, str], dict[str, SpecifierSet]]:
    """Split a pip file into exact ``==`` pins and every other version constraint.

    Returns ``({name: version}, {name: specifier})``.  A line that does not parse
    raises: silently dropping it is precisely how a real disagreement survived.
    """
    pins: dict[str, str] = {}
    ranges: dict[str, SpecifierSet] = {}
    for line in _requirement_lines(filename):
        try:
            requirement = Requirement(line)
        except InvalidRequirement as exc:
            raise AssertionError(f"{filename}: cannot parse {line!r} ({exc})") from exc
        name = _canonical(requirement.name)
        specifiers = list(requirement.specifier)
        if len(specifiers) == 1 and specifiers[0].operator == "==":
            pins[name] = specifiers[0].version
        elif specifiers:
            ranges[name] = requirement.specifier
    return pins, ranges


def _read_pins(filename: str) -> dict[str, str]:
    return _parse_requirements(filename)[0]


def _declared_extras() -> dict[str, list[str]]:
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())
    extras: dict[str, list[str]] = data["project"]["optional-dependencies"]
    return extras


def test_the_lock_is_not_empty() -> None:
    """Guard the guard: a parser that silently matched nothing would pass everything."""
    pins = _read_pins("requirements.txt")
    assert len(pins) > 100, f"only parsed {len(pins)} pins from requirements.txt"
    assert "weasyprint" in pins


def test_the_constraints_file_is_not_empty() -> None:
    """The same floor for ``constraints.txt``, which had only ``assert constraints``.

    One surviving pin out of twelve satisfied that, so a parser failure there was
    invisible where the same failure in the lock was caught.
    """
    pins, ranges = _parse_requirements("constraints.txt")
    assert len(pins) >= 10, f"only parsed {len(pins)} pins from constraints.txt"
    assert ranges, "constraints.txt declares ceilings; none were parsed"
    assert "weasyprint" in pins


def test_constraints_never_contradict_the_lock() -> None:
    """Where both files constrain a package, the lock must satisfy the constraint.

    Covers ceilings (``pandas<3``) as well as exact pins.  Ceilings were dropped
    entirely by the first version of this control, which is 5 of the 17
    declarations in the file it reads.
    """
    lock = _read_pins("requirements.txt")
    pins, ranges = _parse_requirements("constraints.txt")

    disagreements = {
        name: (lock[name], pins[name])
        for name in lock.keys() & pins.keys()
        if lock[name] != pins[name]
    }
    assert not disagreements, (
        "requirements.txt and constraints.txt pin different versions "
        f"(name: lock vs constraint): {disagreements}"
    )

    violated = [
        f"{name}: lock {lock[name]} violates constraint {spec}"
        for name, spec in ranges.items()
        if name in lock and not spec.contains(Version(lock[name]), prereleases=True)
    ]
    assert not violated, f"the lock breaches a declared constraint ceiling: {violated}"


@pytest.mark.parametrize("extra", sorted(_declared_extras()))
def test_declared_extra_specs_are_satisfied_by_the_lock(extra: str) -> None:
    """Every locked version must satisfy the specifier pyproject declares for it."""
    lock = _read_pins("requirements.txt")

    violations: list[str] = []
    for spec in _declared_extras()[extra]:
        try:
            requirement = Requirement(spec)
        except InvalidRequirement:  # pragma: no cover - pyproject's own bug
            continue
        name = _canonical(requirement.name)
        if name not in lock or not str(requirement.specifier):
            continue
        if not requirement.specifier.contains(Version(lock[name]), prereleases=True):
            violations.append(
                f"{name}: locked {lock[name]} does not satisfy {requirement.specifier}"
            )

    assert not violations, (
        f"[{extra}] extra disagrees with requirements.txt: {violations}. "
        "A built distribution would record a specifier its own lock violates."
    )


#: Extras whose packages are deliberately absent from the CI lock, so the
#: lock-agreement control above has nothing to check for them.  ``[pareto]``
#: (pymoo) and ``[solar]`` (pvlib) are heavy opt-in scientific stacks guarded at
#: call time, not installed in the base lane.  Listed explicitly so the gap is
#: DECLARED rather than silent -- the control below fails in both directions, so
#: locking one of these, or a new extra going unlocked, forces a decision here.
_EXTRAS_DELIBERATELY_NOT_LOCKED = frozenset({"pareto", "solar"})


def test_no_extra_is_silently_vacuous() -> None:
    """Every extra either checks something, or is on the declared-gap list.

    ``test_declared_extra_specs_are_satisfied_by_the_lock`` skips any spec whose
    package is absent from the lock.  For ``[pareto]`` and ``[solar]`` that is
    the *only* spec, so those two parametrisations asserted ``not []`` -- they
    could not fail, and an unfailable control is unverified under VERIFY-01.
    They presented as two passing checks while checking nothing.
    """
    lock = _read_pins("requirements.txt")

    unlocked: set[str] = set()
    for extra, specs in _declared_extras().items():
        checked = [
            s
            for s in specs
            if _canonical(Requirement(s).name) in lock and str(Requirement(s).specifier)
        ]
        if not checked:
            unlocked.add(extra)

    undeclared = unlocked - _EXTRAS_DELIBERATELY_NOT_LOCKED
    assert not undeclared, (
        f"these extras assert nothing, because none of their packages is pinned in "
        f"requirements.txt: {sorted(undeclared)}. Lock them, or add them to "
        "_EXTRAS_DELIBERATELY_NOT_LOCKED so the gap is declared, not silent."
    )

    stale = _EXTRAS_DELIBERATELY_NOT_LOCKED - unlocked
    assert not stale, (
        f"{sorted(stale)} now have locked packages and are really being checked; "
        "remove them from _EXTRAS_DELIBERATELY_NOT_LOCKED"
    )


def test_every_dbpl_package_is_locked_and_within_its_declared_pin() -> None:
    """DBPL-01's complete stack must be locked, since the print core fails loud."""
    lock = _read_pins("requirements.txt")
    specs = _declared_extras()[DBPL_EXTRA]

    names = {_canonical(Requirement(s).name) for s in specs}
    missing = {"weasyprint", "reportlab", "geopandas", "contextily"} - names
    incomplete = (
        f"DBPL-01 requires the COMPLETE [report] extra; {sorted(missing)} not declared"
    )
    assert not missing, incomplete

    for spec in specs:
        requirement = Requirement(spec)
        name = _canonical(requirement.name)
        unpinned = f"[report] package {name} is not pinned in requirements.txt"
        assert name in lock, unpinned
        assert requirement.specifier.contains(Version(lock[name]), prereleases=True), (
            f"{name} locked at {lock[name]}, outside declared {requirement.specifier}; "
            "require_dbpl_stack() would raise DbplDependencyError at render time"
        )


# ── Hard-coded version literals in integration guards ────────────────────────
#
# Several integration guards assert an exact installed version as a string
# literal.  Each is another declaration of the same pin, duplicated away from the
# lock, and a bump that misses one fails deep in a slow integration shard rather
# than here.  That is exactly how the WeasyPrint 70.0 bump first broke CI.
#
# Parsed with ``ast`` rather than a regex: a regex matched the same text inside
# comments and docstrings, so documenting this control inside a file it governs
# turned the suite red.


def _version_asserts_in(path: Path) -> list[tuple[str, str]]:
    """Return ``(distribution, asserted version)`` pairs from real code in *path*.

    A **list**, not a dict.  Keying by distribution meant the last occurrence in
    a file won, so a genuine stale ``== "69.0"`` followed later by a correct
    ``== "70.0"`` passed this control -- the motivating bug surviving the guard
    written for it.
    """
    found: list[tuple[str, str]] = []
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare) or len(node.comparators) != 1:
            continue
        if not isinstance(node.ops[0], ast.Eq):
            continue
        for call, other in (
            (node.left, node.comparators[0]),
            (node.comparators[0], node.left),
        ):
            if (
                isinstance(call, ast.Call)
                and isinstance(call.func, ast.Name | ast.Attribute)
                and (
                    call.func.id if isinstance(call.func, ast.Name) else call.func.attr
                )
                == "version"
                and len(call.args) == 1
                and isinstance(call.args[0], ast.Constant)
                and isinstance(call.args[0].value, str)
                and isinstance(other, ast.Constant)
                and isinstance(other.value, str)
            ):
                found.append((_canonical(call.args[0].value), other.value))
    return found


def _hard_coded_version_asserts() -> dict[Path, list[tuple[str, str]]]:
    """Map each integration guard to the ``(distribution, version)`` pairs it asserts.

    ``rglob``, not ``glob``: the non-recursive form missed a stale literal moved
    one directory down.
    """
    found: dict[Path, list[tuple[str, str]]] = {}
    for path in sorted((REPO_ROOT / "tests" / "integration").rglob("*.py")):
        pairs = _version_asserts_in(path)
        if pairs:
            found[path] = pairs
    return found


def test_the_version_assert_scanner_still_finds_its_subjects() -> None:
    """Guard the guard: a scanner that matched nothing would pass everything.

    Both known subject files are named, not just one distribution: re-spelling
    every literal in one file made that whole file invisible while the control
    stayed green.
    """
    found = _hard_coded_version_asserts()
    assert found, "no hard-coded version asserts found; the scanner has gone blind"

    seen = {path.name for path in found}
    for expected in ("test_report_jobs_tooling.py", "test_ingestion_tooling.py"):
        assert expected in seen, (
            f"{expected} no longer contributes version asserts; if its literals were "
            "deliberately removed, update this control with them"
        )

    distributions = {name for pairs in found.values() for name, _ in pairs}
    assert "weasyprint" in distributions


def test_hard_coded_version_asserts_match_the_lock() -> None:
    """An integration guard may not assert a version the lock contradicts.

    This is the control the three-file check alone did not provide, and the one
    that would have caught the WeasyPrint bump breaking
    ``tests/integration/test_report_jobs_tooling.py`` before CI did.
    """
    lock = _read_pins("requirements.txt")

    drift: list[str] = []
    for path, pairs in _hard_coded_version_asserts().items():
        rel = path.relative_to(REPO_ROOT)
        for name, asserted in pairs:
            locked = lock.get(name)
            if locked is not None and locked != asserted:
                drift.append(f"{rel}: asserts {name}=={asserted}, lock says {locked}")

    assert not drift, (
        "integration guards assert versions the lock contradicts; bump them together "
        f"or the failure surfaces in a slow shard instead of here: {drift}"
    )
