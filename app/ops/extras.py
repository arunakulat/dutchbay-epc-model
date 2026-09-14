"""Optional-extra availability probe — CASPER state read from package metadata.

Why this exists
---------------
Verifying what an *already-deployed* instance actually has installed previously required shell
or deploy access to the machine. That is an ops-credential dependency sitting in front of a
question that is really about the runtime's own state, and it blocks anyone without those
credentials — including CI, and including a reviewer checking a claim.

This module lets the instance answer for itself. Paired with the ``/health/readiness`` route it
turns "log into Fly and look" into "GET the endpoint", which needs no credential at all.

Single source of truth
----------------------
The declared pins come from whichever artifact governs the code that is actually **executing**:
the ``pyproject.toml`` beside this package when there is one, and the installed distribution's
recorded metadata otherwise.

That matters: a pre-existing hard-coded ``GRID_EXTRA_PINS`` table in
:mod:`app.reports.grid_screening_emit` drifted from the project declaration, so the grid report
surfaced false dependency provenance. Reading the project's own declaration removes that whole
class of bug rather than correcting one instance of it.

Why not metadata alone
----------------------
This module used to read metadata *only*, reasoning that it is generated from ``pyproject.toml``
at build time and therefore "cannot drift". Metadata is indeed authoritative for the distribution
it describes — but it is not authoritative for a source tree it did not build, and locally those
are not the same tree.

``app/`` is deliberately not a packaged directory (see the ``Dockerfile`` header and
``[tool.setuptools.packages.find]``), so this very module always loads from the checkout, and
ENV-01 puts the active checkout first on ``PYTHONPATH`` so ``analytics`` and ``finance`` do too.
One non-editable install in the shared governed venv therefore served eighteen worktrees sitting
at differing commits, and the pins it reported described whichever checkout last built it.
Observed 2026-09-14: a build declaring ``weasyprint<70,>=69`` outlived the ``>=70,<71`` bump of
#1256, and reconciling the venv to the pinned 70.0 turned a latent mismatch into nine hard
:class:`~app.reports.dbpl.print_core.DbplDependencyError` failures — the guard rejecting the very
version the lock requires. A venv built by ``setup_venv.sh`` alone has no project distribution at
all, which made the extra declare nothing and failed every DBPL PDF outright. CI saw neither: it
installs with ``pip install -e``, whose metadata is rebuilt at every install.

Reading the executing tree's own declaration removes both failure modes without installing
anything, and stays correct in the container, where the editable install's source and
``/app/pyproject.toml`` are the same tree. :attr:`ExtraStatus.spec_source` records which artifact
answered, because a pin whose provenance is invisible is the class of bug this module exists to
prevent.

Installed is not the same as working
------------------------------------
Metadata presence proves a distribution is installed. It does **not** prove it imports: WeasyPrint
is installed-but-broken without the pango/cairo system libraries, and that is precisely the failure
an image build can introduce. :func:`probe_extra` therefore reports ``installed`` from metadata
(cheap, always safe) and, when ``deep=True``, additionally attempts the import and reports
``importable``. The two are kept as separate fields because conflating them is the mistake.

CASPER
------
Every probe degrades rather than raising. A distribution that is absent, a requirement string that
cannot be parsed, or an import that fails for any reason produces an honest recorded state — never
an exception out of this module. A health endpoint that can crash is worse than no health endpoint.

GWTF:
    - CESSPIT: the one hard failure is asking for an extra the distribution does not declare, which
      is a caller bug and raises :class:`UnknownExtraError`. Runtime *state* is always reported,
      never raised on.
    - CCCDIR: pure introspection. No finance, no scenario, no engine imports; nothing here can
      influence canonical KPIs.
"""

from __future__ import annotations

import importlib
import importlib.metadata as importlib_metadata
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Iterable, Mapping, Optional

from packaging.requirements import InvalidRequirement, Requirement

__all__ = [
    "DEFAULT_DISTRIBUTION",
    "DEPLOYED_EXTRAS",
    "PackageStatus",
    "ExtraStatus",
    "ExtraDeclarations",
    "UnknownExtraError",
    "declared_extras",
    "resolve_declared_extras",
    "probe_extra",
    "probe_extras",
]

