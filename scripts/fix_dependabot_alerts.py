#!/usr/bin/env python3
"""
Script to fetch Dependabot alerts and generate dependency update commands.
Requires: pip install requests
"""

import json
import subprocess
import sys
from typing import Any, Dict, List


def get_dependabot_alerts_manual():
    """
    Since we can't make API calls without token, provide manual instructions.
    """
    print("=" * 70)
    print("DEPENDABOT ALERT CHECKER")
    print("=" * 70)
    print("\nTo fetch Dependabot alerts, run this command in your terminal:\n")
    print("curl -L \\")
    print('  -H "Accept: application/vnd.github+json" \\')
    print('  -H "Authorization: Bearer YOUR_GITHUB_TOKEN" \\')
    print('  -H "X-GitHub-Api-Version: 2022-11-28" \\')
    print(
        "  https://api.github.com/repos/arunakulat/dutchbay-epc-model/dependabot/alerts?state=open"
    )
    print("\n" + "=" * 70)
    print("\nPaste the JSON output here (or press Ctrl+D when done):\n")

    # Read JSON from stdin
    try:
        json_data = sys.stdin.read()
        alerts = json.loads(json_data)
        return alerts
    except json.JSONDecodeError as e:
        print(f"\nError parsing JSON: {e}")
        return []
    except KeyboardInterrupt:
        print("\n\nCancelled by user.")
        return []


def analyze_alerts(alerts: List[Dict[str, Any]]):
    """Analyze alerts and generate fix recommendations"""

    if not alerts:
        print("\n✅ No open Dependabot alerts found!")
        return

    print(f"\n📋 Found {len(alerts)} open alert(s)\n")
    print("=" * 70)

    fixes = []

    for alert in alerts:
        num = alert.get("number", "N/A")
        # state = alert.get("state", "unknown")  # unused; safe to drop for now

        dep = alert.get("dependency", {})
        package_info = dep.get("package", {})
        package_name = package_info.get("name", "unknown")
        ecosystem = package_info.get("ecosystem", "unknown")
        manifest_path = dep.get("manifest_path", "unknown")

        advisory = alert.get("security_advisory", {})
        severity = advisory.get("severity", "unknown")
        summary = advisory.get("summary", "No summary")
        cve_id = advisory.get("cve_id", "N/A")
        ghsa_id = advisory.get("ghsa_id", "N/A")

        vuln = alert.get("security_vulnerability", {})
        vuln_range = vuln.get("vulnerable_version_range", "unknown")
        patched = vuln.get("first_patched_version", {})
        patched_version = patched.get("identifier", "N/A") if patched else "N/A"

        print(f"\nAlert #{num}: {package_name}")
        print(f"  Severity: {severity.upper()}")
        print(f"  CVE: {cve_id} | GHSA: {ghsa_id}")
        print(f"  Summary: {summary[:80]}...")
        print(f"  Ecosystem: {ecosystem}")
        print(f"  Manifest: {manifest_path}")
        print(f"  Vulnerable: {vuln_range}")
        print(f"  Fix Version: {patched_version}")
        print("-" * 70)

        if ecosystem == "pip" and patched_version != "N/A":
            fixes.append(
                {
                    "package": package_name,
                    "fix_version": patched_version,
                    "manifest": manifest_path,
                    "severity": severity,
                }
            )

    if fixes:
        print("\n🔧 RECOMMENDED FIXES:\n")
        print("=" * 70)

        # Group by manifest file
        by_manifest = {}
        for fix in fixes:
            manifest = fix["manifest"]
            if manifest not in by_manifest:
                by_manifest[manifest] = []
            by_manifest[manifest].append(fix)

        for manifest, packages in by_manifest.items():
            print(f"\nFile: {manifest}")
            print("Update these packages:\n")
            for pkg in packages:
                print(f"  {pkg['package']}>={pkg['fix_version']}")
            print()

        # Generate pip upgrade commands
        print("\n📦 PIP UPGRADE COMMANDS:\n")
        for fix in fixes:
            print(f"pip install --upgrade '{fix['package']}>={fix['fix_version']}'")


def main():
    print("\n🔍 Checking Dependabot Alerts for dutchbay-epc-model\n")

    # Option 1: Try to get alerts from GitHub CLI if installed
    try:
        result = subprocess.run(
            [
                "gh",
                "api",
                "/repos/arunakulat/dutchbay-epc-model/dependabot/alerts",
                "--jq",
                ".",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            alerts = json.loads(result.stdout)
            analyze_alerts(alerts)
            return
    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
        pass

    # Option 2: Manual entry
    print("GitHub CLI (gh) not available or not authenticated.")
    print("Falling back to manual mode...\n")
    alerts = get_dependabot_alerts_manual()
    analyze_alerts(alerts)


if __name__ == "__main__":
    main()
