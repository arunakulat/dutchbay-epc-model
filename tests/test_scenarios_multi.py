from dutchbay_v13 import cli


def test_scenarios_multi(tmp_path):
    d1 = tmp_path / "a"
    d2 = tmp_path / "b"
    d1.mkdir()
    d2.mkdir()
    (d1 / "s1.yaml").write_text("tariff_usd_per_kwh: 0.1\n", encoding="utf-8")
    (d2 / "s2.yaml").write_text("tariff_usd_per_kwh: 0.2\n", encoding="utf-8")
    out = tmp_path / "out"
    rc = cli.main(
        [
            "--mode",
            "scenarios",
            "--scenarios",
            str(d1),
            str(d2),
            "--outputs-dir",
            str(out),
            "--format",
            "both",
        ]
    )
    assert rc == 0
    assert (out / "scenarios" / "scenarios.jsonl").exists()
    assert (out / "scenarios" / "scenarios.csv").exists()