#: The project's own distribution name, as recorded in package metadata.
DEFAULT_DISTRIBUTION = "dutchbay-epc-model"

#: The extras the deployed image installs (``Dockerfile``: ``pip install -e '.[api,jobs,report]'``).
#: Probing exactly these is what makes a deployment check meaningful rather than decorative.
DEPLOYED_EXTRAS: tuple[str, ...] = ("api", "jobs", "report")

#: Distribution names whose import name differs from the distribution name. Only needed for the
#: opt-in deep probe; the metadata probe keys on the distribution name throughout.
_IMPORT_NAME_OVERRIDES: Mapping[str, str] = {
    "opendssdirect.py": "opendssdirect",
    "redis": "redis",
    "markitdown": "markitdown",
    "opendssdirect": "opendssdirect",
}

#: Leading distribution name in a PEP 508 requirement string, e.g. ``redis[hiredis]<6,>=5`` ->
#: ``redis``. The health-probe hot path retains this small regex; the lender-facing grid provenance
#: path uses the now-direct runtime dependency ``packaging.Requirement`` for strict PEP 508 parsing.
_REQ_NAME_RE = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")

#: Marker fragment identifying which extra a requirement belongs to.
_EXTRA_MARKER_RE = re.compile(r"""extra\s*==\s*['"]([^'"]+)['"]""")

#: The ``pyproject.toml`` governing the source tree this module was loaded from. ``app/`` is not
#: a packaged directory, so this file always resolves inside a checkout — or ``/app`` in the
#: container image — and the project root is two levels above ``app/ops/``. Module-level so a
#: test can point the resolution at a different tree.
GOVERNING_PYPROJECT = Path(__file__).resolve().parents[2] / "pyproject.toml"

#: PEP 503 name normalization, so ``dutchbay_epc_model`` and ``dutchbay-epc-model`` compare equal.
_NAME_SEPARATOR_RE = re.compile(r"[-_.]+")


def _normalize_distribution(name: str) -> str:
    """Return ``name`` in PEP 503 normalized form."""
    return _NAME_SEPARATOR_RE.sub("-", name).lower()


def _read_pyproject_extras(
    distribution: str,
) -> tuple[Optional[Mapping[str, tuple[str, ...]]], Optional[str]]:
    """Read pyproject declarations and preserve present-source failures.

    A missing file or different distribution is ordinary absence and returns ``(None, None)``.
    Present-but-unreadable, malformed, or structurally invalid content returns a diagnostic so
    lender-facing consumers can fail loudly while health probes still degrade.
    """
    try:
        with GOVERNING_PYPROJECT.open("rb") as handle:
            project = tomllib.load(handle)["project"]
    except FileNotFoundError:
        return None, None
    except (
        Exception
    ) as exc:  # noqa: BLE001 - retain failure while CASPER consumers degrade
        return (
            None,
            f"governing pyproject is unreadable or malformed: {type(exc).__name__}: {exc}",
        )

    try:
        if _normalize_distribution(str(project["name"])) != _normalize_distribution(
            distribution
        ):
            return None, None
        optional = (
            project["optional-dependencies"]
            if "optional-dependencies" in project
            else {}
        )
        if not isinstance(optional, Mapping):
            raise TypeError("project.optional-dependencies must be a table")
        for extra, requirements in optional.items():
            if not isinstance(requirements, list) or not all(
                isinstance(requirement, str) for requirement in requirements
            ):
                raise TypeError(
                    f"project.optional-dependencies.{extra} must be an array of strings"
                )
        extras = {
            str(extra): tuple(str(requirement).strip() for requirement in requirements)
            for extra, requirements in optional.items()
        }
        return extras, None
    except Exception as exc:  # noqa: BLE001 - retain malformed declaration detail
        return (
            None,
            f"governing pyproject declaration is malformed: {type(exc).__name__}: {exc}",
        )


def _pyproject_extras(
    distribution: str,
) -> Optional[Mapping[str, tuple[str, ...]]]:
    """CASPER projection of declarations from the governing pyproject."""
    return _read_pyproject_extras(distribution)[0]


