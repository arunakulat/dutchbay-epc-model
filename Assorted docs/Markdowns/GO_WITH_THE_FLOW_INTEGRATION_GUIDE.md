# GO-WITH-THE-FLOW RULESET: COMPLETE PACKAGE
## Master Reference & Integration Guide
**Status:** ✅ Complete | **Date:** 2025-11-27 | **Version:** 2.0 (Canonical)

---

## THE COMPLETE RULESET (4-Document System)

### Document 1: GO_WITH_THE_FLOW_GOLD_STANDARD.md (5,000+ words)
**The Foundation – Team Standards & Practices**

**Contents:**
- Definition of Done (mandatory checklist for all code)
- Banned patterns (hard rules: F541, B008, F821, >88 chars)
- Content rules (docstrings, logging, function signatures)
- Process enforcement (pre-commit hooks, fast-lane CI)
- Blessed templates (CLI, analytics, test modules)
- MyPy hardening roadmap (gold standards)
- Deferred violations registry (explicit tracking)
- Authority & sources (Hypermodern Python, PEP 8, Instagram/Facebook, academic research)

**When to use:** Reference for team members, code reviews, onboarding

---

### Document 2: SPRINT_4_ROADMAP.md (2,500+ words)
**The Execution Plan – Day-by-Day Implementation**

**Contents:**
- Day 1: Pre-commit infrastructure (3h)
- Day 2: Fast-lane CI validation (3.5h)
- Day 3: Blessed templates (3h)
- Day 4: MyPy hardening (4h)
- Day 5: Team alignment (3h)
- Success criteria & metrics
- Expectations for Sprint 5+

**When to use:** Project planning, sprint execution, tracking progress

---

### Document 3: GO_WITH_THE_FLOW_AI_COLLABORATION_CONTRACT.md (NEW – THIS DOC)
**The Automation Treaty – What "Go with the Flow" Means**

**Contents:**
- The magic phrase (what triggers automatic compliance)
- Formatting & lint contract (automatic)
- Types & v14 contracts (automatic)
- Structural rules (automatic)
- AI collaboration contract (error handling, multi-file fixes, templates)
- Implicit flow (what happens when you say "Go with the Flow")
- Updates to Gold Standard & Contributing.md
- Enforcement checklist
- Examples (CLI, analytics, error scenarios)

**When to use:** Whenever requesting code generation with "Go with the Flow"

---

### Document 4: This Document
**The Integration Guide – How It All Works Together**

**Contents:**
- Complete ruleset overview
- Integration timeline
- How to reference in code requests
- Quick-reference checklists
- FAQ & troubleshooting
- Next steps

**When to use:** Quick reference, explaining system to new team members

---

## INTEGRATION TIMELINE

### NOW (2025-11-27)
✅ All 4 documents created and merged
✅ AI collaboration contract locked in
✅ "Go with the Flow" phrase now canonical

### IMMEDIATE (This Week)
- [ ] Commit all 4 documents to repo
- [ ] Update GO_WITH_THE_FLOW_GOLD_STANDARD.md Section 1.5 (AI contract)
- [ ] Update CONTRIBUTING.md (reference section)
- [ ] Announce to team: "Go with the Flow is now the standard"

### SPRINT 4 (Next Week)
- [ ] Execute SPRINT_4_ROADMAP.md day-by-day
- [ ] Install pre-commit hooks
- [ ] Set up fast-lane CI
- [ ] Create blessed templates
- [ ] MyPy hardening (2 gold-standard modules)
- [ ] Team alignment meeting

### SPRINT 5+ (Ongoing)
- [ ] All new code starts from blessed templates
- [ ] Pre-commit hooks enforce (zero violations reach main)
- [ ] AI generates code with implicit "Go with the Flow" standards
- [ ] Velocity increases by 2-3 hours/week per developer

---

## HOW TO USE "GO WITH THE FLOW"

### When Requesting Code

**Invoke the contract with the magic phrase:**

```
"Go with the Flow: [describe what you need]"
```

**Examples:**

```
Go with the Flow: Create a Typer CLI that validates scenario JSON and exports metrics.

Go with the Flow: Implement a tornado sensitivity analysis that returns TornadoResult.

Go with the Flow: Add unit tests for the cashflow module using pytest parametrize.
```

### What Happens Automatically

When AI sees "Go with the Flow", this applies instantly:

