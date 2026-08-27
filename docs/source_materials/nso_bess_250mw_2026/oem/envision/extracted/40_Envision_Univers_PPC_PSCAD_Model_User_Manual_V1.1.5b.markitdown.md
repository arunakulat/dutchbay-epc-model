Envision Energy
Univers Power Plant Controller
PSCAD Model User Manual
Version 1.1.5b
2026-7-31
© Envision Energy. All Rights Reserved.

Doc. Title: Envision Energy Univers PPC PSCAD Model User Manual V1.1.5b
Disclaimer
While every precaution has been taken in the preparation of this document, Envision Energy assumes no liability
with respect to the operation or use of Envision Energy products and documentation described herein, for any
act or omission of Envision Energy concerning such products or this documentation, for any interruption of
service, loss or interruption of business, loss of anticipatory profits, or for punitive, incidental or consequential
damages in connection with the furnishing, performance, or use of the Envision Energy products and
documentation provided herein. Please use the applicable specifications in their latest versions. Images do not
necessarily reflect the exact scope of supply. The actual scope of supply can be subject to technical alterations at
any time.
© Envision Energy. All Rights Reserved. Page 1 of 12

Doc. Title: Envision Energy Univers PPC PSCAD Model User Manual V1.1.5b
Contents
1 Introduction .......................................................................................................................... 3
2 PPC Model Overview ............................................................................................................. 3
3 PPC Model Inputs and Outputs .............................................................................................. 4
3.1 Model Inputs ................................................................................................................................... 4
3.1.1 Measurement Inputs ........................................................................................................ 4
3.1.2 Command Inputs ............................................................................................................... 4
3.1.3 Controlled Equipment Information Inputs ....................................................................... 4
3.2 Model Outputs ................................................................................................................................ 5
4 PPC Model Control Functions and Parameters ....................................................................... 5
4.1 General Configurations ................................................................................................................... 5
4.2 Reactive Power and Voltage Control .............................................................................................. 6
4.3 Active power Control ...................................................................................................................... 7
4.4 Frequency Response ....................................................................................................................... 7
4.5 Inertia Response ........................................................................................................................... 10
4.6 Voltage lock logic .......................................................................................................................... 10
4.7 SVG Control ................................................................................................................................... 10
4.7.1 SVG dispatch logic ........................................................................................................... 10
4.7.2 SVG control inputs and outputs ...................................................................................... 11
© Envision Energy. All Rights Reserved. Page 2 of 12