def _metadata_declaration_without_selector(
    requirement: str,
) -> tuple[tuple[str, ...], Optional[str], Optional[str]]:
    """Associate metadata safely without laundering marker semantics.

    Installed ``Requires-Dist`` uses a marker to associate a requirement with an extra. Only a
    marker whose *entire* expression is one ``extra == "name"`` selector can be removed without
    changing the declaration. Any compound expression is retained verbatim (after packaging's
    normalization), so the strict lender resolver rejects rather than silently weakening it.
    """
    parsed = Requirement(requirement)
    if parsed.marker is None:
        return (), None, None

    marker = str(parsed.marker)
    selectors = tuple(dict.fromkeys(_EXTRA_MARKER_RE.findall(marker)))
    base = requirement.split(";", 1)[0].strip()
    if len(selectors) == 1 and _EXTRA_MARKER_RE.fullmatch(marker) is not None:
        return selectors, base, None
    if selectors:
        # Equality selectors are sufficient to associate the declaration, but removing even one
        # atom from a compound expression would change its meaning. Keep the complete marker.
        return selectors, f"{base}; {marker}", None
    if re.search(r"\bextra\b", marker):
        return (
            (),
            None,
            f"unsupported metadata extra association marker: {marker}",
        )
    # A marker that does not reference ``extra`` describes a base dependency, not an optional
    # dependency association, and is intentionally outside this extras projection.
    return (), None, None


def _read_metadata_extras(
    distribution: str,
) -> tuple[Mapping[str, tuple[str, ...]], Optional[str]]:
    """Read installed metadata declarations while retaining malformed-source detail."""
    try:
        requirements = importlib_metadata.requires(distribution) or []
    except importlib_metadata.PackageNotFoundError:
        return {}, None
    except (
        Exception
    ) as exc:  # noqa: BLE001 - health callers degrade; lender callers inspect
        return {}, f"installed metadata is unreadable: {type(exc).__name__}: {exc}"

    grouped: dict[str, list[str]] = {}
    errors: list[str] = []
    for requirement in requirements:
        try:
            extras, declaration, association_error = (
                _metadata_declaration_without_selector(requirement)
            )
        except InvalidRequirement as exc:
            errors.append(f"invalid requirement {requirement!r}: {exc}")
            continue
        if association_error is not None:
            errors.append(association_error)
        if declaration is None:
            continue
        for extra in extras:
            grouped.setdefault(extra, []).append(declaration)
    result = {extra: tuple(reqs) for extra, reqs in grouped.items()}
    return result, "; ".join(errors) if errors else None


def _metadata_extras(distribution: str) -> Mapping[str, tuple[str, ...]]:
    """CASPER projection of optional dependencies from installed metadata."""
    return _read_metadata_extras(distribution)[0]


class UnknownExtraError(KeyError):
    """Raised when a caller asks for an extra the distribution does not declare."""


@dataclass(frozen=True)
class PackageStatus:
    """The state of ONE package inside an optional extra.

    Fields
        distribution: the distribution name, e.g. ``weasyprint``.
        declared_spec: version-specifier text extracted from the declaration selected from the
            governing ``pyproject.toml`` or installed distribution metadata. Empty string when
            the requirement pins nothing. Consult ``ExtraStatus.spec_source`` for the supplying
            artifact; this field alone does not identify its source.
        installed_version: the resolved installed version, or ``None`` when absent.
        installed: True iff the distribution is present in the environment.
        importable: True/False when a deep probe ran, else ``None`` (not probed). Kept separate
            from ``installed`` because a package can be installed yet fail to import — WeasyPrint
            without pango/cairo is the canonical case.
        import_error: the exception summary when a deep probe failed, else ``None``.
        satisfies_spec: whether the installed version satisfies ``declared_spec``; ``None`` when
            not installed, nothing is pinned, or the version/specifier cannot be evaluated.
    """

    distribution: str
    declared_spec: str
    installed_version: Optional[str] = None
    installed: bool = False
    importable: Optional[bool] = None
    import_error: Optional[str] = None
    satisfies_spec: Optional[bool] = None

    @property
    def healthy(self) -> bool:
        """Installed, satisfying its pin if that could be checked, and importable if probed."""
        if not self.installed:
            return False
        if self.satisfies_spec is False:
            return False
        return self.importable is not False


