from dutchbay_v13 import cli


def test_modes_smoke(tmp_path):
    # minimal config yaml
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text("tariff_usd_per_kwh: 0.1\n", encoding="utf-8")
    out = tmp_path / "out"

    # Modes to exercise (excluding 'api')
    modes = [
        "baseline",
        "sensitivity",
        "optimize",
        "report",
        "montecarlo",
        "validate",
        "irr",
        "utils",
        "debt",
        "cashflow",
    ]

    for m in modes:
        rc = cli.main(["--mode", m, "--config", str(cfg), "--outputs-dir", str(out)])
        assert rc == 0, f"{m} returned {rc}"
