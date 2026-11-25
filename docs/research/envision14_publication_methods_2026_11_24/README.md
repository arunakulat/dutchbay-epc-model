# Envision14 study — source-independent methods only (#1939)

This narrowly scoped publication candidate contains reusable, illustrative screening and
verification methods with invented, hand-calculable synthetic inputs. It is **not** the
site-specific Envision14/Wariyapola study, an EIA crosswalk, an equipment specification,
an approved layout, an energy-yield assessment, a utility study or the integrated DBPL
report. No project numerical results are supplied. The historical private working package
and review receipts remain withheld from this publication. No lender, Board, regulatory
or external reliance; F-5, #1110 and applicable repository HOLDs remain. Do not merge
without prior explicit owner approval.

## Included methods

- Wind nameplate versus assumed active cap and energy-accounting checks. The inputs are
  synthetic and do not calculate wake losses or resource uncertainty.
- Paired illustrative export boundaries, magnitude-only SCR and instantaneous transformer
  capacity limits. No voltage, transformer impedance, reactive, protection, QSTS, EMT,
  operational or annual curtailment study is performed. The physical boundary and
  shared-asset allocation remain unknown; no design is selected.
- Runtime curve-byte digest and schema validation, not an OEM authorization or validated
  turbine curve.
- A path guard and bounded generated-PDF structural and decoded-content checks. The PDF
  profile is deliberately narrow; a synthetic structural fixture is not a valid report.
  These checks cannot establish rights, authenticity, confidentiality absence, hidden
  information in pixels/fonts or steganography, or suitability for external reliance.

No original or derived private source datasets, project-specific screening results,
environmental source-page crosswalks, plots, report PDFs, commercial figures, private
identifiers, or private logs are included. The repo's existing proprietary evaluation
license applies to the owner-authorized code, not to any withheld third-party material.

Run with the repository's governed environment and bytecode disabled:

```sh
PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider docs/research/envision14_publication_methods_2026_11_24/tools
```

This is a source-independent replacement scope, not completion or publication of all
deliverables in #1939. Site-specific evidence requires separately documented source
rights and fresh independent review before public release.
