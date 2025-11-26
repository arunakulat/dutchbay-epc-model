# 1. Make changes, commit to git
git add .
git commit -m "Update WACC calculation"
git push

# 2. Generate snapshot for Perplexity
python scripts/make_clean_zip.py DutchBay_EPC_$(date +%Y%m%d_%H%M)

# 3. Drag .md file to Perplexity Mac desktop app
# Now Perplexity has your complete, current codebase!
