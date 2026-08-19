# DutchBay Wind Feasibility — Reproduce Kit

Self-contained kit to regenerate the **full-stack** DutchBay 150 MW wind feasibility **offline,
using only the repo `.venv`**. Every module the study fires (fresh wind→AEP, GeoGIS, micro-siting,
finance, Monte-Carlo, Sobol/PAWN, capital-structure optimiser, grid screen, all emitters) is run
here — not the finance-only shortcut.

## Quick start
```bash
cd ~/Downloads/dutchbay-epc-model          # repo root (for the .venv + model)
bash feasibility_reproduce/run_all.sh      # ~15–25 min; offline; no network
```
Outputs: `feasibility_reproduce/report/*.pdf` (study 11 pp + coverage + catalog) and per-step
artifacts under `feasibility_reproduce/_run_out/`.

## Contents
| Path | Role |
|---|---|
| `run_all.sh` | Orchestrator — runs steps 0–10 offline |
| `HOWTO.md` | **Detailed manual** — every step, exact command, expected number, offline notes |
| `MANIFEST.md` | Provenance: engine SHA, golden KPIs, expected outputs, dep set |
| `lib/wind_provenance.py` | Fresh AEP + AEP tornado + TopFarm/PyWake micro-siting (+ cached ERA5) |
| `lib/mc_run.py` | Clean Monte-Carlo driver (2,500 trials, captured, no detachment) |
| `lib/run_global_sa.py` | Sobol + PAWN + Morris global sensitivity |
| `lib/build_study_pdf.py`, `lib/build_md_pdf.py` | markdown → PDF (Acrobat-safe, de-emoji) |
| `report/*.md` | The study / coverage / catalog sources |
| `cache/` | Network-dependent inputs shipped for offline: ERA5-ARCO result, GIS GeoTIFFs, grid + interaction scenarios, fresh AEP summary |
| `cache/expected/` | Reference outputs to verify a run against |

## Notes
- **Only two steps need network** (ERA5 retrieval, ERA5-grid GIS export); their outputs are cached,
  so the default run is fully offline. Online-refresh commands are in `HOWTO.md` (§2, §9).
- **Golden numbers** (finance canon, must be byte-identical): project_irr `-0.001166233356501311` ·
  equity_irr `−0.07853839579881527` · min_dscr `1.3`.
- One-line install: `pip install -r requirements.txt && pip install -e ".[dev,feasibility]"`
  (see `HOWTO.md` §0) on **Python >=3.12**. `[grid]` is included since the 3.12 baseline
  migration, so step 7's grid screen runs from the same environment as everything else.
- Helper scripts live in `lib/` (`mc_run.py`, `wind_provenance.py`, `run_global_sa.py`,
  `build_study_pdf.py`, `build_md_pdf.py`). They were absent from the repo until #1040/#1041
  because an unanchored `lib/` rule in `.gitignore` silently ignored them.
- **Micro-siting (§2) runs against a SYNTHETIC geometry**: the real site boundary and
  baseline layout were never committed, so `cache/micrositing_synthetic_site.yaml` derives
  both from committed scenario parameters (array centroid, turbine count, spacing,
  orientation) projected into UTM 44N. Its uplift quantifies the OPTIMISER WIRING, not
  DutchBay's siting headroom — the emitted `layout_optimized_synthetic.json` carries
  `provenance: synthetic_derived` and never overwrites the committed
  `cache/expected/layout_optimized.json`. Micro-siting is KPI-neutral, so the finance canon
  is unaffected either way.
