- **Agentic-delivery practice evidence ingressed** — `docs/AGENTIC_DELIVERY_PRACTICE.md`
  opens a second corpus strand covering how the model is *produced* (not what it models),
  with a graded source register, a critical evaluation, and an explicit adopted/rejected
  split. First source: a practitioner retrospective on one month of unmetered agentic
  coding (`AGP-SRC-001`, tier `practitioner testimony`).
- **`tests/finance/test_canon_vector_is_computed.py`** — states directly, for the first
  time, that the canonical lender KPI vector must be *computed* rather than *returned*:
  three economic drivers are perturbed through the canonical gateway and every value KPI
  must move materially. A pipeline short-circuited to emit the pinned canon passes the
  value oracle and fails this guard (verified by negative control). Asserts
  responsiveness only — never a magnitude or direction — so it is KPI-neutral and must
  not be re-baselined when the canon moves.
- **Pull-request template now collects verification receipts** rather than self-attested
  checkboxes: the command and its result for each check, with an explicit place to
  declare a check that was *not* run.
