# Session handover — 22 November 2026: new gates, the 15.28 to 15.33 version line, and where open work lives

## Status and authority

Written under `PERSIST-01` by a Claude cloud writer session (the project's drafts writer) for work
item #1903, governance drift item G6 of 21 November. It is the **successor** to
`docs/SESSION_HANDOVER_2026-11-13_BLUE_WHALE_CURRENCY_GUARDS.md`, its **predecessor**, which was the
newest record `scripts/list_session_handover_records.py` resolved until this one. Between the two
records `main` took 144 first-parent landings, from `62db8927` (#1628) to `5c23c8d9` (#1894), and
`VERSION` moved from 15.27.0 to 15.33.0. Nothing in this record is new policy: each gate it names is
already on `main` and is cited by the pull request that put it there.

**Startup record and carried-forward state.** `AGENTS.md` "Session continuity" tells the next
session to take these from this record, not from a filename in the gateway. This record carries
forward, and does **not** replace:

- the **v15.6.1 startup record**, `docs/SESSION_HANDOVER_2026-10-05_RELEASE_15_6_1.md`. It is still
  the startup record because no release has been cut since: the newest release tag and the newest
  released `CHANGELOG.md` section are both v15.6.1. `VERSION` has moved without a release (see "The
  version line" below), so the startup record's figures are history; read live KPIs from `main`;
- the declared work list `docs/SESSION_HANDOVER_2026-10-12_THREAD_TODO.md` and the sibling capability
  handover `docs/SESSION_HANDOVER_2026-10-11_CAPABILITY_ROADMAP.md`, as the 22 October and 13 November
  records declared them;
- from its predecessor: the residual queue #1629 (Blue Whale native-currency and financing gaps,
  still open), the refusal guards of #1627, and every source, professional, lender, Board and release
  boundary it listed. Its own queue (#1628 and three Dependabot pull requests) has landed or closed,
  so that section is history.

Run the resolver and read its newest result first. It refuses shallow history, so fetch
`--unshallow --tags` before relying on it (`CLAUDE.md` "Full history and tags").

This file grants no writer, merge, finance, evidence, professional, utility, release, lender, Board,
publication, deployment, issue-closure or `HOLD` authority.

**No `HOLD` was lifted.** #1110 remains open with its Board and lender circulation hold. The F-5 bar
stands: no quarterly CFADS or intra-year DSCR figure supports a covenant, lender or IC
representation. #1894 landed the first of four parts of the monthly CFADS cascade (#1893), the path
that could one day lift F-5; it is opt-in, nothing reads it yet, and its own changelog fragment
restates that F-5 stays in force. The v15.6.1 release boundary is unchanged.

## Gates now enforced on `main`

Each of these is checked by CI or by a lint test, so a session that skips it fails a required check
rather than a reviewer's memory. Read the cited pull request before relying on the summary here.

| Gate | What it requires | Landed by |
|---|---|---|
| Handover resolver in CI | Every `SESSION_HANDOVER_*` record declares a startup record and its carried-forward state; the resolver runs on live history | #1674 (#1409) |
| VERIFY-01 receipts | The receipts table in the pull request body; a check not run is written `not run - <reason>`, never `n/a` | `scripts/ci/check_pr_receipts.py`; split from intake in #1804 |
| INTAKE-01 intake | One `Work item:` line naming a scoped issue, a `Base SHA:`, a tracker #1353 comment recorded before edits, and an open-PR sweep that names every pull request open when this one was opened (from its latest reopen, if reopened) | #1805, #1876 (#1875), #1880 (#1877) |
| Independent review pair | An R2 or R3 body declares `Risk class:`; the required check then wants a domain and an assurance record, each bound to the exact current head and not from that head's writer. R1 takes one lane under `REVIEW-01`, which the check does not enforce | #1839 (#1486) |
| Module role ledger | Every new module has a `config/module_roles.yaml` entry, and `docs/MODULE_COVERAGE_MAP.md` agrees with an import scan (regenerate it with `scripts/module_coverage_map.py`) | #1813, #1772 (#1751) |
| No code default for a project input | Gearing, target DSCR, downside factor, tenor, build time, capacity rate, balloon limit and DSRA months come from the scenario YAML or the run refuses | #1733, #1798, #1860 (#1429) |
| No site literal in code | Every site input comes from configuration; scripts and tools are held to the same rule | #1761 (#1759), #1777 (#1775) |
| DOC-02 option B | A pull request that moves a KPI bumps `VERSION`; `CHANGELOG.md` changes only at a release cut; every change carries a `changelog.d/` fragment | #1835 (#1826), #1873 (#1872) |
| Sizing summary inputs | The solar + BESS sizing summary names its inputs by digest, not by `VERSION`, so a version bump alone no longer forces its regeneration | #1865 (#1864), #1868 (#1867) |
| Monte Carlo toy fallback | Off by default everywhere; a smoke configuration opts in | #1849 (#962) |
| Test shards | Eight shards; lint tests pin `TOTAL_SHARDS` | #1879 (#1878) |

The required "Code Quality Checks" job runs `ruff check .`, `black --check .`,
`isort --check-only .` and two `mypy` runs repo-wide (`.github/workflows/test-suite.yml`).
`ruff check` alone does not catch import order.

## The version line

`VERSION` moved six times between the two records. Each move is a KPI-moving change under DOC-02
option B, with its own fragment; none is a release.

| Version | Change | Pull request |
|---|---|---|
| 15.28.0 | Per-technology capex escalated to the construction draws, and disclosed in batch results | #1800 (#1578) |
| 15.29.0 | One cash basis for the post-maturity sweep and the fee deferral | #1840 (#1736) |
| 15.30.0 | The held battery carried into the Blue Whale headline KPIs | #1851 (#1823) |
| 15.31.0 | Lock-up tests the refinanced balloon tranche | #1863 (#1779) |
| 15.32.0 | Revenue SSCL dropped from the 15 CEB-supply scenarios | #1886 (#1874) |
| 15.33.0 | The lender case sized to the annual covenant DSCR | #1892 (#1845) |

A version bump moves several pins together; follow `RELEASING.md` and the lint tests that pin
`VERSION`. One consequence of 15.33.0 that later work should know: the lender case's equity cash
flows now change sign once, so its equity IRR ranks it and the #1688 ranking caveat (#1821) no longer
shows on it. Pessimistic and stress cases still carry the caveat.

## What changed in the model's scope

- **Universal model.** Every analysis first built for Blue Whale now runs for any scenario that
  declares its block, with location, size and technology read from the scenario YAML: wind battery
  options (#1797), PV + BESS sizing (#1801), FX and tenor screening (#1796), equipment cost parity
  (#1758), the solar assessment report (#1785), standalone battery economics (#1776) and the EPC
  construction margin (#1782). Scenario blocks for the site analyses landed in #1757.
- **Blue Whale is wind plus BESS** (owner decision of 17 November, recorded in
  `conf/site_analysis_sections.yaml`). The solar + BESS work remains as universal code and as a
  scenario, but it is not the Blue Whale configuration.
- **Lender report.** It is now produced from the command line as HTML and a `DBPL-01` PDF (#1844),
  with an F-5 line (#1852), wind-resource AEP sensitivity (#1854), capital-structure screening
  (#1859), lender sensitivities (#1866), the balloon treatment of each compared case (#1855) and one
  section per site analysis (#1861). Slices iii and iv of #1825 are still to come.
- **Jurisdiction packs.** A pack schema, the Sri Lanka reference pack and a resolver by subject and
  valuation date (#1847, #1858), and the Sri Lanka tax and levy code refuses another jurisdiction
  (#1883).

## Where open work lives

Read these live; any list copied here goes stale within hours.

- Tracker #1353: the capability and assurance roadmap and every `INTAKE-01` record. Merge-queue
  and landing records moved to #1713, and agent-to-agent messages to #1714.
- #1110 (programme audit, Board and lender gate) and #1629 (the predecessor's residual queue).
- #1893: parts 2 to 4 of the monthly CFADS cascade. Parts 2 and 3 are R3 and move `VERSION`.
- #1825 slices iii and iv, #1829 (the IRR ranking caveat on the surfaces #1821 does not cover) and
  #1900 (lock-up wording on scenarios that declare no lock-up covenant).
- The solar + BESS sizing summary is pinned by digest to its inputs. A refresh of its code digests
  and one wording change wait for the next pull request that regenerates it anyway; the #1353
  comment that records this names the files.

At the time of writing, the open pull requests were #1821, #1901 and #1902, and the next set of
drafts had been approved for the coordinator to assign to writers.

## Environment and continuation

Most work in this period ran in Claude cloud containers, under the `CLAUDE.md` fallback: the
checkout-local `.venv` from `.claude/hooks/session-start.sh`, Python 3.12. The owner's Mac runtime
was not used and was not modified. In a container, up to five
`tests/lint/test_cloud_audit_review_sandbox.py` watchdog cases and
`tests/integration/test_ingestion_tooling.py::test_governed_ingestion_versions_are_installed` can
fail on an unmodified `main`; declare the count observed as pre-existing and local.

Coordination ran through a coordinator, a merge-queue manager and per-area writers, with fresh
independent review lanes per pull request. Review records live on each pull request between `8<`
markers; this record does not restate any lane's disposition. A new session should re-read the live
heads, checks and records of anything it picks up: no review carries across a head change.

When this record lands, apply `CLEANUP-01` for #1903 and post the landing on #1713.
