#!/usr/bin/env bash
set -Eeuo pipefail

# Ensure macOS Keychain helper is enabled
git config --global credential.helper osxkeychain || true

read -rp "GitHub username: " GH_USER
read -srp "GitHub Personal Access Token (PAT): " GH_PAT
echo

# Store credentials via the configured helper (Keychain on macOS)
git credential approve <<EOF
protocol=https
host=github.com
username=${GH_USER}
password=${GH_PAT}
EOF

echo "✓ Credentials saved to macOS Keychain for ${GH_USER}@github.com"
echo "Next: bash scripts/push_and_tag.sh  # or with args: bash scripts/push_and_tag.sh main v13-irr-restore"

