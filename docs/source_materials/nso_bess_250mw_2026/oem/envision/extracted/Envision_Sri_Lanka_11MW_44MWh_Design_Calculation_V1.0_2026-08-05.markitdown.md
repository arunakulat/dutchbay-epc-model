Envision Energy
Design Calculation Description for Sri
Lanka 11MW/44MWh project
05/08/2026
V1.0
© 2026 Envision Energy. All Rights Reserved.
Conf idential and privileged information. Any unauthorised review, use, disclosure, or
distribution is prohibited without written consent from Envision Energy.

2
Table of Contents
1 Introduction .............................................................................................................................................................................. 3
2 Key Project Information....................................................................................................................................................... 3
3 General BESS Design Parameters................................................................................................................................... 3
4 Proposed BESS Design ........................................................................................................................................................ 4
4.1 Proposed Overall Solution ...................................................................................................................................................................... 4
4.2 Performance Curves ................................................................................................................................................................................... 5
4.3 Design Sizing.................................................................................................................................................................................................... 8
4.3.1 DC Unit .......................................................................................................................................................................................................... 8
4.3.2 AC Skid .......................................................................................................................................................................................................... 8
4.4 Assumptions .................................................................................................................................................................................................... 9
5 PCC Requirements ................................................................................................................................................................. 9
6 Conclusion ............................................................................................................................................................................... 10
Disclaimer
While every precaution has been taken in the preparation of this document, Envision Energy
assumes no liability with respect to the operation or use of Envision Energy products and
documentation described herein, for any act or omission of Envision Energy concerning such
products or this documentation, for any interruption of service, loss or interruption of business,
loss of anticipatory profits, or for punitive, incidental or consequential damages in connection with
the furnishing, performance, or use of the Envision Energy products and documentation provided
herein. Please use the applicable specifications in their latest versions. Images do not necessarily
reflect the exact scope of supply. The actual scope of supply can be subject to technical
alterations at any time.
© 2026 Envision Energy. All Rights Reserved.
Conf idential and privileged information. Any unauthorised review, use, disclosure, or
distribution is prohibited without written consent from Envision Energy.

3

1  Introduction

This document describes design calculations for the Sri Lanka 11MW/44MWh  BESS project.

2  Key Project Information
| Project name  |     |     | Sri Lanka 11MW/44MWh  |     |
| ------------- | --- | --- | --------------------- | --- |
BESS project
| Environmental conditions                   |     |     | -30°C to +45°C.        |     |
| ------------------------------------------ | --- | --- | ---------------------- | --- |
| Auxiliary losses                           |     |     | Calculated at 35ºC     |     |
| Voltage at Point of Connection (POC)       |     |     | 33kV                   |     |
| Power output at Point of Connection (POC)  |     |     | 11 MW (nominal)        |     |
| Usable energy at Beginning of Life (BoL)   |     |     | 43.9 MWh offered       |     |
| Cycles per day                             |     |     | 1.1                    |     |
| Proposed solution                          |     |     | 2 sets ENS-D06G-24120- |     |
10100-000

3  General BESS Design Parameters

| AC skid  | PCS rated power       | 4 x 2520 kW      |     |     |
| -------- | --------------------- | ---------------- | --- | --- |
|          | Transformer voltages  | 0.69 kV / 33 kV  |     |     |
|          | Transformer type      | 3 windings       |     |     |
|          | Transformer rated     | 10100 kVA        |     |     |
capacity
| DC container  | Voltage range of DC  | 1165 VDC to 1500 VDC  |     |     |
| ------------- | -------------------- | --------------------- | --- | --- |
system
|     | Rack configuration  | 10 racks per DC container  |     |     |
| --- | ------------------- | -------------------------- | --- | --- |
|     |                     |                            |     |     |
© 2026 Envision Energy. All Rights Reserved.

Conf idential and privileged information. Any unauthorised review, use, disclosure, or

distribution is prohibited without written consent from Envision Energy.

4

4  Proposed BESS Design
4.1  Proposed Overall Solution

2 sets ENS-D06G-24120-10100-000

| Item                   | Value  | Unit  | Comments  |
| ---------------------- | ------ | ----- | --------- |
| Rated power            | 20.1   | MVA   |           |
| Required active power  | 11     | MW    | At PoC    |
| Usable active power    | 18.7   | MW    | At PoC    |
| Installed capacity     | 48.2   | MWh   |           |
| Usable capacity @ POC  | 43.9   | MWh   | At BoL    |

