import importlib, pytest

def _find_map(m):
    for k in ("MODE_MAP","HANDLERS","DISPATCH","ADAPTERS","MODE_HANDLERS"):
        if hasattr(m, k) and isinstance(getattr(m, k), dict):
            return getattr(m, k), k
    return None, None

def _resolve_target(val):
    import importlib
    if callable(val):
        return val
    if isinstance(val, str) and "::" in val:
        mod, func = val.split("::", 1)
        mm = importlib.import_module(mod)
        return getattr(mm, func)
    return None

def test_adapters_mapping_present_and_resolves_some_keys():
    m = importlib.import_module("dutchbay_v13.adapters")
    mapping, name = _find_map(m)
    if mapping is None:
        pytest.xfail("No adapters mapping exported yet")
    assert isinstance(mapping, dict)
    expected = {"irr","sensitivity","matrix","scenarios","report","report-pdf"}
    present = expected & set(mapping.keys())
    assert present, "no expected keys present in adapters mapping"
    for k in present:
        tgt = mapping[k]
        resolved = _resolve_target(tgt)
        assert (callable(tgt) or resolved), f"handler for {k} not import-resolvable"
