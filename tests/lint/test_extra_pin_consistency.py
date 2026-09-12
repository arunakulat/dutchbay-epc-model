"""CESSPIT pre-flight guard: the three places a dependency pin is declared must agree.

A ``[report]`` package is declared in three places, and nothing until now checked
that they say the same thing:

* ``requirements.txt`` -- the reproducibility lock CI installs and ``pip-audit`` reads;
* ``constraints.txt`` -- the resolver ceiling;
* ``pyproject.toml`` ``[project.optional-dependencies]`` -- the specifier that is
  baked into the built distribution's metadata.

The third is not documentation.  ``app.ops.extras.probe_extra`` reads
``declared_spec`` back out of that metadata and sets ``satisfies_spec``, and
``app.reports.dbpl.print_core.require_dbpl_stack`` raises
``DbplDependencyError`` when an installed package "violates its declared pin"
(DBPL-01).  So bumping the lock while leaving the ``pyproject`` ceiling behind
does not produce a version disagreement on paper -- it stops every DBPL PDF from
rendering at runtime, which is the deliverable itself.

That is precisely the drift ``app/ops/extras.py`` was written for; its module
docstring records a case where the image "should have matched pyproject and was
not".  This control makes the same class of drift fail in CI instead.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest
from packaging.requirements import Requirement
from packaging.version import Version

REPO_ROOT = Path(__file__).resolve().parents[2]

#: The extra whose pins are load-bearing at runtime, not merely at install time.
DBPL_EXTRA = "report"

_PIN_RE = re.compile(r"^([A-Za-z0-9._-]+)==([^\s;]+)$")


def _canonical(name: str) -> str:
    return name.lower().replace("_", "-")


def _read_pins(filename: str) -> dict[str, str]:
    """Return ``{canonical name: pinned version}`` for one ``==``-pinned file."""
    pins: dict[str, str] = {}
    for raw in (REPO_ROOT / filename).read_text().splitlines():
        line = raw.split("#", 1)[0].strip()
        match = _PIN_RE.match(line)
        if match:
            pins[_canonical(match.group(1))] = match.group(2)
    return pins


def _declared_extras() -> dict[str, list[str]]:
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())
    extras: dict[str, list[str]] = data["project"]["optional-dependencies"]
    return extras


def test_the_lock_is_not_empty() -> None:
    """Guard the guard: a parser that silently matched nothing would pass everything."""
    pins = _read_pins("requirements.txt")
    assert len(pins) > 100, f"only parsed {len(pins)} pins from requirements.txt"
    assert "weasyprint" in pins


def test_constraints_never_contradict_the_lock() -> None:
    """Where both files pin a package, they must pin the same version."""
    lock = _read_pins("requirements.txt")
    constraints = _read_pins("constraints.txt")

    assert constraints, "constraints.txt parsed to nothing"

    disagreements = {
        name: (lock[name], constraints[name])
        for name in lock.keys() & constraints.keys()
        if lock[name] != constraints[name]
    }
    assert not disagreements, (
        "requirements.txt and constraints.txt disagree "
        f"(name: lock vs constraint): {disagreements}"
    )


@pytest.mark.parametrize("extra", sorted(_declared_extras()))
def test_declared_extra_specs_are_satisfied_by_the_lock(extra: str) -> None:
    """Every locked version must satisfy the specifier pyproject declares for it.

    Checked for all extras, not just ``[report]``: the same metadata round-trip
    backs :func:`app.ops.extras.probe_extra` for every extra it can be asked about.
    """
    lock = _read_pins("requirements.txt")

    violations: list[str] = []
    for spec in _declared_extras()[extra]:
        try:
            requirement = Requirement(spec)
        except Exception:  # pragma: no cover - a malformed spec is pyproject's own bug
            continue
        name = _canonical(requirement.name)
        if name not in lock or not str(requirement.specifier):
            continue
        if not requirement.specifier.contains(Version(lock[name]), prereleases=True):
            violations.append(
                f"{name}: locked {lock[name]} does not satisfy declared {requirement.specifier}"
            )

    assert not violations, (
        f"[{extra}] extra disagrees with requirements.txt: {violations}. "
        "A built distribution would record a specifier its own lock violates."
    )


def test_every_dbpl_package_is_locked_and_within_its_declared_pin() -> None:
    """DBPL-01's complete stack must be locked, since the print core fails loud.

    ``require_dbpl_stack()`` raises when any of these is missing or violates its
    declared pin, so a gap here is not a degraded render -- it is no PDF at all.
    """
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
