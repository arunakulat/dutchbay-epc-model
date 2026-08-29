Fire Protection System Specification
ENS-D10
错误!未知的 EE-FPS-ENS-D10 Version 2.0 Released

Disclaimer
While every precaution has been taken in the preparation of this document, Envision Energy Co., Ltd
(hereinafter refers to as “Envision Energy”) assumes no liability with respect to the operation or use of
Envision Energy products and documentation described herein.
Envision Energy shall not be liable for any act or omission concerning the products or documentation,
interruption of service, loss or interruption of business, loss of anticipatory profits, or punitive, incidental,
or consequential damages in connection with the furnishing, performance, or any use of Envision Energy
products or documentations provided herein.
Please use the latest version of the applicable specifications. Figures of this documentation do not
necessarily reflect the exact scope of supply. The actual scope of supply is subject to technical alterations at
any time.
© Envision Energy. All Rights Reserved.

VERSION HISTORY
| Version  | Date           | Designer   | Reviewed By  | Description      |
| -------- | -------------- | ---------- | ------------ | ---------------- |
| 1.0      | Sep. 30, 2025  | Chi Zhang  | Xiangyu Ge   | Initial release  |
|          | Feb. 06, 2026  | Zhiyi Pu   | Chi Zhang    | Edit Typos       |
1.1
Updated general arrangement based on
updated number of aerosol dispensers
| 1.2  | Feb. 11, 2026  | Zhiyi Pu  | Chi Zhang  |     |
| ---- | -------------- | --------- | ---------- | --- |
(Figure 1)
Updated responsive actions (Table 2)
Updated according to the system
| 2.0  | May. 21, 2026  | Zhiyi Pu  | Chi Zhang  |     |
| ---- | -------------- | --------- | ---------- | --- |
configuration modification
|     |     |     |     |     |
| --- | --- | --- | --- | --- |

|     |     |     |     |     |
| --- | --- | --- | --- | --- |
© Envision Energy. All Rights Reserved.

CONTENTS
1. DESIGN THEME ........................................................................................................................... 1
2. FIRE PROTECTION SYSTEM GENERAL ARRANGEMENT ..................................................................... 2
3. FIRE ALARM SETTINGS AND CONTROL LOGIC................................................................................. 4
4. FIRE PROTECTION SYSTEM COMPONENTS ..................................................................................... 6
4.1 Heat and Smoke Sensors ................................................................................................................................... 6
4.2 Combustible Gas Sensors................................................................................................................................... 6
4.3 Alarm System ..................................................................................................................................................... 7
4.4 Active Ventilation System .................................................................................................................................. 7
4.5 Deflagration Panel ............................................................................................................................................. 8
4.6 Aerosol ............................................................................................................................................................... 8
4.7 Fire Alarm Control Panel .................................................................................................................................... 9
© Envision Energy. All Rights Reserved.

1. DESIGN THEME
Envision Energy's fire safety strategy is rooted in the ethos of "putting prevention first and combining
prevention and containment." Our approach focuses on preventing and containing thermal runaway events
through a multi-tiered safety protocol covering prevention, detection, suppression, and containment.
Central to our philosophy is the thorough understanding of the thermal runaway mechanisms and mitigating
the risks accordingly with efficiency. Envision Energy's comprehensive fire safety design and protocols
address every facet of fire prevention, detection, suppression, and containment.
Prevention by Design:
• Advanced raw material recipe and engineering to improve lithium-ion battery’s intrinsic safety.
• Implementation of rigorous manufacturing management and quality control protocols to ensure
exceptional cleanliness and performance uniformity throughout the lengthy battery manufacturing
process.
Early Detection:
• Deployment of gas detection systems, including hydrogen, carbon monoxide sensors, to identify off-
gassing concentrations and facilitate rapid response and early risk mitigation.
• Integration of a Battery Management System (BMS) with a three-layer control topology, actively
monitoring and regulating cell parameters to prevent failures and maintain optimal performance.
Suppression and Containment:
• Implementation of total-flooding fire suppression systems to ensure effective and precise suppression
of fire incidents.
• Adoption of fire-resistant enclosure designs to prevent thermal propagation under sustained large-scale
fire conditions.
© Envision Energy. All Rights Reserved. CONFIDENTIAL Page 1 of 9

2.  FIRE PROTECTION SYSTEM GENERAL ARRANGEMENT
The fire protection system detects, alarms, and suppresses thermal runaway events at early stage. Each
modular battery segment is equipped with smoke sensor, heat sensor, and combustible gas sensors to swiftly
identify potential risks of battery or electrical fires. The active ventilation and deflagration venting system
are designed to NFPA 69 and 68.
Battery Segment  Combined Segment
Figure 1. General arrangement of fire protection system of ENS-D10

