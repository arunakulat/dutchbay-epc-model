from dutchbay_v13 import cli


def test_cli_missing_mode_help():
    assert cli.main([]) == 2
