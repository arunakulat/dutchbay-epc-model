"""Fail the security gate unless every advisory feed can still report a known advisory now.

A clean ``make security`` means "no feed returned a finding". That is only evidence about the
lock if the feeds could have returned one at that moment. On 2026-10-27 the required
``Security Scan`` reported a lock pinning ``hydra-core==1.3.7`` clean at 17:19Z (job
122348327291) three minutes after the same workflow redded the same pin (job 122346893695),
and a later run reported one of two live advisories (job 122353695670). Recorded as residual
D-10 on dutchbay-epc-model#1353 and hardened under #1464. The cause is not established, and
this script does not claim one.

What it adds is the negative control the gate lacked: before the real audit is trusted, each
vulnerability service that ``make security`` consults audits a canary file of pins carrying
known, published advisories, and this script fails unless that service reports every one of
them. A service that answers stale, partial or empty fails here, in the same job and minutes
before the verdict it would otherwise have produced. Two pins rather than one, because the
#1461 miss was one advisory of two: a canary that holds a single advisory cannot observe a
partial answer.

The canary pins are the two from the 2026-10-27 incident. Both advisories were published
that day and both feeds carried them on 2026-10-28. If either is ever withdrawn this script
fails for every pull request, by design - replace that canary with another published
advisory, measured against both services, rather than weakening the check.

Standard library only: the security job installs ``bandit`` and ``pip-audit`` and nothing
else.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Final, Mapping, Sequence

#: The vulnerability services ``make security`` consults: PyPI's for the resolve and
#: declared-pin passes, OSV's for the cross-check. A service added there belongs here.
SERVICES: Final[tuple[str, ...]] = ("pypi", "osv")

#: Canary package -> (pinned version, every ID the advisory is known by). A service passes
#: when, for every canary, the IDs it reports intersect that set. Aliases are accepted
#: because a feed may lead with either name: on 2026-10-28 OSV reported the msgpack
#: advisory as CVE-2026-114613 with alias GHSA-j586-36cw-2gc2.
CANARIES: Final[Mapping[str, tuple[str, frozenset[str]]]] = {
    "hydra-core": ("1.3.7", frozenset({"GHSA-wf6j-7hvr-gr93"})),
    "msgpack": ("1.2.1", frozenset({"CVE-2026-114613", "GHSA-j586-36cw-2gc2"})),
}

#: pip-audit's exit status when it found at least one vulnerability. Any other status means
#: it found nothing or did not finish, and neither is a detection.
FOUND_EXIT: Final[int] = 1


def canary_requirements() -> str:
    """Return the canary requirements file, one exact pin per line."""
    return "".join(f"{name}=={version}\n" for name, (version, _) in CANARIES.items())


def missing_detections(returncode: int, report_text: str) -> list[str]:
    """Return one message per canary advisory a service failed to report.

    An empty list means the service reported every canary. Fails closed: a status other
    than ``FOUND_EXIT``, an unreadable report, or a report with an unexpected shape is a
    failure, never a pass.
    """
    if returncode != FOUND_EXIT:
        return [
            f"pip-audit exited {returncode}, expected {FOUND_EXIT} (vulnerabilities "
            "found); a canary that is not reported is not a working feed"
        ]
    try:
        report = json.loads(report_text)
    except ValueError as exc:
        return [f"pip-audit report is not JSON: {exc}"]
    dependencies = report.get("dependencies") if isinstance(report, dict) else None
    if not isinstance(dependencies, list):
        return ["pip-audit report has no `dependencies` list"]

    reported: dict[str, set[str]] = {}
    for dependency in dependencies:
        if not isinstance(dependency, dict):
            continue
        name = str(dependency.get("name", "")).lower()
        ids = reported.setdefault(name, set())
        for vuln in dependency.get("vulns") or []:
            if not isinstance(vuln, dict):
                continue
            ids.add(str(vuln.get("id", "")))
            ids.update(str(alias) for alias in vuln.get("aliases") or [])

    missing: list[str] = []
    for name, (version, expected) in CANARIES.items():
        if not reported.get(name, set()) & expected:
            missing.append(
                f"{name}=={version}: none of {sorted(expected)} reported, got "
                f"{sorted(reported.get(name, set()))}"
            )
    return missing


def run_service(service: str, requirements: Path, report: Path) -> list[str]:
    """Audit the canary through one service and return what it failed to report."""
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip_audit",
            "--vulnerability-service",
            service,
            "--no-deps",
            "--disable-pip",
            "--format",
            "json",
            "--output",
            str(report),
            "-r",
            str(requirements),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    report_text = report.read_text(encoding="utf-8") if report.is_file() else ""
    missing = missing_detections(completed.returncode, report_text)
    if missing and completed.stderr.strip():
        # Plain lines, not an annotation: an annotation keeps only its first line.
        print(f"pip-audit stderr ({service}):\n{completed.stderr.strip()}")
    return missing


def main(argv: Sequence[str] | None = None) -> int:
    """Audit the canary through every service; return 0 only if each reported all of it."""
    del argv  # no options: the canary and the services are fixed by design
    failures = 0
    with tempfile.TemporaryDirectory() as tmp:
        requirements = Path(tmp) / "canary-requirements.txt"
        requirements.write_text(canary_requirements(), encoding="utf-8")
        for service in SERVICES:
            missing = run_service(service, requirements, Path(tmp) / f"{service}.json")
            if missing:
                failures += 1
                for message in missing:
                    print(f"::error::audit canary, {service} service: {message}")
            else:
                print(
                    f"audit canary, {service} service: reported all "
                    f"{len(CANARIES)} canary advisories"
                )
    if failures:
        print(
            f"{failures} of {len(SERVICES)} advisory services could not report a known "
            "advisory, so a clean audit from them would not be evidence of a clean lock"
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
