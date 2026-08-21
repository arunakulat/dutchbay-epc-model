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
The declared pins come from :func:`importlib.metadata.requires` on the installed distribution —
i.e. from the package's own recorded metadata, which is generated from ``pyproject.toml`` at build
time. They are therefore **authoritative and cannot drift**.

That matters: the pre-existing hard-coded ``GRID_EXTRA_PINS`` table in
:mod:`app.reports.grid_screening_emit` claimed in its docstring to be "kept in sync with
pyproject" and was not — it pinned ``pandapower==3.3.0`` while the project declared
``pandapower>=3.5,<4``, so the grid report surfaced a false pin as dependency provenance. Reading
metadata removes that whole class of bug rather than correcting one instance of it.

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
cannot be parsed, an import that fails for any reason, or a missing optional ``packaging`` library
all produce an honest recorded state — never an exception out of this module. A health endpoint
that can crash is worse than no health endpoint.

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
from dataclasses import dataclass
from typing import Iterable, Mapping, Optional

__all__ = [
    "DEFAULT_DISTRIBUTION",
    "DEPLOYED_EXTRAS",
    "PackageStatus",
    "ExtraStatus",
    "UnknownExtraError",
    "declared_extras",
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
#: ``redis``. Deliberately a small regex rather than a ``packaging`` import: ``packaging`` is a
#: TRANSITIVE dependency here, not a declared one, and this repository has already been bitten by
#: an undeclared dependency riding the requirements freeze (the #756 post-mortem). The optional
#: ``packaging`` use below is CASPER-guarded for the same reason.
_REQ_NAME_RE = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")

#: Marker fragment identifying which extra a requirement belongs to.
_EXTRA_MARKER_RE = re.compile(r"""extra\s*==\s*['"]([^'"]+)['"]""")


class UnknownExtraError(KeyError):
    """Raised when a caller asks for an extra the distribution does not declare."""


@dataclass(frozen=True)
class PackageStatus:
    """The state of ONE package inside an optional extra.

    Fields
        distribution: the distribution name, e.g. ``weasyprint``.
        declared_spec: the version specifier declared by the project, verbatim from metadata
            (e.g. ``<70,>=69``). Empty string when the requirement pins nothing.
        installed_version: the resolved installed version, or ``None`` when absent.
        installed: True iff the distribution is present in the environment.
        importable: True/False when a deep probe ran, else ``None`` (not probed). Kept separate
            from ``installed`` because a package can be installed yet fail to import — WeasyPrint
            without pango/cairo is the canonical case.
        import_error: the exception summary when a deep probe failed, else ``None``.
        satisfies_spec: whether the installed version satisfies ``declared_spec``; ``None`` when
            not installed, when nothing is pinned, or when the optional ``packaging`` library is
            unavailable to evaluate it.
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
class ExtraStatus:
    """The state of one optional extra as a whole."""

    extra: str
    packages: tuple[PackageStatus, ...] = ()
    deep: bool = False

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
    """The version specifier portion, verbatim, with any extras marker stripped."""
    body = requirement.split(";", 1)[0].strip()
    remainder = body[len(name) :].strip() if body.startswith(name) else body
    if remainder.startswith("["):  # drop an extras group, e.g. redis[hiredis]<6,>=5
        _, _, remainder = remainder.partition("]")
    return remainder.strip()


def declared_extras(
    distribution: str = DEFAULT_DISTRIBUTION,
) -> Mapping[str, tuple[str, ...]]:
    """Map every declared extra to its requirement strings, read from package metadata.

    Returns an empty mapping when the distribution is not installed as package metadata — which
    happens in a bare source checkout — rather than raising, so a probe degrades to "nothing
    known" instead of crashing a health route.
    """
    try:
        requirements = importlib_metadata.requires(distribution) or []
    except importlib_metadata.PackageNotFoundError:
        return {}

    grouped: dict[str, list[str]] = {}
    for requirement in requirements:
        marker = _EXTRA_MARKER_RE.search(requirement)
        if marker is None:
            continue
        grouped.setdefault(marker.group(1), []).append(
            requirement.split(";", 1)[0].strip()
        )
    return {extra: tuple(reqs) for extra, reqs in grouped.items()}


def _check_spec(version: str, spec: str) -> Optional[bool]:
    """Whether ``version`` satisfies ``spec``; ``None`` when it cannot be evaluated.

    CASPER: ``packaging`` is transitive here, not declared, so its absence degrades this to
    ``None`` rather than failing the probe.
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


def probe_extra(
    extra: str,
    *,
    distribution: str = DEFAULT_DISTRIBUTION,
    deep: bool = False,
) -> ExtraStatus:
    """Probe one optional extra.

    Args:
        extra: the extra name, e.g. ``report``.
        distribution: the distribution declaring it.
        deep: additionally attempt to import each installed package, so an
            installed-but-broken native dependency is caught. Costs real import time.

    Raises:
        UnknownExtraError: the distribution does not declare ``extra``. This is a caller bug, so
            it fails loud — unlike runtime state, which is always reported rather than raised on.
    """
    extras = declared_extras(distribution)
    if extras and extra not in extras:
        raise UnknownExtraError(
            f"{distribution!r} declares no extra {extra!r}; known: {sorted(extras)}"
        )
    statuses = [_probe_package(req, deep=deep) for req in extras.get(extra, ())]
    return ExtraStatus(
        extra=extra,
        packages=tuple(s for s in statuses if s is not None),
        deep=deep,
    )


def probe_extras(
    names: Iterable[str] = DEPLOYED_EXTRAS,
    *,
    distribution: str = DEFAULT_DISTRIBUTION,
    deep: bool = False,
) -> tuple[ExtraStatus, ...]:
    """Probe several extras. Unknown names degrade to an empty status rather than raising, so a
    health route stays up even if the deployed image declares a different extra set."""
    results: list[ExtraStatus] = []
    for name in names:
        try:
            results.append(probe_extra(name, distribution=distribution, deep=deep))
        except UnknownExtraError:
            results.append(ExtraStatus(extra=name, packages=(), deep=deep))
    return tuple(results)