Table 1 Key components of the fire protection system (ENS-D10)
| Battery Segment  | Combined Segment  |     |
| ---------------- | ----------------- | --- |
Fire Protection System
Components
| # per Segment             | # per Segment  |     |
| ------------------------- | -------------- | --- |
| Smoke sensor              | 1              | 1   |
| Heat sensor               | 1              | 1   |
| Combustible gas sensor    | 1              | 1   |
| Aerosol dispenser         | 4              | 6   |
| Ventilation system        | 1              | 1   |
| Fire alarm control panel  | 0              | 1   |
| Manual release button     | 0              | 1   |
Emergency stop
|     | 0   | 1   |
| --- | --- | --- |
(for aerosol release)
| Fan start/stop button          | 0   | 1   |
| ------------------------------ | --- | --- |
| Horn strobe (Red/White)        | 0   | 2   |
| Deflagration panel (optional)  | 2   | 3   |
© Envision Energy. All Rights Reserved.  CONFIDENTIAL  Page 2 of 9

Figure 2 General arrangement of fire protection system of ENS-D6
Table 2 Key components of the fire protection system (ENS-D6)
ENS-D6
Fire Protection System Components
# per Segment
Smoke sensor 1
Heat sensor 1
Combustible gas sensor 1
Aerosol dispenser 6
Ventilation system 1
Fire alarm control panel 1
Manual release button 1
Emergency stop
1
(for aerosol release)
Fan start/stop button 1
Horn strobe 2
Deflagration panel 3
© Envision Energy. All Rights Reserved. CONFIDENTIAL Page 3 of 9

@
3. FIRE ALARM SETTINGS AND CONTROL LOGIC
A two-level alarm setting is implemented for the system. The level 1 alarm is triggered by any one of the
smoke sensors, temperature sensors, or combustible gas sensors within the entire system. The level 2 alarm
is activated by triggering heat sensor and smoke sensor simultaneously within an individual segment.
Table 3 Fire alarm levels and responsive actions
Alarm Levels Conditions Responsive Actions
Alarm bell is triggered.
A: Smoke sensor is triggered
Charging or discharging is disabled for the entire system.
Alarm bell is triggered.
B: Heat sensor is triggered
Level 1 Charging or discharging is disabled for the entire system.
Warning:
For the entire system:
A/B/C
• Alarm bell is triggered.
C: Combustible gas sensor in the
• Charging or discharging is disabled
battery compartment
For the segment with triggered sensor:
• Active ventilation system starts up.
For the entire system:
• Horn strobe is triggered.
A: Smoke sensor and heat sensor • Battery charging or discharging is disabled.
in the same segment For the segment with triggered sensors:
Level 2 • Aerosol system is initiated with a 30-second
Alarming: delay.
A/B For the entire system:
• Horn strobe is triggered.
B: Aerosol is manually initiated • Battery charging or discharging is disabled.
• Aerosol system is initiated for all segments with a
30-second delay.
Component
FPS component failure Warning message transmitted to EMS and SCADA
failure
© Envision Energy. All Rights Reserved. CONFIDENTIAL Page 4 of 9

Figure 3 Fire suppression control logic
Figure 4 Active ventilation control logic
© Envision Energy. All Rights Reserved. CONFIDENTIAL Page 5 of 9

4.  FIRE PROTECTION SYSTEM COMPONENTS
4.1 Heat and Smoke Sensors
The heat and smoke sensors are installed to detect temperature abnormalities and smoke release at early
stage of thermal runaway events. Both heat and smoke sensors are securely mounted with anti-loosening
fasteners and designed with anti-interference signal transmission capabilities.
Table 4 General specification: heat and smoke sensor
| Specifications     | Smoke Sensor    | Heat Sensor     |
| ------------------ | --------------- | --------------- |
| Sensor Type        | Point detector  | Point detector  |
| Operating Voltage  | 10 – 30 VDC     | 10 – 30 VDC     |
Opto-electronic measuring
Reliable response behavior for slow and
| Key Features  | chamber provides excellent  |     |
| ------------- | --------------------------- | --- |
rapid temperature rises
detection of smoke particles
|     | EN54-7  | EN 54-7  |
| --- | ------- | -------- |
Code Compliance
|     | CE, LPCB, VdS  | CE, LPCB, VdS  |
| --- | -------------- | -------------- |

