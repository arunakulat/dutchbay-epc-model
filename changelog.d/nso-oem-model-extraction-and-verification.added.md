Added `scripts/analysis/extract_oem_dynamic_models.py`, which reads OEM dynamic-model deliverables
without running PSCAD or PSS(R)E, and used it to close two findings that had been carried as
UNVERIFIED.

PSCAD and PSS(R)E are commercial, Windows-only, licensed tools, and PSCAD additionally needs an
Intel Fortran compiler to build the supplied `.obj`/`.lib` interface objects, so the models cannot
be executed in this repository's CI. They can still be read: a `.dyr` is ASCII and a `.pscx` is
XML. The extractor parses both and reports compiled `.dll`/`.obj`/`.lib` artifacts as metadata
only, stating explicitly that the control law in them is not recoverable.

Two register findings move off UNVERIFIED as a result:

- **B2, protection envelope — verified, and wider than recorded.** The delivered `.dyr` sets
  47.5 Hz / 1800 s and 46.9 Hz / 0.04 s under-frequency, and 51.5 Hz / 1800 s and 52.1 Hz / 0.04 s
  over-frequency. The PSS(R)E UDM manual confirms these CONs are trip thresholds, and the ENPCS2520
  specification states the same behaviour in words, including separation from the grid within 0.2 s
  inside the 47-47.5 Hz band where Annex A A.05.04 requires continuous operation. The specification
  also states the parameters are adjustable to the local grid code, so this is a settings defect
  with a vendor-stated remedy rather than a hardware limit.
- **B3, reactive capability — checked and cleared.** The concern rested on the 10 MW figure of
  +/-3.29 Mvar. The 11 MW design calculation states +/-3.62 Mvar, which exceeds the +/-3.3 Mvar
  implied at a declared 11 MW. The finding is withdrawn and retained as a closed item.

One new CRITICAL finding is added. **A6**: the ENPCS2520 specification states 110 % overload for
10 minutes at 45 degrees C, 110 % continuous only at 40 degrees C, and 120 % for 1 minute at
35 degrees C, against Annex A A.05.02(a)'s requirement of 110 % continuous and 120 % for at least
two minutes. Unlike the frequency settings, no adjustability note attaches — these are thermal
ratings. Clarification 64 requested exactly this relief and was refused.

The register now carries 22 gaps and **no finding marked UNVERIFIED**: every item is anchored to a
primary source held in the corpus.
