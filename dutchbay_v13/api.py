from __future__ import annotations
from typing import Dict, Any, Generator
from pathlib import Path
import json
import yaml

try:
    from fastapi import FastAPI, Request
    from fastapi.responses import StreamingResponse, HTMLResponse
    import uvicorn
except Exception:  # pragma: no cover
    FastAPI = None  # type: ignore

from .core import build_financial_model
from .scenario_runner import run_scenario, _validate_params_dict, _validate_debt_dict
from .schema import SCHEMA, DEBT_SCHEMA

HTML_TMPL = """
<!doctype html>
<html>
<head><meta charset="utf-8"><title> DutchBay V13 – Params Editor </title>
<style>
body { font-family: Arial, sans-serif; margin: 24px; }
h1,h2 { margin: 8px 0; }
fieldset { margin-bottom: 16px; }
label { display:block; margin: 6px 0 2px; font-weight: 600; }
input { width: 240px; padding: 6px; }
small { color: #555; }
button { padding: 8px 12px; margin-top: 12px; }
</style></head>
<body>
<h1>Params Editor</h1>
<form method="post" action="/form/save">
  <fieldset><legend><b>Project Params</b></legend>
    {param_inputs}
  </fieldset>
  <fieldset><legend><b>Debt Terms</b></legend>
    {debt_inputs}
  </fieldset>
  <label>Output YAML file name (in inputs/scenarios/)</label>
  <input type="text" name="outfile" value="edited.yaml"/>
  <br/>
  <button type="submit">Save YAML</button>
</form>
</body>
</html>
"""


def _input_row(name: str, value: Any, unit: str, rng: str) -> str:
    return f'<label>{name} <small>({unit}, {rng})</small></label><input name="{name}" value="{value}"/>'


def _render_form() -> str:
    param_html = "\n".join(
        _input_row(
            k, "", SCHEMA[k]["unit"], f"[{SCHEMA[k]['min']}, {SCHEMA[k]['max']}]"
        )
        for k in SCHEMA
    )
    debt_html = "\n".join(
        _input_row(
            f"debt.{k}",
            "",
            DEBT_SCHEMA[k]["unit"],
            f"[{DEBT_SCHEMA[k]['min']}, {DEBT_SCHEMA[k]['max']}]",
        )
        for k in DEBT_SCHEMA
    )
    return HTML_TMPL.format(param_inputs=param_html, debt_inputs=debt_html)


def create_app() -> Any:
    if FastAPI is None:  # pragma: no cover
        raise RuntimeError("FastAPI not installed. pip install .[web]")
    app = FastAPI(title="DutchBay V13 API")

    @app.get("/schema")
    async def schema() -> Dict[str, Any]:
        return {"params": SCHEMA, "debt": DEBT_SCHEMA}

    @app.post("/run/baseline")
    async def run_baseline(payload: Dict[str, Any]) -> Dict[str, Any]:
        # Accept optional 'debt' mapping
        params = payload or {}
        return {
            k: v for k, v in build_financial_model(params).items() if k != "annual_data"
        }

    @app.post("/run/scenarios/stream")
    async def run_scenarios_stream(payload: Dict[str, Any]):
        """Stream JSONL for each scenario: [{name, params}]"""
        scenarios = payload.get("scenarios", [])

        def gen() -> Generator[bytes, None, None]:
            for sc in scenarios:
                name = sc.get("name", "scenario")
                params = sc.get("params", {})
                row = run_scenario(name, params, outdir=None)
                yield (json.dumps(row) + "\n").encode("utf-8")

        return StreamingResponse(gen(), media_type="application/x-ndjson")

    @app.get("/form", response_class=HTMLResponse)
    async def form():
        return _render_form()

    @app.post("/form/save", response_class=HTMLResponse)
    async def form_save(request: Request):
        form = await request.form()
        outname = str(form.get("outfile") or "edited.yaml")
        params: Dict[str, Any] = {}
        debt: Dict[str, Any] = {}
        for k, v in form.items():
            if k == "outfile":
                continue
            if k.startswith("debt."):
                debt[k.split(".", 1)[1]] = v
            else:
                params[k] = v
        # validate and coerce
        p = _validate_params_dict(params, where="form.params")
        d = _validate_debt_dict(debt, where="form.debt") if debt else {}
        if d:
            p["debt"] = d
        out_dir = Path("inputs/scenarios")
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / outname).write_text(
            yaml.safe_dump(p, sort_keys=True), encoding="utf-8"
        )
        return HTMLResponse(
            f"<p>Saved to inputs/scenarios/{outname}</p><p><a href='/form'>Back</a></p>"
        )

    return app


def run(host: str = "0.0.0.0", port: int = 8000):
    if FastAPI is None:  # pragma: no cover
        raise RuntimeError("FastAPI not installed. pip install .[web]")
    uvicorn.run(create_app(), host=host, port=port)