Doc. Title: Envision Energy Univers PPC PSCAD Model User Manual V1.1.5b
1 Introduction
The Envision Energy EMS Power Plant Controller (PPC) PSCAD model is a simulation model developed
in PSCAD/EMTDC simulation software, used with Envision Energy wind turbine or BESS PCS PSCAD
model to support grid-connection simulation studies.
This document focuses on the model usage and the control functions with adjustable parameters of
the PPC model in PSCAD.
2 PPC Model Overview
The PPC model is provided within one PSCAD file together with Envision Energy WTG or PCS model
as shown in Figure 1 below, user could set parameters accordingly in the model menu by double
clicking on the module. The model is compatible with PSCAD V5.0.0 and later versions and supports
the Intel Fortran Compiler XE 15 and above. Model package folder name and model file name
indicates if it is compatible with 32bit or 64bit compiler.
Figure 1 PPC model representation in PSCAD
© Envision Energy. All Rights Reserved. Page 3 of 12
B
B E S S Fb k1
(MW |MVar|kV|kVA)
E n visio n
G FL-P C S
E S S C m d 1N = S ca l_ N u m b e r
(kW |kVar) V 1 1 0
(2 .7 5 x 2 ) x S ca l_ N u m b e r
A
3
6 0 .5 [M V A ]
3 [kV ] / 2 2 0 [kV
# 2 # 1
] Envisio n
PO C M eter
R = 0
I nI
B
B E S S Fb k1
(MW |MVar|kV|kVA)
E n visio n
G FL-P C S
E S S C m d 1N = S ca l_ N u m b e r
(kW |kVar) V 1 1 0
(2 .7 5 x 2 ) x S ca l_ N u m b e r
A
3
6 0 .5 [M V A ]
3 [kV ] / 2 2 0 [kV
# 2 # 1
]
P ccM e a s
(kW |kVar|kV|kV|kV|Hz|Hz/s)
P C C M e a s
Envisio n
PO C M eter
R = 0
I nI
P ccM e a s
(kW |kVar|kV|kV|kV|Hz|Hz/s)
P C C M e a s
PCS model for example
PPC model measurement
PPccccMMeeaass
PPC model
11 UUnniivveerrss PPPPCC
PPC commands sent to
PPC measurement 22
WTG/PCS models
input signals 33 VV11..11..77bb
PPCCCC MMeeaass
66 BBEESSSSCCmmdd11
((kkWW||kkVVaarr||kkVV||kkVV||kkVV||HHzz||HHzz//ss))
77 BBEESSSSCCmmdd11
BBEESSSSFFbbkk11 I n I n 44 WWTT//PPCCSS CCmmdd
dd
BBEESSSSFFbbkk11 mm 55 ((kkWW||kkVVaarr))
CC
33 PPC com Q U Q Umands input
PP
44 PPQQUUCCmmddIInn PPQQVV RReeff
PCS status input
((kkWW||kkVVaarr||kkVV||--||--))
PPC commands sent to SVG
models (if there are)
WWTT//PPCCSS IInnffoo
00
((kkVV||kkVVAA))
SSTTAATTCCOOMM CCmmdd
SSVVGG__eennaabbllee
((kkVVaarr))
00
SVG status input
00
SSTTAATTCCOOMM IInnffoo
SSVVGGrraattiinngg__kkVVaarr
((kkVVaarr||--))

Doc. Title: Envision Energy Univers PPC PSCAD Model User Manual V1.1.5b
The PPC model is able to control the active power and reactive power or voltage of its control point
and regulate the power to respond to frequency change with “PPC Enable” switched to Enable, or
either to work as an EMS dispatcher, bypassing all the closed controllers and directly dispatch active
power and reactive power commands to the WTG or PCS models, with “PPC Enable” switched to
Disable.
Up to four lumps of WTG or PCS can be controlled by the PPC model. In case more interface is
required for plant simulation, please contact Envision Energy to discuss.
The PPC model also provides SVG control function and relevant interfaces; however, please confirm
with Envision Energy on product feasibility for SVG control before conducting simulation studies.
3 PPC Model Inputs and Outputs
3.1 Model Inputs
3.1.1 Measurement Inputs
A PPC measurement module, as shown in Figure 2 below, has been prepared by Envision to provide
necessary measurement signals to the PPC model.
The module will provide real value measurements to the PPC model to conduct control functionalities.
User needs to locate the measurement module to the PPC control point and doesn’t need to any
setting; please keep the “PCC_Measure” signal name unchanged so that it can be read by PPC.
Figure 2 PPC measurement module
3.1.2 Command Inputs
The PPC model reads commands via the multi-dimension signal “PQUCmdIn”. It reads PPC signals in
sequence as below:
1) Active power setpoint in kW,
2) Reactive power setpoint in kVA,
3) Voltage setpoint in kV,
4) Power factor setpoint.
3.1.3 Controlled Equipment Information Inputs
To have the PPC model correctly calculate controlled capacity and have status of controlled lumps,
PPC needs to read terminal voltage and total capacity of each aggregated WTG or PCS model. This is
© Envision Energy. All Rights Reserved. Page 4 of 12

Doc. Title: Envision Energy Univers PPC PSCAD Model User Manual V1.1.5b

achieved via reading multi-dimension signal “WTfbk” from WTG model output or “BESSfbk” from PCS
model output. If more WTG or PCS model lumps are to be controlled by the PPC model, user needs
to set the input signal for the additional WTG or PCS model accordingly. Each of the WTG/PCS inputs
is a two-dimension signal including in sequence terminal voltage in kV and lump capacity in kW.
3.2  Model Outputs
To each WTG or PCS model, the PPC model outputs a two-dimension signal “WTCmd” or “BESSCmd”,
including active power and reactive power commands to the aggregated WTG or PCS lump, in kW
and KVA. If more WTG or PCS model lumps are to be controlled by the PPC model, user needs to set
the output signal for the additional WTG or PCS model accordingly.
4  PPC Model Control Functions and Parameters
4.1  General Configurations
In sub-menu “General”, user could configure the basic and general settings of the PPC model. Table
below describes the parameters.
Table 1 PPC general settings description
| Parameter  |                              | Description  | Remark             |
| ---------- | ---------------------------- | ------------ | ------------------ |
|            | Enable = regular master PPC  |              | User to configure  |
PPC enable
|     | Disable = EMS dispatcher*   |     | accordingly  |
| --- | --------------------------- | --- | ------------ |
Time to start PPC regulation, considering that
PPC Initialization Time [s]**  PPC regulation should not start until WTG or  Not adjustable
BESS model is initialized
WT/BESS Terminal Rated  Controlled WT or BESS PCS rated voltage at low
Not adjustable
| Voltage [kV]  | voltage side of step-up transformer  |     |     |
| ------------- | ------------------------------------ | --- | --- |
User to configure
| PPC Rated Voltage [kV]  | PPC control point rated voltage  |     |     |
| ----------------------- | -------------------------------- | --- | --- |
accordingly
User to configure
| Rated Frequency [Hz]  | System frequency  |     |     |
| --------------------- | ----------------- | --- | --- |
accordingly
Reserved line compensation, please contact
| Par_XL [ohm]  |     |     | Not adjustable  |
| ------------- | --- | --- | --------------- |
Envision if it is required
Reserved line compensation, please contact
| Par_R [ohm]  |     |     | Not adjustable  |
| ------------ | --- | --- | --------------- |
Envision if it is required
Sampling Frequency [Hz]  PPC sampling frequency  Not adjustable
| Sampling Period [s]  | PPC sampling period  |     | Not adjustable  |
| -------------------- | -------------------- | --- | --------------- |
Filter Time Constant [s]  Reserved interface. Filtering dealt with internally  Not adjustable
Delay Time [s]  Data collection and communication delay  Not adjustable
© Envision Energy. All Rights Reserved.                                                                      Page 5 of 12

