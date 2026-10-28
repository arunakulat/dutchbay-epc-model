"""Grid-free transport, lifecycle, and compatibility failure controls for #1229."""

from __future__ import annotations

import io
import json
import math
import os
import subprocess
import sys
import textwrap
from dataclasses import asdict, replace
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from analytics.contracts_v14 import (
    GridStrengthResult,
    PowerFlowResult,
    ReactiveCapabilityResult,
)
from analytics.grid import _pandapower_worker as worker
from analytics.grid import pandapower_screening as adapter


def _strength() -> GridStrengthResult:
    return GridStrengthResult.from_screen(
        scr_min=2.0,
        fault_level_poc_min_mva=20.0,
        plant_rating_mva=10.0,
        fault_level_poc_max_mva=22.0,
        method="pandapower_iec60909",
    )


def _reactive(converged: bool) -> tuple[ReactiveCapabilityResult, PowerFlowResult]:
    return (
        ReactiveCapabilityResult.from_screen(
            pf_required_min=-0.95,
            pf_required_max=0.95,
            mvar_required=5.0,
            mvar_available=4.0,
            pf_at_poc=0.95,
            governing_converged=converged,
        ),
        PowerFlowResult(
            converged=converged,
            bus_voltages_pu={"POC": 1.0} if converged else {},
            poc_voltage_pu=1.0 if converged else float("nan"),
            poc_pf=0.95,
        ),
    )


def test_canonical_contract_round_trip() -> None:
    original = _strength()
    assert (
        adapter._decode_result("strength", adapter._encode_result(original)) == original
    )
    for converged in (True, False):
        expected = _reactive(converged)
        result = adapter._decode_result("reactive", adapter._encode_result(expected))
        assert isinstance(result, tuple) and result[1] is not None
        assert result[0] == expected[0]
        assert result[1].converged is converged
        if converged:
            assert result[1] == expected[1]
        else:
            assert math.isnan(result[1].poc_voltage_pu)
            assert result[0].inside_pq_box is False


@pytest.mark.parametrize(
    "bad", [float("nan"), float("inf"), -float("inf"), {1: 2}, b"bad", object()]
)
def test_transport_rejects_unsupported_or_nonfinite_inputs(bad: object) -> None:
    with pytest.raises(ValueError):
        adapter._json_value(bad)


def test_transport_normalizes_sequences_and_preserves_precision() -> None:
    values = {"nested": (True, None, 0.9404814334303563, -0.0, "text")}
    result = json.loads(json.dumps(adapter._json_value(values), allow_nan=False))
    assert result["nested"][2].hex() == values["nested"][2].hex()
    assert result["nested"][3].hex() == "-0x0.0p+0"


@pytest.mark.parametrize("top", [None, {}, {5: 2.4, 7.9: 1.5, "11": 9, True: 4}])
def test_numeric_spectrum_transport_preserves_parser_semantics(top: object) -> None:
    from analytics.grid.harmonics import _harmonic_spectrum

    grid = {"harmonic_spectrum": top, "gridcode": {"harmonic_spectrum": {11: 0.9}}}
    original = repr(grid)
    transported = adapter._wire_parameters({"grid": grid})
    assert _harmonic_spectrum(transported["grid"]) == _harmonic_spectrum(grid)
    assert repr(grid) == original


@pytest.mark.parametrize(
    "mutation", ["bankable", "method", "missing", "extra", "nan", "type"]
)
def test_worker_contract_corruption_is_rejected(mutation: str) -> None:
    data = asdict(_strength())
    if mutation == "bankable":
        data["bankable"] = True
    elif mutation == "method":
        data["method"] = "closed_form"
    elif mutation == "missing":
        del data["scr"]
    elif mutation == "extra":
        data["extra"] = 1
    elif mutation == "nan":
        data["scr"] = float("nan")
    else:
        data["scr"] = "2.0"
    with pytest.raises(ValueError):
        adapter._decode_result("strength", data)


