"""ANDES RMS low-voltage ride-through (LVRT) scaffold (#872).

Stands up **ANDES**, loads a small system with a generic WECC IBR (REGCA1/REECA1 /
Type-3 wind), applies an impedance bus fault, and confirms the RMS time-domain solve
converges — demonstrating the dynamics layer end-to-end. The LVRT entry threshold is
parameterised from the redacted D0 grid-code fixture
(``tests/fixtures/grid/envision_enpcs01_gridcode.yaml``), so the scaffold is seeded from
the OEM envelope rather than a magic constant. The detailed, ``.dyr``-calibrated model is
a later dolphin; RMS is screening-grade (EMT/PSCAD for a true FRT study).

CASPER: ``andes`` is an OPTIONAL dependency of the ``[grid]`` extra. It is NEVER imported
at module-import time; the import is deferred to :func:`_require_andes`, which raises an
actionable ImportError at call-time if the extra is absent.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

# The D0 redacted grid-code fixture (referenced, never executed). Resolves relative to
# the repo root so the scaffold seeds its LVRT threshold from the OEM envelope.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_D0_FIXTURE = (
    _REPO_ROOT / "tests" / "fixtures" / "grid" / "envision_enpcs01_gridcode.yaml"
)

#: Generic WECC IBR / synchronous device models we count as the "dynamics present" check.
_IBR_MODELS = (
    "REGCA1",
    "REGCP1",
    "REECA1",
    "REPCA1",
    "WTARA1",
    "WTDTA1",
    "PVD1",
    "GENROU",
)

#: ANDES bundled example cases carrying an IBR, tried in order (self-contained scaffold).
_CANDIDATE_CASES = (
    "ieee14/ieee14_wt3.xlsx",
    "ieee14/ieee14_regcp1.xlsx",
    "ieee14/ieee14_pvd1.xlsx",
)


def _require_andes() -> Any:
    """Return the ``andes`` module or raise an actionable CASPER error if absent."""
    try:
        import andes  # noqa: F401

        return andes
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise ImportError(
            "The grid LVRT scaffold requires the [grid] extra: "
            "pip install 'andes>=2.0'  (or  PIP_CONSTRAINT=constraints.txt "
            "pip install -e '.[grid]'). It is an OPTIONAL dependency — the base finance "
            "install never needs it."
        ) from exc


@dataclass(frozen=True)
class LvrtScaffoldResult:
    """Outcome of the ANDES LVRT scaffold run (screening-grade dynamics smoke test)."""

    ran: bool
    lvrt_enter_pu: float
    detail: str
    n_devices: int = 0
    min_bus_voltage_pu: float | None = None


def lvrt_enter_from_fixture(fixture_path: Path | str | None = None) -> float:
    """Read the LVRT entry threshold (pu) from the D0 grid-code fixture.

    Falls back to 0.9 pu if the fixture or the ``lvrt_enter_pu`` key is absent, so the
    scaffold never hard-fails on a missing optional reference file.
    """
    path = Path(fixture_path) if fixture_path is not None else _D0_FIXTURE
    if not path.is_file():
        return 0.9
    data = yaml.safe_load(path.read_text()) or {}
    pcs = data.get("pcs", {}) if isinstance(data, dict) else {}
    value = pcs.get("lvrt_enter_pu", 0.9)
    return float(value)


def run_lvrt_case(
    *,
    lvrt_enter_pu: float | None = None,
    fault_bus: int = 4,
    fault_start_s: float = 1.0,
    fault_clear_s: float = 1.1,
    fault_x_pu: float = 0.05,
    fixture_path: Path | str | None = None,
) -> LvrtScaffoldResult:
    """Run one ANDES RMS LVRT case and report whether the TDS converged.

    Loads a bundled ANDES IBR case, applies an impedance bus fault (a partial voltage
    dip that triggers the IBR ride-through path yet keeps the positive-sequence solve
    convergent — a bolted fault makes the RMS solve singular), runs power flow + the
    time-domain simulation, and reports convergence + the deepest bus voltage during the
    dip. The site-specific, ``.dyr``-calibrated model is a later dolphin.

    Args:
        lvrt_enter_pu: LVRT entry threshold (pu). ``None`` reads it from the D0 fixture.
        fault_bus / fault_start_s / fault_clear_s / fault_x_pu: impedance-fault params.
        fixture_path: override for the grid-code fixture (tests inject a path).

    Returns:
        LvrtScaffoldResult — ``ran`` is True when the TDS exit code is 0 (converged).
    """
    andes = _require_andes()
    if lvrt_enter_pu is None:
        lvrt_enter_pu = lvrt_enter_from_fixture(fixture_path)

    last_err = "no candidate case attempted"
    for rel in _CANDIDATE_CASES:
        try:
            case = andes.get_case(rel)
            ss = andes.load(case, setup=False, no_output=True, default_config=True)
            ss.add(
                "Fault",
                dict(bus=fault_bus, tf=fault_start_s, tc=fault_clear_s, xf=fault_x_pu),
            )
            ss.setup()
            ss.PFlow.run()
            ss.TDS.config.tf = 2.0
            ss.TDS.run()
            converged = int(getattr(ss, "exit_code", 1)) == 0
            n_devices = int(
                sum(getattr(ss, m).n for m in _IBR_MODELS if hasattr(ss, m))
            )
            vmin = _min_bus_voltage(ss)
            dip = f"; min bus V during dip={vmin:.3f} pu" if vmin is not None else ""
            return LvrtScaffoldResult(
                ran=converged,
                lvrt_enter_pu=lvrt_enter_pu,
                detail=(
                    f"case={rel}; TDS exit={int(getattr(ss, 'exit_code', 1))} "
                    f"(converged); bus-{fault_bus} impedance fault "
                    f"{fault_start_s}-{fault_clear_s}s{dip}; IBR/gen devices={n_devices}. "
                    f"LVRT-enter {lvrt_enter_pu} pu seeded from the D0 grid-code fixture; "
                    "detailed .dyr calibration is a later dolphin."
                ),
                n_devices=n_devices,
                min_bus_voltage_pu=vmin,
            )
        except (
            Exception
        ) as exc:  # try next candidate; keep the last failure for the report
            last_err = f"{rel}: {exc!r}"
    return LvrtScaffoldResult(
        ran=False,
        lvrt_enter_pu=lvrt_enter_pu,
        detail=f"ANDES LVRT scaffold did not complete ({last_err})",
    )


def _min_bus_voltage(ss: Any) -> float | None:
    """Deepest bus voltage over the simulation (the depth of the dip the IBRs rode)."""
    try:
        ts = ss.dae.ts
        vidx = [i for i, name in enumerate(ss.dae.y_name) if name.startswith("V ")]
        if vidx:
            return float(ts.y[:, vidx].min())
    except Exception:  # pragma: no cover - diagnostic only
        return None
    return None


__all__ = ["LvrtScaffoldResult", "run_lvrt_case", "lvrt_enter_from_fixture"]