| Category | Automatic Behavior |
|----------|-------------------|
| **Line Length** | ≤ 88 chars (all contexts) |
| **Formatting** | black/isort/flake8 first-gen clean |
| **Type Hints** | Full annotations (args, returns, dataclass fields) |
| **MyPy** | Strict compliance (no `Any`, no implicit Optional) |
| **v14 Contracts** | Use TornadoResult, ScenarioKPIs, etc. (not custom dicts) |
| **Banned Patterns** | Zero F541, B008, F821, unused imports |
| **Templates** | Start from template_cli.py / template_v14.py / test_template |
| **Structural Safety** | No side effects, module-level constants, proper entry points |
| **Error Handling** | If lint fails, AI treats as generation bug, provides patch |

**Result:** Code is **merge-ready on first generation**. No post-hoc cleanup.

---

## QUICK REFERENCE CHECKLIST

### For Code Generators (AI or Human)

- [ ] Invoked with "Go with the Flow"? → Apply all standards
- [ ] All lines ≤ 88 chars? (code, docstrings, logging)
- [ ] No F541 (f-strings with no placeholders)?
- [ ] No B008 (function calls in defaults)?
- [ ] No F821 (undefined names without # noqa)?
- [ ] No unused imports/variables?
- [ ] No single-letter vars (l, O, I)?
- [ ] Full type hints (args, returns)?
- [ ] Using v14 contracts (TornadoResult, etc.)?
- [ ] No top-level side effects (except `if __name__ == "__main__"`)?
- [ ] CLI uses module-level constants for defaults?
- [ ] Started from blessed template?
- [ ] Tested with: black, isort, flake8, mypy?
- [ ] Ready for `git add` without post-processing?

---

### For Code Reviewers

When reviewing code generated with "Go with the Flow":

- ✅ **Should be black/isort/flake8/mypy clean** – If not, ask why (generation bug)
- ✅ **Should follow templates** – Check against blessed structure
- ✅ **Should use v14 contracts** – No ad-hoc dicts
- ✅ **Should have full types** – No `Any` shortcuts
- ✅ **Should be ready to merge** – No "we'll clean this up later"

**If violations exist:** Ask: "Why wasn't 'Go with the Flow' applied?"

---

### For Team Members (Developers, Managers, PMs)

| Role | Action |
|------|--------|
| **Developer** | Use "Go with the Flow" in all code requests |
| **Code Reviewer** | Expect first-gen compliance; block violations |
| **Team Lead** | Ensure pre-commit hooks installed; track metrics |
| **Manager** | Monitor: lint violations per sprint (should be 0) |
| **AI/Assistant** | Apply all sections 1–6 implicitly |

---

## FAQ & TROUBLESHOOTING

### Q: Do I need to paste the full ruleset every time I ask for code?
**A:** No. Just use the phrase "Go with the Flow". The full standards are implicit.

**Example:**
```
DON'T: "Create a CLI that... and make sure it follows Section 2.1 of the Gold Standard..."
DO:    "Go with the Flow: Create a CLI that validates scenarios."
```

---

### Q: What if the generated code fails lint/mypy?
**A:** Paste the exact error. AI treats it as a generation bug, not cleanup work.

```
You: "Got this mypy error:
     error: Name "TornadoResult" is not defined"

AI: [acknowledges as generation bug, produces corrected code]
```

---

### Q: Can I skip "Go with the Flow" compliance?
**A:** No. Pre-commit hooks will block any code that violates it. The contract is non-negotiable.

---

### Q: What if I'm generating multiple files?
**A:** Same rules apply to all. Use Python scripts (not sed/awk) for bulk fixes, following the gather-violations.py pattern.

---

### Q: How do I know if code is truly Go-with-the-Flow compliant?
**A:** Run the pre-commit checks:
```bash
python scripts/go_with_the_flow_ci.py --fast --files <your_files>
```

If all pass → compliant. If any fail → not ready.

---

### Q: What about legacy code that doesn't follow these standards?
**A:** Gradually migrated during refactors. Pre-commit hooks only enforce on staged code (new or modified).

---

## EXAMPLE: FULL WORKFLOW

### Step 1: You Request Code

```
"Go with the Flow: Create analytics module that calculates scenario IRR.
Should accept cashflows dict and return float IRR.
Use analytics.v14 contracts where applicable."
```

### Step 2: AI Generates Code (Implicit Compliance)

```python
"""Scenario IRR calculator following v14 conventions."""

from typing import Dict, List
from analytics.core.metrics import IRRResult


def calculate_scenario_irr(
    cashflows: Dict[str, float],
    tolerance: float = 1e-6,
) -> float:
    """
    Calculate internal rate of return for scenario.

    Args:
        cashflows: Dictionary of {year: amount} pairs.
        tolerance: Convergence tolerance (default 1e-6).

    Returns:
        IRR as decimal (e.g., 0.08 for 8%).

    Raises:
        ValueError: If no valid IRR found.
    """
    # Implementation
    ...
```

**Why this passes "Go with the Flow":**
- ✅ Lines ≤ 88 chars
- ✅ Full type hints (args, return)
- ✅ Multi-line docstring (proper format)
- ✅ Starts from v14 template
- ✅ No banned patterns
- ✅ Ready for black/isort/flake8/mypy

### Step 3: You Add to Repo

```bash
git add analytics/irr_calculator.py

# Pre-commit hook runs automatically
# Checks: black, isort, flake8, mypy
# Result: ✅ All pass (no blocking)

git commit -m "feat: scenario IRR calculator"
# Commit succeeds
```

### Step 4: You Push & Review

```bash
git push origin feature/irr
# Open PR

# Reviewer sees:
# ✅ Pre-commit passed
# ✅ Code is lint-clean
# ✅ Code is type-clean
# ✅ Follows template
# → Review focuses on logic, not formatting
```

---

## INTEGRATION CHECKLIST (For Your Team)

### Week 1
- [ ] Commit all 4 ruleset documents to repo
- [ ] Update CONTRIBUTING.md with AI collaboration contract section
- [ ] Update GO_WITH_THE_FLOW_GOLD_STANDARD.md Section 1.5
- [ ] Announce to team
- [ ] Provide quick reference (this document)

### Week 2 (Sprint 4)
- [ ] Execute SPRINT_4_ROADMAP.md
- [ ] Pre-commit hooks installed for all developers
- [ ] Fast-lane CI (`--fast --files`) tested
- [ ] Blessed templates available
- [ ] Team meeting: walkthrough + alignment
- [ ] 2 modules mypy-strict (gold standards created)

### Week 3+
- [ ] All new code uses "Go with the Flow" phrase
- [ ] Pre-commit hooks actively blocking violations
- [ ] Zero lint violations reaching main
- [ ] Velocity metrics tracked & improving
- [ ] Code reviews focus on logic, not formatting

---

## METRIC TARGETS (Sprint 5+)

| Metric | Pre-Ruleset | Post-Ruleset | Status |
|--------|------------|--------------|--------|
| Lint violations per sprint | 15-30 | 0 | ✅ |
| Time on lint fixes per sprint | 2.5h | 0 min | ✅ |
| Code passing first generation | ~70% | 100% | ✅ |
| PR review cycle time | 1-2 days | 4-6h | ✅ |
| Developer velocity gained | — | +2-3h/week | ✅ |

---

## NEXT STEPS

1. **Today/Tomorrow:**
   - Review all 4 documents
   - Get team lead sign-off
   - Commit to repo

2. **This Week:**
   - Update CONTRIBUTING.md
   - Distribute to team
   - Answer questions

3. **Sprint 4:**
   - Execute roadmap
   - Install infrastructure
   - Train team
   - Create gold standards

4. **Sprint 5+:**
   - Use "Go with the Flow" in all code requests
   - Pre-commit gates enforce (no manual enforcement needed)
   - Velocity increases, quality improves, everyone wins

---

## SUPPORT & OWNERSHIP

**Questions about the ruleset?** → Refer to GO_WITH_THE_FLOW_GOLD_STANDARD.md

**Questions about implementation?** → Refer to SPRINT_4_ROADMAP.md

**Questions about AI collaboration?** → Refer to GO_WITH_THE_FLOW_AI_COLLABORATION_CONTRACT.md

**Questions about integration?** → Refer to this document

---

## CANONICAL STATEMENT

**From this moment forward:**

> "Go with the Flow" is the complete, implicit invocation of all standards in:
> - GO_WITH_THE_FLOW_GOLD_STANDARD.md (Sections 1–6)
> - SPRINT_4_ROADMAP.md (implementation guide)
> - GO_WITH_THE_FLOW_AI_COLLABORATION_CONTRACT.md (AI behavior)
>
> When spoken or written in a code request, it means:
> - Emit code that is **production-ready on first generation**
> - No post-hoc cleanup is acceptable
> - Pre-commit hooks will enforce compliance
> - Code reviews will expect merge-readiness
>
> This is non-negotiable, measurable, and enforceable.

---

**Ruleset Version:** 2.0 (Complete)
**Status:** ✅ CANONICAL & BINDING
**Effective Date:** 2025-11-27
**Next Review:** Post-Sprint 4 (gather metrics, assess impact)
