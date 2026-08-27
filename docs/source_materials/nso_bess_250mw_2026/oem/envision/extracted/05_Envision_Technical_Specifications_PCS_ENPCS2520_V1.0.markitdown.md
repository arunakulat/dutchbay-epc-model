Technical Specifications
of Power Conversion System
ENPCS-2520
Confidential ENPCS-2520 Version 1.0 Release

DISCLAIMER
While every precaution has been taken in the preparation of this document, Envision Energy
Co., Ltd (hereinafter refers to as “Envision Energy”) assumes no liability with respect to the
operation or use of Envision Energy products and documentation described herein.
Envision Energy shall not be liable for any act or omission concerning the products or
documentation, interruption of service, loss or interruption of business, loss of anticipatory
profits, or punitive, incidental, or consequential damages in connection with the furnishing,
performance, or any use of Envision Energy products or documentations provided herein.
Please use the latest version of the applicable specifications. Figures of this documentation
do not necessarily reflect the exact scope of supply. The actual scope of supply is subject to
technical alterations at any time.
© Envision Energy. All Rights Reserved.

CONTENTS
1. INTRODUCTION ........................................................................................................................... 1
1.1. PCS Functions..................................................................................................................................................... 1
2. PCS PARAMETERS........................................................................................................................ 3
3. INVERTER TECHNICAL CHARACTERISTICS ...................................................................................... 5
3.1. General Control Functionality ............................................................................................................................ 5
3.2. Power De-Rating due to Temperature .............................................................................................................. 8
3.3. Power De-Rating due to Altitude ....................................................................................................................... 9
3.4. Power De-Rating due to Variations in the PCS Voltage ................................................................................... 10
3.5. Efficiencies ....................................................................................................................................................... 11
3.6. PQ Curve .......................................................................................................................................................... 11
4. POWER QUALITY ....................................................................................................................... 13
4.1. Frequency Range ............................................................................................................................................. 13
4.2. Voltage Range .................................................................................................................................................. 13
5. GRID FOLLOWING TECHNOLOGY AND CAPABILITY ....................................................................... 13
5.1. Response Time and Control Accuracy ............................................................................................................. 13
5.2. Harmonics ........................................................................................................................................................ 15
5.3. Voltage Control ................................................................................................................................................ 16
5.4. Fast Frequency Control .................................................................................................................................... 16
5.5. Islanding Detection “Anti-Islanding” ........................................................................................................... 16
5.6. Low / High Voltage Ride-Through (LVRT / HVRT) ............................................................................................ 17
5.6.1. Low Voltage Ride Through (LVRT) ............................................................................................................... 17
5.6.2. High Voltage Ride Through (HVRT) ............................................................................................................. 18
5.7. Short Circuit Contributions .............................................................................................................................. 19
6. GRID FORMING TECHNOLOGY AND CAPABILITY ........................................................................... 19
© Envision Energy. All Rights Reserved.

1. INTRODUCTION
Introducing our cutting-edge PCS, designed and manufactured in compliance with the industry-
standard IEC/EN 62477-1, IEC/EN 61000-6-2 and IEC/EN 61000-6-4. These standards, developed by the
International Electrotechnical Commission (IEC), ensure that our PCS is safe, reliable, and able to
perform its function to the highest level of efficiency and quality.
IEC/EN 62477-1 is a standard for the safety of power electronic converter systems and equipment,
which ensures that our PCS meets the safety requirements for power electronic systems and
equipment.
IEC/EN 61000-6-2 covers the electromagnetic compatibility (EMC) requirements for residential,
commercial, and light-industrial environments, meaning that our PCS is designed to operate with
minimal interference to other electronic equipment and minimal emission of electromagnetic
interference.
IEC/EN 61000-6-4 is for EMC requirements for industrial environments, which ensures that our PCS will
operate effectively in harsh industrial environments, while also minimizing the emission of
electromagnetic interference.
By adhering to these standards, we ensure that our PCS is safe, reliable, and able to perform its function
to the highest level of efficiency and quality, while also being compliant with the latest international
standards and regulations. This guarantees the performance and longevity of our product and
guarantees that it will exceed your expectations.
Envision’s energy storage PCS is comprised of a bidirectional DC / AC converter, a control unit and more.
The PCS controller receives control instructions from the background through communication, directing
the converter to charge or discharge batteries based on the power instructions' symbol and magnitude.
This adjustment helps regulate the active and reactive power supplied to the grid. The PCS
communicates with the BMS via a CAN interface and dry contact to obtain information about the bank's
state. This facilitates protective charging and discharging of batteries, ensuring their safe operation.
1.1. PCS Functions
The PCS performs several functions, as outlined below:
• On-Grid Operation: During on-grid operation, the PCS autonomously monitors grid voltage
and frequency, efficiently managing bidirectional converter control. It enables precise
adjustment of both active and reactive power individually, allowing intelligent management
of bank-level charging and discharging processes.
• Protection: The PCS incorporates various protection functions to ensure the safe, reliable, and
continuous operation of the system. Key protection functions include short-circuit protection,
DC reverse connection protection, battery overcurrent protection, hardware fault protection,
and overload protection, among others.
© Envision Energy. All Rights Reserved. Page 1 of 24

