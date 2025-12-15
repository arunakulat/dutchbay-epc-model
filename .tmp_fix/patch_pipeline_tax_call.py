import pathlib
import re

PIPELINE = pathlib.Path("analytics/orchestrators/pipeline_v14.py")


def main() -> None:
    s = PIPELINE.read_text(encoding="utf-8")

    # 1) Ensure we cache accepted tax kwargs once (inside the enable_tax_overlay block).
    # Insert right before: for i, row in enumerate(annual_rows, start=1):
    loop_line = "            for i, row in enumerate(annual_rows, start=1):"
    if loop_line not in s:
        raise SystemExit("Could not find annual_rows tax loop in pipeline_v14.py")

    cache_snippet = (
        "            import inspect\n"
        "            _tax_param_names = set(inspect.signature(calculate_tax).parameters)\n\n"
    )

    if "_tax_param_names" not in s:
        s = s.replace(loop_line, cache_snippet + loop_line)

    # 2) Replace the calculate_tax call block with a filtered-kwargs call.
    pattern = re.compile(
        r"(?P<indent>\s*)tax_res: TaxResult\s*=\s*calculate_tax\(\s*(?P<body>[\s\S]*?)\)\s*\n",
        re.MULTILINE,
    )

    m = pattern.search(s)
    if not m:
        raise SystemExit("Could not find calculate_tax(...) call assigning to tax_res")

    indent = m.group("indent")
    replacement = (
        f"{indent}tax_kwargs = {{\n"
        f"{indent}    'tax_profile': tax_profile,\n"
        f"{indent}    'statutory_profile': stat_profile,\n"
        f"{indent}    'stat_profile': stat_profile,\n"
        f"{indent}    'year_index': i,\n"
        f"{indent}    'year': i,\n"
        f"{indent}    'year_idx': i,\n"
        f"{indent}    'ebit_lkr': ebit_lkr,\n"
        f"{indent}    'interest_expense_lkr': interest_lkr,\n"
        f"{indent}    'interest_lkr': interest_lkr,\n"
        f"{indent}    'depreciation_lkr': depreciation_lkr,\n"
        f"{indent}    'interest_to_nonresidents_lkr': interest_to_nonresidents_lkr,\n"
        f"{indent}}}\n"
        f"{indent}tax_res: TaxResult = calculate_tax(**{{k: v for k, v in tax_kwargs.items() if k in _tax_param_names}})\n"
    )

    s = pattern.sub(replacement, s, count=1)

    PIPELINE.write_text(s, encoding="utf-8")
    print("Patched:", str(PIPELINE))


if __name__ == "__main__":
    main()