Doc. Title: Envision Energy Univers PPC PSCAD Model User Manual V1.1.5b
Parameter Description Remark
*Note: when the PPC model is in EMS dispatcher mode, it will bypass all the closed loop controllers and will directly
dispatch P and Q commands to WTG or PCS; in this mode it therefore expects to receive P and Q reference from master
PPC.
**Note: as the PPC model has been implemented with fast initialization logic, to give enough time for initialization,
setpoint change or disturbance should be applied not earlier than PPC Initialization Time +5s (and ensure that the
BESS/WTG model is fully initialized) .
4.2 Reactive Power and Voltage Control
The PPC model provides 4 different reactive power control modes as shown in Table 2 below, user
could select control mode via “Reactive Power Control Mode” under “QControlParam” sub-menu.
When a certain control mode is selected, irrelevant parameter settings will be automatically greyed
out to avoid confusion.
Table 2 Q/V control mode description
Control mode Control function description
The PPC targets to regulate control point reactive power to the setpoint value using
Q Control
a PI controller
The PPC targets to regulate control point reactive power to the target value
Q/P Ratio Control calculated the setpoint and control point active power, via the same control loop as
for Q control mode
The PPC targets to regulate control point reactive power to the target value
Power Factor Control calculated from power factor setpoint value and control point active power, via the
same control loop as for Q control mode
The PPC targets to regulate control point reactive power to the target value
calculated from voltage droop equation Qtarget_kVAr = (Vref_pu – Vmeas_pu) /
V Droop Control
K_droop * Base_kVA, via a PI controller, when detected voltage deviation gets
beyond deadband
The PPC targets to regulate control point voltage to setpoint value via a PI
V Loop Control
controller, when detected voltage deviation gets beyond deadband
Table 3 below provides descriptions of the control parameters.
Table 3 Q/V control parameters description
Applicable
Parameter Name Setting Description
Control Mode
Reactive Power Control
Control mode selection as described in Table 2 /
Mode
Q control,
PCC Max Q Limit [kVAr] Limitation on control point capacitive Q, positive value required
Q/P control,
PF control,
PCC Min Q Limit [kVAr] Limitation on control point inductive Q, negative value required
V droop control
QCmd RampRate Ramp rate limit on reactive power command issued to WTG or
All
Limitation [pu/s] PCS
Q Control Kp Q control proportional gain Q control,
© Envision Energy. All Rights Reserved. Page 6 of 12

