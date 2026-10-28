"""Private, one-request worker for pandapower screening; never a shared service."""

from __future__ import annotations

import contextlib
import faulthandler
import importlib
import json
import logging
import os
import sys
from collections.abc import Callable
from typing import cast

from analytics.grid.pandapower_screening import (
    ScreenKind,
    ScreenResult,
    _encode_result,
    _json_value,
    _policy,
)

_owner_pid: int | None = None
# The parent kills the worker at the policy timeout. This later, in-worker
# deadline covers the case the parent cannot: a caller killed by SIGTERM or
# SIGKILL leaves the worker orphaned, and macOS offers no parent-death signal.
_ORPHAN_GRACE_SECONDS = 5.0


def _install_python_helpers() -> None:
    """Adapt only the known vendor helpers and aliases in this disposable worker.

    The public APIs do not expose a no-JIT switch for these paths. Reusing each
    dispatcher's original Python function preserves its numerical implementation.
    The explicit alias list is version-scoped; future versions fail closed until
    their consumer graph and numerical controls are reviewed.
    """
    pp = importlib.import_module("pandapower")
    _timeout, versions = _policy()
    if pp.__version__ not in versions:
        raise RuntimeError(
            f"Pandapower {pp.__version__} has no verified screening adapter; "
            f"supported versions: {versions}. Use the governed [grid] environment."
        )
    auxiliary = importlib.import_module("pandapower.auxiliary")
    branch = importlib.import_module("pandapower.build_branch")
    estimation = importlib.import_module("pandapower.estimation.results")
    impedance = importlib.import_module("pandapower.shortcircuit.impedance")
    replacements = [
        (auxiliary, "get_values", "_get_values"),
        (auxiliary, "set_elements_oos", "_python_set_elements_oos"),
        (auxiliary, "set_isolated_buses_oos", "_python_set_isolated_buses_oos"),
    ]
    # When Numba is absent, pandapower already selects its Python Ybus routine.
    # Follow that existing selection instead of introducing a Numba requirement.
    ybus_module = impedance.makeYbus.__module__
    if ybus_module == "pandapower.pf.makeYbus_numba":
        ybus = importlib.import_module(ybus_module)
        if impedance.makeYbus is not ybus.makeYbus:
            raise RuntimeError("Unrecognized short-circuit Ybus alias.")
        replacements.append((ybus, "gen_Ybus", "gen_Ybus"))
    elif ybus_module != "pandapower.pypower.makeYbus":
        raise RuntimeError("Unrecognized short-circuit Ybus implementation.")
    for module, name, python_name in replacements:
        current = getattr(module, name)
        original = getattr(current, "py_func", current)
        if (
            not callable(original)
            or getattr(original, "__name__", None) != python_name
            or getattr(original, "__module__", None) != module.__name__
        ):
            raise RuntimeError(
                f"Unrecognized pandapower helper: {module.__name__}.{name}"
            )
        if module is auxiliary and original is not getattr(auxiliary, python_name):
            raise RuntimeError(f"Pandapower Python implementation mismatch: {name}")
        if name == "get_values":
            for alias_module in (branch, estimation):
                if getattr(alias_module, name) is not current:
                    raise RuntimeError(
                        f"Unrecognized get_values alias: {alias_module.__name__}"
                    )
                setattr(alias_module, name, original)
        setattr(module, name, original)


def _execute(kind: ScreenKind, parameters: dict[str, object]) -> ScreenResult:
    """Dispatch only the existing screening functions, with their own validation."""
    from analytics.grid.harmonics import screen_harmonics
    from analytics.grid.reactive_screen import screen_reactive_capability
    from analytics.grid.short_circuit import screen_grid_strength

    operations: dict[ScreenKind, Callable[..., ScreenResult]] = {
        "strength": screen_grid_strength,
        "reactive": screen_reactive_capability,
        "harmonics": screen_harmonics,
    }
    if kind not in operations or parameters.get("use_pandapower", True) is not True:
        raise ValueError(
            "Worker requires an allowlisted pandapower screening operation."
        )
    return operations[kind](**parameters)


def main() -> None:
    """Read one private JSON request, execute its complete batch, and exit.

    Errors are reported on stderr with a nonzero exit. A missing/broken dependency,
    an unsupported version, and a solver error cannot become a fallback result.
    The worker also ends itself, with a traceback and a nonzero exit, once the
    policy timeout plus a grace period has passed, so an orphaned worker cannot
    run unbounded.
    """
    global _owner_pid
    try:
        request = json.loads(sys.stdin.read())
        if not isinstance(request, dict) or set(request) != {"kind", "parameters"}:
            raise ValueError("Invalid screening request envelope.")
        kind = request["kind"]
        parameters = _json_value(request["parameters"])
        if kind not in {"strength", "reactive", "harmonics"} or not isinstance(
            parameters, dict
        ):
            raise ValueError("Invalid screening operation or arguments.")
        timeout, _versions = _policy()
        # Write the deadline traceback to the process's own stderr descriptor; the
        # parent captures it, and a replaced sys.stderr may have no file number.
        faulthandler.dump_traceback_later(
            timeout + _ORPHAN_GRACE_SECONDS, exit=True, file=2
        )
        # Preserve warnings/errors, keeping stdout exclusively for the JSON result.
        logging.getLogger().setLevel(logging.WARNING)
        with contextlib.redirect_stdout(sys.stderr):
            _install_python_helpers()
            _owner_pid = os.getpid()
            result = _execute(
                cast(ScreenKind, kind), cast(dict[str, object], parameters)
            )
            payload = _encode_result(result)
        sys.stdout.write(json.dumps({"result": payload}, allow_nan=False))
    except Exception as exc:
        sys.stderr.write(f"{type(exc).__name__}: {exc}\n")
        raise SystemExit(1) from exc
    finally:
        faulthandler.cancel_dump_traceback_later()
        _owner_pid = None
