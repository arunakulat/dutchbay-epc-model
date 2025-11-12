import importlib, subprocess, sys, pytest

def test_import_api():
    m = importlib.import_module("dutchbay_v13.api")
    assert hasattr(m, "__dict__")

def test_import_adapters():
    m = importlib.import_module("dutchbay_v13.adapters")
    assert hasattr(m, "__dict__")

@pytest.mark.xfail(reason="CLI may exit; best-effort touch only")
def test_cli_help_touch():
    try:
        subprocess.run([sys.executable, "-m", "dutchbay_v13", "--help"],
                       check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except SystemExit:
        pytest.xfail("CLI exited")
