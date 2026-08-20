"""Resolve and validate the governed DutchBay development environment.

The module deliberately uses only the Python standard library so it can inspect a
candidate environment before project dependencies are trusted.  It never creates or
modifies an environment; setup and activation remain separate responsibilities.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

POLICY_SCHEMA = "dutchbay.development_environment.v1"
RECEIPT_SCHEMA = "dutchbay.development_environment_receipt.v1"
DEFAULT_POLICY_PATH = (
    Path(__file__).with_name("config") / "development_environment.json"
)
_POLICY_FIELDS = frozenset(
    {
        "schema",
        "environment_variable",
        "portable_fallback",
        "python_major",
        "python_minor",
        "required_distributions",
        "project_distribution",
        "import_probe",
    }
)


class EnvironmentContractError(RuntimeError):
    """Raised when the selected development environment is unsafe or incomplete."""


@dataclass(frozen=True)
class EnvironmentPolicy:
    """Strict config-first policy for selecting and validating one environment."""

    schema: str
    environment_variable: str
    portable_fallback: str
    python_major: int
    python_minor: int
    required_distributions: tuple[str, ...]
    project_distribution: str
    import_probe: str


@dataclass(frozen=True)
class ResolvedEnvironment:
    """One environment selection bound to the active checkout."""

    path: Path
    source: str
    active_checkout: Path
    policy: EnvironmentPolicy

    @property
    def python(self) -> Path:
        """Return the candidate environment's Python executable path."""

        return self.path / "bin" / "python"


@dataclass(frozen=True)
class EnvironmentReceipt:
    """Concise validated facts for the selected environment and active checkout."""

    schema: str
    status: str
    environment_variable: str
    selection_source: str
    venv_path: str
    portable_fallback: str
    active_checkout: str
    python_executable: str
    python_version: str
    python_prefix: str
    import_probe: str
    import_path: str
    required_distributions: tuple[tuple[str, str], ...]
    project_install_url: str | None
    editable_project_install: bool
    foreign_checkout_paths: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-compatible receipt mapping."""

        return {
            "schema": self.schema,
            "status": self.status,
            "environment_variable": self.environment_variable,
            "selection_source": self.selection_source,
            "venv_path": self.venv_path,
            "portable_fallback": self.portable_fallback,
            "active_checkout": self.active_checkout,
            "python_executable": self.python_executable,
            "python_version": self.python_version,
            "python_prefix": self.python_prefix,
            "import_probe": self.import_probe,
            "import_path": self.import_path,
            "required_distributions": dict(self.required_distributions),
            "project_install_url": self.project_install_url,
            "editable_project_install": self.editable_project_install,
            "foreign_checkout_paths": list(self.foreign_checkout_paths),
        }


def _require_string(raw: Mapping[str, object], field: str) -> str:
    value = raw[field]
    if not isinstance(value, str) or not value.strip():
        raise EnvironmentContractError(
            f"Policy field {field!r} must be a non-empty string."
        )
    return value


def load_environment_policy(path: Path = DEFAULT_POLICY_PATH) -> EnvironmentPolicy:
    """Load the exact governed environment policy from JSON."""

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EnvironmentContractError(
            f"Cannot load environment policy {path}: {exc}"
        ) from exc
    if not isinstance(raw, dict) or set(raw) != _POLICY_FIELDS:
        raise EnvironmentContractError(
            "Environment policy fields must match the governed v1 schema exactly."
        )
    if raw["schema"] != POLICY_SCHEMA:
        raise EnvironmentContractError(
            f"Environment policy schema must be {POLICY_SCHEMA!r}."
        )
    if type(raw["python_major"]) is not int or type(raw["python_minor"]) is not int:
        raise EnvironmentContractError("Policy Python major/minor must be integers.")
    required = raw["required_distributions"]
    if (
        not isinstance(required, list)
        or not required
        or any(not isinstance(item, str) or not item.strip() for item in required)
        or len(set(required)) != len(required)
        or required != sorted(required, key=str.casefold)
    ):
        raise EnvironmentContractError(
            "required_distributions must be a non-empty, unique, sorted string list."
        )
    fallback = Path(_require_string(raw, "portable_fallback"))
    if fallback.is_absolute() or fallback.parts != (".venv",):
        raise EnvironmentContractError(
            "portable_fallback must be exactly the relative .venv path."
        )
    return EnvironmentPolicy(
        schema=POLICY_SCHEMA,
        environment_variable=_require_string(raw, "environment_variable"),
        portable_fallback=str(fallback),
        python_major=raw["python_major"],
        python_minor=raw["python_minor"],
        required_distributions=tuple(required),
        project_distribution=_require_string(raw, "project_distribution"),
        import_probe=_require_string(raw, "import_probe"),
    )


def _validate_checkout(path: Path) -> Path:
    try:
        resolved = path.expanduser().resolve(strict=True)
    except OSError as exc:
        raise EnvironmentContractError(
            f"Active checkout is unavailable: {path}: {exc}"
        ) from exc
    required = ("pyproject.toml", "go_with_the_flow_rules_v3_0_clean.csv")
    missing = [name for name in required if not (resolved / name).is_file()]
    if missing:
        raise EnvironmentContractError(
            f"Active checkout {resolved} is missing required markers: {', '.join(missing)}."
        )
    return resolved


def resolve_environment(
    active_checkout: Path,
    *,
    environ: Mapping[str, str] | None = None,
    policy: EnvironmentPolicy | None = None,
) -> ResolvedEnvironment:
    """Resolve the configured environment or the portable checkout fallback."""

    selected_policy = policy or load_environment_policy()
    selected_environ = os.environ if environ is None else environ
    checkout = _validate_checkout(active_checkout)
    configured = selected_environ.get(selected_policy.environment_variable)
    if configured is not None:
        if not configured.strip():
            raise EnvironmentContractError(
                f"{selected_policy.environment_variable} is set but empty."
            )
        candidate = Path(configured).expanduser()
        if not candidate.is_absolute():
            raise EnvironmentContractError(
                f"{selected_policy.environment_variable} must be an absolute path; "
                f"got {configured!r}."
            )
        source = selected_policy.environment_variable
    else:
        candidate = checkout / selected_policy.portable_fallback
        source = "portable_fallback"
    return ResolvedEnvironment(
        path=candidate.absolute(),
        source=source,
        active_checkout=checkout,
        policy=selected_policy,
    )


_PROBE = r"""
import importlib
import importlib.metadata as metadata
import json
import os
import site
import sys
from pathlib import Path

