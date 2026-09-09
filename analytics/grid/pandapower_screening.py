"""Run each complete pandapower screen in a fresh, single-owner Python process.

Only the child adapts vendor helpers. The calling process keeps its pandapower and
Numba state, including unrelated JIT users, unchanged. This private wire protocol
transports existing contracts; it introduces no alternative grid result contract.
"""

from __future__ import annotations

import json
import math
import os
import re
import subprocess
import sys
import warnings
from collections.abc import Mapping, Sequence
from dataclasses import asdict, fields, replace
from pathlib import Path
from typing import Literal, TypeAlias

from pydantic import TypeAdapter

from analytics.contracts_v14 import (
    GridStrengthResult,
    HarmonicComplianceResult,
    PowerFlowResult,
    ReactiveCapabilityResult,
)

ScreenKind: TypeAlias = Literal["strength", "reactive", "harmonics"]
ScreenResult: TypeAlias = (
    GridStrengthResult
    | tuple[ReactiveCapabilityResult, PowerFlowResult | None]
    | HarmonicComplianceResult
)
JsonValue: TypeAlias = (
    None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]
)
_ROOT = Path(__file__).resolve().parents[2]
_POLICY_PATH = _ROOT / "config/pandapower_screening.json"
_NATIVE_FAILURE = re.compile(
    r"Fatal Python error|Segmentation|node down|replacing crashed worker", re.I
)


class ScreeningProcessError(RuntimeError):
    """A grid worker failed; no successful or approximate screen is substituted."""


