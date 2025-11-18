import os, glob, yaml, json, csv
from dutchbay_v14chat.finance.cashflow import build_annual_rows_v14
from dutchbay_v14chat.finance.debt import apply_debt_layer

def load_config(path):
    if path.endswith('.json'):
        with open(path, 'r') as f:
            return json.load(f)
    elif path.endswith(('.yaml', '.yml')):
        with open(path, 'r') as f:
            return yaml.safe_load(f)
    else:
        raise ValueError(path)

def get_scenario_files(directory):
    pats = ['*.json', '*.yaml', '*.yml']
    files = []
    for pat in pats:
        files.extend(glob.glob(os.path.join(directory, pat)))
    return files

def export_long(directory, outfile="scenario_timeseries.csv"):
    files = get_scenario_files(directory)
    all_rows = []
    for file in files:
        scen_name = os.path.splitext(os.path.basename(file))[0]
        try:
            config = load_config(file)
            annual_rows = build_annual_rows_v14(config)
            debt = apply_debt_layer(config, annual_rows)
            dscr_series = debt.get("dscr_series", [])
            debt_series = debt.get("debt_outstanding", [])
            for i, row in enumerate(annual_rows):
                rec = {
                    "scenario": scen_name,
                    "year": row.get("year", i + 1),
                    "label": row.get("label", ""),
                    "revenue_usd": row.get("revenue_usd"),
                    "opex_usd": row.get("opex_usd"),
                    "cfads": row.get("cfads_usd"),
                    "dscr": dscr_series[i] if i < len(dscr_series) else "",
                    "debt_outstanding": debt_series[i] if i < len(debt_series) else ""
                }
                all_rows.append(rec)
        except Exception as e:
            print(f"Error exporting {scen_name}: {e}")
    keys = ["scenario", "year", "label", "revenue_usd", "opex_usd", "cfads", "dscr", "debt_outstanding"]
    with open(outfile, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(all_rows)
    print(f"[LONG] Full annual timeseries exported to: {outfile}")

def export_wide(directory, outfile="scenario_wide.csv"):
    files = get_scenario_files(directory)
    all_rows, years = [], 0
    cfads_block, dscr_block, debt_block = [], [], []
    for file in files:
        scen = os.path.splitext(os.path.basename(file))[0]
        try:
            cfg = load_config(file)
            annual = build_annual_rows_v14(cfg)
            debt = apply_debt_layer(cfg, annual)
            ys = len(annual); years = max(years, ys)
            cfads_block.append([row.get("cfads_usd") for row in annual])
            dscr_block.append(debt.get("dscr_series",[""]*ys))
            debt_block.append(debt.get("debt_outstanding",[""]*ys))
            all_rows.append({"scenario": scen})
        except Exception as e:
            print(f"Error {scen}: {e}")
    headers = ["scenario"] + \
        [f"cfads_y{y+1}" for y in range(years)] + \
        [f"dscr_y{y+1}" for y in range(years)] + \
        [f"debt_y{y+1}" for y in range(years)]
    for i, row in enumerate(all_rows):
        for y in range(years):
            row[f"cfads_y{y+1}"] = cfads_block[i][y] if y < len(cfads_block[i]) else ""
            row[f"dscr_y{y+1}"] = dscr_block[i][y] if y < len(dscr_block[i]) else ""
            row[f"debt_y{y+1}"] = debt_block[i][y] if y < len(debt_block[i]) else ""
    with open(outfile, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(all_rows)
    print(f"[WIDE] Export complete: {outfile}")

def qc_and_outlier_analysis(csvfile, dscr_minimum=1.25):
    import pandas as pd
    df = pd.read_csv(csvfile)
    print("\nQC: Scenarios with ANY DSCR below {0}:".format(dscr_minimum))
    bad = df[[col for col in df.columns if col.startswith("dscr_y") or col == "scenario"]]
    for idx, row in bad.iterrows():
        dscrs = row.values[1:]
        if any((isinstance(v, float) and v < dscr_minimum) for v in dscrs if v not in ["", "inf"]):
            print(f"  {row['scenario']}: {dscrs}")
    print("\nQC: Scenarios with negative last-year CFADS:")
    badcfads = df[["scenario"]+[c for c in df.columns if c.startswith("cfads_y")]]
    for idx, row in badcfads.iterrows():
        last_val = next((float(val) for val in reversed(row.values[1:]) if val != "" and val != "inf"), 0)
        if last_val < 0:
            print(f"  {row['scenario']}: last CFADS = {last_val}")

def emit_mac_excel_chart_vba(years):
    vba = f"""
' MAC EXCEL VBA: Paste into Excel's VBA editor (Tools > Macro > Visual Basic Editor > Insert Module)
Sub ChartDSCRPerScenario()
    Dim ws As Worksheet
    Set ws = ActiveSheet
    Dim lastRow As Integer
    lastRow = ws.Cells(ws.Rows.Count, 1).End(xlUp).Row
    Charts.Add
    ActiveChart.ChartType = xlLine
    Dim i As Integer
    For i = 2 To lastRow
        With ActiveChart.SeriesCollection.NewSeries
            .Name = ws.Cells(i, 1)
            .Values = ws.Range(ws.Cells(i, {years+2}), ws.Cells(i, {2*years+1}))
            .XValues = ws.Range(ws.Cells(1, 2), ws.Cells(1, {years+1}))
        End With
    Next i
    ActiveChart.Location Where:=xlLocationAsObject, Name:=ws.Name
End Sub
"""
    print("\nCopy-paste the following into Mac Excel VBA Editor to chart DSCR:\n")
    print(vba)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Scenario batch export: long, wide, QC, VBA chart helper")
    parser.add_argument("--dir", "-d", required=True, help="Scenario directory")
    parser.add_argument("--longcsv", "-l", default="scenario_timeseries.csv", help="Long-format CSV filename")
    parser.add_argument("--widecsv", "-w", default="scenario_wide.csv", help="Wide-format CSV filename")
    parser.add_argument("--dscr_qc", "-q", default=1.25, type=float, help="DSCR threshold for QC")
    parser.add_argument("--emitvba", action="store_true", help="Emit Mac Excel VBA snippet for adding DSCR chart")
    args = parser.parse_args()

    export_long(args.dir, args.longcsv)
    export_wide(args.dir, args.widecsv)
    qc_and_outlier_analysis(args.widecsv, args.dscr_qc)
    # VBA macro helper (copies for the correct #years in your data)
    if args.emitvba:
        import pandas as pd
        wide_df = pd.read_csv(args.widecsv)
        years = (len([c for c in wide_df.columns if c.startswith("dscr_y")]))
        emit_mac_excel_chart_vba(years)


