# Report and API test architecture

## Outcome

GWTF TEST-04 separates deterministic transport and renderer contracts from one
explicit complete-production qualification matrix. The ordinary suite retains a
real authentication/token/HTTP/finance-to-HTML path, but replaces supplemental
sensitivity only at the typed `compute_report_sensitivity` boundary. Response-only
tests inject a known `ReportContext` and the missing-PDF test proves backend
preflight happens before report computation.

The controlling CESSPIT source is `config/report_test_policy.yaml`. Its strict v2
schema declares both report sensitivity profiles, the 5.0-second ordinary duration
review policy, written exception register, and qualification observation. Production
defaults are pinned rather than reduced.

## Assurance levels

| Level | Profile | What it proves |
| --- | --- | --- |
| API transport | Ordinary | HTML/PDF response assembly and deterministic dependency/error mapping against a known context with a non-empty run manifest |
| Renderer contracts | Ordinary | Required sections, values, provenance, and empty states render from deterministic contexts |
| Representative live E2E | Ordinary | Real `/v1/token` login, bearer validation, timeout shell, live finance, report builder, HTML renderer, and HTTP response work together; only the typed sensitivity bundle is bounded/stubbed |
| Complete report matrix | Qualification | One live production finance result plus tornado, Morris, and PAWN is composed once, its method/count metadata ties, and the same complete context renders to both HTML and real PDF |

The qualification matrix runs with:

```bash
make test-report-qualification
```

GitHub runs the same `report_qualification` marker on Python 3.12 for
scheduled/manual Test Suite events and tagged releases. Ordinary PR tests use
`DUTCHBAY_TEST_MODE=full`, which collects but governs qualification tests as skips.

## Profiles and structural enforcement

The ordinary `ordinary_bounded` profile requests 15 tornado evaluations, four Morris
trajectories and 128 PAWN evaluations with ten slices. For the representative six
global-SA drivers this records 171 requested and 171 effective evaluations,
both checked against TEST-03's canonical 200-evaluation hard cap. The
`production_full` profile retains 16 Morris trajectories, 256 PAWN evaluations and
ten slices, producing the pinned 15 + 112 + 256 = 383 evaluations for the lender
scenario.

Requested counts remain present when a best-effort sensitivity adapter degrades.
Because an adapter can execute work and then return no renderable block, its effective
count is recorded as unknown rather than falsely reported as zero; the aggregate
effective count is likewise unknown until every method supplies a count. The typed
bundle requires exactly one metadata row for each of tornado, Morris, and PAWN.

The repository-wide AST policy rejects unmarked `_build_report_context` and live
full/production `compute_report_sensitivity` composition. It follows direct imports,
capture-time aliases, and module-local helper parameters. Patch suppression is granted
only to the provenance-tracked pytest `monkeypatch` fixture and its aliases; an arbitrary
`.setattr` method or a production callable captured before a patch cannot suppress a
violation. Calls with all three typed sensitivity computers injected are not treated as
live production work. Synthetic scanner fixtures qualify the helper/alias, explicit
marker, bounded-profile, trusted-patch, pre-patch-alias, and fake-patcher cases.

## Duration-history policy

`.test_durations` is scheduler input, not execution evidence. Every governed report/API
test must have a duration-history entry, and every ordinary entry above 5.0 seconds
requires an exact node-id and written reason in the strict policy; the current exception
register is empty. A qualification skip weight is deliberately tiny and is kept separate
from the observed qualification record.
The latter stores Python version, profile, command, outcome, UTC measurement cutoff,
and observed call duration. Machine-dependent qualification duration is an
observation, not a pass/fail correctness threshold.

The pre-change five-call checkpoint on Python 3.12.13 was 157.92 seconds. The v2
focused ordinary slice completed 10 tests in 3.23 seconds (one existing Starlette
deprecation warning). The final policy/AST plus surface-contract slice passed 31 tests
in 2.87 seconds. The canonical `make test-report-qualification` target passed one item
in a 33.49-second pytest session on Python 3.12.13; that target-level observation is
the value stored in the policy. These are local observations, not cross-machine
performance guarantees. The final `PYTHONDONTWRITEBYTECODE=1 make test` ordinary
gate passed 5,489 tests with 17 governed or optional-dependency skips and 95.41%
coverage in 643.93 seconds.

## Sequencing and non-interference controls

The #1072 frozen identity used for integration is commit
`56be1e1a538865af9323bddb030f516d48b8e972`. The SHA-256 of its binary commit diff
(`git diff --binary HEAD^ HEAD`) is
`4d7fb3478403c719c44e991e802256b2e78896ad85cfbb61af80c83ea2530644`.
All 16 frozen commit paths were rechecked byte-for-byte against the isolated #1101
assembly; all 16 matched. The intersection between those 16 paths and the
TEST-04-owned change inventory is zero.

The frozen #1072 content was delivered without mutation in commit `92a2965`, and the
two source-worktree hardening tests were preserved separately in commit `88b65f4`.
PR #1104 merged both commits to `origin/main` at
`bb1e38fa755d02edec6a86e7966bb8c135ee4b80`. PR #1103 is reconstructed on that
merged head, which supplies real #1072 Git ancestry as well as the merged #1100 test
budget harness; the earlier content-equivalence-only limitation therefore no longer
applies.

Validation uses only isolated worktree-local `.venv` environments running Python
3.12.13. No raw runtime logs are retained; only the minimal structured validation
facts above and in the strict policy are durable.

## Evidence boundary

A green ordinary suite proves regression and coverage behavior only. A green report
qualification gate proves that the selected complete software paths ran; it does not
by itself establish model adequacy, financial correctness, bankability, lender
acceptance, or release approval. Those claims require their own governed inputs,
results, hashes, limitations, and sign-off.