• Display and Communication: A web monitoring interface is provided for parameter
configuration and displaying system status and fault information. The equipment supports
communication protocols such as Modbus RTU, Modbus TCP / IP, ensuring reliable
communication with SCADA / EMS and the reception of power dispatch commands.
• Other Functions: The PCS incorporates functions such as power factor adjustment, reactive
power compensation, and active power adjustment.
© Envision Energy. All Rights Reserved. Page 2 of 24

2. PCS PARAMETERS
Table 1: PCS parameters.
Item ENPCS-2520
Parameters on AC System
AC Connection Three-phase three-wire
Rated Power 2520 kW
110%: 10 min@45 degree
Overload Capacity 110%: Continuous @ 40 degree
120%: 1 minute @ 35 degree
The Rated Voltage on the AC
690 V
Side
Rated Current 2109 A
Rated Grid Frequency 50 Hz (consistent with grid frequency)
Current Waveform THD Compliance with IEEE 519
Power Factor Range [λ] -0.95-0.95
Power Control Deviation ≤ 2%
DC Component 0.5% (at rated current)
Parameters on DC System
DC Voltage Range 1000 – 1500 V
Full-Power DC Voltage
1165 – 1500 V
Range
Voltage Regulation
±2%
Accuracy
Current Regulation
±2%
Accuracy
Protection
© Envision Energy. All Rights Reserved. Page 3 of 24

LVRT Yes
HVRT Yes
Anti-Islanding Protection Yes
AC Over Current / Short
Yes
Circuit Protection
AC Over-Voltage /
Undervoltage
Yes
Protection
AC Over / Under-Frequency
Yes
Protection
Phase Sequence Error
Protection of AC Incoming Yes
Line
DC Over Current / Short
Yes
Circuit Protection
DC Over Voltage /
Undervoltage
Yes
Protection
DC Reverse Polarity
Yes
Protection
Over Temperature
Yes
Protection
Power Module (IGBT)
Yes
Protection
Communication Fault
Yes
Protection
Cooling System Fault
Yes
Protection
DC Component Over-
Yes
Standard
© Envision Energy. All Rights Reserved. Page 4 of 24

Protection
Yes
Fault Recording
No less than 4 cycles, 8 channels.
System
From when a power
dispatch instruction is
Power Response Speed < 30 ms
received in the hot standby
state.
Mutual switchover time
from 100%.
Charge-Discharge
< 30 ms
Charging at rated power to
Switchover Time
100% discharging at rated
power.
Enclosure Protection Class IP65
Cooling Method Liquid cooling
Communications Interface Ethernet / CAN / RS485 (Standard: Modbus, TCP)
Operating Environment
Operating Temperature -30 – 60 (derating above 45 )
Storage Temperature -40 – 70℃ ℃
Allowable Relative Humidity 0 – 100%℃
Altitude No derating at ≤ 2000 m
IEC 62477, IEC61000, IEC 62909-1, IEC 62509, IEC 62109,
Compliance
IEC62271-202, EN 50549, IEC 50530, IEEE 519, G99 etc.
3. INVERTER TECHNICAL CHARACTERISTICS
3.1. General Control Functionality
• The PCS is capable of receiving control instructions from the monitoring system to charge and
discharge the battery.
© Envision Energy. All Rights Reserved. Page 5 of 24

