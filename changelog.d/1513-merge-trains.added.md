- **`TRAIN-01`: reviewed pull requests can share one full-suite run as a merge train.** This is a
  new canonical rule in `go_with_the_flow_rules_v3_0_clean.csv`, on the project owner's decision of
  2026-10-31 ("Trains now"). The merge coordinator may land two or three reviewed draft pull
  requests together. The cars must be path-disjoint, none may be stacked on another, and at most
  one may change a KPI. The train branch starts at `main` and carries one commit per car, each with
  that car's own message. It is opened ready for review, so the full suite runs once on the union.
  It lands by rebase-merge, so each car stays its own revertable commit on `main`.
- **A car's binding carries onto the train only through three proofs.** `RECRUIT-01` module 3
  gains §8. It applies §7's three proofs (blob identity, bidirectional import isolation and the
  complete diff) between the car's reviewed head and the train head. §8 also adds a landing check:
  every landed commit's tree must equal its train commit's tree, in order, on top of the recorded
  `main`.
- **What a train does not prove is stated.** The intermediate commits between cars on `main` were
  never run by the full suite on their own.
- **Routing.** `DELIVERY-01` names a train of dolphin-sized cars as compliant, and `AGENTS.md` and
  the steward skill route to the new rule. `tests/lint/test_train_policy.py` pins every control,
  with a negative control for each. No workflow or ruleset changes: the main ruleset already
  allows rebase merges.