@dataclass(frozen=True)
class ExtraDeclarations:
    """One deeply immutable observation of declarations, source and resolution diagnostics."""

    extras: Mapping[str, tuple[str, ...]]
    spec_source: str
    resolution_error: Optional[str] = None

    def __post_init__(self) -> None:
        copied = {str(extra): tuple(values) for extra, values in self.extras.items()}
        object.__setattr__(self, "extras", MappingProxyType(copied))


@dataclass(frozen=True)
class ExtraStatus:
    """The state of one optional extra as a whole.

    Fields
        extra: the extra name, e.g. ``report``.
        packages: the probed state of each package the extra declares.
        deep: whether the probe also attempted an import of each package.
        spec_source: which artifact the declared pins were read from — ``pyproject`` (the
            executing tree's own declaration), ``metadata`` (the installed distribution), or
            ``none`` (neither could answer). Surfaced rather than inferred, because the two can
            disagree and a pin whose provenance is invisible is exactly how this drifted.
    """

    extra: str
    packages: tuple[PackageStatus, ...] = ()
    deep: bool = False
    spec_source: str = "unknown"

    @property
    def available(self) -> bool:
        """True iff every declared package in the extra is healthy."""
        return bool(self.packages) and all(p.healthy for p in self.packages)

    @property
    def missing(self) -> tuple[str, ...]:
        """Distributions declared by the extra but not installed."""
        return tuple(p.distribution for p in self.packages if not p.installed)

    @property
    def broken(self) -> tuple[str, ...]:
        """Distributions installed but unusable — failed import, or violating their pin."""
        return tuple(
            p.distribution
            for p in self.packages
            if p.installed and (p.importable is False or p.satisfies_spec is False)
        )

    def as_dict(self) -> dict[str, object]:
        """JSON-safe projection for a health endpoint."""
        return {
            "available": self.available,
            "deep_probed": self.deep,
            "spec_source": self.spec_source,
            "missing": list(self.missing),
            "broken": list(self.broken),
            "packages": [
                {
                    "distribution": p.distribution,
                    "declared_spec": p.declared_spec,
                    "installed_version": p.installed_version,
                    "installed": p.installed,
                    "importable": p.importable,
                    "import_error": p.import_error,
                    "satisfies_spec": p.satisfies_spec,
                }
                for p in self.packages
            ],
        }


def _requirement_name(requirement: str) -> Optional[str]:
    """Leading distribution name of a PEP 508 requirement string, or ``None`` if unparseable."""
    match = _REQ_NAME_RE.match(requirement)
    return match.group(1) if match else None


def _requirement_spec(requirement: str, name: str) -> str:
    """The source specifier portion with dependency extras and markers removed."""
    body = requirement.split(";", 1)[0].strip()
    remainder = body[len(name) :].strip() if body.startswith(name) else body
    if remainder.startswith("["):  # drop an extras group, e.g. redis[hiredis]<6,>=5
        _, _, remainder = remainder.partition("]")
    return remainder.strip()


def declared_extras(
    distribution: str = DEFAULT_DISTRIBUTION,
) -> Mapping[str, tuple[str, ...]]:
    """Map every declared extra to its requirement strings.

    Read from the governing ``pyproject.toml`` when that file declares ``distribution``, and from
    the installed distribution's metadata otherwise. The module docstring explains why the
    executing tree's own declaration outranks metadata that may describe a different tree.

    Returns an empty mapping when neither source can answer — an unknown distribution, or a
    checkout with no ``pyproject.toml`` and nothing installed — rather than raising, so a probe
    degrades to "nothing known" instead of crashing a health route.
    """
    return resolve_declared_extras(distribution).extras


def resolve_declared_extras(
    distribution: str = DEFAULT_DISTRIBUTION,
) -> ExtraDeclarations:
    """Read optional dependencies and source in one atomic resolver observation.

    The returned mapping and ``spec_source`` always describe the same lookup. Callers that
    surface provenance must consume this object instead of separately calling
    :func:`declared_extras` and a source probe, because the governing tree can change between
    independent observations.
    """
    from_pyproject, pyproject_error = _read_pyproject_extras(distribution)
    if from_pyproject is not None:
        return ExtraDeclarations(extras=from_pyproject, spec_source="pyproject")
    from_metadata, metadata_error = _read_metadata_extras(distribution)
    resolution_errors = tuple(
        error for error in (pyproject_error, metadata_error) if error is not None
    )
    return ExtraDeclarations(
        extras=from_metadata,
        spec_source="metadata" if from_metadata else "none",
        resolution_error="; ".join(resolution_errors) if resolution_errors else None,
    )


