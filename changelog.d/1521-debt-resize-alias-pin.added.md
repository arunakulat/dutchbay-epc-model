- **debt resize and Financing_Terms alias pinned** — assert that `_resize_for_amortization`
  returns a full deep copy sharing zero containers with caller input (#1521 O-1), and pin
  the alias semantics of `_config_at_debt_ratio` ensuring anchored aliases under sibling
  sections remain unmutated (#1521 O-2), with negative controls.