|     |     |     |     |
| --- | --- | --- | --- |
© 2026 Envision Energy. All Rights Reserved.

Conf idential and privileged information. Any unauthorised review, use, disclosure, or

distribution is prohibited without written consent from Envision Energy.

5
4.2 Performance Curves
1.1 cycles/day
Year Usable Usable System System RTE RTE DC DC-DC Export in Cumulativ
capacity capacity SoH SoH inclu exclu Usable RTE Previous e Export
at 33 kV at 33 kV includi excludi ding ding Dischar Year (MWh)
including excludin ng aux ng aux aux aux ge (MWh)
aux g aux power power powe powe Capacit
power power r r y
(MWh) (MWh) (MWh)
BoL 43.9 44.6 100% 100% 86.9% 89.9% 45.8 94.8%
1 43.1 43.9 98.2% 98.3% 86.6% 89.8% 45 94.7% 17465 17465
2 42 42.8 95.7% 95.9% 86.4% 89.7% 43.9 94.6% 17102 34568
3 41.1 41.9 93.7% 93.8% 86.2% 89.6% 43 94.5% 16703 51271
4 40.3 41.1 91.8% 92% 86.1% 89.5% 42.1 94.4% 16354 67626
5 39.5 40.3 90% 90.3% 86% 89.5% 41.3 94.3% 16036 83662
6 38.8 39.6 88.4% 88.7% 85.8% 89.4% 40.6 94.2% 15740 99403
7 38.1 38.9 86.9% 87.2% 85.7% 89.3% 39.9 94.1% 15462 114865
8 37.5 38.3 85.4% 85.7% 85.6% 89.2% 39.2 94.1% 15198 130064
9 36.9 37.6 84% 84.3% 85.5% 89.2% 38.6 94% 14946 145010
10 36.3 37.1 82.7% 83% 85.4% 89.1% 38 93.9% 14705 159716
11 35.7 36.5 81.4% 81.7% 85.3% 89.1% 37.4 93.9% 14473 174190
© 2026 Envision Energy. All Rights Reserved.
Conf idential and privileged information. Any unauthorised review, use, disclosure, or
distribution is prohibited without written consent from Envision Energy.

6
12 35.2 35.9 80.2% 80.5% 85.2% 89% 36.9 93.8% 14250 188440
13 34.6 35.4 79% 79.3% 85.1% 88.9% 36.3 93.8% 14034 202475
14 34.1 34.9 77.8% 78.2% 85% 88.9% 35.8 93.7% 13825 216300
15 33.6 34.4 76.7% 77% 85% 88.8% 35.3 93.6% 13623 229924
*Usable capacity at PCC including the auxiliary losses
© 2026 Envision Energy. All Rights Reserved.
Conf idential and privileged information. Any unauthorised review, use, disclosure, or
distribution is prohibited without written consent from Envision Energy.

7
*Note that the above values are contingent upon the assumed loss factors shown in the following table. Furthermore,
it is important to note that these values may exhibit a slight variation of 1-2 % in response to actual site conditions,
attributable to fluctuations in ambient temperature (±5 °C deviation) and the measurement accuracy of external
metering equipment (such as PT, CT, etc.). Rest assured, we remain committed to ensuring precision and transparency
throughout this project’s execution. Furthermore, if the RTE is tested using an electricity meter, we consider that the
meter has an error of around 0.5%; therefore, the RTE is deemed compliant within this margin of error.
© 2026 Envision Energy. All Rights Reserved.
Conf idential and privileged information. Any unauthorised review, use, disclosure, or
distribution is prohibited without written consent from Envision Energy.

8
4.3 Design Sizing
4.3.1 DC Unit
ENS-D06G-24120-10100- Value Unit Comments
000
DC container configuration 6030 kWh 6 racks connected in parallel
per Container
Nameplate capacity type 1 24.121 MWh 4 containers connected per
AC twin-skid
4.3.2 AC Skid
Item Value Unit Comments
Step up transformer 10.1 MVA
PCS 2.52 MVA
AC unit 10.08 MW MV AC container. 4x PCS & 1x
transformer
© 2026 Envision Energy. All Rights Reserved.
Conf idential and privileged information. Any unauthorised review, use, disclosure, or
distribution is prohibited without written consent from Envision Energy.

9

4.4  Assumptions

