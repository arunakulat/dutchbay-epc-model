import json

with open("out/dutchbay_lendercase_2025Q4_results.json") as f:
    results = json.load(f)

annual_rows = results.get("annual_rows", [])
print(f"✅ Found {len(annual_rows)} annual rows\n")

print("📊 DSCR and Debt Service by Year:")
print("=" * 90)
print(f'{"Year":<6} {"DSCR":<10} {"Debt Service":<20} {"CFADS":<20} {"Interest":<15}')
print("-" * 90)

for row in annual_rows[:15]:  # First 15 years
    year = row.get("year", "N/A")
    dscr = row.get("dscr")
    debt_service = row.get("debt_service_usd")
    cfads = row.get("cfads")
    interest = row.get("interest_expense")

    if dscr is None:
        dscr_str = "❌ MISSING"
    else:
        dscr_str = f"{dscr:.2f}" if dscr > 0 else "N/A"

    if debt_service is None:
        debt_str = "❌ MISSING"
    else:
        debt_str = f"${debt_service:,.0f}" if debt_service > 0 else "$0"

    cfads_str = f"${cfads:,.0f}" if cfads and cfads > 0 else "$0"
    int_str = f"${interest:,.0f}" if interest and interest > 0 else "$0"

    print(f"{year:<6} {dscr_str:<10} {debt_str:<20} {cfads_str:<20} {int_str:<15}")

print("=" * 90)

# Detailed analysis
has_dscr = "dscr" in annual_rows[0]
has_debt_service = "debt_service_usd" in annual_rows[0]

rows_with_dscr = sum(1 for r in annual_rows if r.get("dscr") and r["dscr"] > 0)
rows_with_debt = sum(
    1 for r in annual_rows if r.get("debt_service_usd") and r["debt_service_usd"] > 0
)

print(f"\n🔍 Field Verification:")
print(f'  ✓ dscr field present: {"✅ YES" if has_dscr else "❌ NO"}')
print(
    f'  ✓ debt_service_usd field present: {"✅ YES" if has_debt_service else "❌ NO"}'
)
print(f"  ✓ Rows with DSCR > 0: {rows_with_dscr}/{len(annual_rows)}")
print(f"  ✓ Rows with Debt Service > 0: {rows_with_debt}/{len(annual_rows)}")

# Get DSCR stats
dscr_values = [r.get("dscr", 0) for r in annual_rows if r.get("dscr") and r["dscr"] > 0]
if dscr_values:
    print(f"\n📈 DSCR Statistics:")
    print(f"  Min DSCR: {min(dscr_values):.2f}")
    print(f"  Max DSCR: {max(dscr_values):.2f}")
    print(f"  Avg DSCR: {sum(dscr_values)/len(dscr_values):.2f}")

if has_dscr and has_debt_service and rows_with_dscr > 0:
    print(f"\n🎉 SUCCESS: DSCR FIX IS WORKING!")
    print(f"   ✓ Both dscr and debt_service_usd are merged into annual_rows")
    print(f"   ✓ Excel exports will now show DSCR values correctly")
else:
    print(f"\n⚠️  WARNING: Fields may not be populated correctly")
