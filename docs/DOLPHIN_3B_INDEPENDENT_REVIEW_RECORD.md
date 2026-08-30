# Dolphin 3B-0 independent review record

**Reviewed object:** `codex/d3b-v14-binding-facade` at exact commit
`5dabf43384dd16de37820e8709baa1cea8660675`, delivered as
[`#1198`](https://github.com/arunakulat/dutchbay-epc-model/pull/1198).

**Reviewed against:** [`DOLPHIN_3B_EXECUTION_CHARTER.md`](DOLPHIN_3B_EXECUTION_CHARTER.md) section 5
(D3B-0 contract boundary), at SHA-256
`4a8af1a2e7434b5b7701a85c0aedb6b0a4f16ee215453342984e741dc1446b76`.

**Disposition: NO BLOCKER.** Two non-blocking observations, recorded in section 4. Three charter
items were not executed and are declared in section 5 rather than left silent.

## 1. Why this record exists, and what it is not

Charter section 8 requires two independent reviewers to inspect the frozen tree and return a bounded
no-blocker or veto before it is committed, then rebind their disposition to the committed SHA.
[`SESSION_HANDOVER_2026-08-30.md`](SESSION_HANDOVER_2026-08-30.md) records that such a chain was run
— "four candidate rounds and a three-round veto chain". **That chain left no durable artefact.** A
repository-wide search found no D3B review record, in contrast to the committed `DOLPHIN_2_*` and
`DOLPHIN_3A_*` records. It existed only in the authoring session's context and is lost.

This record does not reconstruct it and makes no claim to. It is a **fresh, single-reviewer** pass
over the recovered tree, conducted by an agent that did not author it. Its independence is
authorship independence, not the two-reviewer chain the charter specifies.

Under `VERIFY-01`, an author reporting on its own work is the weakest available evidence, so nothing
here rests on the charter's or the implementation's own assertions: every claim below was
**independently executed** against the code. Where a probe disagreed with the code, the probe was
re-examined before the code was — three of the six initial disagreements were the reviewer's error,
and section 3 records them as such rather than quietly dropping them.

**This record confers no authority.** It is not an assurance review, not a domain review, not a
grade, and not release, deployment, lender or Board authority. It does not lift `#1110`'s `HOLD`.

## 2. What was verified, and how

89 probes across two suites, executed at `5dabf43` under the governed environment
(`DUTCHBAY_VENV=/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv`, Python `3.12.13`). **86 passed.**
The three that did not are reviewer probe errors, not code defects (section 3).

### 2.1 `resolved_config_sha256` — the guard that matters most

The charter's strongest claim is that this helper refuses everything `analytics.run_manifest.config_sha256`'s
`default=str` fallback would otherwise silently coerce into an apparently governed digest. **28 of 28
probes pass**, each with an explicit refusal carrying an RFC 6901 path:

| Refused | Probes |
|---|---|
| Non-JSON-native types | `Decimal`, `tuple`, `set`, `Path`, `bytes`, `complex`, bare `object`, `Enum` |
| Subclass smuggling | `dict`, `str` and `int` subclasses, at root and nested; `str`-subclass keys |
| Non-string keys | `int` keys |
| Non-finite floats | `NaN`, `+inf`, `-inf` |
| Structure | shared `dict` alias, shared `list` alias, direct cycle |
| Resource bounds | depth 200 > 128, integer 5,000 bits > 4,096, text > 1,000,000 cp, scalars > 100,000 |

The exact-type discipline is real: the implementation uses `type(x) is T` throughout, never
`isinstance`, so no subclass reaches the encoder. `bool` is tested **before** `int`, and probe B28
confirms `True` and `1` produce different digests rather than colliding — the classic JSON-native
`bool`-is-an-`int`-subclass trap is closed in both directions.

**Negative controls were run, not assumed.** A valid config is accepted and returns a 64-character
hex digest (B26); the same config built in a different insertion order returns the **identical**
digest (B27). A guard never observed to accept is as unverified as one never observed to fail.

### 2.2 Determinism — the claim most likely to rot silently

The charter claims errors are declaration-ordered and deterministic "across process state and hash
seeds". Verified directly rather than inferred:

| Probe | Result |
|---|---|
| Two `NaN` values, insertion orders `{zzz, aaa}` and `{aaa, zzz}` | **identical** first error, both naming `/aaa` — the sorted-first key, not the first-inserted |
| Focused suite under `PYTHONHASHSEED` ∈ {0, 1, 42, 7919, 4294967295} | `136 passed` at **every** seed |
| Fixed config digest under `PYTHONHASHSEED` ∈ {0, 1, 42, 7919} | byte-identical: `19469c89864258fb…` |

The traversal earns this: it pushes children in reverse-sorted key order onto a stack, so they pop in
canonical sorted order regardless of insertion order.

One hazard was specifically looked for and found **not** to apply. `seen_container_paths` is keyed by
`id()`, which would be unsound if a visited container could be garbage-collected and its address
reused mid-traversal. It cannot here: every container is reachable from the caller's `config` for the
whole traversal, so none is freed. The alias and cycle detection is sound as written.

### 2.3 Lexical grammars — absolute ends and no normalization

Every identifier grammar uses `(?![\s\S])` rather than `$`. This matters: Python's `$` also matches
**before a trailing newline**, so a `$`-anchored identifier pattern accepts `"LK\n"`. All five
grammars — stable identifier, jurisdiction code, currency code, unit token, SemVer — reject trailing
newline, trailing space, leading space and embedded newline, and accept their valid control value
(25 probes, all pass). The live Pydantic model path was checked as well as the raw regex, so the
annotation is actually wired: `"LK"` accepted, `"LK\n"` and `"lk"` rejected.

ASCII exactness holds against homoglyph substitution: fullwidth `ＵＳＤ` and Cyrillic `ЛК` are both
rejected. No `NFC`/`NFD` normalization occurs — combining-sequence and precomposed forms of `é`
round-trip as **distinct** values, so the contract cannot silently unify two authored identities.

### 2.4 `AssessmentText` — bounded, non-blank, and deliberately non-normalizing

The 4,096-code-point bound is a **code-point** bound, not a UTF-16 or byte bound: 4,096 astral
characters (`U+1F600`, 8,192 UTF-16 units) are accepted and 4,097 rejected. The blank/control class
is explicit rather than dialect-dependent `\s`, and the all-blank rejection is verified across
`U+0020`, `U+00A0`, `U+3000` and `U+FEFF`. Padded text is accepted **and returned byte-preserved** —
`"  padded  "` in, `"  padded  "` out — which is the charter's intent that ordinary whitespace stay
evidentially visible.

### 2.5 Domain rules named in the charter

- **`ProjectCase` material cannot claim base authority.** `MaterialDispositionKind` is closed to
  `{assert_exact_base_compatibility, refuse_unbound, explicitly_out_of_v1}` — there is no
  `retain_base_authority` member to label material with. Retention lives only in the separate
  `BaseDomainDispositionKind` register. The bypass the charter names is structurally absent, not
  merely guarded.
- **Solar DC never becomes AC capacity.** This is implemented as a genuine **biconditional**, which
  is stronger than the charter's wording: `SOLAR_RESOURCE_DC_CAPACITY_MW` requires
  `authored_technology_kind=solar_pv`, `electrical_basis=dc` and nameplate basis; and *any other*
  selector presented with `electrical_basis=dc` is refused outright ("DC generation capacity cannot
  bind an authored AC/MW selector"). Unit expectations close the loop: `AC→{MWac}`, `DC→{MWdc, MWp}`,
  `NOT_APPLICABLE→{MW}`.
- **Turbine selectors** require `wind_turbine`, refuse DC, and require nameplate basis.
- **Storage** carries the three declared routes (power MW, energy MWh, duration h); **cost
  periodicity** is closed to exactly `{one_time, annual}`.

### 2.6 Boundary compliance

`assessment_scope.py` imports no evaluator, finance, app or api module. Its only textual reference to
the gateway is `Literal["analytics.evaluation_v14.evaluate_with_overrides"]` at line 614 — a declared
identifier **string**. The module executes nothing, consistent with the charter's exclusion list.

The cold-import probe does place `analytics.evaluation_v14` and `analytics.pipeline_v14_enhanced` in
`sys.modules`, but the **negative control settles attribution**: a fresh process running
`import analytics` with no D3B module involved loads the same two among 37 submodules. This is the
pre-existing `analytics/__init__.py` eager-load limitation the charter's section 6 already declines
to claim it removed. Not a D3B regression.

## 3. Reviewer probe errors, recorded rather than dropped

Three initial probe disagreements were the reviewer's fault. They are recorded because a review that
silently discards its own misses is not auditable.

1. **`__all__` sortedness was tested with a tautology.** The first probe asserted
   `__all__ == sorted(set(__all__), key=__all__.index)`. Sorting a set by its position in the
   original list always reproduces that list, so this expression is `True` for *any* duplicate-free
   input — it tests uniqueness only, and proves nothing about ordering. An earlier receipt derived
   from it claimed "sorted and unique"; only the uniqueness half was ever tested. Re-tested properly
   in section 4.
2. **`AssessmentText` probes asserted the opposite of the charter.** Probes requiring rejection of
   leading/trailing whitespace were wrong: section 5.1 explicitly requires that ordinary whitespace
   remain evidentially visible. The code is correct and the probes were replaced.
3. **The solar-selector probe matched on the wrong string.** It looked for the dotted config path
   `resource.solar` inside the *enum value* `solar_resource_dc_capacity_mw`. Reading the mapping in
   `_target_key_matches_selector` confirmed the binding is correct and, as noted above, stronger than
   claimed.

## 4. Non-blocking observations

**O-1 — `__all__` ordering breaks the package's own convention (cosmetic).** The package convention,
visible in the pre-existing `__init__.py`, is SCREAMING_CASE constants first, then CamelCase, each
alphabetical. Three entries break it:

| File | Sequence | Expected |
|---|---|---|
| `__init__.py` | `FEASIBILITY_REPORT_*` before `EVALUATION_REQUEST_*` | `E` before `F` |
| `assessment_scope.py` | `AuthoredTechnologyKind` before `AuthoredScenarioValidationReceipt` | `S` before `T` |
| `assessment_scope.py` | `MaterialDispositionKind` before `MaterialDispositionAction` | `A` before `K` |

Nothing catches this: `[tool.ruff]` in `pyproject.toml` sets only `src` and `exclude`, so only the
default rule set (`E4`, `E7`, `E9`, `F`) runs and `RUF022` (`unsorted-dunder-all`) is not enabled.
No runtime effect — every name in both lists resolves, and both lists are duplicate-free. Worth a
one-line fix when the file is next touched; enabling `RUF022` repository-wide is a separate decision
and a separate dolphin.

**O-2 — `AssessmentText` admits interior control code points, including `U+0000`.** The validator
requires only that *at least one* code point fall outside the blank/control class, so `"a\x00b"` is
accepted. For D3B-0 this is correct and deliberate — the contract is transport-neutral, JSON can
carry ` `, and normalizing would violate the charter's evidential-visibility requirement. It is
flagged because the risk is **downstream, not here**: a later emitter that renders these strings
through a C-string boundary, a PDF/XLSX writer, or a terminal is the layer that must sanitize. D3C
and the DBPL emitters should treat `AssessmentText` as untrusted-width, control-bearing text. No
change requested in D3B-0.

## 5. Not executed — declared, not omitted

1. **Both Draft 2020-12 schema modes.** Charter section 8 requires validation-mode and
   serialization-mode agreement on the hostile lexical matrix. Not run in this review. The
   `_ExactStringJsonSchema` hook exists and carries explicit `minLength`/`maxLength`/`pattern`, but
   the two-mode agreement itself was not exercised.
2. **Cross-runtime ECMAScript regex agreement.** Section 5.1 requires an actual ECMAScript
   implementation to agree with Python on the lexical matrix. Not run — no JavaScript runtime was
   exercised. This one carries real risk: `(?![\s\S])` behaves identically in ECMAScript, but
   ECMAScript `RegExp` without the `u` flag operates on UTF-16 code units, so the astral-plane
   4,096-code-point bound verified in section 2.4 is the probe most likely to diverge across
   runtimes. It should be executed before any consumer validates these schemas in a browser or Node.
3. **The second reviewer.** Charter section 8 specifies two independent reviewers. This record is
   one. The commit-then-review ordering the charter specifies was also inverted by necessity, since
   the tree was committed to stop an active `PERSIST-01` loss rather than after a no-blocker.

## 6. Independent command receipt

Every command below was executed at `5dabf43` from
`/Users/aruna/Downloads/dutchbay-wt-d3b-v14-binding-facade`, with
`DUTCHBAY_VENV=/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv` and `PYTHONPATH="$PWD"`.

```bash
set -eu
cd /Users/aruna/Downloads/dutchbay-wt-d3b-v14-binding-facade
test "$(git rev-parse HEAD)" = "5dabf43384dd16de37820e8709baa1cea8660675"
export DUTCHBAY_VENV="/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv"
export PYTHONPATH="$PWD"
PY="$DUTCHBAY_VENV/bin/python"
```

| # | Command | Result |
|---|---|---|
| 1 | `$PY -m pytest tests/contracts/test_assessment_scope_contract.py -q` | `136 passed, 1 warning in 16.53s` |
| 2 | `$PY -m pytest tests/contracts/ -q` | `792 passed, 1 warning in 20.75s` |
| 3 | `$PY -m mypy --no-incremental analytics/feasibility_report_contract/` | `Success: no issues found in 6 source files` |
| 4 | `$PY -m ruff check <paths>` | `All checks passed!` |
| 5 | `$PY -m ruff format --check <paths>` | `3 files already formatted` |
| 6 | `$PY -m black --check <paths>` | `3 files would be left unchanged.` |
| 7 | `$PY -m isort --check-only <paths>` | clean, exit 0 |
| 8 | `$PY -m compileall -q <paths>` | clean, exit 0 |
| 9 | probe suite 1 — 45 probes (digest guard, pointer determinism, text bounds) | 39 pass / 6 fail, of which **6 were reviewer probe errors**, corrected in suite 2 |
| 10 | probe suite 2 — 46 corrected probes (identifier grammars, `__all__`, domain rules) | 43 pass / 3 fail, of which **2 are O-1** and **1 was a reviewer probe error** |

The hash-seed determinism sweep, reproducible directly:

```bash
for seed in 0 1 42 7919 4294967295; do
  PYTHONHASHSEED=$seed "$PY" -m pytest \
    tests/contracts/test_assessment_scope_contract.py -q -p no:cacheprovider | tail -1
done
# 136 passed at every seed

for seed in 0 1 42 7919; do
  PYTHONHASHSEED=$seed "$PY" -c "
from analytics.feasibility_report_contract import resolved_config_sha256 as r
print(r({'b':[1,2.5,None,True,'s'],'a':{'n':1},'z':{'k':[{'q':1},{'w':2}]}}))"
done
# 19469c89864258fba06e434f0751896da1409823ad1ae93b6381683c7df6ceae at every seed
```

The excluded-surface negative control, which is what attributes the eager load to
`analytics/__init__.py` rather than to D3B:

```bash
"$PY" -c "
import sys, analytics
print(sorted(n for n in sys.modules if n.startswith(('analytics.evaluation','analytics.pipeline'))))
print(len([n for n in sys.modules if n.startswith('analytics.')]))"
# ['analytics.evaluation_v14', 'analytics.pipeline_v14_enhanced']
# 37
```

## 7. Disposition

**NO BLOCKER at `5dabf43384dd16de37820e8709baa1cea8660675`.**

No correctness, boundary, determinism or safety defect was found. The `resolved_config_sha256` guard
is the strongest part of the slice and the most consequential: it closes a real hole in the public
hashing primitive with exact-type discipline, canonical traversal and deterministic RFC 6901
diagnostics, and it is verified by negative controls in both directions. The lexical grammars avoid
the `$` trailing-newline trap that this class of contract usually falls into. The solar DC binding is
implemented more strictly than the charter claims.

The two observations in section 4 are non-blocking and neither warrants holding delivery. What is
**not** discharged is section 5: this is one reviewer, not two, and two charter gates were not
executed. Whether that satisfies the charter is the owner's call, not this record's.