• The PCS can process various alarms of the battery management system (BMS) to ensure
battery safety. Charging and discharging will cease immediately if any warning signal is
received from the BMS or if the terminal voltage of the battery unit reaches the maximum
charging threshold. The PCS also automatically halts charging if the cell voltage monitoring
circuit in the BMS fails or if communication between the PCS and the BMS is disrupted.
• Users have the option to schedule charging and discharging of the PCS using a timer.
• Both AC and DC sides of the PCS are equipped with breaker components and have emergency
shutdown functions. The AC output side of each PCS is equipped with a circuit breaker to
ensure safe isolation from the low-voltage side of the boost transformer.
The PCS has a complete set of protection features, including:
• Low voltage ride through.
• High voltage ride through.
• Island effect protection.
• AC overcurrent / short circuit protection.
• AC overvoltage / undervoltage protection.
• AC over frequency / underfrequency protection.
• AC input phase sequence error protection.
• DC overcurrent / short circuit protection.
• DC overvoltage / undervoltage protection.
• DC polarity reverse protection.
• Over-temperature protection.
• Power module (IGBT) protection.
• Communication fault protection.
• Cooling system fault protection.
• DC component out-of-specification protection.
The PCS device has the following features to support the power grid:
• The PCS can automatically synchronise with the power grid.
© Envision Energy. All Rights Reserved. Page 6 of 24

• The AC component uses LC filtering, in combination with the current repetition control
technology to reduce output current harmonics, proportional-resonant control technology to
suppress specific sub-grid-connected current harmonics, dead-zone compensation
technology to reduce grid-connected current harmonics caused by IGBT switching dead-zone,
and converter modulation algorithm switching technology to reduce grid-connected current
harmonics under low load rate conditions to ensure that the quality of power delivered to the
power grid meets the current power grid requirements to the maximum extent.
• Active power control.
When the active power command is a fixed value, the PCS outputs a constant power
o
value. The active power does not vary with frequency and voltage under normal
operating conditions.
The PCS can control its active power output by following the instructions from the
o
energy storage energy management system. In standby mode, the time from
receiving the power scheduling command to responding to the power output shall
not exceed 100 ms, and the power output shall not exceed the maximum allowable
power of the PCS.
• Voltage/reactive power regulation.
When the reactive power is constant, the PCS can output a constant power, and the
o
reactive power does not vary with frequency and voltage.
The PCS can track and regulate the reactive power output in real time by following
o
the control instructions from the monitoring system in the energy storage power
station.
The power factor at rated power is adjustable between -1~1
o
• Necessary current limiting measures shall be taken at any stage of charging according to the
needs of the battery to avoid damage.
• The PCS has high and low voltage ride-through capabilities.
• The PCS has a certain ability to tolerate system frequency anomalies.
• The PCS supports primary frequency modulation.
© Envision Energy. All Rights Reserved. Page 7 of 24

3.2. Power De-Rating due to Temperature
Temperature de-rating is the reduction of the inverter's maximum power output as temperature
increases. This is necessary as the inverter performance typically decreases with temperature
increases due to factors such as decreased component efficiency, increased conductor resistance,
and reduced cooling capacity. The maximum operating temperature and a de-rating factor are
used to calculate the maximum power output at a given temperature. This helps to prevent
overheating and damage to the inverter and ensures stable power delivery to the grid.
Figure 1: Temperature de-rating of Envision’s inverter.
© Envision Energy. All Rights Reserved. Page 8 of 24

3.3. Power De-Rating due to Altitude
Inverter power de-rating due to altitude refers to the decrease in power output of the inverter as
the altitude increases. This is because the air density decreases at higher altitudes, which reduces
the cooling efficiency of the inverter. As a result, the inverter must be de-rated to prevent
overheating and ensure safe operation.
Envision propose power de-rating when altitude is above 2000 m.
110%
100%
90%
80%
70%
60%
50%
40%
30%
20%
10%
0%
-10% 0 1000 2000 3000 4000
-20%
-30%
-40%
-50%
-60%
-70%
-80%
-90%
-100%
-110%
Figure 2: Altitude de-rating curve of Envision’s inverter.
© Envision Energy. All Rights Reserved. Page 9 of 24
nS/S
Atitude/m

3.4. Power De-Rating due to Variations in the PCS Voltage
The inverter performance typically decreases with voltage increases due to factors such as
decreased component efficiency, increased conductor resistance, and increased power losses.
The maximum operating voltage and a derating factor are used to calculate the maximum power
output at a given voltage. This helps to prevent damage to the inverter and improve power quality
by reducing voltage fluctuations and harmonics. Note that for this current-source inverter (CSI),
the voltage derating results in a higher power factor.
Figure 3: Apparent power vs AC voltage (left) and vs DC voltage (right).
© Envision Energy. All Rights Reserved. Page 10 of 24

