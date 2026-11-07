# SCMC / Ananda College COE STEAM Hub — corpus area

This is the entry point for the Sumathi Convergence Media Centre (SCMC) work and the wider STEAM Hub
at the Ananda College Centre of Excellence. It is separate from the DutchBay wind model: nothing here
changes a model input, a KPI or a canon value.

**Read [`WORK_RECORD.md`](WORK_RECORD.md) next.** It gives the state of the work, the governing
version, the open decisions and every session that contributed.
[`ARTIFACT_REGISTER.tsv`](ARTIFACT_REGISTER.tsv) lists each artifact by SHA-256.

## What is in this repository, and what is not

This repository is public, and publication to it is effectively irreversible. This area therefore
holds a record of the work, not the work product itself.

| Material | Where it is | Why |
|---|---|---|
| Work record, decisions, open actions | Here | Needed by anyone continuing the work |
| Client, consultant and third-party sources | Owner's working folder, SHA-256 here | `AGENTS.md`: no third-party material without explicit authorization |
| Text conversions of those sources | Owner's working folder, SHA-256 here | They carry the same content as the source |
| Owner-authored deliverables and working papers | Owner's working folder, SHA-256 here | They quote client commercial terms. Publication is an open owner decision |
| Commercial figures, named individuals, contact details | Not recorded here | Restricted. See the deliverables |

A hash proves which file is meant. It does not give access to the file. Until the owner decides where
the held material goes, a contributor needs the owner to supply it.

## Working rules

- Route all STEAM, SCMC and Planet Green Force (PGF) work through this repository: record it under
  `INTAKE-01`, then work on a branch and a pull request.
- Before adding anything, ask whether it is third-party, confidential or personal. If it is, record
  its hash and describe the finding in general terms. See "Four ways a corpus commit goes wrong" in
  `AGENTS.md`.
- Keep `MANIFEST.sha256` current. CI fails if a tracked file here is missing from it.
- PGF work has no public corpus area yet. Its existing working folder contains private correspondence
  and must not be copied here. Open a PGF area only after a scoped issue settles what may be public.