def test_reactive_transport_rejects_inconsistent_sentinels() -> None:
    with pytest.raises(ValueError):
        adapter._decode_result("reactive", [])
    for converged, voltage in ((True, None), (False, 1.0)):
        data = [asdict(_reactive(converged)[0]), asdict(_reactive(converged)[1])]
        data[1]["poc_voltage_pu"] = voltage
        with pytest.raises(ValueError):
            adapter._decode_result("reactive", data)
    data = [asdict(_reactive(False)[0]), asdict(_reactive(True)[1])]
    with pytest.raises(ValueError, match="disagree"):
        adapter._decode_result("reactive", data)
    with pytest.raises(ValueError, match="sentinel"):
        adapter._encode_result(
            (_reactive(False)[0], replace(_reactive(False)[1], poc_voltage_pu=1.0))
        )
    with pytest.raises(ValueError):
        adapter._decode_result(
            "reactive", adapter._encode_result((_reactive(False)[0], None))
        )


@pytest.mark.parametrize(
    "change",
    [
        {"timeout_seconds": 0},
        {"timeout_seconds": True},
        {"timeout_seconds": float("inf")},
        {"timeout_seconds": "120"},
        {"supported_pandapower_versions": []},
        {"supported_pandapower_versions": [3]},
        {"supported_pandapower_versions": "3.5.4"},
        {"schema_version": "wrong"},
        {"extra": True},
    ],
)
def test_policy_is_strict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: dict
) -> None:
    data = json.loads(adapter._POLICY_PATH.read_text())
    data.update(change)
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(data))
    monkeypatch.setattr(adapter, "_POLICY_PATH", path)
    with pytest.raises(ValueError):
        adapter._policy()


def test_unknown_operation_fails_before_spawn() -> None:
    with pytest.raises(ValueError, match="Unknown"):
        adapter.run_screening("unknown", {})


def _command(monkeypatch: pytest.MonkeyPatch, source: str) -> None:
    monkeypatch.setattr(
        adapter, "_worker_command", lambda: [sys.executable, "-c", source]
    )


def test_success_uses_exact_interpreter_and_checkout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert adapter._worker_command()[0] == sys.executable
    payload = json.dumps({"result": asdict(_strength())})
    source = (
        "import os,sys,json; from pathlib import Path; "
        f"assert Path.cwd() == Path({str(adapter._ROOT)!r}); "
        f"assert os.environ['PYTHONPATH'].split(os.pathsep)[0] == {str(adapter._ROOT)!r}; "
        "assert json.load(sys.stdin)['kind'] == 'strength'; "
        f"print({payload!r})"
    )
    _command(monkeypatch, source)
    assert adapter.run_screening("strength", {}) == _strength()


@pytest.mark.parametrize(
    "source,expected",
    [
        ("import sys; sys.exit(7)", "exit 7"),
        ("import os,signal; os.kill(os.getpid(), signal.SIGKILL)", "exit -9"),
        ("print('not JSON')", "Invalid"),
        ("print('{}')", "Invalid"),
        ("print('{\"result\": null}')", "Invalid"),
        (
            "import sys; print('Fatal Python error: simulated', file=sys.stderr)",
            "no screening result",
        ),
    ],
)
def test_real_child_failures_do_not_return_results(
    monkeypatch: pytest.MonkeyPatch, source: str, expected: str
) -> None:
    _command(monkeypatch, source)
    with pytest.raises(adapter.ScreeningProcessError, match=expected):
        adapter.run_screening("strength", {})


def test_timeout_kills_and_reaps_child(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pidfile = tmp_path / "child.pid"
    _command(
        monkeypatch,
        f"import os,time; from pathlib import Path; Path({str(pidfile)!r}).write_text(str(os.getpid())); time.sleep(60)",
    )
    monkeypatch.setattr(adapter, "_policy", lambda: (0.5, ["3.5.4"]))
    with pytest.raises(adapter.ScreeningProcessError, match="terminated"):
        adapter.run_screening("strength", {})
    pid = int(pidfile.read_text())
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)
    with pytest.raises(ChildProcessError):
        os.waitpid(pid, os.WNOHANG)


