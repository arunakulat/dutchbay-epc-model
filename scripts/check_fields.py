import json

with open("out/dutchbay_lendercase_2025Q4_results.json") as f:
    results = json.load(f)

annual_rows = results.get("annual_rows", [])

if annual_rows:
    print("📋 All fields in annual_rows[0]:")
    print("=" * 80)
    for key in sorted(annual_rows[0].keys()):
        value = annual_rows[0][key]
        if isinstance(value, (int, float)):
            print(f"  {key:<40} = {value:>20,.2f}")
        else:
            print(f"  {key:<40} = {value}")

    print("\n" + "=" * 80)
    print(f"\nTotal fields: {len(annual_rows[0])}")

    # Check if cfads exists under different name
    cfads_keys = [k for k in annual_rows[0].keys() if "cfads" in k.lower()]
    print(f"\n🔍 CFADS-related fields: {cfads_keys}")

    interest_keys = [k for k in annual_rows[0].keys() if "interest" in k.lower()]
    print(f"🔍 Interest-related fields: {interest_keys}")
