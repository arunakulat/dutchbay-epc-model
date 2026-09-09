"""Exercise real ANDES code generation in private storage without starting pools.

The pool guard is checked outside the core's candidate-fallback exception boundary.
Model preparation and generated-code loading remain real; only storage routing and the
post-preparation disturbance boundary are replaced in the lifecycle-only probes.
"""

from __future__ import annotations

import multiprocessing
import sys
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from analytics.grid import ride_through

pytestmark = [
    pytest.mark.grid,
    pytest.mark.filterwarnings(
        "error:This process .* is multi-threaded.*:DeprecationWarning"
    ),
]


def _clear_pycode_modules() -> None:
    """Remove only generated-code modules before an independently loaded cache state."""
    for name in tuple(sys.modules):
        if name in {"pycode", "andes.pycode"} or name.startswith(
            ("pycode.", "andes.pycode.")
        ):
            del sys.modules[name]


@pytest.fixture
def codegen_probe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    """Route the real ANDES loader to private code and observe every model/pool call."""
    andes = pytest.importorskip("andes")
    import multiprocess
    from andes.core import Model
    from andes.system import codegen

    saved_modules = {
        name: module
        for name, module in sys.modules.copy().items()
        if name in {"pycode", "andes.pycode"}
        or name.startswith(("pycode.", "andes.pycode."))
    }
    before_children = {p.pid for p in multiprocess.active_children()}
    _clear_pycode_modules()
    storage = tmp_path / "pycode"
    prepared: list[str] = []
    pools: list[int] = []
    ready: list[Any] = []
    original_prepare = Model.prepare

    def owned_path(path: str | None = None, mkdir: bool = False) -> str:
        if mkdir:
            storage.mkdir(parents=True, exist_ok=True)
        return str(storage)

    def observe_prepare(model: Any, *args: Any, **kwargs: Any) -> Any:
        prepared.append(model.class_name)
        return original_prepare(model, *args, **kwargs)

    def forbid_pool(ncpu: int) -> Any:
        pools.append(ncpu)
        raise AssertionError("ANDES attempted a code-generation pool")

    def after_prepare(system: Any, spec: Any) -> bool:
        ready.append(system)
        return False  # Lifecycle probe ends before a physical solve.

    monkeypatch.setattr(codegen, "get_pycode_path", owned_path)
    monkeypatch.setattr(codegen, "andes_root", lambda: str(tmp_path / "no-package"))
    monkeypatch.setattr(codegen, "Pool", forbid_pool)
    monkeypatch.setattr(Model, "prepare", observe_prepare)
    monkeypatch.setattr(ride_through, "_apply_disturbance", after_prepare)
    monkeypatch.setattr(ride_through, "_CANDIDATE_CASES", ("ieee14/ieee14_wt3.xlsx",))
    try:
        yield {
            "andes": andes,
            "before_children": before_children,
            "storage": storage,
            "prepared": prepared,
            "pools": pools,
            "ready": ready,
        }
    finally:
        _clear_pycode_modules()
        sys.modules.update(saved_modules)
        assert pools == [], "pool attempts must not disappear inside candidate fallback"
        assert {p.pid for p in multiprocess.active_children()} == before_children


def _load_probe(probe: Any) -> Any:
    """Enter the production dynamics path and require complete real generated calls."""
    probe["ready"].clear()
    ride_through.run_ride_through_case("lvrt", run_dynamics=True)
    assert probe["pools"] == []
    import multiprocess

    assert {p.pid for p in multiprocess.active_children()} == probe["before_children"]
    assert len(probe["ready"]) == 1, "preparation must reach the disturbance boundary"
    system = probe["ready"][0]
    assert system.with_calls
    assert not system.codegen._find_stale_models()
    assert callable(system.PQ.calls.g)
    return system


def _threaded_load_child(probe: Any) -> None:
    """Run one real threaded lifecycle probe inside a killable child process."""
    errors: list[BaseException] = []

    def threaded_load() -> None:
        try:
            _load_probe(probe)
        except (
            BaseException
        ) as exc:  # pragma: no cover - child reports failures by exit
            errors.append(exc)

    worker = threading.Thread(
        target=threaded_load, name="ci-fork-lifecycle-worker", daemon=False
    )
    worker.start()
    worker.join()
    if errors:
        raise errors[0]


def _nonreturning_thread_child() -> None:
    """Keep a non-daemon worker alive until the supervising process terminates us."""
    blocker = threading.Event()
    worker = threading.Thread(target=blocker.wait, name="ci-fork-hanging-worker")
    worker.start()
    worker.join()