def test_spawn_failure_is_actionable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        adapter, "_worker_command", lambda: ["/missing/issue1229/python"]
    )
    with pytest.raises(adapter.ScreeningProcessError, match="Cannot start"):
        adapter.run_screening("strength", {})


def test_injected_interruption_kills_and_reaps_child(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    children = []
    original_popen = subprocess.Popen

    def record_child(*args, **kwargs):
        child = original_popen(*args, **kwargs)
        children.append(child)
        return child

    def interrupt(*args, **kwargs):
        raise KeyboardInterrupt

    _command(monkeypatch, "import time; time.sleep(60)")
    monkeypatch.setattr(subprocess, "Popen", record_child)
    monkeypatch.setattr(original_popen, "communicate", interrupt)
    with pytest.raises(KeyboardInterrupt):
        adapter.run_screening("strength", {})
    assert len(children) == 1 and children[0].returncode is not None
    with pytest.raises(ProcessLookupError):
        os.kill(children[0].pid, 0)
    with pytest.raises(ChildProcessError):
        os.waitpid(children[0].pid, os.WNOHANG)


@pytest.mark.parametrize("attempt", range(3))
def test_real_sigint_kills_and_reaps_child(tmp_path: Path, attempt: int) -> None:
    """Actual signals exercise Python's communicate SIGINT bookkeeping."""
    pidfile = tmp_path / f"worker_{attempt}.pid"
    child = (
        "import os,signal,time; from pathlib import Path; "
        f"Path({str(pidfile)!r}).write_text(str(os.getpid())); "
        "time.sleep(.15); os.kill(os.getppid(),signal.SIGINT); time.sleep(60)"
    )
    caller = textwrap.dedent("""
        import json,os,signal,sys
        from pathlib import Path
        from analytics.grid import pandapower_screening as adapter
        adapter._worker_command = lambda: [sys.executable, '-c', CHILD]
        try:
            adapter.run_screening('strength', {})
        except KeyboardInterrupt:
            pid = int(Path(PIDFILE).read_text())
            try:
                waited, status = os.waitpid(pid, os.WNOHANG)
            except ChildProcessError:
                pass
            else:
                if waited == 0:
                    os.kill(pid, signal.SIGKILL)
                    os.waitpid(pid, 0)
                raise AssertionError('adapter left an unreaped child')
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                pass
            else:
                raise AssertionError('worker still exists after interruption')
            print(json.dumps({'reaped': True}))
        else:
            raise AssertionError('real SIGINT did not interrupt caller')
    """)
    caller = f"CHILD={child!r}\nPIDFILE={str(pidfile)!r}\n" + caller
    result = subprocess.run(
        [sys.executable, "-c", caller], text=True, capture_output=True, timeout=15
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"reaped": True}


def test_child_diagnostics_remain_visible(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = json.dumps({"result": asdict(_strength())})
    _command(
        monkeypatch,
        f"import sys; print('retained warning', file=sys.stderr); print({payload!r})",
    )
    with pytest.warns(RuntimeWarning, match="retained warning"):
        assert adapter.run_screening("strength", {}) == _strength()


def _fake_vendor(monkeypatch: pytest.MonkeyPatch) -> dict[str, ModuleType]:
    modules = {
        name: ModuleType(name)
        for name in (
            "pandapower",
            "pandapower.auxiliary",
            "pandapower.build_branch",
            "pandapower.estimation.results",
            "pandapower.pf.makeYbus_numba",
            "pandapower.shortcircuit.impedance",
        )
    }
    modules["pandapower"].__version__ = "3.5.4"

    def make_ybus() -> None:
        return None

    make_ybus.__module__ = "pandapower.pf.makeYbus_numba"
    modules["pandapower.pf.makeYbus_numba"].makeYbus = make_ybus
    modules["pandapower.shortcircuit.impedance"].makeYbus = make_ybus
    for module_name, name, original_name in (
        ("pandapower.auxiliary", "get_values", "_get_values"),
        ("pandapower.auxiliary", "set_elements_oos", "_python_set_elements_oos"),
        (
            "pandapower.auxiliary",
            "set_isolated_buses_oos",
            "_python_set_isolated_buses_oos",
        ),
        ("pandapower.pf.makeYbus_numba", "gen_Ybus", "gen_Ybus"),
    ):

        def original() -> None:
            return None

        original.__name__ = original_name
        original.__module__ = module_name
        setattr(modules[module_name], original_name, original)
        setattr(modules[module_name], name, SimpleNamespace(py_func=original))
    for name in ("pandapower.build_branch", "pandapower.estimation.results"):
        modules[name].get_values = modules["pandapower.auxiliary"].get_values
    monkeypatch.setattr(worker.importlib, "import_module", lambda name: modules[name])
    return modules


def test_named_helpers_and_prebound_aliases_are_adapted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    modules = _fake_vendor(monkeypatch)
    worker._install_python_helpers()
    aux = modules["pandapower.auxiliary"]
    assert aux.set_elements_oos is aux._python_set_elements_oos
    assert aux.set_isolated_buses_oos is aux._python_set_isolated_buses_oos
    assert aux.get_values is aux._get_values
    assert modules["pandapower.build_branch"].get_values is aux._get_values
    assert modules["pandapower.estimation.results"].get_values is aux._get_values
    assert callable(modules["pandapower.pf.makeYbus_numba"].gen_Ybus)


@pytest.mark.parametrize(
    "defect", ["version", "function", "original", "alias", "ybus_alias", "ybus_module"]
)
def test_unknown_vendor_surface_fails_closed(
    monkeypatch: pytest.MonkeyPatch, defect: str
) -> None:
    modules = _fake_vendor(monkeypatch)
    if defect == "version":
        modules["pandapower"].__version__ = "99.0"
    elif defect == "function":
        modules["pandapower.auxiliary"].get_values = object()
    elif defect == "original":
        modules["pandapower.auxiliary"]._get_values = object()
    elif defect == "alias":
        modules["pandapower.build_branch"].get_values = object()
    elif defect == "ybus_alias":
        modules["pandapower.pf.makeYbus_numba"].makeYbus = object()
    else:
        modules["pandapower.shortcircuit.impedance"].makeYbus.__module__ = "unexpected"
    with pytest.raises((RuntimeError, AttributeError)):
        worker._install_python_helpers()


def test_existing_vendor_python_ybus_is_preserved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    modules = _fake_vendor(monkeypatch)
    impedance = modules["pandapower.shortcircuit.impedance"]
    impedance.makeYbus.__module__ = "pandapower.pypower.makeYbus"
    original = impedance.makeYbus
    worker._install_python_helpers()
    assert impedance.makeYbus is original


def test_native_marker_in_provenance_is_ordinary_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = replace(_strength(), provenance="Historical node down investigation")
    payload = json.dumps({"result": asdict(result)})
    _command(monkeypatch, f"print({payload!r})")
    assert adapter.run_screening("strength", {}) == result


def test_worker_identity_is_pid_scoped(monkeypatch: pytest.MonkeyPatch) -> None:
    assert adapter.in_screening_worker() is False
    monkeypatch.setattr(worker, "_owner_pid", os.getpid())
    assert adapter.in_screening_worker() is True
    monkeypatch.setattr(worker, "_owner_pid", -1)
    assert adapter.in_screening_worker() is False


def test_worker_main_owns_only_the_batch(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        sys, "stdin", io.StringIO('{"kind":"strength","parameters":{}}')
    )
    monkeypatch.setattr(worker, "_install_python_helpers", lambda: None)

    def execute(kind: str, parameters: dict) -> GridStrengthResult:
        assert adapter.in_screening_worker()
        print("vendor diagnostic")
        return _strength()

    monkeypatch.setattr(worker, "_execute", execute)
    worker.main()
    output = capsys.readouterr()
    assert json.loads(output.out)["result"] == asdict(_strength())
    assert output.err == "vendor diagnostic\n"
    assert worker._owner_pid is None


def test_worker_main_arms_and_cancels_its_own_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, object]] = []
    monkeypatch.setattr(
        sys, "stdin", io.StringIO('{"kind":"strength","parameters":{}}')
    )
    monkeypatch.setattr(worker, "_policy", lambda: (7.0, ["3.5.4"]))
    monkeypatch.setattr(worker, "_install_python_helpers", lambda: None)
    monkeypatch.setattr(worker, "_execute", lambda kind, parameters: _strength())
    monkeypatch.setattr(
        worker.faulthandler,
        "dump_traceback_later",
        lambda seconds, exit, file: calls.append(("arm", (seconds, exit, file))),
    )
    monkeypatch.setattr(
        worker.faulthandler,
        "cancel_dump_traceback_later",
        lambda: calls.append(("cancel", None)),
    )
    worker.main()
    assert calls == [
        ("arm", (7.0 + worker._ORPHAN_GRACE_SECONDS, True, 2)),
        ("cancel", None),
    ]


