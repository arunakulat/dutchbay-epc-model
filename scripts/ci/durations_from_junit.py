#!/usr/bin/env python3
"""Rebuild ``.test_durations`` from CI junit timings (#1884).

pytest-split balances the CI shards by the durations in ``.test_durations``. That file
was recorded with ``pytest --store-durations`` on a local machine, where some tests run
several times faster than on the hosted runner (two xdist workers on two SMT cores,
under coverage). The split then strands slow tests in a few shards. This rebuilds the
file from the junit XML the shards already upload, so the split balances on the times
the gate actually sees.

    python scripts/ci/durations_from_junit.py \\
        --nodeids nodeids.txt --durations .test_durations \\
        --output .test_durations run1/*.xml run2/*.xml

``--nodeids`` lists the collected node ids, one per line, from
``pytest tests/ --collect-only -q``. The output holds exactly those ids. Each id takes
the median of its junit times across the given files. An id with no junit time keeps
its recorded duration scaled by the median CI-to-recorded ratio, and an id with
neither is left out, so pytest-split gives it the mean.

Ids under ``KEEP_RECORDED`` keep their recorded value unchanged.
``tests/lint/test_report_test_policy.py`` reads those entries as governed duration
evidence for its five-second review, so a scheduling refresh must not rewrite them.
"""

from __future__ import annotations

import argparse
import json
import statistics
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

JunitKey = tuple[str, str]

# Must equal _REPORT_DURATION_PREFIXES in tests/lint/test_report_test_policy.py
# (pinned by tests/lint/test_durations_from_junit.py).
KEEP_RECORDED = (
    "tests/app/test_api.py::test_run_case_report_",
    "tests/app/test_report_orchestration.py::",
    "tests/app/test_surface_contract.py::test_build_case_surface_projects_a_real_run",
    "tests/integration/test_lender_report_e2e.py::",
)


def junit_key(nodeid: str) -> JunitKey:
    """The (classname, name) pair pytest's junit writer gives a node id."""
    path, _, rest = nodeid.partition("::")
    parts = rest.split("::")
    module = path.removesuffix(".py").replace("/", ".")
    return ".".join([module, *parts[:-1]]), parts[-1]


def read_junit(paths: list[Path]) -> dict[JunitKey, list[float]]:
    """Every testcase time in the given junit files, keyed by (classname, name)."""
    times: dict[JunitKey, list[float]] = defaultdict(list)
    for path in paths:
        for case in ET.parse(path).getroot().iter("testcase"):
            if case.find("skipped") is not None:
                continue
            times[(case.get("classname", ""), case.get("name", ""))].append(
                float(case.get("time") or 0.0)
            )
    return dict(times)


def rebuild(
    nodeids: list[str],
    recorded: dict[str, float],
    junit: dict[JunitKey, list[float]],
) -> dict[str, float]:
    """Durations for exactly ``nodeids``: CI median, else scaled recorded, else omitted.

    Governed ids (``KEEP_RECORDED``) keep their recorded value whenever they have one.
    """
    measured = {
        nodeid: statistics.median(junit[junit_key(nodeid)])
        for nodeid in nodeids
        if junit_key(nodeid) in junit
    }
    ratios = [
        measured[nodeid] / recorded[nodeid]
        for nodeid in measured
        if recorded.get(nodeid, 0.0) > 0.0
    ]
    scale = statistics.median(ratios) if ratios else 1.0
    durations: dict[str, float] = {}
    for nodeid in nodeids:
        if nodeid.startswith(KEEP_RECORDED) and nodeid in recorded:
            durations[nodeid] = recorded[nodeid]
        elif nodeid in measured:
            durations[nodeid] = measured[nodeid]
        elif nodeid in recorded:
            durations[nodeid] = recorded[nodeid] * scale
    return dict(sorted(durations.items()))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--nodeids", type=Path, required=True)
    parser.add_argument("--durations", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("junit", type=Path, nargs="+")
    args = parser.parse_args(argv)

    nodeids = [
        line.strip()
        for line in args.nodeids.read_text(encoding="utf-8").splitlines()
        if "::" in line
    ]
    recorded = json.loads(args.durations.read_text(encoding="utf-8"))
    junit = read_junit(args.junit)
    durations = rebuild(nodeids, recorded, junit)
    args.output.write_text(json.dumps(durations, indent=2) + "\n", encoding="utf-8")
    measured = sum(1 for n in nodeids if junit_key(n) in junit)
    print(
        f"{len(durations)} of {len(nodeids)} node ids written; "
        f"{measured} from junit, {len(durations) - measured} scaled from the record"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
