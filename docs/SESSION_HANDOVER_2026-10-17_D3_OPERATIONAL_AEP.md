# Session handover — 17 October 2026: D3 operational AEP delivery

## Status and authority

This is a scoped successor to `SESSION_HANDOVER_2026-10-15_D2_OPERATIONAL_NORMALIZATION.md`
for the user-directed D3 delivery on
[issue #1333](https://github.com/arunakulat/dutchbay-epc-model/issues/1333). It carries
forward that record's declared `SESSION_HANDOVER_2026-10-12_THREAD_TODO.md` work list,
the sibling 11 October capability handover, and the 5 October v15.6.1 startup record;
it does not replace them. Run the handover resolver and read its newest result first.

This file grants no writer, merge, finance, evidence, professional, utility, release,
lender, Board, publication, deployment, issue-closure, or `HOLD` authority. D3 is a
non-canonical engineering result and is structurally ineligible for finance, scenario,
lender, or Board use. Issue #1110 remains `OPEN`, and its reliance `HOLD` is unchanged.

Protected `main` and `origin/main` were clean and synchronized at
`1638ff4da45411629784b8d1a1e28fdf93ce1e4e`, the squash merge of
[PR #1366](https://github.com/arunakulat/dutchbay-epc-model/pull/1366), before this
handover branch was created. The accepted D3 head was
`4f0aa0c8bbc7419623b755232767ca495e4a6537`; its tree and the merged tree are identical
at `1872b8ba845f39f9b6aa32e52d8a41e1db5d4c75`.

## Delivered result and durable receipts

D3 adds deterministic exact-rational operational energy reconciliation over immutable,
replayed D1/D2 evidence. It reports net meter, turbine-terminal, availability,
curtailment, electrical, known-gross, optional resource/wake, and conditionally derivable
residual quantities without treating missing evidence as zero. Both D1 purpose envelopes
must authorize the complete common population. Malformed nested provenance closes as the
public `PROVENANCE_MISMATCH` state. LTA, P-values, annual/LTA uncertainty, and any
canonical-finance authority remain unavailable.

The final exact-object freeze is
[comment 6229885967](https://github.com/arunakulat/dutchbay-epc-model/issues/1333#issuecomment-6229885967).
Fresh independent review accepted it:

- domain ACCEPT:
  [comment 6229896874](https://github.com/arunakulat/dutchbay-epc-model/issues/1333#issuecomment-6229896874),
  canonical receipt SHA-256
  `4307fc8cdc45a9824767587fa3847ce1d70f4a0437cbef3d6a68698798434512`;
- assurance ACCEPT:
  [comment 6229909310](https://github.com/arunakulat/dutchbay-epc-model/issues/1333#issuecomment-6229909310),
  canonical receipt SHA-256
  `15e25bc7c0cec9ad94bf8b4b97b699306e760fcf1a0a688e8a633a37cee5fe03`.

The accepted object used canonical seven-path Git-blob manifest SHA-256
`7af27f8c3a1b83f3e076ef03e59165fb2f6704698d2ca264494d9d07deb5c49d`
and binary-diff SHA-256
`dbe4c10c7c2a8bdf9cf8f606565ccdf8c3033ed9736f27b146d2211f7414170c`.
`D3-DOM-001` and `D3-ASSURANCE-001/002/003` are closed on that exact object.

Hosted exact-head CI passed all six ordinary shards, Grid Study, combined 95% Coverage
Gate, Test Summary, code quality, security, Fastlane, smoke, FX, CodeQL, audit-image
build, and verification receipts. The governing test-suite run is
[39004493590](https://github.com/arunakulat/dutchbay-epc-model/actions/runs/39004493590).
The prior exact head had exposed the honest 94.94% combined-coverage shortfall; the final
test-only correction exercised 32 additional D3 statements without changing production
source. The final targeted result was 62 tests passing and 93.47% coverage for
`analytics/operational/aep.py`, up from 88.38%.

## Local environment remediation

The shared cloud environment initially lacked installed DutchBay distribution metadata,
and its container PID 1 did not promptly reap orphaned watchdog descendants. The first
metadata repair used an editable candidate install and was correctly rejected as
`D3-ASSURANCE-003`; do not repeat it.

The accepted repair removed the editable finder/path mapping and generated candidate
`egg-info`, then installed equivalent package metadata non-editably from a wheel built
outside all worktrees from a clean `git archive`. `check_venv.sh --no-bootstrap` reported
`editable_project_install: false`, no foreign checkout paths, and active-worktree imports.
The governed two-worktree verifier passed for the candidate and protected main through the
same persistent Python 3.12.14 environment; each imported its own checkout and passed the
75-rule bootstrap plus focused environment tests. A workspace-local child-subreaper at
`/workspace/.local/bin/codex-subreaper` supplies the missing container reaping behavior.
The exact metadata case and all five affected watchdog cases passed together.

These are machine-local environment repairs, not merged repository files. The temporary
proof branch/worktree and isolated source/archive/wheel-build files were removed. Future
environment maintenance must preserve the non-editable, active-worktree-first ENV-01
invariant and rerun the two-worktree verifier after shared-environment changes.

## Live queue and next-session route

At authoring, the only open pull requests were Dependabot PRs #1359 through #1363. They
were not reviewed or changed by this task. Issues #1333, #1353, and #1110 remained open.
The public v15.6.1 release remained non-draft and non-prerelease. Refresh all live state
before acting.

Start from the Codex project named `DutchBay_EPC_Model`; read `AGENTS.md`, the canonical
GWTF rules, and the resolver-selected handover chain. Verify the persistent environment,
fetch `origin/main` and tags, enumerate open PRs, and consult #1353 plus the relevant
focused issue before editing. New work needs its own intake record, writer lease,
exact-object review, CI, final resync, merge, persistence, and cleanup lifecycle.

The owner's Mac-only runtime and confidential project evidence were not available in this
cloud checkout. The D3 implementation and its receipts are complete, but they do not
establish achieved capability grade, authenticated evidence, professional reliance,
utility acceptance, release authority, lender/Board use, issue closure, or permission to
lift #1110's `HOLD`.