checkout = Path(os.environ["DUTCHBAY_ACTIVE_CHECKOUT"]).resolve(strict=True)
probe_name = os.environ["DUTCHBAY_IMPORT_PROBE"]
project_distribution = os.environ["DUTCHBAY_PROJECT_DISTRIBUTION"]
required = json.loads(os.environ["DUTCHBAY_REQUIRED_DISTRIBUTIONS"])
module = importlib.import_module(probe_name)
module_path = Path(module.__file__).resolve(strict=True)

versions = {}
for name in required:
    try:
        versions[name] = metadata.version(name)
    except metadata.PackageNotFoundError:
        versions[name] = None

editable = False
project_install_url = None
try:
    distribution = metadata.distribution(project_distribution)
except metadata.PackageNotFoundError:
    distribution = None
if distribution is not None:
    direct_url_text = distribution.read_text("direct_url.json")
    if direct_url_text:
        direct_url = json.loads(direct_url_text)
        project_install_url = direct_url.get("url")
        editable = direct_url.get("dir_info", {}).get("editable") is True

foreign = set()
for raw_path in sys.path:
    if not raw_path:
        continue
    try:
        candidate = Path(raw_path).resolve(strict=True)
    except OSError:
        continue
    if candidate == checkout:
        continue
    if (candidate / "pyproject.toml").is_file() and (
        candidate / "go_with_the_flow_rules_v3_0_clean.csv"
    ).is_file():
        foreign.add(str(candidate))

for site_path in site.getsitepackages():
    for pth in Path(site_path).glob("*.pth"):
        try:
            lines = pth.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError):
            continue
        for line in lines:
            line = line.strip()
            if not line or line.startswith(("#", "import ")):
                continue
            candidate = Path(line).expanduser()
            if not candidate.is_absolute():
                continue
            try:
                candidate = candidate.resolve(strict=True)
            except OSError:
                continue
            if candidate != checkout and (candidate / "pyproject.toml").is_file() and (
                candidate / "go_with_the_flow_rules_v3_0_clean.csv"
            ).is_file():
                foreign.add(str(candidate))