4.2 Combustible Gas Sensors
Each modular battery segment and combined segment is equipped with one combustible gas sensor. An
alarming signal is generated once the gas concentration reaches 10% LFL or other pre-set thresholds.
Table 5 General specification: combustible gas sensors
Combustible Gas Sensor Specifications
| Operating Voltage  24 VDC  |     |     |
| -------------------------- | --- | --- |
| Current Loop  4 – 20 mA    |     |     |
| Measuring Range  10%LEL    |     |     |
| Code Compliance  CE, ETL   |     |     |

|     |     |     |
| --- | --- | --- |
© Envision Energy. All Rights Reserved.  CONFIDENTIAL  Page 6 of 9

4.3 Alarm System
The alarming system consists of an alarm bell and a horn strobe. The alarm bell is triggered under level 1
fire alarm, where a single sensor is activated. The horn strobe is triggered under level 2 fire alarm, where
the heat and smoke sensors are activated simultaneously.
Table 6 General specification: alarm bell and horn strobe
| Specifications     | Alarm Bell  | Horn Strobe  |
| ------------------ | ----------- | ------------ |
| Operating Voltage  | 24 VDC      | 24 VDC       |
Sound Output
|     | NA  | 800Hz to 950Hz swept at 9Hz  |
| --- | --- | ---------------------------- |
Frequency
| Flash Rate            | NA           | 1 per second  |
| --------------------- | ------------ | ------------- |
| Sound Pressure Level  | 96 dB at 1m  | 100 dB at 1m  |
| Code Compliance       | CE, LPCB     | CE, LPCB      |

4.4 Active Ventilation System
The active ventilation system consists of electrically actuated ventilation louvers, explosion-proof fans,
and a central controller. The active ventilation system is linked with the hydrogen and carbon monoxide
detectors to receive start and stop commands.
Once the gas concentration is detected above the pre-set thresholds, the electric louvers are opened,
and the explosion-proof fan starts to discharge until the combustible gas concentration falls below the
pre-set values.
Table 7 General specification: active ventilation
| General Specification  | Exhaust Fan  |     |
| ---------------------- | ------------ | --- |
| Rated Voltage          | DC 24V       |     |
Nominal Operating
1000 CFM
Airflow
| Protection Class        | IP55              |     |
| ----------------------- | ----------------- | --- |
| Explosion-Proof Rating  | Ex-d IIC T4       |     |
| Code Compliance         | CE, ATEX, IEC-Ex  |     |

|     |     |     |
| --- | --- | --- |
© Envision Energy. All Rights Reserved.  CONFIDENTIAL  Page 7 of 9

4.5 Deflagration Panel
A deflagration vent panel serves as a crucial safety component designed to release pressure in the event
of a sudden pressure build-up, preventing potential damage to the enclosure. The deflagration panels are
installed on the top of the enclosure. When the pressure within the enclosure exceeds the static opening
pressure threshold (typically around 0.1 bar), the vent panel is designed to passively open to relieve the
pressure. This passive deflagration mechanism minimises the risk of structural damage or catastrophic
failure of the enclosure.
The sizing and design of the explosion vent panel is carried out according to NFPA 68 and EN 14797.
Table 8 General specification: deflagration panel
Deflagration General Specifications
IP Rating IP 55
Material 316L stainless steel
Static Activation Pressure 0.1 bar-g
Code Compliance CE, ATEX, EN 14797, EN 14994, NFPA 68
4.6 Aerosol
Table 9 General specification: aerosol system
Aerosol System Specifications
Operating Voltage 24 VDC
Initiating Current ≤ 2A
Operating Temperature -40 – 50
℃
Storage Temperature -45 – 60
℃
Operating Humidity Relative humidity ≤ 100%
Code Compliance CE (EN 15276-1&2), BSI
© Envision Energy. All Rights Reserved. CONFIDENTIAL Page 8 of 9

4.7 Fire Alarm Control Panel
The fire alarm control panel (FACP) aggregates addressable signals from sensors and responds to a
potential thermal runaway event. The FACP is installed in the combined segment, supervising the sensor
status throughout all modular segments with the EN 10 system platform. Backup power is supplied by
batteries to sustain continuous alarming for at least 2 hours and essential communication functions for
24 hours.
Table 10 General specification: FACP
FACP Specifications
Rate Voltage 230 Vac
Dimensions (L x H x T) 436 x 402 x 185 mm
Backup Battery 12V, 12Ah
Code Compliance CE (EN 54-2&4, EN 12094-1)
© Envision Energy. All Rights Reserved. CONFIDENTIAL Page 9 of 9
