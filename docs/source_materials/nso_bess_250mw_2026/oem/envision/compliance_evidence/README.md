# Envision OEM compliance evidence register

- Tender: `TR/REP&PM/ICB/2026/001/C`
- Configuration: 10 MW / 40 MWh standalone BESS unit
- OEM: Envision Energy

This register distinguishes evidence actually received from evidence required by the tender.
An item is not complete until its source artifact is committed beside this register and its
checksum is added to the package manifest.

## Evidence received

| Evidence | Status | Location | Limitation |
|---|---|---|---|
| Design calculation V1.0, 29 July 2026 | Received | `../Envision_10MW_40MWh_Design_Calculation_V1.0_2026-07-29.pdf` | Design calculation only; not a complete compliance package |
| Redacted ENPCS01 grid-code parameters | Received previously | `../../../../../../tests/fixtures/grid/envision_enpcs01_gridcode.yaml` | Reference constants only; grid-following topology; proprietary binaries absent |

## Outstanding OEM evidence

| Requirement | Status | Evidence needed |
|---|---|---|
| True grid-forming V/F operation | Missing | Signed OEM declaration and control-description evidence demonstrating voltage-source, voltage-controlled operation under normal and fault conditions |
| PSS(R)E RMS model | Missing | Executable model, parameter set, model guide and validation report |
| PSCAD/EMTDC model | Missing | Executable EMT model, model guide and validation report |
| SCR and phase-step validation | Missing | V/P/Q results at SCR 1, 3, 5 and 10, X/R 5, including the required +/-50 degree phase-angle step |
| Standards compliance | Missing | Certificates or type-test reports for IEEE 1547-2018, IEEE 2800-2022, UL 1741-SB, IEC 62477-1, IEC 62109-1/2 and IEC TS 62786-3 |
| 45 degree C performance | Missing | Guaranteed usable-energy, power, auxiliary-load and AC-to-AC RTE substantiation at the maximum site ambient |
| Capacity Maintenance Plan | Missing | BoL/EoL capacity basis, augmentation timing and MWh, rack/module replacement plan, outage coordination and recycling/decommissioning commitments |
| Ride-through and controls | Missing | Frequency/voltage envelope, LVRT/HVRT, droop settings, reactive-current response and EMS logging description |
| Single-line diagram and export limiter | Missing | SLD through the Grid Point and documented 10 MW +10% power-limiting method at the Termination Point |
| Equipment design life | Missing | Evidence of at least 20 years for non-battery equipment and 15 years for cells/modules/racks under the ESA duty cycle |
| Fire safety and protection | Missing | Fire detection/suppression, thermal-runaway mitigation, compartmentalisation and PCS fault-contribution/withstand evidence |

## Important boundary

The repository's Python grid screens, generic RMS ride-through simulations, financial BESS
degradation model and redacted fixture are design-stage analytical aids. They are not substitutes
for the OEM-certified models, certificates, test reports or site-specific engineering package
required by the tender.
