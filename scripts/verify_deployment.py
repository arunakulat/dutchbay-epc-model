"""Verify a DEPLOYED instance from outside, using only its public health surface.

Why this exists
---------------
Confirming what a running deployment actually has installed previously needed ``flyctl`` access
to the machine. That put an ops credential in front of an engineering question, and it blocked
everyone who lacked one — CI, a reviewer checking a claim, a colleague during an incident.

This script asks the instance instead. It needs a URL and nothing else: no Fly token, no SSH, no
cloud console. Anything it reports came from the deployment's own ``/health`` and
``/health/readiness`` routes.

What it checks
--------------
1. Liveness, and that the contract version matches what this checkout expects.
2. Runtime-critical configuration is PRESENT (booleans only — the routes never echo a secret).
3. Every optional extra the image installs is present, satisfies its declared pin, and — with
   ``--deep`` — actually imports. The deep check is the one that catches WeasyPrint installed
   without the pango/cairo system libraries, which is a real and silent image-build failure.

Exit codes
----------
``0`` all checks passed · ``1`` a check failed · ``2`` the instance was unreachable or answered
something that is not this application. A non-zero exit is CI-usable as a post-deploy gate.

Usage
-----
    python scripts/verify_deployment.py https://dutchbay-epc-model.fly.dev
    python scripts/verify_deployment.py https://staging.example --deep --json
    python scripts/verify_deployment.py https://staging.example --expect-extra report

GWTF:
    - CLI-01: argparse is banned repo-wide, so this parses ``sys.argv`` directly. It is an ops
      utility outside the Hydra-configured application surface, not a pipeline entrypoint.
    - CESSPIT: no silent defaults. An unreachable host, a non-JSON body and a missing key are
      each reported distinctly rather than collapsing to a generic failure.
"""

from __future__ import annotations

import json
import pathlib
import sys
import urllib.error
import urllib.request
from typing import Any, Optional

#: Exit codes.
OK, FAILED, UNREACHABLE = 0, 1, 2

#: Seconds to wait per request. A deep probe imports real packages, so it needs headroom.
DEFAULT_TIMEOUT = 30.0

_TICK, _CROSS, _WARN = "PASS", "FAIL", "WARN"


class Reporter:
    """Collects results so the exit code reflects everything, not just the first failure."""

    def __init__(self, *, as_json: bool) -> None:
        self.as_json = as_json
        self.rows: list[dict[str, Any]] = []
        self.failed = False

    def record(
        self, check: str, ok: bool, detail: str, *, warn_only: bool = False
    ) -> None:
        status = _TICK if ok else (_WARN if warn_only else _CROSS)
        if not ok and not warn_only:
            self.failed = True
        self.rows.append({"check": check, "status": status, "detail": detail})
        if not self.as_json:
            print(f"  [{status}] {check}: {detail}")

    def finish(self) -> int:
        if self.as_json:
            print(json.dumps({"ok": not self.failed, "checks": self.rows}, indent=2))
        elif self.failed:
            print("\nFAILED — one or more checks did not pass.")
        else:
            print("\nAll checks passed.")
        return FAILED if self.failed else OK


def fetch(url: str, timeout: float) -> Any:
    """GET a URL and parse JSON, raising a plain RuntimeError with a usable message."""
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code} from {url}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"cannot reach {url}: {exc.reason}") from exc
    except OSError as exc:
        raise RuntimeError(f"cannot reach {url}: {exc}") from exc
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"{url} did not return JSON (first 120 chars: {raw[:120]!r})"
        ) from exc


def expected_contract_version() -> Optional[str]:
    """The contract version this checkout expects, or ``None`` if it cannot be imported.

    Running ``python scripts/verify_deployment.py`` puts ``scripts/`` on ``sys.path``, not the
    repository root, so the project package is added explicitly. Running detached from the source
    tree entirely — e.g. the script copied onto a bastion — is legitimate and degrades to
    ``None`` (reported as a warning, not a failure).
    """
    root = str(pathlib.Path(__file__).resolve().parent.parent)
    if root not in sys.path:
        sys.path.insert(0, root)
    try:
        from app.api.responses import API_CONTRACT_VERSION

        return str(API_CONTRACT_VERSION)
    except (
        Exception
    ):  # noqa: BLE001 - running detached from the source tree is legitimate
        return None


