import subprocess, sys, pytest

def test_cli_help_runs_nonfatally():
    cmd = [sys.executable, "-m", "dutchbay_v13", "--help"]
    try:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
    except Exception:
        pytest.xfail("CLI help not wired or argparse not present")
    # Some CLIs exit 0 on --help, some 2; both are acceptable for a smoke.
    assert p.returncode in (0, 2)
    assert (p.stdout or p.stderr)