Doc. Title: Envision Energy Univers PPC PSCAD Model User Manual V1.1.5b
Applicable
Parameter Name Setting Description
Control Mode
Q/P control,
Q Control Ki Q control integral gain
PF control
WT/BESS Qcapacity PPC to WTG/PCS Q command limitation in power factor@Pn
All
Factor format, Pn as kW rating of the WTG/PCS equipment
WT/BESS Terminal V PPC freezes reactive power command sent to WTG/PCS if
All
Protect Factor [pu] equipment voltage deviation based on 1pu exceeds the setting
V Droop Control Base “Base_kVA” as in V-Q formular Qtarget_kVAr = (Vref_pu –
V droop control
[kVAr] Vmeas_pu) / K_droop * Base_kVA
“K_droop” as in V-Q formular Qtarget_MVAr = (Vref_pu –
V Droop Control Slope V droop control
Vmeas_pu) * K_droop * Base_kVA
V Droop Control Positive V droop control
the positive dead-band of voltage for voltage droop control
Deadband [pu] V loop control
V Droop Control Negative V droop control
the negative dead-band of voltage for voltage droop control
Deadband [pu] V loop control
V Droop Control Kp V droop control proportional gain V droop control
V Droop Control Ki V droop control integral gain V droop control
V Loop Control Kp V loop control proportional gain V loop control
V Loop Control Ki V loop control integral gain V loop control
4.3 Active power Control
The PPC targets to regulate control point active power to the setpoint value using a PI controller;
active power ramp rate can be applied if required. Parameters for active power control could be
found in “PControlParam” of the PPC model menu as Table 4 shows below.
Table 4 P control parameters description
Parameter Name Setting Description
P Limitation Coefficient [pu] Plant active power higher limitation
Dispatch PCmd RampRate
AGC active power regulation command execution ramp rate limit
Limitation [pu/s]
P Control Kp P control proportional gain
P Control Ki P control integral gain
4.4 Frequency Response
The PPC provides several different frequency response control modes and relevant parameters can
be adjusted in “FrequencyResponseParam” tab of the PPC model menu.
In all different control modes when the control is triggered, the PPC regulates active power change
of the plant as the same formular as below. The active power change is added to active power
command and the same PI controller as for active power control is used.
∆P_kW = Base_kW*∆f_Hz /(50*Droop)
© Envision Energy. All Rights Reserved. Page 7 of 12

Doc. Title: Envision Energy Univers PPC PSCAD Model User Manual V1.1.5b
Where:
∆P represents the active power adjustment for frequency response and the unit is kW;
∆f represents the system frequency variation with deadband considered, and the unit is Hz;
Droop is the parameter frequency droop factor;
Base is the real value calculation base in kW.
Table 5 below describes how the frequency control mode should be configured in regards to different
grid requirements.
Table 5 Frequency control mode configuration guide
Control requirement Configuration description
Primary frequency response (PFR) Put “Frequency Response Control Mode” as “FSM” and “FFR Enable”
Frequency sensitive mode (FSM) as “Disable”
Limited frequency sensitive model -
Put “Frequency Response Control Mode” as “LFSM-O/U”
over/under (LFSM)
Both FSM and LFSM on* Put “Frequency Response Control Mode” as “FSM//LFSM”
Both FSM and LFSM on, and during
LFSM the delta P calculated from Put “Frequency R esponse Control Mode” as “FSM+LFSM”
FSM and LFSM are summed up
Put “Deload Enable” as “Enable” while LFSM function is selected in
“Frequency Response Control Mode”. Deload function will then be
(UK BESS) LFSM with Deload
automatically triggered with latching when BESS is in import mode
under LFSM-U
Put “Frequency Response Control Mode” as “FSM” to represent PFR
(India) PFR and FFR
function, and “FFR Enable” as “Enable”
*Note: When both FSM and LFSM on, LFSM stage active power change will be the summation of delta P
calculated from FLSM and the FSM maximum delta P.
More parameters for frequency control could be found in the menu when certain control mode is
selected, as shown in Figure 3 below. Deadband, P-f droop and delta P limit for each control mode
can be tuned as the parameter names indicate straightaway. A few other parameters are described
in Table 6.
© Envision Energy. All Rights Reserved. Page 8 of 12

Doc. Title: Envision Energy Univers PPC PSCAD Model User Manual V1.1.5b
Figure 3 PPC frequency control parameters
Table 6 Frequency response parameters (in addition to deadband, droop and deltaP limit) description
Parameter Name Setting Description
Frequency Response
Control mode selection as described in Table 5
Control Mode
P-f factor calculation Base
“Base” as in ∆f-∆P formular “∆P_kW = Base_kW*∆f_Hz /(50*Droop)”
[kW]
Minimum P for Trigger Minimum P level that the plant can respond to frequency response and
FreqRes [pu] minimum P level that the plant can be curtailed to in over-frequency response
FreqRes Pcmd Ramprate Frequency response P command execution ramp rate limit (separate ramprate
Limitation [pu/s] settings are provided for FFR and Deload mode)
FFR PCmd RampRate
FFR mode P ramp rate limit
Limitation [pu/s]
Deload PCmd RampRate
Deload mode P ramp rate limit
Limitation [pu/s]
This switch works for all control modes except for Deload mode, which is
hardcoded with latching function enabled.
Enable = once frequency response is triggered, plant delta P does not decrease
Latching Function Enable
with delta f decreases, until frequency is back within deadband;
Disable = plant active power dynamically changes with delta f when frequency
is out of deadband range.
Enable = BESS plant is allowed to change between export mode and import
FreqRes Reserve Limitation mode during frequency response;
Enable (for PCS) Disable = BESS plant is only allowed to operate in the same mode
(export/import) during frequency response.
© Envision Energy. All Rights Reserved. Page 9 of 12

