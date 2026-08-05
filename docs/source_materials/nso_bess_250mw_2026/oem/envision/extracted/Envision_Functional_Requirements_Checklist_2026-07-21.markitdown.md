## Compliance Checklist
| Ref. Clause | Category | Requirement Summary | Specific Parameter / Limit | Supplier Compliance | Supplier Remarks |
| --- | --- | --- | --- | --- | --- |
| Annex A | NaN | NaN | NaN | NaN | NaN |
| A.01 | Integration | Power Plant Controller (PPC) controlling point | 33 kV POC | Yes | NaN |
| A.01 | Integration | Performance monitoring point | 33 kV POC | Yes | NaN |
| A.02.04 | Environmental | Continuous operation temperature range | 10°C to 40°C | Yes | NaN |
| A.02.04 | Environmental | Design relative humidity (24h period) | 95% | Yes | NaN |
| A.03.02 | Control & Security | User access control for NSO staff | Minimum 3 levels | Yes | NaN |
| A.04 | System Characteristics | Nominal / Max / Min AC system voltage | 33 kV / 36 kV / 30 kV | Yes | NaN |
| A.04 | System Characteristics | Nominal / Max / Min continuous frequency | 50 Hz / 50.5 Hz / 49.5 Hz | Yes | NaN |
| A.04 | System Characteristics | Max rate of change of frequency (df/dt) | 2.5 Hz/s (500ms avg) | Yes | NaN |
| A.04 | System Characteristics | Basic insulation level / Switching impulse | 170 kV peak / 70 kV peak | Yes | NaN |
| A.05 | Capability | Grid-forming control capability | Instant unbalanced power sharing, V response, Q injection | Yes | NaN |
| A.05.02 | Overload | PCS AC-side current operation (Continuous) | 110% rated current | Yes | NaN |
| A.05.02 | Overload | PCS AC-side current operation (2 minutes) | 120% rated current | Yes | <35° can meet |
| A.05.02 | Overload | PCS AC-side current operation (10 seconds) | 150% rated current | Yes | <35° can meet |
| A.05.02 | Frequency Support | Active/Reactive power capability range | 47 Hz to 52 Hz | Yes | NaN |
| A.05.03 | Frequency Support | Droop curve configuration range | 1% to 9% (Default 4%) | Yes | NaN |
| A.05.03 | Frequency Support | Synthetic inertia time constant | >= 20 seconds | No | <=12 seconds |
| A.05.03 | Frequency Support | Synthetic inertia activation time | <= 5 ms | Yes | NaN |
| A.05.03 | Frequency Support | Primary frequency regulation response time | < 0.2 s (Deviation <= 2%) | Yes | NaN |
| A.05.04 | Frequency Withstand | Frequency ride through configurable bands | Minimum 4 bands (45 Hz - 55 Hz) | No | NaN |
| A.05.04 | Frequency Withstand | Operation limit: 53.0 >= f > 52.0 Hz | 1 minute | No | 1 minute can not meet |
| A.05.04 | Frequency Withstand | Operation limit: 47.0 > f >= 45.0 Hz | 10 seconds | No | 10 seconds can not meet |
| A.05.05 | RoCoF Withstand | RoCoF withstand limit (250ms avg) | 4.0 Hz/s | Yes | NaN |
| A.05.06 | Voltage Capability | Active/Reactive delivery under V variations | ±10% of rated voltage at POC | Yes | NaN |
| A.05.07 | Voltage Support | Configurable droop curve range | 1% to 6% | Yes | NaN |
| A.05.07 | Voltage Support | AVR 5% voltage step response time | < 50 ms (Overshoot <= 30%) | Partial | The test requirements are not clear. |
| A.05.08 | Voltage Withstand | Voltage ride through configurable bands | Minimum 10 bands (0 to 1.3 p.u.) | Yes | NaN |
| A.05.08 | Voltage Withstand | Operation limit: v = 0.00 p.u. | 0.2 seconds | Yes | NaN |
| A.05.08 | Voltage Withstand | Operation limit: v > 1.30 p.u. | 0.02 seconds | Yes | NaN |
| A.05.09 | Disturbance | Continuous uninterrupted operation capability | Up to 6 disturbances within 5 min | No | Our test report only includes 2 faults. |
| A.05.10 | Reactive Current | Reactive current injection during fault | 2% per 1% V drop (Default) / Configurable 1-6% | Yes | NaN |
| A.05.10 | Fault Recovery | Active power recovery post-fault clearance | >= 95% within 100 ms | No | Active power recovery time exceeds 100 ms. |
| A.05.10 | Fault Recovery | Reactive current activation delay | 20 ms to 40 ms (Provide fully within 70ms) | Yes | NaN |
| A.05.11 | Power Quality | Rapid voltage changes | <= 3% of nominal voltage | Yes | NaN |
| A.05.13 | Reactive Power | Reactive power capability limit (Any P) | ± 0.3 p.u. (Four quadrant operation) | Yes | NaN |
| A.05.14 | Control Modes | Supported automatic control modes | Voltage, Droop, Reactive Power, Power Factor | Yes | NaN |
| A.05.15 | Set-Point Response | Set-point command commence / achieve time | < 50 ms / < 300 ms | Yes | NaN |
| A.05.15 | Set-Point Response | Set-point overshoot / settling time | <= 10% / < 400 ms (to 1%) | Yes | NaN |
| A.05.17 | Oscillation Damping | Low-frequency oscillation suppression | 0.2 Hz - 2.5 Hz (P variation 10%-30% Pn) | Yes | NaN |
| A.05.17 | Grid Control | AGC regulation range | -100% to +100% Pn | Yes | NaN |
| A.05.17 | Grid Control | Minimum Short Circuit Ratio (SCR) | 1.2 (Grid-following), 1.0 (Grid-forming) | Yes | NaN |
| A.05.19 | Safety | Loss of communications response | Revert to safe state (No auto-restart) | Yes | NaN |
| A.05.22 | Communication | Supported integration protocols | IEC 60870-5-104/101 | Yes | NaN |
| A.05.23 | Simulation Models | Required model formats | PSS®E (v35.x), PSCAD (v5.x), PowerFactory | Yes | NaN |
| A.05.24 | Testing | Grid connection testing scope | Harmonics, FRT, Frequency, Q, V, EMI, Noise | Yes | NaN |
| Annex B | NaN | NaN | NaN | NaN | NaN |
| 3.6.3 | Power Quality | Voltage Waveform Distortion | Limit to indicative planning levels in IEC 61000-3-6 Table 2 | Yes | comply but cannot provide certificate |
| 3.6.4 | Power Quality | Voltage Fluctuation / Flicker | Limit to indicative planning levels in IEC 61000-3-7 Table 2 | Yes | comply but cannot provide certificate |
| 3.8 | Power Quality | Current Distortion Limits | Comply with IEEE 519-1992 limits | Yes | NaN |
| 3.7.1 & App A 3.1(G) | Protection | Basic Impulse Level (BIL) | 170 kV for 33 kV system | Yes | NaN |
| 3.7.2 & App A 3.1(H) | Protection | Power Frequency Withstand (1 min) | 70 kV for 33 kV system | Yes | NaN |
| 3.17.1.3 I (iii) | Active Power | Maximum / Minimum Power Step Size | Adjustable step sizes as specified by the Transmission Licensee | Yes | NaN |
| 3.17.1.3 II | Active Power | Active Power Ramp Rates | Settling time (Ts) 20-30 seconds, Tolerance -2% to +2% | Yes | NaN |
| 3.17.1.7 | Frequency Control | LFSM-U Activation | Activated when frequency falls below 49.8 Hz | Yes | NaN |
| 3.17.1.7 | Frequency Control | LFSM-O Activation | Activated when frequency rises above 50.1 Hz | Yes | NaN |
| 3.17.1.7 | Frequency Control | LFSM Step Response Time | Typically 2s to 5s | Yes | NaN |
| 3.17.1.7 | Frequency Control | LFSM Settling Time | Typically 20s to 30s | Yes | NaN |
| 3.17.2.5 II | Power Quality | Harmonic Apportionment Factor (M) | Default 0.25 (unless specified in connection agreement) | No | NaN |