def _json_value(value: object) -> JsonValue:
    """Normalize ordinary configuration containers and reject nonfinite numbers."""
    if value is None or isinstance(value, (bool, str, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("Screening transport requires finite numerical values.")
        return value
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise ValueError("Screening configuration keys must be strings.")
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_json_value(item) for item in value]
    raise ValueError(f"Unsupported screening transport value: {type(value).__name__}")


def _policy() -> tuple[float, list[str]]:
    """Read and strictly validate the committed lifecycle/compatibility policy."""
    policy = json.loads(_POLICY_PATH.read_text(encoding="utf-8"))
    if not isinstance(policy, dict) or set(policy) != {
        "schema_version",
        "timeout_seconds",
        "supported_pandapower_versions",
    }:
        raise ValueError("Invalid pandapower screening policy fields.")
    timeout = policy["timeout_seconds"]
    versions = policy["supported_pandapower_versions"]
    if (
        policy["schema_version"] != "dutchbay.pandapower_screening.v1"
        or isinstance(timeout, bool)
        or not isinstance(timeout, (int, float))
        or not math.isfinite(timeout)
        or timeout <= 0
        or not isinstance(versions, list)
        or not versions
        or any(not isinstance(v, str) or not v for v in versions)
    ):
        raise ValueError("Invalid pandapower screening lifecycle/compatibility policy.")
    return float(timeout), versions


def _worker_command() -> list[str]:
    """Use the caller's governed interpreter and an explicit private entrypoint."""
    return [
        sys.executable,
        "-c",
        "from analytics.grid._pandapower_worker import main; main()",
    ]


def _wire_parameters(parameters: Mapping[str, object]) -> JsonValue:
    """Represent supported numeric spectrum mappings as equivalent ordered pairs.

    Keep both source locations and their precedence intact. Numeric keys retain
    their types; string and boolean keys remain values the existing parser ignores.
    """
    arguments = dict(parameters)
    grid = arguments.get("grid")
    if isinstance(grid, Mapping):
        grid = dict(grid)
        arguments["grid"] = grid
        gridcode = grid.get("gridcode")
        containers = [grid]
        if isinstance(gridcode, Mapping):
            gridcode = dict(gridcode)
            grid["gridcode"] = gridcode
            containers.append(gridcode)
        for container in containers:
            spectrum = container.get("harmonic_spectrum")
            if isinstance(spectrum, Mapping):
                container["harmonic_spectrum"] = list(spectrum.items())
    return _json_value(arguments)


def in_screening_worker() -> bool:
    """Return whether this interpreter owns the initialized, adapted worker."""
    module = sys.modules.get("analytics.grid._pandapower_worker")
    return module is not None and getattr(module, "_owner_pid", None) == os.getpid()


def _encode_result(result: ScreenResult) -> JsonValue:
    """Serialize contracts, encoding only the established nonconvergence NaN as null."""
    if isinstance(result, tuple):
        reactive, power_flow = result
        pf_data = asdict(power_flow) if power_flow is not None else None
        if power_flow is not None and not power_flow.converged:
            if not math.isnan(power_flow.poc_voltage_pu):
                raise ValueError(
                    "Nonconverged power flow must carry its NaN voltage sentinel."
                )
            assert pf_data is not None
            pf_data["poc_voltage_pu"] = None
        return _json_value([asdict(reactive), pf_data])
    return _json_value(asdict(result))


def _check_fields(data: object, cls: type[object], method: str) -> None:
    """Reject incomplete, extra, relabelled, or bankable worker results."""
    if (
        not isinstance(data, dict)
        or set(data) != {field.name for field in fields(cls)}  # type: ignore[arg-type]
        or data.get("bankable") is not False
        or data.get("method") != method
    ):
        raise ValueError("Worker returned an invalid screening contract.")


def _decode_result(kind: ScreenKind, value: object) -> ScreenResult:
    """Validate finite wire values and reconstruct the canonical typed contracts."""
    value = _json_value(value)
    if kind == "strength":
        _check_fields(value, GridStrengthResult, "pandapower_iec60909")
        return TypeAdapter(GridStrengthResult).validate_json(
            json.dumps(value), strict=True
        )
    if kind == "harmonics":
        _check_fields(value, HarmonicComplianceResult, "pandapower_zbus")
        return TypeAdapter(HarmonicComplianceResult).validate_json(
            json.dumps(value), strict=True
        )
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError("Worker returned an invalid reactive result pair.")
    reactive, pf_data = value
    _check_fields(reactive, ReactiveCapabilityResult, "pandapower_runpp")
    _check_fields(pf_data, PowerFlowResult, "pandapower_runpp")
    assert isinstance(pf_data, dict)
    missing_voltage = pf_data["poc_voltage_pu"] is None
    if missing_voltage:
        if pf_data["converged"] is not False:
            raise ValueError("A converged power flow cannot have an absent voltage.")
        pf_data["poc_voltage_pu"] = 0.0
    elif pf_data["converged"] is False:
        raise ValueError("Nonconverged power flow lost its voltage sentinel.")
    pair = TypeAdapter(tuple[ReactiveCapabilityResult, PowerFlowResult]).validate_json(
        json.dumps(value), strict=True
    )
    if pair[0].governing_converged != pair[1].converged:
        raise ValueError("Reactive and power-flow convergence disagree.")
    return pair[0], (
        replace(pair[1], poc_voltage_pu=float("nan")) if missing_voltage else pair[1]
    )


def run_screening(kind: ScreenKind, parameters: Mapping[str, object]) -> ScreenResult:
    """Execute one complete screen and reap its worker on completion or failure.

    Args:
        kind: One of the three private, allowlisted screening operations.
        parameters: Arguments of that existing screen, using finite JSON values.

    Returns:
        The existing canonical screening contract, with unchanged mathematics.

    Raises:
        ValueError: Configuration or arguments cannot be represented faithfully.
        ScreeningProcessError: Timeout, process death, dependency/solver failure,
            or invalid worker output. These failures never select a fallback.
    """
    if kind not in {"strength", "reactive", "harmonics"}:
        raise ValueError(f"Unknown screening operation: {kind}")
    timeout, _versions = _policy()
    request = json.dumps(
        {"kind": kind, "parameters": _wire_parameters(parameters)}, allow_nan=False
    )
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        filter(None, [str(_ROOT), env.get("PYTHONPATH", "")])
    )
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        # Own cleanup explicitly: Python 3.12's run() can leave a killed child
        # unreaped after real SIGINT consumes communicate()'s brief signal wait.
        with subprocess.Popen(
            _worker_command(),
            text=True,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=_ROOT,
            env=env,
        ) as child:
            try:
                stdout, stderr = child.communicate(request, timeout=timeout)
            except BaseException:
                child.kill()
                child.wait()
                raise
            completed = subprocess.CompletedProcess(
                child.args, child.returncode, stdout, stderr
            )
    except subprocess.TimeoutExpired as exc:
        raise ScreeningProcessError(
            f"Pandapower {kind} worker exceeded {timeout:g} seconds and was terminated."
        ) from exc
    except OSError as exc:
        raise ScreeningProcessError(
            f"Cannot start pandapower {kind} worker: {exc}"
        ) from exc
    if completed.returncode or _NATIVE_FAILURE.search(completed.stderr):
        raise ScreeningProcessError(
            f"Pandapower {kind} worker failed (exit {completed.returncode}); "
            f"no screening result accepted. {completed.stderr[-2000:]}"
        )
    try:
        response = json.loads(completed.stdout)
        if not isinstance(response, dict) or set(response) != {"result"}:
            raise ValueError("Invalid response envelope.")
        result = _decode_result(kind, response["result"])
    except (ValueError, TypeError) as exc:
        raise ScreeningProcessError(
            f"Invalid pandapower {kind} worker response: {exc}"
        ) from exc
    if completed.stderr.strip():
        warnings.warn(
            f"Pandapower {kind} worker: {completed.stderr[-2000:]}",
            RuntimeWarning,
            stacklevel=2,
        )
    return result