def _check_spec(version: str, spec: str) -> Optional[bool]:
    """Whether ``version`` satisfies ``spec``; ``None`` when it cannot be evaluated.

    CASPER: although ``packaging`` is a direct runtime dependency, an unavailable/broken import
    or an invalid version/specifier still degrades this health probe to ``None``.
    """
    if not spec:
        return None
    try:
        from packaging.specifiers import SpecifierSet
        from packaging.version import Version

        return Version(version) in SpecifierSet(spec)
    except Exception:  # noqa: BLE001 - CASPER: unknown beats crashing a health route
        return None


def _probe_package(requirement: str, *, deep: bool) -> Optional[PackageStatus]:
    """Probe one requirement string. ``None`` when the requirement cannot be parsed."""
    name = _requirement_name(requirement)
    if name is None:
        return None
    spec = _requirement_spec(requirement, name)

    version: Optional[str] = None
    try:
        version = importlib_metadata.version(name)
    except importlib_metadata.PackageNotFoundError:
        version = None
    except (
        Exception
    ):  # noqa: BLE001 - CASPER: a malformed dist must not crash the probe
        version = None

    installed = version is not None
    importable: Optional[bool] = None
    import_error: Optional[str] = None
    if deep and installed:
        module = _IMPORT_NAME_OVERRIDES.get(name, name.replace("-", "_"))
        try:
            importlib.import_module(module)
            importable = True
        except (
            Exception
        ) as exc:  # noqa: BLE001 - the whole point is to catch native-lib failures
            importable = False
            import_error = f"{type(exc).__name__}: {exc}"[:200]

    return PackageStatus(
        distribution=name,
        declared_spec=spec,
        installed_version=version,
        installed=installed,
        importable=importable,
        import_error=import_error,
        satisfies_spec=_check_spec(version, spec) if installed and version else None,
    )


def _probe_extra_from_declarations(
    extra: str,
    *,
    distribution: str,
    declarations: ExtraDeclarations,
    deep: bool = False,
) -> ExtraStatus:
    """Probe one extra from one already-resolved declaration/source observation."""
    extras = declarations.extras
    if extras and extra not in extras:
        raise UnknownExtraError(
            f"{distribution!r} declares no extra {extra!r}; known: {sorted(extras)}"
        )
    statuses = [_probe_package(req, deep=deep) for req in extras.get(extra, ())]
    return ExtraStatus(
        extra=extra,
        packages=tuple(s for s in statuses if s is not None),
        deep=deep,
        spec_source=declarations.spec_source,
    )


def probe_extra(
    extra: str,
    *,
    distribution: str = DEFAULT_DISTRIBUTION,
    deep: bool = False,
) -> ExtraStatus:
    """Probe one optional extra from one atomic declaration/source observation.

    Args:
        extra: the extra name, e.g. ``report``.
        distribution: the distribution declaring it.
        deep: additionally attempt to import each installed package, so an
            installed-but-broken native dependency is caught. Costs real import time.

    Raises:
        UnknownExtraError: the distribution does not declare ``extra``. This is a caller bug, so
            it fails loud — unlike runtime state, which is always reported rather than raised on.
    """
    declarations = resolve_declared_extras(distribution)
    return _probe_extra_from_declarations(
        extra,
        distribution=distribution,
        declarations=declarations,
        deep=deep,
    )


def probe_extras(
    names: Iterable[str] = DEPLOYED_EXTRAS,
    *,
    distribution: str = DEFAULT_DISTRIBUTION,
    deep: bool = False,
) -> tuple[ExtraStatus, ...]:
    """Probe extras from one observation; unknown names degrade instead of raising."""
    declarations = resolve_declared_extras(distribution)
    results: list[ExtraStatus] = []
    for name in names:
        try:
            results.append(
                _probe_extra_from_declarations(
                    name,
                    distribution=distribution,
                    declarations=declarations,
                    deep=deep,
                )
            )
        except UnknownExtraError:
            results.append(
                ExtraStatus(
                    extra=name,
                    packages=(),
                    deep=deep,
                    spec_source=declarations.spec_source,
                )
            )
    return tuple(results)