def test_missing_valid_stale_and_broken_code_lifecycle(codegen_probe: Any) -> None:
    """Cold code is generated, warm calls reuse it, and one stale model is repaired."""
    probe = codegen_probe
    system = _load_probe(probe)
    assert sorted(probe["prepared"]) == sorted(system.models)

    probe["prepared"].clear()
    for _ in range(3):
        _load_probe(probe)
    # A caller's worker thread must follow the same in-process preparation lifecycle. Put
    # the real threaded probe in a child so a hung non-daemon worker can be terminated
    # without restoring the fixture's patches while it is still executing.
    context = multiprocessing.get_context("fork")
    threaded_process = context.Process(target=_threaded_load_child, args=(probe,))
    threaded_process.start()
    threaded_process.join(timeout=60)
    if threaded_process.is_alive():
        threaded_process.terminate()
        threaded_process.join(timeout=5)
    threaded_process_alive = threaded_process.is_alive()
    assert not threaded_process_alive, "threaded lifecycle child was not terminated"
    assert threaded_process.exitcode == 0
    threaded_process.close()
    assert probe["prepared"] == []

    bus = probe["storage"] / "Bus.py"
    bus.write_text(bus.read_text() + "\nmd5 = 'deliberately-stale'\n")
    _clear_pycode_modules()
    _load_probe(probe)
    assert probe["prepared"] == ["Bus"]

    # An importable module can retain its current checksum while losing a required stored
    # member.  ANDES reports that partial load through ``with_calls=False``; the production
    # fallback must regenerate every model rather than trusting the matching checksum.
    complete_bus = bus.read_text()
    assert "md5 = " in complete_bus
    assert "f_args = " in complete_bus
    bus.write_text(
        "\n".join(
            line
            for line in complete_bus.splitlines()
            if not line.lstrip().startswith("f_args = ")
        )
        + "\n"
    )
    _clear_pycode_modules()
    probe["prepared"].clear()
    repaired = _load_probe(probe)
    assert sorted(probe["prepared"]) == sorted(repaired.models)

    # A genuinely non-returning worker is contained in a child and must be terminated by
    # the supervising test within its explicit deadline.
    hanging_process = context.Process(target=_nonreturning_thread_child)
    hanging_process.start()
    hanging_process.join(timeout=1)
    assert hanging_process.is_alive()
    hanging_process.terminate()
    hanging_process.join(timeout=5)
    assert not hanging_process.is_alive()
    assert hanging_process.exitcode != 0
    hanging_process.close()

    # Invalid Python preserves the explicit setup-failure path and cannot create a pool.
    init = probe["storage"] / "__init__.py"
    original = init.read_bytes()
    init.write_text("invalid generated Python !!!\n")
    _clear_pycode_modules()
    probe["ready"].clear()
    result = ride_through.run_ride_through_case("lvrt", run_dynamics=True)
    import multiprocess

    assert result.ran is False
    assert result.rode_through is None
    assert "SyntaxError" in result.detail
    assert probe["ready"] == []
    assert probe["pools"] == []
    assert {p.pid for p in multiprocess.active_children()} == probe["before_children"]

    init.write_bytes(original)
    _clear_pycode_modules()
    probe["prepared"].clear()
    _load_probe(probe)
    assert probe["prepared"] == []


def test_codegen_failure_remains_explicit(
    codegen_probe: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A real preparation failure cannot become a solved or compliant result."""
    from andes.core import Model

    def fail_prepare(model: Any, *args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("injected code-generation failure")

    monkeypatch.setattr(Model, "prepare", fail_prepare)
    result = ride_through.run_ride_through_case("lvrt", run_dynamics=True)
    assert result.ran is False
    assert result.converged is False
    assert result.rode_through is None
    assert "injected code-generation failure" in result.detail
    assert codegen_probe["ready"] == []


def test_dynamics_off_never_reaches_andes(monkeypatch: pytest.MonkeyPatch) -> None:
    """All default-off studies finish without dependency loading or code generation."""
    calls: list[str] = []

    def forbidden_import() -> Any:
        calls.append("import")
        raise AssertionError("ANDES reached with dynamics off")

    monkeypatch.setattr(ride_through, "_require_andes", forbidden_import)
    for kind in ride_through.RIDE_THROUGH_CASES:
        result = ride_through.run_ride_through_case(kind, run_dynamics=False)
        assert result.ran is False
        assert result.rode_through is None
    assert calls == []
