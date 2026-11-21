# DutchBay wake loss: why the live model is far above the frozen value (#1589)

**Work item:** #1589. **Related:** #1568, #1577, #1587, #1786.
**Status:** investigation and disclosed sensitivity. No scenario input, calibration or KPI
changes. The lender basis stays `wake_loss_14_pct` in
`docs/wind/dutchbay_14_turbine_wake_summary.json` (7.32%).

Every figure below is in `docs/wind/dutchbay_wake_gap_1589_summary.json`, written by
`scripts/analyze_dutchbay_wake_deficit_gap_1589.py` from
`conf/dutchbay_wake_gap_1589.yaml`. That config composes
`conf/dutchbay_wake_14_turbines.yaml`, so the investigation runs on exactly the inputs of the
#1577 re-baseline: the recorded layout, the IEA 10 MW reference machine (rotor 198 m, hub
150 m), the lender case's Weibull (A 8.199 m/s, k 2.665), ambient turbulence intensity 0.10
and the Bastankhah-Porté-Agel deficit. `tests/wind/test_wake_deficit_gap_1589.py` checks that
the summary pins those inputs, that this note's figures match it, and that a fresh run
reproduces it.

## 1. The gap

#1577 re-derived the 14-turbine wake loss by scaling the frozen 15-turbine value (7.28%) by
the ratio of two live PyWake runs: 7.28% × 19.44 / 19.33 = 7.32%. The ratio keeps the frozen
calibration, so the absolute live figures never enter a KPI. But the live absolute figures
are about two and a half times the frozen one:

| Case (live PyWake, configured rose) | Wake loss |
|---|---|
| Frozen value, 15 turbines (offline, inputs not all recorded) | 7.28% |
| Synthetic single row the frozen value cites, all 15 | 8.19% |
| Synthetic single row, 14 counted, T2 standing and waking | 8.15% |
| Recorded layout, all 15 | 19.33% |
| Recorded layout, 14 counted, T2 standing and waking | 19.44% |

The issue asks three questions. Sections 2 to 4 answer them in turn.

## 2. What drives the gap

Read along the path from the frozen value to the live recorded-layout figure (12.05 pp in
all, 15 turbines, configured rose):

| Step | Change |
|---|---|
| Frozen 7.28% to the live synthetic row | +0.91 pp |
| Synthetic row to the recorded layout | +11.14 pp |
| **Frozen to live recorded layout** | **+12.05 pp** |

**Layout is almost all of it.** The synthetic row is a straight north-south line at 650 m,
3.28 rotor diameters (D). In the recorded layout each counted turbine's nearest neighbour is
2.28 D to 3.14 D away, and the array is two-dimensional, so a turbine is waked from several
directions rather than only along the row. Under a uniform rose the layout alone adds
9.62 pp; under the configured rose it adds 11.14 pp.

**The rose adds about 2 pp on the recorded layout.** Several turbine pairs line up on
bearings of about 190° to 203° (T1 and T2, T2 and T3, T5 and T7, T12 and T13), close to the
rose's heaviest sector (210°). Against a uniform rose the configured one adds 1.95 pp on the
recorded layout but only 0.43 pp on the single row. Note what that rose is: the conf calls
it the SW-dominant rose of the committed single-row wake tests. It is a test rose, not a
measured site rose.

**Machine size matters through spacing in rotor diameters.** Re-reading the same layout at
smaller rotor diameters, holding the 10 MW curves and the hub height, gives:

| Rotor diameter | Closest counted spacing | All 15 | 14 counted, T2 waking |
|---|---|---|---|
| 120 m | 3.76 D | 9.79% | 9.78% |
| 140 m | 3.22 D | 12.22% | 12.23% |
| 160 m | 2.82 D | 14.68% | 14.71% |
| 180 m | 2.51 D | 17.14% | 17.21% |
| 198 m (configured) | 2.28 D | 19.33% | 19.44% |

This is a geometric sensitivity, not a model of another machine, whose power and thrust
curves would differ. It shows that the recorded spacing is tight for a 198 m rotor, and that
the live loss falls toward the frozen range as spacing in diameters opens.

**Turbulence and the deficit model do not close it.** Over ambient turbulence intensity 0.06
to 0.14 the live loss on the recorded layout runs from 22.23% down to 17.12% (all 15). Lower
turbulence slows wake recovery and raises the loss. The TurbOPark deficit gives 23.75% (all
15) and 23.87% (14 counted), above Bastankhah-Porté-Agel, so the configured model is not the
high outlier. No turbulence or deficit-model case comes within 9 pp of the frozen value.

**Per turbine** (#1786's sensitivity, same run): the counted turbines' live losses run from
3.64% at T15, at the south-west end, to 31.31% at T6, inside the array.

## 3. Is the frozen 7.28% still right for the recorded layout?

Not as a description of it. The frozen value sits within 1 pp of the live single-row figure
it cites (8.19%), and far from every recorded-layout case at the configured 198 m rotor
(17% to 24%). On the
evidence here, it reflects a wide single row, not the recorded two-dimensional layout with a
198 m rotor.

What this investigation cannot settle is the right absolute value for the project. The live
figures rest on a proxy machine (the IEA 10 MW reference, not the project's turbine), a test
rose rather than a measured one, and the engine's default turbulence intensity, and there is
no measured Dutch Bay wind or turbulence data. Each of those can move the live loss by
several points (section 2).

## 4. P50 and P90 if the live value replaced the basis

As a disclosed sensitivity only. Gross energy, the non-wake losses and the uncertainty
budget are unchanged, so net energy scales by the ratio of wake retentions,
(1 − 0.1944) / (1 − 0.0732) = 0.8693, and every exceedance level moves by the same factor:

| Level | Relative change |
|---|---|
| P50 | −13.07% |
| P90, one year | −13.07% |
| P90, 20-year life | −13.07% |

This is not a lender figure, and no P90 is claimed: the F-5 HOLD stands.

## 5. What follows

1. **The lender basis is unchanged.** Replacing 7.32% would move every DutchBay scenario's
   AEP and KPIs. That is an R3 calibration change, which needs the owner's decision and
   sign-off, and on this evidence it would trade one unvalidated figure for another.
2. **The inputs that would settle it** are a measured site rose and turbulence intensity
   (mast or lidar), and the project turbine's own power and thrust curves. Until then the
   live figures stay a labelled sensitivity beside the basis, as #1786's per-turbine block
   already is.
3. **Loads, not only energy.** Nearest-neighbour spacing of 2.28 D to 3.14 D along the
   prevailing direction is a site-suitability question (IEC 61400-1 effective turbulence,
   OEM approval), already open as #1568 domain N-1. Wake energy cannot answer it.
