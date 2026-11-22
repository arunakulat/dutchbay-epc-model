"""`.test_durations` rebuilt from CI junit timings (#1884)."""

from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts/ci/durations_from_junit.py"
REPORT_POLICY = REPO_ROOT / "tests/lint/test_report_test_policy.py"


def _load() -> Any:
    spec = importlib.util.spec_from_file_location("durations_from_junit", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


rebuild_mod = _load()


@pytest.mark.parametrize(
    "nodeid, key",
    [
        ("tests/a/test_b.py::test_c", ("tests.a.test_b", "test_c")),
        (
            "tests/a/test_b.py::TestX::test_c[p-1]",
            ("tests.a.test_b.TestX", "test_c[p-1]"),
        ),
        (
            "tests/test_b.py::TestX::TestY::test_c",
            ("tests.test_b.TestX.TestY", "test_c"),
        ),
    ],
)
def test_junit_key_matches_pytests_junit_writer(
    nodeid: str, key: tuple[str, str]
) -> None:
    assert rebuild_mod.junit_key(nodeid) == key


def test_rebuild_prefers_ci_median_then_scaled_record_then_omits() -> None:
    nodeids = [
        "tests/a/test_m.py::test_measured",
        "tests/a/test_m.py::test_scaled",
        "tests/a/test_m.py::test_unknown",
    ]
    recorded = {
        "tests/a/test_m.py::test_measured": 1.0,
        "tests/a/test_m.py::test_scaled": 2.0,
        "tests/a/test_m.py::test_stale": 9.0,
    }
    junit = {("tests.a.test_m", "test_measured"): [3.0, 4.0, 99.0]}

    durations = rebuild_mod.rebuild(nodeids, recorded, junit)

    # median 4.0; ratio 4.0 / 1.0 scales the unmeasured test; unknown and stale omitted.
    assert durations == {
        "tests/a/test_m.py::test_measured": 4.0,
        "tests/a/test_m.py::test_scaled": 8.0,
    }


def test_governed_report_entries_keep_their_recorded_value() -> None:
    nodeid = "tests/app/test_report_orchestration.py::test_x"
    junit = {("tests.app.test_report_orchestration", "test_x"): [50.0]}

    assert rebuild_mod.rebuild([nodeid], {nodeid: 0.5}, junit) == {nodeid: 0.5}


def test_keep_list_is_the_report_policys_governed_prefixes() -> None:
    tree = ast.parse(REPORT_POLICY.read_text(encoding="utf-8"))
    governed = next(
        ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "_REPORT_DURATION_PREFIXES"
            for target in node.targets
        )
    )
    assert rebuild_mod.KEEP_RECORDED == governed


def test_read_junit_skips_skipped_cases(tmp_path: Path) -> None:
    xml = tmp_path / "r.xml"
    xml.write_text(
        '<testsuites><testsuite name="pytest">'
        '<testcase classname="tests.a.test_m" name="test_ran" time="1.5"/>'
        '<testcase classname="tests.a.test_m" name="test_skip" time="0.0">'
        '<skipped message="x"/></testcase>'
        "</testsuite></testsuites>",
        encoding="utf-8",
    )
    assert rebuild_mod.read_junit([xml]) == {("tests.a.test_m", "test_ran"): [1.5]}


def test_main_writes_sorted_json(tmp_path: Path) -> None:
    nodeids = tmp_path / "ids.txt"
    nodeids.write_text(
        "tests/a/test_m.py::test_b\ntests/a/test_m.py::test_a\n13 tests\n"
    )
    recorded = tmp_path / "rec.json"
    recorded.write_text(json.dumps({"tests/a/test_m.py::test_a": 1.0}))
    xml = tmp_path / "r.xml"
    xml.write_text(
        '<testsuite><testcase classname="tests.a.test_m" name="test_b" time="2.0"/>'
        "</testsuite>",
        encoding="utf-8",
    )
    out = tmp_path / "out.json"

    assert (
        rebuild_mod.main(
            [
                "--nodeids",
                str(nodeids),
                "--durations",
                str(recorded),
                "--output",
                str(out),
                str(xml),
            ]
        )
        == 0
    )
    assert list(json.loads(out.read_text())) == [
        "tests/a/test_m.py::test_a",
        "tests/a/test_m.py::test_b",
    ]
    assert out.read_text().endswith("}\n")


def test_committed_durations_are_sorted_and_positive() -> None:
    durations = json.loads((REPO_ROOT / ".test_durations").read_text(encoding="utf-8"))
    assert list(durations) == sorted(durations)
    assert all(seconds >= 0.0 for seconds in durations.values())
