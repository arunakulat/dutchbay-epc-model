from dutchbay_v13 import cli


def test_cli_v14_smoke(tmp_path, capsys):
    """
    Smoke test for the new v14 CLI mode.

    It should:
      - run without raising
      - print the 'V14 run complete.' marker
      - write a v14_summary.csv file in the given out_dir
    """
    out_dir = tmp_path / "cli_v14_out"

    config_path = "full_model_variables_updated.yaml"

    argv = [
        "--config",
        config_path,
        "--mode",
        "v14",
        "--out-dir",
        str(out_dir),
        "--validation-mode",
        "strict",
    ]

    cli.main(argv)

    captured = capsys.readouterr()
    assert "V14 run complete." in captured.out

    summary_path = out_dir / "v14_summary.csv"
    assert summary_path.exists(), "v14_summary.csv was not created by CLI v14 mode"

    text = summary_path.read_text(encoding="utf-8")
    lines = [ln for ln in text.splitlines() if ln.strip()]
    assert len(lines) > 1
    assert lines[0].startswith("year,cfads_pre_debt,debt_service,dscr")

    