3.5.  Efficiencies
The PCS efficiency which determines how much net DC power is generated and is converted to
AC power is generally variable. These variations depend on the loading, as well as the voltages of
the inverter and rectifier. The rectifier and inverter efficiency as a function of varying DC voltage
and operating power are given in Table 2.
Table 2: Inverter efficiency as a function of varying DC voltage
AC side power point
Udc (V)
|                 | 33% Pn   | 100% Pn  |
| --------------- | -------- | -------- |
| U  (Discharge)  | 98.851%  | 98.396%  |
max
| U (Discharge)  | 98.965%  | 98.436%  |
| -------------- | -------- | -------- |
mid
| U (Discharge)  | 99.053%  | 98.501%  |
| -------------- | -------- | -------- |
min
| U  (Charge)  | 98.817%  | 98.244%  |
| ------------ | -------- | -------- |
max
| U (Charge)  | 98.914%  | 98.297%  |
| ----------- | -------- | -------- |
mid
| U min  (Charge)  | 99.004%  | 98.352%  |
| ---------------- | -------- | -------- |

3.6.  PQ Curve
The PQ curve is a graphical representation of the inverter's operating range, showing the active
power (P) and reactive power (Q) it can supply to the grid. It determines the inverter's operating
limits and can be used to optimize its operation and assess its power quality.
© Envision Energy. All Rights Reserved.  Page 11 of 24

Figure 4: To avoid any doubt, the capability is limited by the apparent current which is 1.1 pu of rated current (P=2520 kW, U=1, Power factor=1).
And the maximum apparent power is 110% of P rated (2520kW).
© Envision Energy. All Rights Reserved. Page 12 of 24

4. POWER QUALITY
4.1. Frequency Range
Table 3: Requirements for frequency ranges.
Frequency
Requirements
Range (Hz)
The PCS shall not be charged.
< 47 The PCS shall determine whether to separate from the grid based on the minimum
allowable frequency or the requirements of the grid dispatch centre.
The PCS being charged shall be switched to discharging within 0.2 s. If it does not have
the discharging condition or under other special circumstances, it shall be separated
47 – 47.5
from the grid within 0.2 s.
The PCS being discharged shall operate for 30 mins.
47.5 – 51.5 Operation with normal charging or discharging.
The PCS being discharged shall be switched to charging within 0.2 s. If it does not have
the charging condition or under other special circumstances, it shall be separated from
51.5 – 52
the grid within 0.2 s.
The PCS being charged shall operate for 30 mins.
The PCS shall not be discharged.
> 52 The PCS shall determine whether to separate from the grid based on the maximum
allowable frequency.
NOTE: The PCS software parameters can be adjusted to the local grid code frequency protection
requirements.
4.2. Voltage Range
Table 4: Runtime modes for voltage ranges.
Voltage Range (UN) Runtime
110% – 130% HVRT
90% – 110% Continuous operation
0% – 90% LVRT
NOTE: The PCS software parameters can be adjusted to the local grid code voltage protection
requirements.
5. GRID FOLLOWING TECHNOLOGY AND CAPABILITY
5.1. Response Time and Control Accuracy
© Envision Energy. All Rights Reserved. Page 13 of 24

Response time and ramp rate are closely related but are distinct parameters that describe the
performance of an energy storage system inverter. Response time, also known as reaction time,
measures the amount of time it takes for an inverter to respond to a change in grid conditions. It
is the time interval between a grid event (i.e. a disturbance, a drop or an increase in voltage) and
the inverter's reaction (i.e. starting to increase or decrease power). Meanwhile, ramp rate
measures the rate at which the power output of an inverter can change, usually measured in watts
per second (W/s) or as a percentage of the rated power per second. The importance of both
parameters is crucial for ensuring stability of the grid and protecting the equipment from damage.
While both parameters are closely related, the main distinction between them lies in their focus:
response time refers to the reaction time, while ramp rate is the change of power output.
The response time is defined in Figure 5.
Figure 5: Example of step response.
• Reaction time is the time interval between when the power order is sent and the initial moment
when the inverter starts to inject.
• Rise time is the time needed by the inverter to go from point t (10% of the reference value) to
1
point t (90% of the reference value).
2
• Response time is the time interval between t to t .
0 2
• Settling time is the time between the moment in which the inverter reacts to power command
(t ) and the moment in which the power is stabilized within +/-2% of the set point (t ).
0 3
© Envision Energy. All Rights Reserved. Page 14 of 24

