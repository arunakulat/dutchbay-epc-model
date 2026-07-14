- **`antlr4-python3-runtime` pinned to 4.9.\* to keep the lock installable (#939 fallout).** The weekly
  Dependabot `python-deps` group swept `antlr4-python3-runtime` 4.9.3 → 4.13.2, which is a
  `ResolutionImpossible`: `hydra-core==1.3.4` and `omegaconf==2.3.1` — the config stack the whole CLI
  is built on (GWTF CLI-01, Hydra-only) — both require `antlr4-python3-runtime==4.9.*` (the grammar
  runtime their parsers were generated against), so `pip install -r requirements.txt` could not resolve.
  Canon was never at risk (no core numeric lib moved), but no fresh env or CI image could be built from
  that lock. A `constraints.txt` hard-cap (`antlr4-python3-runtime<4.10`) plus a `.github/dependabot.yml`
  ignore of semver-major **and** -minor bumps (4.9→4.13 is a minor) now hold it on 4.9.\*; patches within
  4.9.\* still flow. Lift only in lockstep with a `hydra-core`/`omegaconf` upgrade that regenerates their
  grammars against a newer antlr runtime. Tooling/lock policy only; no engine or financial behaviour changed.
