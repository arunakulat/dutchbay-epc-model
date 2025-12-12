DutchBay_EPC_Model – Risk Haircut Implementation Patch (2025-12-04)
===================================================================

Scope
-----
This patch does **not** replace your existing `finance/cashflow_v14.py` file.
Instead it gives you:
  * A focused pytest file to assert that the CFADS haircut is applied.
  * A suggested code change snippet for `cashflow_v14.build_annual_rows` which
    you can paste into your existing implementation in the right place.

The goal is:
  * `risk_haircut_amount = cfads_pre_haircut * cfads_haircut_pct`
  * `cfads_final_lkr = cfads_pre_haircut - risk_haircut_amount`
  * Row-level fields carry `risk_haircut_pct` and `risk_haircut_amount`
  * Timeseries exposes `risk_haircut_amount_lkr` correctly.

Where to change cashflow_v14
----------------------------
In `finance/cashflow_v14.py`, inside `build_annual_rows(config)` you should
have a per-year loop which ends roughly like this **before** the change:

    posttax_cfads = pretax_cfads - tax_lkr

    # current behaviour (no risk haircut applied)
    risk_haircut_pct = params.cfads_haircut_pct
    risk_haircut_amount = 0.0
    cfads_final_lkr = posttax_cfads

    row = {
        ...
        "pretax_cfads": pretax_cfads,
        "posttax_cfads": posttax_cfads,
        "risk_haircut_pct": risk_haircut_pct,
        "risk_haircut_amount": risk_haircut_amount,
        "cfads_final_lkr": cfads_final_lkr,
        ...
    }

Replace that part with the following logic:

    posttax_cfads = pretax_cfads - tax_lkr

    # --- CFADS risk haircut implementation ---
    # Use post-tax CFADS as the base for the haircut
    risk_haircut_pct = params.cfads_haircut_pct
    cfads_pre_haircut = posttax_cfads

    risk_haircut_amount = cfads_pre_haircut * risk_haircut_pct
    cfads_final_lkr = cfads_pre_haircut - risk_haircut_amount

    row = {
        ...
        "pretax_cfads": pretax_cfads,
        "posttax_cfads": posttax_cfads,
        "risk_haircut_pct": risk_haircut_pct,
        "risk_haircut_amount": risk_haircut_amount,
        "cfads_final_lkr": cfads_final_lkr,
        ...
    }

Then, in the `cashflow` summary dict that `build_annual_rows` returns, make
sure you have:

    cashflow = {
        "annual_rows": rows,
        "cfads_final_lkr": [r["cfads_final_lkr"] for r in rows],
        ...
        "risk_haircut_amount_lkr": [r["risk_haircut_amount"] for r in rows],
        "risk_haircut_pct": risk_haircut_pct,
        ...
    }

Pytest: new focused test
------------------------
Drop `tests/api/test_cashflow_risk_haircut_v14.py` from this patch into your
repo and run:

    python -m pytest tests/api/test_cashflow_risk_haircut_v14.py
    python -m pytest
    python -m mypy analytics finance dutchbay_v14chat run_full_pipeline_v14.py
    python -m black .
    python -m ruff check .
    python -m isort .

The test assumes you already have the scenario
`scenarios/dutchbay_lendercase_2025Q4.yaml` with:

    risk_adjustment:
      cfads_haircut_pct: 0.1

and that `build_annual_rows` reads that through your parameter extraction
layer.

After the patch, for that scenario you should see, for every year i:

    row["cfads_final_lkr"][i] == approx(row["posttax_cfads"][i] * 0.9)
    row["risk_haircut_amount"][i] == approx(row["posttax_cfads"][i] * 0.1)

If the test passes and your full pipeline still runs cleanly, you’re done.