These times strongly depend on the inverter internal control configuration and the grid conditions
(SCR and X/R ratio) measured at the inverter terminals.
Table 5: Dynamic response of Envisions PCS in grid following mode
Reaction Time Response Time Setting Time
≤ 5 ms ≤ 30 ms ≤ 50 ms
5.2. Harmonics
Power harmonics refer to the presence of unwanted frequencies in the electrical system that can
cause problems such as equipment malfunction and power loss. Inverters, as power electronic
devices, can generate harmonic currents that can affect the quality of power. Harmonics occur as
integer multiples of the fundamental frequency which is typically 50 Hz or 60 Hz in electronic
power grids. Harmonic currents cause voltage drops, which superimpose the nominal grid voltage
resulting in distortion of the sine wave of the grid voltage. Harmonics can be generated by non-
linear loads or from power electronic means with high frequent switching transistors (inverter for
example). The International Electrotechnical Commission (IEC / EN) has established standards for
power harmonics in IEEE 519. These standards include limits on the harmonic distortion levels,
specifically, the Total Harmonic Distortion (THD) should not exceed 3% and the individual
harmonic components should not exceed the limits specified in the standard.
Envision’s PCS adheres with the IEEE 519 requirements concerning harmonics. For a
comprehensive understanding of harmonic current injection, we can provide a detailed report
upon request.
© Envision Energy. All Rights Reserved. Page 15 of 24

5.3. Voltage Control
It could work as a reactive power source and be controlled by the whole plant control system to
control the voltage at the plant connection point.
5.4. Fast Frequency Control
PCS supports the primary frequency control (frequency droop control) and the inertia control. It
could also work as an active power source and be controlled by the whole plant control system
to release the frequency droop control at the plant connection point.
5.5. Islanding Detection “Anti-Islanding”
Islanding refers to the operation of a power grid as an isolated system, disconnected from external
transmission lines. This can occur intentionally, as a planned outage or maintenance procedure,
or unintentionally, due to a fault in the transmission system or a natural disaster. When a power
grid is islanded, it must rely on local generation sources, such as solar panels or wind turbines, to
meet the energy demands of the area. Islanding can be a challenge for power systems because it
can be difficult to maintain a stable frequency and voltage without the support of external
transmission lines. Envision’s inverters play a key role in islanded power systems by converting
the direct current (DC) power produced by local generation sources into alternating current (AC)
power, which can be used by consumers.
With the function of active islanding detection, the PCS could disconnect from the grid within 2
seconds after grid failure.
Figure 6 shows the field test data of active islanding detection. It shows the PCS disconnects from
the grid within 840 ms.
© Envision Energy. All Rights Reserved. Page 16 of 24

Load Voltage
Load Current
Grid Current
Load Voltage
Load Current
Grid Current
Figure 6: Field test data of active islanding detection.
5.6. Low / High Voltage Ride-Through (LVRT / HVRT)
Voltage ride-through refers to the ability of the inverter to maintain its connection to the grid
during voltage sags or dips. LVRT is the ability of the inverter to continue operating and supplying
power to the grid during low voltage events, while HVRT is the ability to do the same during high
voltage events. Maintaining a connection to the grid during voltage fluctuations is important for
the stability and reliability of the power system.
The PCS can remain electrically connected to the utility grid system during certain voltage dip
events (fault events). This functionality is known as ‘Fault Ride Through’.
5.6.1. Low Voltage Ride Through (LVRT)
The profile that the PCS can ‘ride through’ remains within the limits shown in Figure 7.
If the voltage dip is deeper or lasts longer than the specified settings the PCS may be
disconnected from the grid. Envision’s PCS LVRT capability could cover global different
requirements as shown in the figure below.
© Envision Energy. All Rights Reserved. Page 17 of 24

Figure 7: LVRT curve demonstrating that the PCS can ‘ride through’ low voltage events.
5.6.2. High Voltage Ride Through (HVRT)
The profile that the PCS can ‘Ride Through’ remains within the limits shown in Figure 8.
Figure 8: HVRT curve demonstrating that the PCS can ‘ride through’ high voltage events.
© Envision Energy. All Rights Reserved. Page 18 of 24

