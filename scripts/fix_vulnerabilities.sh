#!/bin/bash
# Automated fix for Dependabot alerts
# Date: 2025-12-07

set -e

echo "🔧 Fixing Dependabot vulnerabilities..."
echo ""

# Activate virtual environment
source .venv311/bin/activate

echo "📦 Upgrading vulnerable packages..."

# Fix HIGH severity (urllib3)
echo "  ⚠️  HIGH: Upgrading urllib3 to 2.6.0..."
pip install --upgrade 'urllib3>=2.6.0'

# Fix MODERATE severity
echo "  📌 MODERATE: Upgrading Django to 5.2.9..."
pip install --upgrade 'Django>=5.2.9'

echo "  📌 MODERATE: Upgrading fonttools to 4.60.2..."
pip install --upgrade 'fonttools>=4.60.2'

echo ""
echo "✅ All packages upgraded!"
echo ""

# Update requirements files
echo "📝 Updating requirements files..."

# Backup existing files
cp requirements.txt requirements.txt.bak
cp requirements_dev.txt requirements_dev.txt.bak

# Generate new requirements
pip freeze > requirements_new.txt

# Update specific packages in requirements.txt
sed -i.tmp 's/^urllib3==.*/urllib3>=2.6.0/' requirements.txt
sed -i.tmp 's/^Django==.*/Django>=5.2.9/' requirements.txt
sed -i.tmp 's/^fonttools==.*/fonttools>=4.60.2/' requirements.txt

# Update requirements_dev.txt
sed -i.tmp 's/^Django==.*/Django>=5.2.9/' requirements_dev.txt
sed -i.tmp 's/^fonttools==.*/fonttools>=4.60.2/' requirements_dev.txt

# Clean up temp files
rm -f requirements.txt.tmp requirements_dev.txt.tmp

echo ""
echo "✅ Requirements files updated!"
echo ""
echo "📋 Summary of fixes:"
echo "  - urllib3: upgraded to >=2.6.0 (CVE-2025-66471, CVE-2025-66418)"
echo "  - Django: upgraded to >=5.2.9 (CVE-2025-64460, CVE-2025-13372)"
echo "  - fonttools: upgraded to >=4.60.2 (CVE-2025-66034)"
echo ""
echo "🧪 Next steps:"
echo "  1. Run your tests: python -m pytest"
echo "  2. Verify the pipeline: python run_full_pipeline_v14.py config=scenarios/dutchbay_lendercase_2025Q4.yaml"
echo "  3. Commit changes: git add requirements*.txt && git commit -m 'fix: upgrade vulnerable dependencies'"
echo "  4. Push: git push"
echo ""
