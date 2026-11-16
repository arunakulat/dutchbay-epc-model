"""Guard for ``.github/dependabot.yml``: it must parse, and its load-bearing entries must stay.

Until #1406 nothing parsed the file; ``test_gwtf_canonical_source.py`` only names it as a string. A
dropped ``ignore`` entry or a split group is silent: Dependabot proposes the bump, and the lock
then fails to install (#1326 split numba from llvmlite). The audit below reads the loaded YAML and
reports every way the file can lose one of those entries; the real file must audit clean, and each
deliberately broken fixture must not.

The expected sets are deliberate pins. Removing or relaxing an ``ignore`` entry is a policy
decision, so it takes an edit here as well as in the YAML, reviewed together.
"""

from __future__ import annotations

import copy
import fnmatch
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
DEPENDABOT = REPO_ROOT / ".github" / "dependabot.yml"

Config = dict[str, Any]

_MAJOR = "version-update:semver-major"
_MINOR = "version-update:semver-minor"
_PATCH = "version-update:semver-patch"
_UPDATE_TYPES = frozenset({_MAJOR, _MINOR, _PATCH})

#: Dependency -> the update types the pip ecosystem must ignore. Mirrors the rationale
#: comments in ``.github/dependabot.yml``.
EXPECTED_IGNORES: dict[str, frozenset[str]] = {
    "pandas": frozenset({_MAJOR}),
    "pandas-stubs": frozenset({_MAJOR}),
    "numpy": frozenset({_MAJOR, _MINOR}),
    "mpmath": frozenset({_MAJOR, _MINOR}),
    "scipy": frozenset({_MAJOR}),
    "scipy-stubs": frozenset({_MAJOR}),
    "pydantic": frozenset({_MAJOR}),
    "cachebox": frozenset({_MAJOR}),
    "redis": frozenset({_MAJOR}),
    "protobuf": frozenset({_MAJOR}),
    "pydantic-core": frozenset({_MAJOR, _MINOR, _PATCH}),
    "mypy": frozenset({_MAJOR, _MINOR, _PATCH}),
    "isort": frozenset({_MAJOR}),
    "ruff": frozenset({_MAJOR, _MINOR}),
    "black": frozenset({_MAJOR}),
    "antlr4-python3-runtime": frozenset({_MAJOR, _MINOR}),
    "pandapower": frozenset({_MAJOR, _MINOR, _PATCH}),
    "pyarrow": frozenset({_MAJOR}),
    "numpy-typing-compat": frozenset({_MAJOR, _MINOR, _PATCH}),
    "magika": frozenset({_MAJOR, _MINOR}),
    "openmdao": frozenset({_MAJOR, _MINOR}),
    "websockets": frozenset({_MAJOR}),
    "starlette": frozenset({_MAJOR}),
}

#: Groups the pip ecosystem must keep.
EXPECTED_GROUPS = frozenset(
    {"ingestion", "jobs", "numerics", "micrositing", "api-runtime", "numba-llvmlite"}
)

#: Packages that cannot be bumped apart: numba pins its llvmlite release exactly.
PAIRED = ("numba", "llvmlite")


def _pip(config: Config) -> Config:
    updates = config.get("updates")
    assert isinstance(updates, list), "`updates` must be a list"
    pip = [
        u
        for u in updates
        if isinstance(u, dict) and u.get("package-ecosystem") == "pip"
    ]
    assert len(pip) == 1, f"expected exactly one pip ecosystem, got {len(pip)}"
    return pip[0]


def _groups_matching(groups: Config, name: str) -> list[str]:
    matched = []
    for group, body in groups.items():
        patterns = body.get("patterns") if isinstance(body, dict) else None
        if isinstance(patterns, list) and any(
            isinstance(p, str) and fnmatch.fnmatchcase(name, p) for p in patterns
        ):
            matched.append(group)
    return matched


