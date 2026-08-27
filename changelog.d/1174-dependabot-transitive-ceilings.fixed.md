- **Dependabot ignore rules now cover transitive-consumer ceilings, not just declared majors** —
  four weekly PRs (#1064, #1066, #1067, #1068/#1166) were opened, went red, and sat for a week
  because each crossed a ceiling declared by a package *other* than the one being bumped. The
  existing rules were major-only, and three of the four breaches were **minor** bumps, so nothing
  could have caught them. Now encoded, each with the specifier that sets it: `magika` capped
  `~=0.6.1` by markitdown (every release 0.1.2–0.1.7), `openmdao` capped `==3.39.*` by topfarm,
  `numpy` capped `<2.5` by pandapower — the existing major-only numpy rule is extended to minors —
  `websockets` capped `<17` and `starlette` capped `<2`, both by streamlit. Blocking level is set
  per specifier rather than uniformly: `magika`, `openmdao` and `numpy` break at minor, while
  `websockets` and `starlette` remain free to take minors inside their ceilings. Verified against
  all four historical bumps plus six controls — every real breach blocked, every safe bump still
  permitted. Also corrects the `pandapower` rationale, which still described the retired
  `==3.3.0` / `scipy==1.17.1` state; the lock carries 3.5.4 against scipy 1.18.1, and it is
  pandapower's `numpy<2.5` that blocks #1169.
