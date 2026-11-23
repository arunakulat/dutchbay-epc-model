"""Screen-only Wariyapola interface study using source-assigned line R
and EXPLICITLY illustrative X, source-fault and P/Q assumptions.

No utility-approved SCR/voltage or interconnection claims. Outputs external
to the checkout; the committed lendercase is never edited.
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

import yaml
from path_guard import require_external_path

from analytics.grid.evaluate_grid import evaluate_grid
from analytics.grid.grid_interface_schema import validate_grid_block

PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parents[2]


def calculate(config: dict, repo: Path) -> dict:
    s = yaml.safe_load((repo / config["base_scenario"]).read_text())
    grid = s["grid"]
    line = config["line"]
    e = config["electrical"]
    assert grid["study_enabled"] is False
    grid["study_enabled"] = True
    grid["allow_unvalidated_grid"] = True
    grid["poc_voltage_kv"] = line["nominal_kv"]
    grid["poc"].update(
        bus_name=line["collector_bus"],
        nominal_kv=line["nominal_kv"],
        plant_rated_mva=e["plant_rating_mva_screening_assumption"],
    )
    grid["plant_rating_mva"] = e["plant_rating_mva_screening_assumption"]
    grid["source_rx"] = e["assumed_source_rx"]
    grid["thevenin"]["x_r"] = e["assumed_network_thevenin_x_r"]
    grid["thevenin"]["assumption_basis"] = "screening_estimate"

    cases = []
    for fault_mva in e["screening_source_fault_mva"]:
        for circuits in (2, 1):
            # Source conductor resistance from Annex III I, divided by twin
            # bundle and by circuits remaining; X is an explicit sensitivity.
            grid["connection_r_ohm"] = round(
                line["route_km"]
                * line["conductor_ac_resistance_25C_ohm_per_km"]
                / line["conductors_per_phase_bundle"]
                / circuits,
                5,
            )
            grid["connection_x_ohm"] = round(
                line["route_km"]
                * line["assumed_single_circuit_reactance_ohm_per_km"]
                / circuits,
                5,
            )
            grid["source_fault_level_mva"] = fault_mva
            grid["thevenin"]["short_circuit_mva_min"] = min(fault_mva, 700.0)
            grid["thevenin"]["short_circuit_mva_max"] = max(fault_mva, 1100.0)
            errors: list[str] = []
            validate_grid_block(s, errors)
            if errors:
                raise ValueError(
                    "invalid illustrative grid configuration: " + ", ".join(errors)
                )
            res = evaluate_grid(
                copy.deepcopy(s), use_pandapower=False, run_reactive=False
            )
            cases.append(
                {
                    "fault_mva_ASSUMED": fault_mva,
                    "circuits": circuits,
                    "line_R_ohm": grid["connection_r_ohm"],
                    "line_X_ohm_ASSUMED": grid["connection_x_ohm"],
                    "SCR_ILLUSTRATIVE": res.strength.scr,
                    "bankable": False,
                }
            )
    return {
        "status": "ADVISORY_NON_BANKABLE",
        "method": "magnitude_only_screening_evaluate_grid_no_pandapower_no_reactive",
        "poc_definition": "Dutch Bay plant-side collector end; series line connects to hypothetical Wariyapola source",
        "upstream_bus": "Wariyapola 220 kV assumed source; authenticated CEB model absent",
        "transformer_n_minus_one": "NOT MODELLED: 2 x 90 MVA, one offline leaves 90 MVA < assumed 133 MW, minimum 32.3% active-power curtailment even at power factor 1",
        "line_voltage_and_charging": "not modelled; no EMT/QSTS or grid-code certification",
        "assumption_sources": {
            "fault_mva": "illustrative, old Puttalam proxy not valid Wariyapola evidence",
            "line_X": "illustrative 0.27 ohm/km/circuit; no utility model",
            "line_R": "EIA Annex III I 25C prelim, not issued-for-construction",
        },
        "route_length_km_EIA_PRELIMINARY": line["route_km"],
        "poc_kv_ASSUMED": line["nominal_kv"],
        "plant_mva_ASSUMED": e["plant_rating_mva_screening_assumption"],
        "cases": cases,
        "hold": [
            "PCC and transmission ownership not confirmed",
            "Wariyapola fault-level equivalent not provided by utility",
            "positive-sequence reactance and dynamic converter models unverified",
            "national 2030 line versus legacy 2027 COD unresolved",
            "not utility-approved or suitable for lender representation",
        ],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=Path, default=PACKAGE / "grid_screen_config.yaml")
    ap.add_argument("--repo", type=Path, default=REPO)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    try:
        out = require_external_path(args.output, declared_repo=args.repo)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    result = calculate(yaml.safe_load(args.config.read_text()), args.repo)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"cases": len(result["cases"]), "status": result["status"]}))


if __name__ == "__main__":
    main()
