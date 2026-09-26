"""Tests for the optional-extra availability probe.

The probe backs a health endpoint, so the property that matters most is that it NEVER raises on
runtime state — an absent package, a broken import, or a malformed requirement must degrade to
an honest recorded value.
"""

from __future__ import annotations

import importlib.metadata as importlib_metadata
import tomllib
from pathlib import Path

import pytest

from app.ops import extras as ops_extras
from app.ops.extras import (
    DEPLOYED_EXTRAS,
    ExtraStatus,
    PackageStatus,
    UnknownExtraError,
    declared_extras,
    probe_extra,
    probe_extras,
)

# ── Declared pins come from the tree that is executing ───────────────────────


def test_declared_extras_reads_the_projects_own_declaration() -> None:
    extras = declared_extras()
    assert "report" in extras, "the project declares a [report] extra"
    joined = " ".join(extras["report"])
    for pkg in ("weasyprint", "reportlab", "geopandas", "contextily"):
        assert pkg in joined


def test_declared_extras_degrades_to_empty_for_an_unknown_distribution() -> None:
    assert declared_extras("no-such-distribution-xyz") == {}


def test_deployed_extras_are_all_declared_by_the_project() -> None:
    declared = declared_extras()
    for extra in DEPLOYED_EXTRAS:
        assert (
            extra in declared
        ), f"Dockerfile installs [{extra}] but pyproject does not declare it"


# ── Probing ──────────────────────────────────────────────────────────────────


def test_probe_extra_reports_declared_spec_and_installed_version() -> None:
    status = probe_extra("report")
    assert status.extra == "report"
    by_name = {p.distribution: p for p in status.packages}
    weasy = by_name["weasyprint"]
    assert weasy.declared_spec, "the declared specifier must be surfaced verbatim"
    assert weasy.installed is (weasy.installed_version is not None)


def test_unknown_extra_raises_because_it_is_a_caller_bug() -> None:
    with pytest.raises(UnknownExtraError, match="declares no extra"):
        probe_extra("definitely-not-an-extra")


def test_probe_extras_degrades_unknown_names_instead_of_raising() -> None:
    results = probe_extras(["report", "definitely-not-an-extra"])
    assert len(results) == 2
    assert results[1].packages == ()
    assert results[1].available is False


def test_deep_probe_records_importability_separately_from_installation() -> None:
    shallow = probe_extra("report", deep=False)
    deep = probe_extra("report", deep=True)
    assert all(
        p.importable is None for p in shallow.packages
    ), "shallow must not import"
    assert deep.deep is True
    assert all(p.importable is not None for p in deep.packages if p.installed)


# ── Derived state ────────────────────────────────────────────────────────────


def _pkg(**kw: object) -> PackageStatus:
    base: dict[str, object] = {"distribution": "x", "declared_spec": ">=1"}
    base.update(kw)
    return PackageStatus(**base)  # type: ignore[arg-type]


def test_installed_but_unimportable_is_not_healthy() -> None:
    pkg = _pkg(installed=True, installed_version="1.0", importable=False)
    assert pkg.healthy is False
    status = ExtraStatus("e", (pkg,), deep=True)
    assert status.available is False
    assert status.broken == ("x",)
    assert status.missing == ()


def test_installed_violating_its_pin_is_not_healthy() -> None:
    pkg = _pkg(installed=True, installed_version="0.1", satisfies_spec=False)
    assert pkg.healthy is False
    assert ExtraStatus("e", (pkg,)).broken == ("x",)


def test_absent_package_is_missing_not_broken() -> None:
    status = ExtraStatus("e", (_pkg(installed=False),))
    assert status.missing == ("x",)
    assert status.broken == ()
    assert status.available is False


def test_unevaluated_spec_does_not_make_a_package_unhealthy() -> None:
    # None means the spec could not be evaluated; that is unknown, not a failure.
    assert (
        _pkg(installed=True, installed_version="1.0", satisfies_spec=None).healthy
        is True
    )


def test_empty_extra_is_not_available() -> None:
    assert ExtraStatus("e", ()).available is False


