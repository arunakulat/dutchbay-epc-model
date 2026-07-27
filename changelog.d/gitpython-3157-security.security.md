- **GitPython `3.1.50` → `3.1.57` (security, #985)** — clears two High-severity advisories
  affecting the pinned `3.1.50`: GHSA-2f96-g7mh-g2hx (CVSS 8.8, CVE-2026-42215 — OS command
  injection via git long-option prefix abbreviation, RCE on clone/fetch/pull/push; fixed
  3.1.51) and GHSA-94p4-4cq8-9g67 (CVSS 7.5 — environment-variable exfiltration via URL
  expansion in `create_remote()`/`Remote.add()`; fixed 3.1.55). GitPython is transitive via
  `streamlit` (which requires `gitpython!=3.1.19,<4,>=3.0.7` — 3.1.57 satisfies); surgical
  single-line lock bump. Also restores the `make security` (pip-audit) CI gate to green.
