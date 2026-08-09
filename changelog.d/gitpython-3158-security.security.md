- **Bump GitPython 3.1.57 -> 3.1.58 to clear five new advisories** — pip-audit began flagging five
  GHSAs against GitPython 3.1.57 (GHSA-9rj7-rf2p-w77r, GHSA-4gmw-gg2m-w46p, GHSA-hh9p-6wh2-4mfc,
  GHSA-wvpp-8hx9-p66j, GHSA-jm78-9fvv-mhgr), all fixed in 3.1.58, which was failing the mandatory
  `make security` gate (and therefore every PR). GitPython is a transitive dependency of streamlit,
  explicitly pinned in `requirements.txt`; 3.1.58 satisfies streamlit's `gitpython!=3.1.19,<4,>=3.0.7`
  constraint, and `pip-audit -r requirements.txt` reports no known vulnerabilities after the bump.
  Dependency-only change; no runtime or KPI impact.