| Item                  |     | Efficiency  | Remarks                        |     |
| --------------------- | --- | ----------- | ------------------------------ | --- |
| Calendar degradation  |     | 97 %        | From cell manufacture to Site  |     |
Acceptance Test (SAT). Assuming
6 months from Factory
Acceptance Test (FAT) to SAT
Usable DC capacity  98 %  Includes battery cell efficiency &
| ratio         |     |         | DOD limitations               |     |
| ------------- | --- | ------- | ----------------------------- | --- |
| LV DC cables  |     | 99.9 %  | Assuming that the cables are  |     |
aluminium @ 30m, provided by
BoP
| PCS  |     | 98.5%  | At Rated Power, provided by  |     |
| ---- | --- | ------ | ---------------------------- | --- |
Envision
| LV/MV transformer  |     | 99.2%  | Compliance with EU Ecodesign  |     |
| ------------------ | --- | ------ | ----------------------------- | --- |
standards, provided by Envision
| MV/HV transformer  |     | 100 %   | Assumed, provided by BoP  |     |
| ------------------ | --- | ------- | ------------------------- | --- |
| MV cable           |     | 99.6 %  | Assumed, provided by BoP  |     |
| HV cable           |     | 100 %   | Assumed, provided by BoP  |     |

| Item  |     | Energy consumption  | Remarks  |     |
| ----- | --- | ------------------- | -------- | --- |
Aux consumption at  0.17 MW x 4 h  Auxiliary consumption cannot be
| BoL  |     |     | guaranteed separately  |     |
| ---- | --- | --- | ---------------------- | --- |

| Item               |     | Impedance  | Remarks                       |     |
| ------------------ | --- | ---------- | ----------------------------- | --- |
| LV/MV transformer  |     | 9 %        | Compliance with EU Ecodesign  |     |
standards
| MV/HV transformer  |     | 16 %  | Assumed, provided by BoP  |     |
| ------------------ | --- | ----- | ------------------------- | --- |

5  PCC Requirements

| Parameter  | Unit  Discharge- | Discharge- | Charge- | Charge- |
| ---------- | ---------------- | ---------- | ------- | ------- |
Overexcitation  Underexcitation  Overexcitation  Underexcitation
| P required  | MV  11  | 11  | -11  | -11  |
| ----------- | ------- | --- | ---- | ---- |
at PCC
| S required  | MVA  11.58  | 11.58  | 11.58  | 11.58  |
| ----------- | ----------- | ------ | ------ | ------ |
at PCC
| Q required  | MVAR  3.62  | -3.62  | 3.62  | -3.62  |
| ----------- | ----------- | ------ | ----- | ------ |
at PCC
| Power  | -  0.95  | -0.95  | 0.95  | -0.95  |
| ------ | -------- | ------ | ----- | ------ |
factor at
PCC
| P required  | MW  11.37  | 11.36  | -10.64  | -10.64  |
| ----------- | ---------- | ------ | ------- | ------- |
at PCS
| S required  | MVA  12.37  | 11.61  | 11.68  | 10.91  |
| ----------- | ----------- | ------ | ------ | ------ |
at PCS
© 2026 Envision Energy. All Rights Reserved.

Conf idential and privileged information. Any unauthorised review, use, disclosure, or

distribution is prohibited without written consent from Envision Energy.

10
Q required MVAR 4.87 -2.37 4.82 -2.42
at PCS
Power - 0.92 -0.98 0.91 -0.98
factor at
PCS
PQ Required and Provided By PCS at PCC Level at 0.9 PU
*Note that the above power flow calculation results are only valid when the PCS terminal voltage is within 0.9–1.1 pu
range.
6 Conclusion
This document describes and proposes 2 sets ENS-D06G-24120-10100-000 for the Sri Lanka
11MW/44MWh BESS project. It outlines the essential parameters of the DC unit of the BESS
with representative images of the DC containers, including details of the performance curves,
State of Health (SoH) of battery and Round-Trip Efficiency (RTE) of the battery in accordance
with the project's stipulated requirement. The yearly usable energy capacity of the system has
also been presented in the performance curve table throughout the design life of the project.
Whilst every effort has been taken to ensure accuracy of the report, we reserve all rights to
amend and update our materials, data and images without providing prior notification. We
remain committed to providing you our best support.
© 2026 Envision Energy. All Rights Reserved.
Conf idential and privileged information. Any unauthorised review, use, disclosure, or
distribution is prohibited without written consent from Envision Energy.