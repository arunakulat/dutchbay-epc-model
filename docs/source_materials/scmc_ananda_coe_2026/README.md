# SCMC / Ananda College COE STEAM Hub — corpus area

This is the entry point for the Sumathi Convergence Media Centre (SCMC) work and the wider STEAM Hub
at the Ananda College Centre of Excellence. It is separate from the DutchBay wind model: nothing here
changes a model input, a KPI or a canon value.

**Read [`WORK_RECORD.md`](WORK_RECORD.md) next.** It gives the state of the work, the governing
version, the open decisions and every session that contributed.
[`ARTIFACT_REGISTER.tsv`](ARTIFACT_REGISTER.tsv) lists each artifact by SHA-256.

## What is in this repository, and what is not

This repository is public, and publication to it is effectively irreversible. This area therefore
holds a record of the work, not the work product itself. The work product is in the private corpus,
and this area links to it for sanitised use.

| Item | Value |
|---|---|
| Private location | `arunakulat/DutchBay_RAG`, `corpus/scmc_ananda_coe_2026/held/` |
| Pinned commit | `e60a1392dfb4178420358d4507f02402fa0d2fca`, on branch `claude/private-scmc-pgf-corpus` until `arunakulat/DutchBay_RAG#41` merges |
| Files | 175, each checked against `ARTIFACT_REGISTER.tsv` when copied |

| Material | Where it is | Why |
|---|---|---|
| Work record, decisions, open actions | Here | Needed by anyone continuing the work |
| Client, consultant and third-party sources | Private corpus, SHA-256 here | `AGENTS.md`: no third-party material without explicit authorization |
| Text conversions of those sources | Private corpus, SHA-256 here | They carry the same content as the source |
| Owner-authored deliverables and working papers | Private corpus, SHA-256 here | They quote client commercial terms |
| Commercial figures, named individuals, contact details | Private corpus only | Restricted. See the deliverables |
| Regenerable page images | Owner's working folder, SHA-256 here | Can be rebuilt from the PDFs |

A hash proves which file is meant. It does not give access to the file. Reading the held material
needs access to the private repository, which the owner grants.

## Using held material here

Anything derived from the private corpus must be sanitised before it enters this repository: no
source text, commercial figures, named individuals or contact details. Describe the finding in general
terms and cite the file by its SHA-256. If publishing more is intended, that is a project-owner
decision and the change must say so.

## Working rules

- Route all STEAM, SCMC and Planet Green Force (PGF) work through this repository: record it under
  `INTAKE-01`, then work on a branch and a pull request.
- Before adding anything, ask whether it is third-party, confidential or personal. If it is, record
  its hash and describe the finding in general terms. See "Four ways a corpus commit goes wrong" in
  `AGENTS.md`.
- Keep `MANIFEST.sha256` current. CI fails if a tracked file here is missing from it.
- PGF material is private and must stay out of any public repository. Its public entry point is
  [`../planet_green_force_2026/README.md`](../planet_green_force_2026/README.md).