def check_liveness(base: str, rep: Reporter, timeout: float) -> None:
    body = fetch(f"{base}/health", timeout)
    rep.record(
        "liveness", body.get("status") == "ok", f"/health -> {body.get('status')!r}"
    )
    served = body.get("contract_version")
    expected = expected_contract_version()
    if expected is None:
        rep.record(
            "contract version",
            True,
            f"instance reports {served!r}; not comparable (source tree unavailable)",
            warn_only=True,
        )
    else:
        rep.record(
            "contract version",
            served == expected,
            f"instance {served!r} vs this checkout {expected!r}",
        )


def check_readiness(
    base: str, rep: Reporter, timeout: float, *, deep: bool, expect: tuple[str, ...]
) -> None:
    url = f"{base}/health/readiness" + ("?deep=true" if deep else "")
    body = fetch(url, timeout)

    runtime = body.get("runtime") or {}
    if runtime:
        rep.record(
            "runtime identity",
            True,
            f"{runtime.get('distribution')} {runtime.get('version')} on Python "
            f"{runtime.get('python')} / {runtime.get('platform')}",
        )

    checks = body.get("checks") or {}
    for key, present in sorted(checks.items()):
        rep.record(f"config: {key}", bool(present), "present" if present else "MISSING")

    if body.get("extras_error"):
        rep.record("extras probe", False, f"probe failed: {body['extras_error']}")
        return

    extras = body.get("extras") or {}
    if not extras:
        rep.record(
            "extras probe",
            False,
            "instance reported no extras block — it predates the readiness extras diagnostic",
        )
        return

    for name in expect:
        if name not in extras:
            rep.record(f"extra: {name}", False, "not reported by the instance")

    for name, status in sorted(extras.items()):
        detail = []
        if status.get("missing"):
            detail.append(f"missing={','.join(status['missing'])}")
        if status.get("broken"):
            detail.append(f"broken={','.join(status['broken'])}")
        if not detail:
            versions = ", ".join(
                f"{p['distribution']}=={p['installed_version']}"
                for p in status.get("packages", ())
                if p.get("installed_version")
            )
            detail.append(versions or "no packages declared")
        if deep and status.get("deep_probed") and status.get("available"):
            # Confirm the deep probe actually ran and every package imported. Without this a
            # successful deep run is indistinguishable from a shallow one, which would make the
            # flag's most important guarantee invisible.
            detail.append("all imported")
        rep.record(f"extra: {name}", bool(status.get("available")), "; ".join(detail))

        if deep and not status.get("deep_probed"):
            rep.record(
                f"extra: {name} (deep)",
                False,
                "deep probe requested but the instance did not perform one",
            )
        for pkg in status.get("packages", ()):
            if pkg.get("importable") is False:
                rep.record(
                    f"import: {pkg['distribution']}",
                    False,
                    pkg.get("import_error") or "import failed",
                )
            if pkg.get("satisfies_spec") is False:
                rep.record(
                    f"pin: {pkg['distribution']}",
                    False,
                    f"installed {pkg['installed_version']} violates {pkg['declared_spec']}",
                )


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if not a.startswith("-")]
    flags = {a for a in argv[1:] if a.startswith("-")}

    if not args or "-h" in flags or "--help" in flags:
        print(__doc__)
        return OK if ("-h" in flags or "--help" in flags) else FAILED

    base = args[0].rstrip("/")
    if not base.startswith(("http://", "https://")):
        base = "https://" + base
    deep = "--deep" in flags
    as_json = "--json" in flags
    expect = tuple(a for a in args[1:]) or ()
    for flag in flags:
        if flag.startswith("--expect-extra="):
            expect += (flag.split("=", 1)[1],)

    rep = Reporter(as_json=as_json)
    if not as_json:
        print(f"Verifying {base}{' (deep)' if deep else ''}\n")
    try:
        check_liveness(base, rep, DEFAULT_TIMEOUT)
        check_readiness(base, rep, DEFAULT_TIMEOUT, deep=deep, expect=expect)
    except RuntimeError as exc:
        if as_json:
            print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        else:
            print(f"  [{_CROSS}] unreachable: {exc}")
        return UNREACHABLE
    return rep.finish()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