def test_as_dict_is_json_safe_and_keeps_the_two_states_distinct() -> None:
    import json

    payload = ExtraStatus(
        "e", (_pkg(installed=True, installed_version="1.0", importable=True),)
    ).as_dict()
    json.dumps(payload)  # must not raise
    entry = payload["packages"][0]  # type: ignore[index]
    assert entry["installed"] is True  # type: ignore[index]
    assert entry["importable"] is True  # type: ignore[index]


# ── CASPER: runtime state never raises ───────────────────────────────────────


def test_malformed_requirement_is_skipped_not_raised(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        ops_extras,
        "resolve_declared_extras",
        lambda *a, **k: ops_extras.ExtraDeclarations(
            extras={"e": ("!!!bad!!!",)}, spec_source="pyproject"
        ),
    )
    assert probe_extra("e").packages == ()


def test_metadata_lookup_failure_degrades_to_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(_name: str) -> str:
        raise RuntimeError("corrupt dist-info")

    monkeypatch.setattr(importlib_metadata, "version", boom)
    status = probe_extra("report")
    assert status.available is False
    assert all(not p.installed for p in status.packages)


def test_import_failure_is_captured_not_raised(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(_name: str) -> object:
        raise OSError("cannot load library 'pango-1.0'")

    monkeypatch.setattr(ops_extras.importlib, "import_module", boom)
    status = probe_extra("report", deep=True)
    broken = [p for p in status.packages if p.importable is False]
    assert broken, "a native-library failure must be recorded"
    assert "pango" in (broken[0].import_error or "")
    assert status.available is False


def test_missing_packaging_degrades_spec_check_to_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_import = ops_extras.importlib.import_module

    def no_packaging(name: str, *a: object, **k: object) -> object:
        if name.startswith("packaging"):
            raise ImportError("no packaging")
        return real_import(name, *a, **k)

    monkeypatch.setattr(ops_extras.importlib, "import_module", no_packaging)
    monkeypatch.setitem(__import__("sys").modules, "packaging.specifiers", None)
    # _check_spec swallows any failure; the contract is that it returns None, never raises.
    assert ops_extras._check_spec("1.0", ">=1") in (True, None)
    assert ops_extras._check_spec("1.0", "") is None


# ── Requirement-string parsing ───────────────────────────────────────────────


@pytest.mark.parametrize(
    ("requirement", "name", "spec"),
    [
        ("weasyprint<71,>=70", "weasyprint", "<71,>=70"),
        ("redis[hiredis]<6,>=5", "redis", "<6,>=5"),
        ("opendssdirect.py>=0.9.4", "opendssdirect.py", ">=0.9.4"),
        ("reportlab>=4.0", "reportlab", ">=4.0"),
        ("bare-package", "bare-package", ""),
    ],
)
def test_requirement_parsing(requirement: str, name: str, spec: str) -> None:
    parsed = ops_extras._requirement_name(requirement)
    assert parsed == name
    assert ops_extras._requirement_spec(requirement, name) == spec


def test_requirement_name_of_garbage_is_none() -> None:
    assert ops_extras._requirement_name("!!!") is None


def test_genuinely_absent_package_is_reported_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The ordinary 'extra not installed' path — PackageNotFoundError, not an error state.

    Every package the project declares happens to be installed in the development venv, so this
    path is only reachable by declaring one that is not.
    """
    monkeypatch.setattr(
        ops_extras,
        "resolve_declared_extras",
        lambda *a, **k: ops_extras.ExtraDeclarations(
            extras={"e": ("definitely-not-installed-xyz>=1.0", "pytest>=7.0")},
            spec_source="pyproject",
        ),
    )
    status = probe_extra("e")
    by_name = {p.distribution: p for p in status.packages}

    absent = by_name["definitely-not-installed-xyz"]
    assert absent.installed is False
    assert absent.installed_version is None
    assert absent.satisfies_spec is None, "an absent package has no version to check"
    assert absent.healthy is False

    assert by_name["pytest"].installed is True
    assert status.available is False
    assert status.missing == ("definitely-not-installed-xyz",)
    assert status.broken == (), "absent is missing, not broken"


# ── Resolution: pyproject first, metadata as the deferral ────────────────────
#
# Regression guard for the 2026-09-14 defect. `app/` is not a packaged directory, so this
# module always executes from a checkout, while the installed distribution in the shared
# governed venv was built from whichever checkout last ran `pip install`. The pins it
# reported therefore described a tree that was not running. Two observed consequences:
# a build declaring `weasyprint<70,>=69` outlived the `>=70,<71` bump of #1256 and rejected
# the very version the lock requires, and a venv built by `setup_venv.sh` alone carried no
# project distribution at all, so the extra declared nothing and every DBPL PDF failed.


PYPROJECT = Path(__file__).resolve().parents[2] / "pyproject.toml"


def _stale_metadata(*specs: str):
    """An installed build whose recorded pins disagree with the checkout."""
    return lambda name: [f'{spec}; extra == "report"' for spec in specs]


def test_declared_extras_is_a_backward_projection_of_one_observation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = {"report": ("render-engine>=1",)}
    calls = 0

    def observe(*_args: object, **_kwargs: object) -> ops_extras.ExtraDeclarations:
        nonlocal calls
        calls += 1
        return ops_extras.ExtraDeclarations(extras=expected, spec_source="pyproject")

    monkeypatch.setattr(ops_extras, "resolve_declared_extras", observe)
    assert declared_extras() == expected
    assert calls == 1


def test_extra_declarations_are_deeply_immutable() -> None:
    source = {"grid": ["pandapower>=3.5,<4"]}
    observation = ops_extras.ExtraDeclarations(  # type: ignore[arg-type]
        extras=source, spec_source="pyproject"
    )
    source["grid"].append("substituted>=9")
    assert observation.extras["grid"] == ("pandapower>=3.5,<4",)
    with pytest.raises(TypeError):
        observation.extras["grid"] = ("substituted>=9",)  # type: ignore[index]


def test_probe_extra_cannot_mix_values_with_a_later_source_observation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A changing resolver cannot relabel first-read declarations at ExtraStatus."""
    calls = 0

    def changing(*_args: object, **_kwargs: object) -> ops_extras.ExtraDeclarations:
        nonlocal calls
        calls += 1
        if calls == 1:
            return ops_extras.ExtraDeclarations(
                extras={"report": ("first-source-package>=1",)},
                spec_source="pyproject",
            )
        return ops_extras.ExtraDeclarations(
            extras={"report": ("substituted-package>=9",)},
            spec_source="metadata",
        )

    monkeypatch.setattr(ops_extras, "resolve_declared_extras", changing)
    status = probe_extra("report")
    assert calls == 1
    assert status.spec_source == "pyproject"
    assert [package.distribution for package in status.packages] == [
        "first-source-package"
    ]


def test_probe_extras_reuses_one_observation_for_the_entire_tuple(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One returned status tuple cannot contain declarations from different sources."""
    calls = 0

    def changing(*_args: object, **_kwargs: object) -> ops_extras.ExtraDeclarations:
        nonlocal calls
        calls += 1
        if calls == 1:
            return ops_extras.ExtraDeclarations(
                extras={"alpha": ("alpha-package>=1",), "beta": ("beta-package>=2",)},
                spec_source="pyproject",
            )
        return ops_extras.ExtraDeclarations(
            extras={"alpha": ("substituted>=9",)}, spec_source="metadata"
        )

    monkeypatch.setattr(ops_extras, "resolve_declared_extras", changing)
    statuses = probe_extras(("alpha", "unknown", "beta"))
    assert calls == 1
    assert [status.spec_source for status in statuses] == [
        "pyproject",
        "pyproject",
        "pyproject",
    ]
    assert [package.distribution for package in statuses[0].packages] == [
        "alpha-package"
    ]
    assert statuses[1].packages == ()
    assert [package.distribution for package in statuses[2].packages] == [
        "beta-package"
    ]


def test_declared_pins_follow_the_executing_tree_not_the_installed_build(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The pins must come from the tree running, not from whatever last built the dist."""

    live = tuple(declared_extras()["report"])

    monkeypatch.setattr(
        ops_extras.importlib_metadata,
        "requires",
        _stale_metadata("weasyprint<70,>=69"),
    )

    # Negative control: metadata-only resolution -- the behaviour before this fix -- really
    # does return the stale pin, so the assertion below is not comparing against an inert stub.
    assert ops_extras._metadata_extras(ops_extras.DEFAULT_DISTRIBUTION)["report"] == (
        "weasyprint<70,>=69",
    )

    # The live resolution is unmoved by it.
    assert tuple(declared_extras()["report"]) == live
    assert probe_extra("report").spec_source == "pyproject"


def test_declared_pins_match_the_checkouts_pyproject_verbatim() -> None:
    """What is resolved is exactly what the active checkout declares."""

    with PYPROJECT.open("rb") as handle:
        optional = tomllib.load(handle)["project"]["optional-dependencies"]

    for extra, requirements in optional.items():
        assert tuple(declared_extras()[extra]) == tuple(requirements)


def test_an_absent_project_distribution_still_declares_the_extra(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A venv built by ./setup_venv.sh alone installs no project distribution at all."""

    def absent(name: str):
        raise importlib_metadata.PackageNotFoundError(name)

    monkeypatch.setattr(ops_extras.importlib_metadata, "requires", absent)

    # Negative control: metadata alone can say nothing here.
    assert ops_extras._metadata_extras(ops_extras.DEFAULT_DISTRIBUTION) == {}

    status = probe_extra("report")
    assert status.spec_source == "pyproject"
    assert {p.distribution for p in status.packages} >= {
        "weasyprint",
        "reportlab",
        "geopandas",
        "contextily",
    }


def test_metadata_answers_when_no_pyproject_sits_beside_the_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A deployed wheel has no source tree; metadata is then the only truthful source."""

    monkeypatch.setattr(
        ops_extras, "GOVERNING_PYPROJECT", Path("/nonexistent/pyproject.toml")
    )
    monkeypatch.setattr(
        ops_extras.importlib_metadata,
        "requires",
        _stale_metadata("weasyprint<70,>=69"),
    )

    status = probe_extra("report")
    assert status.spec_source == "metadata"
    assert [p.declared_spec for p in status.packages] == ["<70,>=69"]


def test_an_unparseable_pyproject_degrades_to_metadata(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """CASPER: an unreadable source defers to the other one, it never raises."""

    broken = tmp_path / "pyproject.toml"
    broken.write_text("this is not [valid toml at all ===\n", encoding="utf-8")
    monkeypatch.setattr(ops_extras, "GOVERNING_PYPROJECT", broken)

    assert probe_extra("report").spec_source == "metadata"
    observation = ops_extras.resolve_declared_extras()
    assert observation.spec_source == "metadata"
    assert observation.resolution_error is not None
    assert "unreadable or malformed" in observation.resolution_error


def test_an_unreadable_pyproject_path_is_distinct_from_absence(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    unreadable = tmp_path / "pyproject.toml"
    unreadable.mkdir()
    monkeypatch.setattr(ops_extras, "GOVERNING_PYPROJECT", unreadable)

    observation = ops_extras.resolve_declared_extras()
    assert observation.resolution_error is not None
    assert "IsADirectoryError" in observation.resolution_error


def test_missing_and_foreign_pyprojects_are_absence_not_resolution_errors(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(ops_extras, "GOVERNING_PYPROJECT", tmp_path / "missing.toml")
    assert ops_extras.resolve_declared_extras().resolution_error is None

    foreign = tmp_path / "foreign.toml"
    foreign.write_text('[project]\nname = "another-project"\n', encoding="utf-8")
    monkeypatch.setattr(ops_extras, "GOVERNING_PYPROJECT", foreign)
    assert ops_extras.resolve_declared_extras().resolution_error is None


def test_a_foreign_pyproject_does_not_answer_for_this_distribution(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Another project's pyproject must not be mistaken for ours."""

    foreign = tmp_path / "pyproject.toml"
    foreign.write_text(
        '[project]\nname = "somebody-elses-project"\n'
        '[project.optional-dependencies]\nreport = ["nonsense>=1"]\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(ops_extras, "GOVERNING_PYPROJECT", foreign)

    assert probe_extra("report").spec_source == "metadata"
    assert "nonsense" not in " ".join(declared_extras()["report"])


def test_a_hyphen_underscore_name_difference_still_matches() -> None:
    """PEP 503: dutchbay_epc_model and dutchbay-epc-model are the same distribution."""

    assert declared_extras("dutchbay_epc_model") == declared_extras(
        "dutchbay-epc-model"
    )


def test_spec_source_is_surfaced_for_a_health_route() -> None:
    """Provenance is reported, not inferred -- the two sources can disagree."""

    payload = probe_extra("report").as_dict()
    assert payload["spec_source"] in {"pyproject", "metadata", "none"}