def audit_dependabot(config: Config) -> list[str]:
    """Return one message per way ``config`` drops or malforms a load-bearing entry."""
    if not isinstance(config, dict):
        return ["dependabot.yml does not load as a mapping"]
    if config.get("version") != 2:
        return [f"`version` must be 2, got {config.get('version')!r}"]
    try:
        pip = _pip(config)
    except AssertionError as exc:
        return [str(exc)]

    problems: list[str] = []

    groups = pip.get("groups")
    if not isinstance(groups, dict):
        problems.append("pip ecosystem has no `groups` mapping")
        groups = {}
    for missing in sorted(EXPECTED_GROUPS - set(groups)):
        problems.append(f"group {missing!r} is missing")
    for name, body in groups.items():
        patterns = body.get("patterns") if isinstance(body, dict) else None
        if not isinstance(patterns, list) or not patterns:
            problems.append(f"group {name!r} has no `patterns` list")
        elif not all(isinstance(p, str) and p for p in patterns):
            problems.append(f"group {name!r} has a malformed pattern")
    homes = {name: _groups_matching(groups, name) for name in PAIRED}
    if (
        any(len(h) != 1 for h in homes.values())
        or len({h[0] for h in homes.values() if h}) != 1
    ):
        problems.append(
            f"{' and '.join(PAIRED)} must land in one shared group, got {homes}"
        )

    ignores = pip.get("ignore")
    if not isinstance(ignores, list):
        problems.append("pip ecosystem has no `ignore` list")
        ignores = []
    seen: dict[str, frozenset[str]] = {}
    for entry in ignores:
        name = entry.get("dependency-name") if isinstance(entry, dict) else None
        types = entry.get("update-types") if isinstance(entry, dict) else None
        if not isinstance(name, str) or not name:
            problems.append(f"ignore entry without a `dependency-name`: {entry!r}")
            continue
        if not isinstance(types, list) or not types:
            problems.append(f"ignore entry {name!r} has no `update-types` list")
            continue
        unknown = sorted(set(map(str, types)) - _UPDATE_TYPES)
        if unknown:
            problems.append(f"ignore entry {name!r} has unknown update types {unknown}")
        seen[name] = seen.get(name, frozenset()) | frozenset(map(str, types))
    for name, expected in EXPECTED_IGNORES.items():
        if name not in seen:
            problems.append(f"ignore entry {name!r} was dropped")
        elif not expected <= seen[name]:
            lost = sorted(expected - seen[name])
            problems.append(f"ignore entry {name!r} no longer blocks {lost}")
    return problems


def _load() -> Config:
    loaded: Config = yaml.safe_load(DEPENDABOT.read_text(encoding="utf-8"))
    return loaded


def test_dependabot_yml_audits_clean() -> None:
    assert audit_dependabot(_load()) == []


def test_numba_and_llvmlite_share_one_group() -> None:
    """A split numba/llvmlite bump cannot install (#1326), so one group must name both."""
    groups = _pip(_load())["groups"]
    assert _groups_matching(groups, "numba") == ["numba-llvmlite"]
    assert _groups_matching(groups, "llvmlite") == ["numba-llvmlite"]


def _mutated(mutate: Any) -> Config:
    config = copy.deepcopy(_load())
    mutate(_pip(config))
    return config


def _drop_ignore(name: str) -> Any:
    def mutate(pip: Config) -> None:
        pip["ignore"] = [e for e in pip["ignore"] if e["dependency-name"] != name]

    return mutate


def _narrow_ignore(name: str) -> Any:
    def mutate(pip: Config) -> None:
        for entry in pip["ignore"]:
            if entry["dependency-name"] == name:
                entry["update-types"] = [_MAJOR]

    return mutate


def _split_pair(pip: Config) -> None:
    pip["groups"]["numba-llvmlite"]["patterns"] = ["numba"]


def _pair_in_two_groups(pip: Config) -> None:
    pip["groups"]["numba-llvmlite"]["patterns"] = ["numba"]
    pip["groups"]["numerics"]["patterns"].append("llvmlite")


BROKEN = {
    "numba and llvmlite split": (_split_pair, "shared group"),
    "numba and llvmlite in two groups": (_pair_in_two_groups, "shared group"),
    "pair group dropped": (lambda p: p["groups"].pop("numba-llvmlite"), "is missing"),
    "groups removed": (lambda p: p.pop("groups"), "no `groups`"),
    "pattern list emptied": (
        lambda p: p["groups"]["jobs"].update(patterns=[]),
        "no `patterns`",
    ),
    "ignore list removed": (lambda p: p.pop("ignore"), "no `ignore`"),
    "ignore entry dropped": (_drop_ignore("numpy"), "'numpy' was dropped"),
    "exact-pin ignore dropped": (_drop_ignore("pydantic-core"), "'pydantic-core'"),
    "ignore narrowed to majors": (_narrow_ignore("mpmath"), "no longer blocks"),
    "ignore without a name": (
        lambda p: p["ignore"].append({"update-types": [_MAJOR]}),
        "without a `dependency-name`",
    ),
    "ignore without update types": (
        lambda p: p["ignore"].append({"dependency-name": "extra"}),
        "no `update-types`",
    ),
    "ignore with a misspelt update type": (
        lambda p: p["ignore"][0].update({"update-types": ["version-update:major"]}),
        "unknown update types",
    ),
}


@pytest.mark.parametrize("case", sorted(BROKEN))
def test_the_audit_rejects_a_broken_fixture(case: str) -> None:
    mutate, expected = BROKEN[case]
    problems = audit_dependabot(_mutated(mutate))
    assert any(expected in p for p in problems), problems


@pytest.mark.parametrize("loaded", [None, [], "text", {"version": 1}, {"version": 2}])
def test_the_audit_rejects_a_file_that_is_not_a_dependabot_config(loaded: Any) -> None:
    assert audit_dependabot(loaded)