def test_orphaned_worker_ends_itself_without_its_parent() -> None:
    # Run the real worker main() with no parent-side timeout at all: only the
    # worker's own deadline can stop a solve that never returns.
    source = textwrap.dedent("""
        import io, sys, time
        from analytics.grid import _pandapower_worker as worker
        worker._policy = lambda: (0.2, ["3.5.4"])
        worker._ORPHAN_GRACE_SECONDS = 0.3
        worker._install_python_helpers = lambda: None
        worker._execute = lambda kind, parameters: time.sleep(60)
        sys.stdin = io.StringIO('{"kind":"strength","parameters":{}}')
        worker.main()
        """)
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        filter(None, [str(adapter._ROOT), env.get("PYTHONPATH", "")])
    )
    completed = subprocess.run(
        [sys.executable, "-c", source],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=adapter._ROOT,
        env=env,
    )
    assert completed.returncode != 0
    assert completed.stdout == ""
    assert "Timeout" in completed.stderr


@pytest.mark.parametrize(
    "wire_request",
    [
        "bad",
        "{}",
        '{"kind":"other","parameters":{}}',
        '{"kind":"strength","parameters":[]}',
    ],
)
def test_worker_rejects_bad_request(
    monkeypatch: pytest.MonkeyPatch,
    wire_request: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO(wire_request))
    with pytest.raises(SystemExit) as exc:
        worker.main()
    assert exc.value.code == 1
    output = capsys.readouterr()
    assert output.out == "" and output.err
    assert worker._owner_pid is None


def test_worker_exception_clears_ownership(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        sys, "stdin", io.StringIO('{"kind":"strength","parameters":{}}')
    )

    def fail() -> None:
        raise RuntimeError("dependency failed")

    monkeypatch.setattr(worker, "_install_python_helpers", fail)
    with pytest.raises(SystemExit):
        worker.main()
    assert "dependency failed" in capsys.readouterr().err
    assert worker._owner_pid is None


def test_worker_dispatch_is_allowlisted(monkeypatch: pytest.MonkeyPatch) -> None:
    from analytics.grid import harmonics, reactive_screen, short_circuit

    monkeypatch.setattr(
        short_circuit, "screen_grid_strength", lambda **kwargs: _strength()
    )
    monkeypatch.setattr(
        reactive_screen, "screen_reactive_capability", lambda **kwargs: _reactive(True)
    )
    monkeypatch.setattr(harmonics, "screen_harmonics", lambda **kwargs: _strength())
    assert worker._execute("strength", {}) == _strength()
    assert worker._execute("reactive", {}) == _reactive(True)
    assert worker._execute("harmonics", {}) == _strength()
    for kind, args in (("unknown", {}), ("strength", {"use_pandapower": False})):
        with pytest.raises(ValueError):
            worker._execute(kind, args)