print(json.dumps({
    "python_version_info": list(sys.version_info[:3]),
    "python_version": sys.version.split()[0],
    "python_executable": str(Path(sys.executable).resolve(strict=True)),
    "python_prefix": str(Path(sys.prefix).resolve(strict=True)),
    "import_path": str(module_path),
    "required_distributions": versions,
    "project_install_url": project_install_url,
    "editable_project_install": editable,
    "foreign_checkout_paths": sorted(foreign),
}, sort_keys=True))
"""


def _require_under(path: Path, parent: Path, label: str) -> None:
    try:
        path.relative_to(parent)
    except ValueError as exc:
        raise EnvironmentContractError(f"{label} {path} is outside {parent}.") from exc


def validate_environment(
    resolved: ResolvedEnvironment,
    *,
    environ: Mapping[str, str] | None = None,
    timeout_seconds: int = 30,
) -> EnvironmentReceipt:
    """Validate one selected environment without changing it."""

    if not resolved.path.exists():
        raise EnvironmentContractError(
            f"Selected environment does not exist: {resolved.path}. "
            "Create it through the governed setup entrypoint."
        )
    if resolved.path.is_symlink() or not resolved.path.is_dir():
        raise EnvironmentContractError(
            f"Selected environment must be a real directory, not a symlink: {resolved.path}."
        )
    if not resolved.python.is_file() or not os.access(resolved.python, os.X_OK):
        raise EnvironmentContractError(
            f"Selected environment is incomplete; executable missing: {resolved.python}."
        )
    probe_environ = dict(os.environ if environ is None else environ)
    previous_pythonpath = probe_environ.get("PYTHONPATH")
    probe_environ.update(
        {
            "DUTCHBAY_ACTIVE_CHECKOUT": str(resolved.active_checkout),
            "DUTCHBAY_IMPORT_PROBE": resolved.policy.import_probe,
            "DUTCHBAY_PROJECT_DISTRIBUTION": resolved.policy.project_distribution,
            "DUTCHBAY_REQUIRED_DISTRIBUTIONS": json.dumps(
                resolved.policy.required_distributions
            ),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONPATH": str(resolved.active_checkout)
            + (os.pathsep + previous_pythonpath if previous_pythonpath else ""),
        }
    )
    try:
        completed = subprocess.run(
            [str(resolved.python), "-c", _PROBE],
            cwd=resolved.active_checkout,
            env=probe_environ,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise EnvironmentContractError(
            f"Unable to inspect selected environment {resolved.path}: {exc}"
        ) from exc
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "no diagnostic"
        raise EnvironmentContractError(
            f"Environment probe failed for {resolved.path}: {detail}"
        )
    try:
        raw = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise EnvironmentContractError(
            "Environment probe did not emit valid JSON."
        ) from exc
    expected_version = [resolved.policy.python_major, resolved.policy.python_minor]
    if raw.get("python_version_info", [])[:2] != expected_version:
        raise EnvironmentContractError(
            f"Selected environment uses Python {raw.get('python_version', 'unknown')}; "
            f"Python {resolved.policy.python_major}.{resolved.policy.python_minor} is required."
        )
    actual_prefix = Path(raw["python_prefix"])
    expected_prefix = resolved.path.resolve(strict=True)
    if actual_prefix != expected_prefix:
        raise EnvironmentContractError(
            f"Python prefix mismatch: selected {expected_prefix}, runtime reported {actual_prefix}."
        )
    missing = [
        name
        for name, version in raw["required_distributions"].items()
        if version is None
    ]
    if missing:
        raise EnvironmentContractError(
            "Selected environment is incomplete; missing governed distributions: "
            + ", ".join(sorted(missing, key=str.casefold))
            + "."
        )
    import_path = Path(raw["import_path"])
    _require_under(import_path, resolved.active_checkout, "Active import")
    if raw["editable_project_install"]:
        raise EnvironmentContractError(
            "Selected environment contains an editable DutchBay installation; recreate it "
            "without binding site-packages to one checkout."
        )
    foreign = tuple(raw["foreign_checkout_paths"])
    if foreign:
        raise EnvironmentContractError(
            "Selected environment is path-contaminated by another DutchBay checkout: "
            + ", ".join(foreign)
            + "."
        )
    versions = tuple(
        sorted(
            raw["required_distributions"].items(), key=lambda item: item[0].casefold()
        )
    )
    return EnvironmentReceipt(
        schema=RECEIPT_SCHEMA,
        status="PASS",
        environment_variable=resolved.policy.environment_variable,
        selection_source=resolved.source,
        venv_path=str(expected_prefix),
        portable_fallback=resolved.policy.portable_fallback,
        active_checkout=str(resolved.active_checkout),
        python_executable=raw["python_executable"],
        python_version=raw["python_version"],
        python_prefix=str(actual_prefix),
        import_probe=resolved.policy.import_probe,
        import_path=str(import_path),
        required_distributions=versions,
        project_install_url=raw["project_install_url"],
        editable_project_install=False,
        foreign_checkout_paths=(),
    )


def _active_checkout_from_environment(environ: Mapping[str, str]) -> Path:
    configured = environ.get("DUTCHBAY_REPO_ROOT")
    return Path(configured) if configured else Path.cwd()


def main(argv: Sequence[str] | None = None) -> int:
    """Validate the selected environment and emit one JSON object."""

    if argv is None:
        argv = sys.argv[1:]
    if argv:
        print(
            json.dumps(
                {
                    "schema": RECEIPT_SCHEMA,
                    "status": "FAIL",
                    "error": "This bootstrap validator accepts configuration through environment variables only.",
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    try:
        resolved = resolve_environment(_active_checkout_from_environment(os.environ))
        receipt = validate_environment(resolved)
    except EnvironmentContractError as exc:
        print(
            json.dumps(
                {"schema": RECEIPT_SCHEMA, "status": "FAIL", "error": str(exc)},
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 1
    print(json.dumps(receipt.to_dict(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
