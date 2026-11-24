"""G5: classify supplied observations, not authenticate them or authorize recovery.

The fixed schema deliberately excludes raw logs, commands, paths, environment
variables, free-text explanations and credentials. A digest is an integrity
reference, not proof of the underlying event. Keep source evidence separately
under the applicable confidentiality controls.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if not TYPE_CHECKING and __package__:
    from . import gwtf_checkpoint_receipt as receipt
    from . import gwtf_interruption_recovery as recovery
else:
    import gwtf_checkpoint_receipt as receipt
    import gwtf_interruption_recovery as recovery

EXECUTION = {"NOT_STARTED", "RUNNING", "EXITED", "UNKNOWN"}
PHASES = {"PREFLIGHT", "FORMATTER", "TEST", "COMMIT", "REVIEW", "OTHER"}
FAILURES = {
    "NONE",
    "FORMATTER_MUTATION",
    "TEST_FAILURE",
    "GIT_REJECTION",
    "ENVIRONMENT_FAILURE",
    "WRITER_COLLISION",
    "UNKNOWN",
}
REPORTING = {"OBSERVED", "NOT_OBSERVED", "UNKNOWN"}
DRIFT = {"UNCHANGED", "ALLOWLIST_ONLY", "OUTSIDE_ALLOWLIST", "UNKNOWN"}
FIELDS = {
    "execution",
    "phase",
    "exit_code",
    "failure",
    "platform_restriction",
    "reporting",
    "drift",
    "evidence_sha256",
}
HEX = re.compile(r"[0-9a-f]{64}\Z")


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def choice(value: Any, allowed: set[str]) -> bool:
    return isinstance(value, str) and value in allowed


def validate(observation: dict[str, Any]) -> None:
    require(
        isinstance(observation, dict) and set(observation) == FIELDS,
        "invalid observation schema",
    )
    for key, allowed in (
        ("execution", EXECUTION),
        ("phase", PHASES),
        ("failure", FAILURES),
        ("reporting", REPORTING),
        ("drift", DRIFT),
    ):
        require(choice(observation[key], allowed), f"invalid {key}")
    code = observation["exit_code"]
    require(
        code is None or (type(code) is int and -255 <= code <= 255), "invalid exit code"
    )
    require(
        observation["platform_restriction"] is None
        or type(observation["platform_restriction"]) is bool,
        "invalid restriction state",
    )
    digest = observation["evidence_sha256"]
    require(
        digest is None or (isinstance(digest, str) and bool(HEX.fullmatch(digest))),
        "invalid evidence digest",
    )


def classify(observation: dict[str, Any]) -> dict[str, Any]:
    """Conservative classification, with separate reporting disposition.

    Restrictions and uncertain execution always require reconciliation. This
    function has no process-control, Git mutation, retry or notification powers.
    """
    validate(observation)
    x = observation
    execution, code, failure = x["execution"], x["exit_code"], x["failure"]
    contradictory = (execution == "EXITED") != (code is not None)
    contradictory |= execution != "EXITED" and failure not in {
        "NONE",
        "UNKNOWN",
        "WRITER_COLLISION",
    }
    contradictory |= (
        execution == "EXITED" and code == 0 and failure not in {"NONE", "UNKNOWN"}
    )
    contradictory |= execution != "EXITED" and x["reporting"] == "OBSERVED"
    contradictory |= failure == "FORMATTER_MUTATION" and (
        x["phase"] not in {"FORMATTER", "COMMIT"} or x["drift"] != "ALLOWLIST_ONLY"
    )
    contradictory |= failure == "TEST_FAILURE" and x["phase"] != "TEST"
    contradictory |= failure == "GIT_REJECTION" and x["phase"] != "COMMIT"
    # The observation of a platform restriction is never downgraded by another
    # classification. Even ambiguous or contradictory execution remains held.
    if x["platform_restriction"] is True:
        kind = "PLATFORM_EXECUTION_RESTRICTION"
    elif contradictory:
        kind = "CONTRADICTORY_OBSERVATIONS"
    elif failure == "WRITER_COLLISION":
        kind = "WRITER_COLLISION"
    elif x["drift"] == "OUTSIDE_ALLOWLIST":
        kind = "UNEXPECTED_DRIFT"
    elif (
        x["platform_restriction"] is None
        or execution == "UNKNOWN"
        or x["drift"] == "UNKNOWN"
    ):
        kind = "UNKNOWN_OUTCOME"
    elif execution == "RUNNING":
        kind = "EXECUTION_RUNNING"
    elif execution == "NOT_STARTED":
        kind = "EXECUTION_NOT_STARTED"
    elif x["evidence_sha256"] is None:
        kind = "MISSING_EXECUTION_EVIDENCE"
    elif code == 0:
        kind = (
            "EXECUTION_SUCCEEDED"
            if failure == "NONE" and x["drift"] == "UNCHANGED"
            else "RECONCILIATION_REQUIRED"
        )
    elif failure in {
        "FORMATTER_MUTATION",
        "TEST_FAILURE",
        "GIT_REJECTION",
        "ENVIRONMENT_FAILURE",
    }:
        kind = failure
    else:
        kind = "UNCLASSIFIED_EXECUTION_FAILURE"

    if execution != "EXITED" or code is None or contradictory:
        report = "COMPLETION_NOT_ESTABLISHED"
    elif x["reporting"] == "NOT_OBSERVED":
        report = "COMPLETED_BUT_UNREPORTED"
    elif x["reporting"] == "OBSERVED":
        report = "REPORT_OBSERVED_DELIVERY_UNCONFIRMED"
    else:
        report = "REPORTING_UNKNOWN"

    return {
        "schema": 1,
        "execution_disposition": kind,
        "reporting_disposition": report,
        "contradictory_observations": contradictory,
        "platform_restriction_observed": x["platform_restriction"],
        "reconciliation_required": kind
        not in {"EXECUTION_RUNNING", "EXECUTION_NOT_STARTED", "EXECUTION_SUCCEEDED"}
        or report == "COMPLETED_BUT_UNREPORTED",
        "checkpoint_verified": False,
        "independent_review_complete": False,
        "writer_authorized": False,
        "retry_authorized": False,
        "merge_authorized": False,
        "delivery_confirmed": False,
        "evidence_authenticated": False,
    }


def persist(observation: dict[str, Any], output: Path) -> str:
    """Exclusive external fixed-schema receipt; no raw diagnostic text."""
    disposition = classify(observation)
    output = receipt.safe_external(output)
    record = {
        "recorded_utc": datetime.now(timezone.utc).isoformat(),
        "observation": observation,
        "disposition": disposition,
    }
    data = receipt.canonical(record) + b"\n"
    recovery.write_new(output, data)
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--observation", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    try:
        observation = json.loads(args.observation.read_text())
        tip = persist(observation, args.receipt)
        print(json.dumps({"receipt_sha256": tip, **classify(observation)}, indent=2))
    except (OSError, ValueError, KeyError, TypeError):
        # Avoid echoing arbitrary input content or sensitive filesystem paths.
        print(
            "STOP: incident observation or receipt could not be validated",
            file=sys.stderr,
        )
        return 1
    # A successful receipt write is not a successful underlying execution.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
