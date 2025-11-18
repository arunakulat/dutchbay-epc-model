import yaml

def prompt_float(label, default):
    inp = input(f"{label} [{default}]: ")
    return float(inp) if inp.strip() else default

def prompt_int(label, default):
    inp = input(f"{label} [{default}]: ")
    return int(inp) if inp.strip() else default

def main():
    print("DutchBay v14 Scenario YAML Generator")

    scenario = {}
    scenario['project'] = {
        "capacity_mw": prompt_float("Project MW", 100),
        "capacity_factor": prompt_float("Capacity factor (0-1)", 0.36),
        "degradation": prompt_float("Degradation per year (0-1)", 0.005),
    }
    scenario['tariff'] = {
        "lkr_per_kwh": prompt_float("Tariff LKR/kWh", 52),
    }
    scenario['opex'] = {
        "usd_per_year": prompt_float("Annual Opex USD", 1150000),
    }
    scenario['capex'] = {
        "usd_total": prompt_float("CAPEX total USD", 128000000),
    }
    ft = {}
    ft['debt_ratio'] = prompt_float("Debt ratio", 0.75)
    ft['tenor_years'] = prompt_int("Debt tenor (years)", 14)
    ft['construction_periods'] = prompt_int("Construction periods", 2)
    cs = []
    print("Enter construction schedule per year (%) as comma-separated (e.g. 60, 60):")
    cs_inp = input(f"Construction Schedule (default: 60,60): ")
    ft['construction_schedule'] = [float(x) for x in cs_inp.split(",")] if cs_inp.strip() else [60.0, 60.0]
    ddd = []
    print("Enter debt drawdown per year (%) as comma-separated (e.g. 0.5,0.5):")
    dd_inp = input(f"Debt drawdown schedule (default: 0.5,0.5): ")
    ft['debt_drawdown_pct'] = [float(x) for x in dd_inp.split(",")] if dd_inp.strip() else [0.5, 0.5]
    ft['grace_years'] = prompt_int("Grace years", 1)
    ft['interest_only_years'] = prompt_int("Interest only years", 0)
    ft['amortization_style'] = input("Amortization style (annuity/linear) [annuity]: ") or "annuity"
    ft['target_dscr'] = prompt_float("Target DSCR", 1.35)
    ft['mix'] = {
        "lkr_max": prompt_float("LKR mix", 0.0),
        "dfi_max": prompt_float("DFI mix", 0.0),
        "usd_commercial_min": prompt_float("USD min mix", 1.0)
    }
    ft['rates'] = {
        "usd_nominal": prompt_float("USD nominal rate", 0.08)
    }
    scenario['Financing_Terms'] = ft
    fname = input("Output filename (e.g. scenario_my_test.yaml): ").strip()
    if not fname:
        fname = "scenario_autogen.yaml"
    with open(fname, "w") as f:
        yaml.dump(scenario, f, default_flow_style=False)
    print(f"Scenario written to {fname}")

if __name__ == "__main__":
    main()