5.7. Short Circuit Contributions
When the grid experiences a failure, the AC voltage of the PCS decreases. To maintain stability,
the inverter will enter an LVRT phase to supply reactive current to the power grid and control
overcurrent. According to testing, when the inverter is in charging or discharging mode and the
AC voltage drops below 10%, the maximum current that can be supplied by the inverter and
injected into the grid is 1.2 times the rated current. To account for any margin of error in actual
situations, it is considered that the maximum current supplied by the PCS during a grid failure is
1.3 times the rated current.
6. GRID FORMING TECHNOLOGY AND CAPABILITY
The PCS can run in both grid following and grid forming mode with seamless transition. It works
as a virtual synchronous generator like a voltage source and supports active power control,
reactive power control, virtual inertia, primary frequency control and voltage droop control. Also,
the PCS has a current control in its inner loop to make sure the equipment operates safety.
The different application scenario for grid forming and grid following is displayed in the table
below, while grid forming has irreplaceable advantages on weak grid and off grid modes.
Table 6: Application scenarios for grid forming and grid following.
Grid Following Grid Forming
Strong Grid Applicable. Applicable.
Applicable. Applicable.
Weak Grid
Limited transient response capability. Effective transient response.
Off Grid Not Applicable. Applicable.
The key technical functions of PCS for grid forming are shown below.
Table 7: Key functions of PCS for grid forming.
Functionalities Corresponding Control Blocks
Frequency Governor
Frequency Support & Stabilisation
Virtual Inertia
Voltage Support Automatic Voltage Regulator
Current limitation during faults & inrush Unit Control
Grid Strengthen when SCR < 2 Synthetic Impedance
© Envision Energy. All Rights Reserved. Page 19 of 24

Islanding Control Unit Control
The LVRT simulation comparison results between grid forming (GFM) and the enhanced grid
following (GFL) are shown below. The enhanced grid following is also referred to as grid
supporting in some literature, which integrates the primary frequency and voltage regulation in
the inverter to provide better frequency and voltage regulation during the transition. The
comparison shows that grid frequency and voltage when grid forming works are much better than
when the enhanced grid following is used.
Figure 9: LVRT simulation results comparing grid forming and grid following.
© Envision Energy. All Rights Reserved. Page 20 of 24

Phase jump is an important gird disturbance scenario, especially in a renewable dominated power
plant. The simulation result of 60° phase jump in a weak grid scenario for both GFM and enhanced
GFL strategies are displayed in figure 10. The figure depicts grid frequency being stabilized by the
virtual inertia of GFM.
Figure10: 60° phase jump simulation results.
© Envision Energy. All Rights Reserved. Page 21 of 24

The simulation result of P load step change comparison between GFM and enhanced GFL is
displayed in 11; GFM transient performance is seen to be much better than enhanced GFL.
Figure 11: P load step change simulation results.
© Envision Energy. All Rights Reserved. Page 22 of 24

PCS can transit between GFM and enhanced GFL mode seamlessly. Figure 12 shows the seamless
transition operation data. The PCS could keep the voltage, and the current of load has little
disruption.
Figure12: Seamless transition of grid following and grid forming mode.
In discussions on grid-forming inverters, it's essential to note that most of them are implemented
based on the power synchronization mechanism of synchronous machines. Consequently,
classical stability issues such as power angle stability persist. Notably, the aggregation scale of the
PCS is much larger than that of traditional synchronous power stations, while the average rated
power of each PCS is much smaller. This scenario poses challenges for the stable operation of a
large-scale aggregation of PCSs operating in VSG (Virtual Synchronous Generator) mode.
Envision employs virtual impedance emulation on PCSs based on large synchronous power station
models, tailored to match weak grids or island-operating renewable energy systems. By detecting
grid impedance, the output impedance of PCSs is adjusted to facilitate stabilized operation.
Moreover, stability is further enhanced with the deployment of more PCSs based on the same
impedance matching technology.
Envision has amassed considerable expertise in oscillation analysis and suppression, leveraging
widely used impedance theory in China's renewable power sector. Figure 13 illustrates the
simplified impedance theory. In scenarios with a high penetration rate of renewable energy in the
grid, sources like wind and solar power, along with PCSs, may oscillate with the grid, particularly
in weak grid conditions or grids with series-inductor compensators. Figure 14 demonstrates wind
turbine oscillation current, which can be detrimental to both the grid and wind power systems.
© Envision Energy. All Rights Reserved. Page 23 of 24

Figure 15 depicts oscillation suppression achieved through matched impedance based on
algorithm optimization.
Im
Stable
Z g (s)/Z t (s) Critical
Unstable
0
(-1, j0)
Re
I(s) Z(s)
g
I t (s) Z t (s) V g (s)
Turbine Grid
Figure13: System stability analysis based on impedance theory.
Figure 14 Wind turbine oscillation with grid.
Figure 15: Oscillation suppression with matched impedance.
© Envision Energy. All Rights Reserved. Page 24 of 24
