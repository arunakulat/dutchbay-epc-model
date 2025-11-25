#!/usr/bin/env python3
import argparse
import json
import sys
import tempfile
import subprocess
from copy import deepcopy
import yaml

TRY_JSON = ["--format", "json"]

SCENARIOS = [
    {"name": "150MW_DSRA", "capacity_mw": 150, "risk_cover": "DSRA"},
    {"name": "150MW_IDA", "capacity_mw": 150, "risk_cover": "IDA"},
    {"name": "120MW_DSRA", "capacity_mw": 120, "risk_cover": "DSRA"},
    {"name": "120MW_IDA", "capacity_mw": 120, "risk_cover": "IDA"},
    {"name": "100MW_DSRA", "capacity_mw": 100, "risk_cover": "DSRA"},
    {"name": "100MW_IDA", "capacity_mw": 100, "risk_cover": "IDA"},
]


def _read_yaml(path):
    with open(path, "r") as f:
        return yaml.safe_load(f)


def _dump_yaml(d, path):
    with open(path, "w") as f:
        yaml.safe_dump(d, f, sort_keys=False)


def _apply_overrides(base_cfg: dict, capacity_mw: int, cover: str, tax_holiday: bool):
    base = deepcopy(base_cfg)
    t = base.setdefault("Technical", {})
    f = base.setdefault("Finance", {})
    t["nameplate_mw"] = capacity_mw
    f["fx_initial"] = 300
    f["fx_depr"] = 0.03
    f["cod_year"] = 2029
    f["corp_tax_rate"] = 0.30
    f["tax_holiday_years"] = 5 if tax_holiday else 0
    f["use_dsra"] = cover == "DSRA"
    f["use_ida_prg"] = cover == "IDA"
    return base


def _run_cli(tmp_yaml_path: str):
    cmd = [
        sys.executable,
        "-m",
        "dutchbay_v13.cli",
        "--config",
        tmp_yaml_path,
        "--mode",
        "irr",
    ] + TRY_JSON
    out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
    # Expect JSON
    return json.loads(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-config", required=True)
    ap.add_argument("--tax-holiday", choices=["on", "off"], default="off")
    args = ap.parse_args()

    base_cfg = _read_yaml(args.base_config)
    tax_holiday = args.tax_holiday == "on"
    results = []

    for sc in SCENARIOS:
        cfg = _apply_overrides(
            base_cfg, sc["capacity_mw"], sc["risk_cover"], tax_holiday
        )
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as tf:
            _dump_yaml(cfg, tf.name)
            tmp = tf.name
        metrics = _run_cli(tmp)
        results.append(
            {
                "scenario": sc["name"],
                "capacity_mw": sc["capacity_mw"],
                "risk_cover": sc["risk_cover"],
                "tax_holiday_years": 5 if tax_holiday else 0,
                "metrics": metrics,
            }
        )

    print(
        json.dumps(
            {
                "generated_by": "run_exporter.py",
                "base_config": args.base_config,
                "tax_holiday": tax_holiday,
                "scenarios": results,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