Doc. Title: Envision Energy Univers PPC PSCAD Model User Manual V1.1.5b
4.5 Inertia Response
When inertia response function is enabled, the plant will regulate change of active power based on
rate of change of frequency (RoCoF) according to the following formula, and the active power change
is added to active power command to help suppress the system RoCoF:
∆P_kW = Base_kW*(-Tj_s*df/dt_Hz/s)/50
The relevant parameters can be adjusted under “InertiaResponseParam” tab and are described in
Table 7 below.
Table 7 Inertia response parameters description
Parameter Name Setting Description
Inertia Response Enable Function switch
Inertia Time Constant(Tj) [s] Equivalent inertia time constant
IR Positive Deadband [Hz/s] Positive RoCoF deadband for inertia response
IR Negative Deadband [Hz/s] Negative RoCoF deadband for inertia response
IR deltaP UpLimit [pu] Increase P regulation amount limit
IR deltaP DnLimit [pu] Decrease P regulation amount limit
IR PCmd RampRate Limitation [pu/s] P ramp rate limit for inertia response
4.6 Voltage lock logic
The PPC is implemented with high voltage and low voltage lock logic.
PPC control point phase voltage is used in the detection, when either of the phase voltages exceeds
high/low voltage lock on level for delay time, PPC locks the P and Q commands issued to equipment
lumps, until all the phase voltages at control point is recovery back to within high/low voltage lock
off level for delay time.
The relevant parameters can be adjusted under “PPCLockParam” tab as the parameter names
indicate straightaway. Working as threshold hysteresis, “Low Voltage Lock Off Level” should be higher
than “Low Voltage Lock On Level”, “High Voltage Lock Off Level” should be lower than “High Voltage
Lock On Level”.
4.7 SVG Control
The PPC model provides SVG control function for up to 4 SVGs; however, please confirm with Envision
Energy on product feasibility for SVG control before conducting simulation studies.
4.7.1 SVG dispatch logic
The PPC model provides three different modes on reactive power command dispatch when PPC
controlling SVG. The dispatch mode can be selected via ‘Q Distribute Priority’ setting in the PPC menu,
and dispatch logic in each mode is described as below:
© Envision Energy. All Rights Reserved. Page 10 of 12

Doc. Title: Envision Energy Univers PPC PSCAD Model User Manual V1.1.5b
 SVG first
- SVG are dispatched in priority; if SVGs’ capacity is not enough, reactive power of the wind
turbines will then be regulated.
 WT/BESS first
- WT/BESS are dispatched in priority; if WT/BESSs’ capacity is not enough, reactive power of
the SVG will then be regulated.
 Proportional (by installed Q capacity)
- WT/BESS and SVG are dispatched equally in proportion to the WT/BES and SVG installed Q
capacity.
With either of the modes, when there are more than one SVG, the dispatch among different SVGs
will be per unit equal, based on each SVG’s rating.
4.7.2 SVG control inputs and outputs
The PPC model gives 4 sets of SVG interfaces while each of the sets is for interface of one SVG and
the first set of interface is labelled by default for reference. Each of the SVG input is a two-
dimensional interface, with the first one as SVG enabled switch (0 as disabled, 1 as enabled) and the
second one as the SVG rating in kVAr (rating must be positive). The relevant output signal gives SVG
reactive power command in kVAr. Figure below gives two examples of controlling 2 SVGs and 3 SVGs
respectively. The fourth set of the interfaces can be set in the same way if there are 4.
Example 1: PPC controlling two SVGs, SVG 1 rated at 70MVAr and SVG 2 rated at 25MVAr.
Q command
sent to SVG 1
SVG 1 enabled
SVG 1 rated at 70000kVAr
Q command
sent to SVG 2
SVG 2 enabled
SVG 2 rated at 25000kVAr
The remaining SVG inputs can be left as 0
Figure 4 Interface setting example of controlling 2 SVGs
© Envision Energy. All Rights Reserved. Page 11 of 12

Doc. Title: Envision Energy Univers PPC PSCAD Model User Manual V1.1.5b
Example 2: PPC controlling three SVGs rated at 70MVAr, 50MVAr and 25kVAr respectively.
Figure 5 Interface setting example of controlling 3 SVGs
© Envision Energy. All Rights Reserved. Page 12 of 12
