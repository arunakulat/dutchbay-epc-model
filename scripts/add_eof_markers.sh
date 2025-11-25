#!/bin/bash
# Add # EOF markers to all scripts that don't have them
#
# Go with the Flow Compliance:
# - Adds # EOF to end of all .py and .sh files in scripts/
# - Only adds if not already present
# - Preserves file permissions

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🔖 Adding EOF markers to scripts..."

# Function to add EOF marker if missing
add_eof_if_missing() {
    local file="$1"
    
    # Check if file already ends with # EOF
    if tail -1 "$file" | grep -q "^# EOF$"; then
        echo "   ✓ Already has EOF: $(basename "$file")"
        return 0
    fi
    
    # Add EOF marker
    echo "" >> "$file"
    echo "# EOF" >> "$file"
    echo "   ✅ Added EOF: $(basename "$file")"
}

# Process all Python scripts
for script in "$SCRIPT_DIR"/*.py; do
    [ -f "$script" ] && add_eof_if_missing "$script"
done

# Process all Shell scripts
for script in "$SCRIPT_DIR"/*.sh; do
    [ -f "$script" ] && add_eof_if_missing "$script"
done

# Process research subdirectory
if [ -d "$SCRIPT_DIR/research" ]; then
    for script in "$SCRIPT_DIR/research"/*.py; do
        [ -f "$script" ] && add_eof_if_missing "$script"
    done
fi

echo ""
echo "✅ EOF markers added to all scripts"

# EOF
