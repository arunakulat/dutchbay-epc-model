"""Fresh-process native-path controls for the actual #1229 screening adapter."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from decimal import Decimal, localcontext
from pathlib import Path
from uuid import uuid4

import pytest

pytestmark = pytest.mark.grid
pytest.importorskip("pandapower")

from analytics.grid import pandapower_screening as adapter  # noqa: E402
from analytics.grid.harmonics import screen_harmonics  # noqa: E402
from analytics.grid.reactive_screen import screen_reactive_capability  # noqa: E402
from analytics.grid.short_circuit import screen_grid_strength  # noqa: E402

CHARTER = dict(
    poc_voltage_kv=33.0,
    source_fault_level_mva=900.0,
    source_rx=0.083,
    connection_r_ohm=0.6,
    connection_x_ohm=6.0,
    plant_rating_mva=159.6,
)
GRID = {
    "poc": {"nominal_kv": 33.0, "plant_rated_mva": 159.6},
    "gridcode": {"pf_range": [-0.95, 0.95], "voltage_window_pu": [0.9, 1.1]},
    "resources": [{"reactive_capability": {"min_q_mvar": -40.0, "max_q_mvar": 40.0}}],
    "source_rx": 0.1,
    "connection_r_ohm": 0.3,
    "connection_x_ohm": 3.5,
    "harmonic_spectrum": [[1, 100.0], [5, 2.4], [7, 1.5], [11, 0.9], [13, 0.7]],
}


def guard_command(mode: str, receipt: Path) -> list[str]:
    """Inject a pre-import compile sentinel without any production test switch."""
    source = textwrap.dedent("""
        import json, importlib
        from pathlib import Path
        import numba
        from numba.core.dispatcher import Dispatcher
        from analytics.grid import _pandapower_worker as worker
        stats = {'compile_attempts': [], 'sc_completed': 0, 'runpp_completed': 0}
        class CompileBlocked(BaseException):
            pass
        def block(self, *args, **kwargs):
            name = self.py_func.__name__
            stats['compile_attempts'].append(name)
            raise CompileBlocked(name)
        Dispatcher.compile = block
        install = worker._install_python_helpers
        def instrument():
            import pandapower as pp
            import pandapower.shortcircuit as sc
            aux = importlib.import_module('pandapower.auxiliary')
            ybus = importlib.import_module('pandapower.pf.makeYbus_numba')
            saved = {name: getattr(aux, name) for name in ('get_values', 'set_elements_oos', 'set_isolated_buses_oos')}
            saved_ybus = ybus.gen_Ybus
            if MODE != 'stock':
                install()
            if MODE == 'without_auxiliary':
                for name, value in saved.items():
                    setattr(aux, name, value)
                importlib.import_module('pandapower.build_branch').get_values = saved['get_values']
                importlib.import_module('pandapower.estimation.results').get_values = saved['get_values']
            if MODE == 'without_ybus':
                ybus.gen_Ybus = saved_ybus
            original_sc, original_runpp = sc.calc_sc, pp.runpp
            def calc(*args, **kwargs):
                result = original_sc(*args, **kwargs)
                stats['sc_completed'] += 1
                return result
            def run(*args, **kwargs):
                assert kwargs['numba'] is False
                result = original_runpp(*args, **kwargs)
                stats['runpp_completed'] += 1
                return result
            sc.calc_sc, pp.runpp = calc, run
            stats['global_disable_jit'] = numba.config.DISABLE_JIT
        worker._install_python_helpers = instrument
        try:
            worker.main()
        finally:
            Path(RECEIPT).write_text(json.dumps(stats))
    """)
    source = f"MODE={mode!r}\nRECEIPT={str(receipt)!r}\n" + source
    return [sys.executable, "-c", source]


def invoke(kind: str):
    """Exercise actual public consumers, including their production process boundary."""
    if kind == "strength":
        return screen_grid_strength(**CHARTER)
    if kind == "reactive":
        return screen_reactive_capability(GRID)
    return screen_harmonics(GRID, scr=5.0)


@pytest.mark.parametrize("location", ["top", "nested", "precedence", "empty_top"])
def test_spectrum_mapping_matches_list_across_real_consumers(location: str) -> None:
    """Existing mapping/list and precedence semantics survive both process callers."""
    mapping = deepcopy(GRID)
    mapping.pop("harmonic_spectrum")
    spectrum = {5: 2.4, 7.9: 1.5, "11": 9.0, True: 4.0}
    pairs = [[5, 2.4], [7.9, 1.5], ["11", 9.0], [True, 4.0]]
    if location == "top":
        mapping["harmonic_spectrum"] = spectrum
    else:
        mapping["gridcode"]["harmonic_spectrum"] = spectrum
        if location == "precedence":
            mapping["harmonic_spectrum"] = {13: 0.7}
        elif location == "empty_top":
            mapping["harmonic_spectrum"] = {}
    listed = deepcopy(mapping)
    if location == "top":
        listed["harmonic_spectrum"] = pairs
    else:
        listed["gridcode"]["harmonic_spectrum"] = pairs
        if location == "precedence":
            listed["harmonic_spectrum"] = [[13, 0.7]]
        elif location == "empty_top":
            listed["harmonic_spectrum"] = []
    before = repr(mapping)
    assert screen_harmonics(mapping, scr=5.0) == screen_harmonics(listed, scr=5.0)
    assert screen_reactive_capability(mapping, p_steps=2) == screen_reactive_capability(
        listed, p_steps=2
    )
    assert repr(mapping) == before


def test_numeric_spectrum_runs_real_report_core_and_harmonics() -> None:
    """Numeric spectrum data cannot abort the mandatory reactive report core."""
    from app.reports.grid_screening_emit import build_grid_screening_model
    from tests.app.test_grid_screening_emit import _scenario

    mapping = _scenario()
    mapping["grid"]["harmonic_spectrum"] = {5: 2.4, 7: 1.5}
    listed = deepcopy(mapping)
    listed["grid"]["harmonic_spectrum"] = [[5, 2.4], [7, 1.5]]
    models = [
        build_grid_screening_model(
            scenario, scenario_variant="numeric-spectrum", generated_at="2020-01-01"
        )
        for scenario in (mapping, listed)
    ]
    assert models[0] == models[1]
    assert models[0].study.reactive.method == "pandapower_runpp"
    assert models[0].harmonics.method == "pandapower_zbus"


@pytest.mark.parametrize(
    "kind,sc_count,flow_count",
    [("strength", 2, 0), ("reactive", 0, 15), ("harmonics", 0, 5)],
)
def test_public_screens_complete_without_compilation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
    sc_count: int,
    flow_count: int,
) -> None:
    receipt = tmp_path / "guard.json"
    monkeypatch.setattr(
        adapter, "_worker_command", lambda: guard_command("adapted", receipt)
    )
    result = invoke(kind)
    stats = json.loads(receipt.read_text())
    assert stats == {
        "compile_attempts": [],
        "sc_completed": sc_count,
        "runpp_completed": flow_count,
        "global_disable_jit": 0,
    }
    if kind == "strength":
        assert result.scr.hex() == float(0.9404814334303563).hex()
        assert result.fault_level_poc_mva.hex() == float(150.10083677548485).hex()
        assert result.fault_level_poc_max_mva.hex() == float(162.7411166572655).hex()
        assert result.bankable is False and result.method == "pandapower_iec60909"


@pytest.mark.parametrize(
    "mode,kind,target",
    [
        ("stock", "strength", "_python_set_elements_oos"),
        ("stock", "reactive", "_python_set_elements_oos"),
        ("stock", "harmonics", "_python_set_elements_oos"),
        ("without_auxiliary", "strength", "_python_set_elements_oos"),
        ("without_ybus", "strength", "gen_Ybus"),
    ],
)
def test_guard_kills_stock_and_independently_removed_adaptations(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
    kind: str,
    target: str,
) -> None:
    receipt = tmp_path / "guard.json"
    monkeypatch.setattr(
        adapter, "_worker_command", lambda: guard_command(mode, receipt)
    )
    with pytest.raises(adapter.ScreeningProcessError, match=target):
        invoke(kind)
    stats = json.loads(receipt.read_text())
    assert stats["compile_attempts"] == [target]
    assert stats["sc_completed"] == stats["runpp_completed"] == 0


def test_independent_radial_oracle_and_driver_responsiveness() -> None:
    # The scalar radial Thevenin oracle and pre-change fixture precede this patch.
    with localcontext() as context:
        context.prec = 60
        D = Decimal

        def scalar(c: str, resistance: str) -> Decimal:
            voltage_factor = D(c)
            z_source = voltage_factor * D(33) ** 2 / D(900)
            x_source = z_source / (1 + D(".083") ** 2).sqrt()
            r_source = x_source * D(".083")
            return (
                voltage_factor
                * D(33) ** 2
                / ((r_source + D(resistance)) ** 2 + (x_source + 6) ** 2).sqrt()
            )

        minimum, maximum = float(scalar("1", ".744")), float(scalar("1.1", ".6"))
    base = screen_grid_strength(**CHARTER)
    assert base.fault_level_poc_mva == pytest.approx(minimum, abs=1e-12, rel=0)
    assert base.fault_level_poc_max_mva == pytest.approx(maximum, abs=1e-12, rel=0)
    for key, value in (
        ("source_fault_level_mva", 600.0),
        ("source_rx", 0.3),
        ("connection_r_ohm", 1.2),
        ("connection_x_ohm", 8.0),
    ):
        changed = screen_grid_strength(**{**CHARTER, key: value})
        assert changed.fault_level_poc_mva != base.fault_level_poc_mva
        assert changed.fault_level_poc_max_mva != base.fault_level_poc_max_mva
    doubled = screen_grid_strength(**{**CHARTER, "plant_rating_mva": 319.2})
    assert doubled.scr == base.scr / 2


def test_concurrent_screens_preserve_parent_dispatchers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import importlib

    import numba

    aux = importlib.import_module("pandapower.auxiliary")
    ybus = importlib.import_module("pandapower.pf.makeYbus_numba")
    original = (
        aux.get_values,
        aux.set_elements_oos,
        aux.set_isolated_buses_oos,
        ybus.gen_Ybus,
        numba.config.DISABLE_JIT,
        dict(os.environ),
    )
    monkeypatch.setattr(
        adapter,
        "_worker_command",
        lambda: guard_command("adapted", tmp_path / f"{uuid4()}.json"),
    )
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(invoke, ["strength", "reactive", "harmonics"]))
    assert len(results) == 3
    assert original == (
        aux.get_values,
        aux.set_elements_oos,
        aux.set_isolated_buses_oos,
        ybus.gen_Ybus,
        numba.config.DISABLE_JIT,
        dict(os.environ),
    )
    receipts = [json.loads(p.read_text()) for p in tmp_path.glob("*.json")]
    assert len(receipts) == 3
    assert sum(r["sc_completed"] for r in receipts) == 2
    assert sum(r["runpp_completed"] for r in receipts) == 20
    assert all(r["compile_attempts"] == [] for r in receipts)


def test_numba_absence_keeps_vendor_python_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    command = [
        sys.executable,
        "-c",
        "import sys; sys.modules['numba'] = None; from analytics.grid._pandapower_worker import main; main()",
    ]
    monkeypatch.setattr(adapter, "_worker_command", lambda: command)
    result = screen_grid_strength(**CHARTER)
    assert result.method == "pandapower_iec60909"
    assert result.scr == pytest.approx(0.9404814334303563, abs=1e-14, rel=0)


def test_sparse_oos_aliases_and_late_import_match_vendor() -> None:
    source = textwrap.dedent("""
        import importlib,json
        import numpy as np
        import pandapower as pp
        import pandapower.shortcircuit as sc
        from numba.core.dispatcher import Dispatcher
        aux=importlib.import_module('pandapower.auxiliary')
        branch=importlib.import_module('pandapower.build_branch')
        stats={'elements':0,'isolated':0,'values':0}
        if ADAPTED:
            from analytics.grid._pandapower_worker import _install_python_helpers
            _install_python_helpers()
            def block(self,*args,**kwargs):
                raise AssertionError('unexpected compile: '+self.py_func.__name__)
            Dispatcher.compile=block
            for name,label in [('set_elements_oos','elements'),('set_isolated_buses_oos','isolated'),('get_values','values')]:
                original=getattr(aux,name)
                def wrapped(*args, _original=original, _label=label, **kwargs):
                    stats[_label]+=1
                    return _original(*args,**kwargs)
                setattr(aux,name,wrapped)
                if name=='get_values':
                    branch.get_values=wrapped
            # A consumer imported after adaptation receives the current Python alias.
            namespace={}
            exec('from pandapower.auxiliary import get_values',namespace)
            lookup=np.arange(50,dtype=np.int64)
            values=np.arange(50,dtype=float)*2
            assert namespace['get_values'](values,np.array([20,5]),lookup).tolist()==[40.,10.]
        net=pp.create_empty_network()
        for index,kv,active in [(5,110.,True),(20,20.,True),(30,20.,True),(40,20.,False)]:
            pp.create_bus(net,vn_kv=kv,index=index,in_service=active)
        pp.create_ext_grid(net,5,s_sc_max_mva=1000.,s_sc_min_mva=1000.,rx_max=.1,rx_min=.1)
        pp.create_transformer_from_parameters(net,5,20,sn_mva=25.,vn_hv_kv=110.,vn_lv_kv=20.,vk_percent=10.,vkr_percent=.5,pfe_kw=0.,i0_percent=0.,shift_degree=0.)
        pp.create_load(net,20,p_mw=2.,q_mvar=.5)
        pp.create_load(net,20,p_mw=200.,q_mvar=50.,in_service=False)
        pp.create_load(net,30,p_mw=1.,q_mvar=.1)
        pp.create_load(net,40,p_mw=1.,q_mvar=.1)
        pp.runpp(net,numba=False)
        assert bool(net.converged)
        result={'vm_pu':float(net.res_bus.at[20,'vm_pu']),'p_hv_mw':float(net.res_trafo.at[0,'p_hv_mw']),'active_loads':net._is_elements['load'].tolist()}
        sc.calc_sc(net,case='max')
        result['ikss_ka']=float(net.res_bus_sc.at[20,'ikss_ka'])
        if ADAPTED:
            assert all(count>0 for count in stats.values()),stats
        print(json.dumps({'result':result,'helper_calls':stats}))
    """)
    results = []
    for adapted in (False, True):
        completed = subprocess.run(
            [sys.executable, "-c", f"ADAPTED={adapted!r}\n" + source],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        assert completed.returncode == 0, completed.stderr
        results.append(json.loads(completed.stdout))
    assert results[0]["result"] == results[1]["result"]
    assert results[1]["result"]["active_loads"] == [True, False, False, False]
