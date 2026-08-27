Envision Energy PCS
PSCAD Model User Manual
Version 4.1b1
2026/8/11
© Envision Energy. All Rights Reserved.

Doc. Title: Envision Energy PCS PSCAD Model User Manual V4.1b1
Disclaimer
While every precaution has been taken in the preparation of this document, Envision Energy assumes no liability
with respect to the operation or use of Envision Energy products and documentation described herein, for any
act or omission of Envision Energy concerning such products or this documentation, for any interruption of
service, loss or interruption of business, loss of anticipatory profits, or for punitive, incidental or consequential
damages in connection with the furnishing, performance, or use of the Envision Energy products and
documentation provided herein. Please use the applicable specifications in their latest versions. Images do not
necessarily reflect the exact scope of supply. The actual scope of supply can be subject to technical alterations at
any time.
© Envision Energy. All Rights Reserved. Page 1 of 7

Doc. Title: Envision Energy PCS PSCAD Model User Manual V4.1b1
Contents
1 Introduction ..................................................................................................................................... 3
2 Model Overview ............................................................................................................................... 3
3 Model Setup and Dependencies ........................................................................................................ 4
4 Configuration and parameter settings ............................................................................................... 5
4.1 PCS model scaling information .....................................................................................................................5
4.2 PCS model input and output ........................................................................................................................5
4.3 PCS Protection Setting ..................................................................................................................................6
© Envision Energy. All Rights Reserved. Page 2 of 7

Doc. Title: Envision Energy PCS PSCAD Model User Manual V4.1b1

1  Introduction
The Envision PCS model is a simulation model developed based on PSCAD/EMTDC simulation
software, mainly used to support the grid-connection simulation testing.
This document focuses on the usage and configuration of the PCS model. For the usage of PPC model,
please refer to PPC model user manual.
2  Model Overview
The PCS and PPC (power plant controller) are modelled separately in PSCAD, and are provided
together as a ready simulation case when both models are required, as model main page shown in
Figure 1 for example.
The cables and main transformer are set up for testing purpose only and user should configure them
as actual plant BoP design accordingly. The “Envision POC Meter” module is for observation for
reference, user could delete or replace them as required.
  Representing one 5.5/6.9/10.1MVA
PCS skid unit at 33kV
Scaling input
|     | BESSFbk1 BESSFbk1 |     | Current scale  |     |     |
| --- | ----------------- | --- | -------------- | --- | --- |
(MW|MVar|kV|kVA) (MW|MVar|kV|kVA)
|     | Envision Envision |     | 60.5 [M 60.5 [M VA] VA]                   | PccM PccM eas eas PPC measurement                     |     |
| --- | ----------------- | --- | ----------------------------------------- | ----------------------------------------------------- | --- |
|     |                   | I I | 33 [kV] 33 [kV]  /   /  220 [kV] 220 [kV] | (kW|kVar|kV|kV|kV|Hz|Hz/s) (kW|kVar|kV|kV|kV|Hz|Hz/s) |     |
10.0 10.0 Scal_Num Scal_Num ber ber GFL-PCS GFL-PCS nI nI Envision Envision
|     | BESSCm BESSCm d1N= d1N= Scal_Num Scal_Num ber ber | A A | # # 2 2 # # 1 1 | PCCM PCCM eas eas | POC POC M M eter eter |
| --- | ------------------------------------------------- | --- | --------------- | ----------------- | --------------------- |
Scale base: 5.5M Scale base: 5.5M VA VA (kW|kVar) (kW|kVar) V110 V110 R= R= 0 0
(2.75 x 2) x Scal_Num (2.75 x 2) x Scal_Num ber ber

PccM PccM eas eas
PPC Input PPC Input
1236745 1
| 55000.0 55000.0 PCm PCm | dIn dIn     |     |               | U U n n iv iv e e rs rs  P  P P P C C |     |
| ----------------------- | ----------- | --- | ------------- | ------------------------------------- | --- |
| 0.0 0.0                 | 1 1         |     | 2             |                                       |     |
| 220.0 220.0 Q Q Cm Cm   | dIn dIn 2 2 |     | 3             | V1.1.7b V1.1.7b                       |     |
| VCm VCm                 | dIn dIn     |     | 6 PCC M PCC M | eas eas BESSCm BESSCm d1 d1           |     |
0.95 0.95 Pow Pow erfactor erfactor 3 3 7 (kW|kVar|kV|kV|kV|Hz|Hz/s) (kW|kVar|kV|kV|kV|Hz|Hz/s) BESSCm BESSCm d1 d1
| 0.31 0.31 PQ PQ | Ratio Ratio 4 4       |                   | nIdm nIdm |                           |     |
| --------------- | --------------------- | ----------------- | --------- | ------------------------- | --- |
|                 | 5 5                   | BESSFbk1 BESSFbk1 | 4         | W W T/PCS Cm T/PCS Cm d d |     |
|                 |                       | BESSFbk1 BESSFbk1 | CUQ CUQ 5 | (kW|kVar) (kW|kVar)       |     |
|                 | PQ PQ UCm UCm dIn dIn | 34 34             |           |                           |     |
P P
PQ PQ UCm UCm dIn dIn PQ PQ V Ref V Ref
(kW|kVar|kV|-|-) (kW|kVar|kV|-|-)
W W T/PCS Info T/PCS Info
| PPC model  |     | 0 0 |     |     |     |
| ---------- | --- | --- | --- | --- | --- |
(kV|kVA) (kV|kVA)
| and inputs  |     |                       |     | STATCO STATCO M M  Cm  Cm d d |     |
| ----------- | --- | --------------------- | --- | ----------------------------- | --- |
|             |     | SVG_enable SVG_enable |     | (kVar) (kVar)                 |     |
00 00
|     |     | SVGrating_kVar SVGrating_kVar | STATCO STATCO | M M  Info  Info |     |
| --- | --- | ----------------------------- | ------------- | --------------- | --- |
(kVar|-) (kVar|-)

Figure 1 Model main page illustration (model name may differ for different versions)
Each PCS electrical topology is shown in Figure 2, featuring two converters connected in parallel.

© Envision Energy. All Rights Reserved.                                                                  Page 3 of 7

Doc. Title: Envision Energy PCS PSCAD Model User Manual V4.1b1
Figure 2 PCS electrical connection
The PCS PSCAD model simplifies the DC side controller since the battery can be taken as stable current source.
The other functionality/modules are represented with real control source code of the PCS, thus all of features
such as saturations, time-delay, non-linearity, dead-band, wind-up are well included.
PCS operates in active power and reactive power control mode, that is, the PCS responds to the external (PPC
or local) reactive and active power commands.
PPC can operate in reactive power control mode, power factor control mode, direct voltage control mode, or
voltage droop control mode; active power control mode and frequency response control mode are also
provided.
3 Model Setup and Dependencies
The compressed file obtained by users should contain two folders named "dll" and "Interface" respectively,
with the PSCAD model as “pscx” format. The ‘dll’ folder includes the .dll file which is the real Wind Turbine
source code complied model. When configuring the simulation project, user needs to make sure that the “dll”
and “Interface” folders are placed in the same path as the PSCAD project file.
To run the PCS with PPC PSCAD model correctly, it is recommended to use PSCAD V5.0 and intel Fortran
Compiler XE 15 and above. The PSCAD model file name will indicate if it works with 32bit or 64bit compiler.
© Envision Energy. All Rights Reserved. Page 4 of 7

Doc. Title: Envision Energy PCS PSCAD Model User Manual V4.1b1
The ‘interface’ folder includes necessary .obj files for the model to operate, user needs to make sure all the .obj
files are in the ‘resource’ folder in PSCAD, as example shown in the figure below.
Figure 3 Link object files in PSCAD
The Intel Fortran compiler should also be configured correctly before running the simulation,
otherwise the object files cannot be linked and the dll files cannot be loaded appropriately, leading
to failure in running the model.
The simulation time step works at anywhere between rang 1us ~ 200us, and 50us recommended,
and the model is represented with current source.
4 Configuration and parameter settings
4.1 PCS model scaling information
The current scaling component at the output of the PCS model reads scaling setting that can be configured by
user, as shown in Figure 4.
Current scale
Scaling input that
user to configure
Figure 4 PCS scale number setting
4.2 PCS model input and output
The PCS models receives active power command and reactive power command form PPC model via multi-
dimensional signal ‘BESSCmdx’ and provide required feedback variables to PPC via ‘BESSFBKx’. With PPC model
implemented, the overall model receives PPC command inputs to regulate the plant active power and reactive
power at plant Point of Connection.
The settings in the PCS model menu are for Envision R&D to configure, user please do not change those
settings.
© Envision Energy. All Rights Reserved. Page 5 of 7

Doc. Title: Envision Energy PCS PSCAD Model User Manual V4.1b1
4.3 PCS Protection Setting
PCS PSCAD protection consists of low voltage, high voltage, low frequency and high frequency protection
functions. By double clicking on the “Envision Volt & Freq Protection”, user could read the protection settings
and configure if required, as the menu shown in Figure below.
Figure 5 protection settings interface
All protection functions are configured using a point-based definition method. Users specify discrete voltage–
time (V–t) or frequency–time (f–t) points, and the protection characteristic curve is generated by linear
interpolation between these points. Voltage values are defined in per unit (p.u.), frequency values in hertz
(Hz), and time durations in seconds (s).
Each protection type generates an independent fault signal, including low-voltage, high-voltage, low-
frequency, and high-frequency faults. When a protection criterion is met, the corresponding fault signal is
activated. If a fault signal outputs a fault code with value x, it indicates that the voltage or frequency protection
level defined between Set x and Set (x+1) has been triggered for the corresponding voltage or frequency range.
A trip may result in multiple protection functions being triggered in sequence. Therefore, the first activated
protection flag should be considered as the primary cause of PCS trip.
As an example illustrated in the figure below, the high-frequency protection fault is triggered with a fault code
of 1. This indicates that the high frequency range defined by Set 1 to Set 2 has been activated, which is
consistent with the configured frequency protection settings.
© Envision Energy. All Rights Reserved. Page 6 of 7

Doc. Title: Envision Energy PCS PSCAD Model User Manual V4.1b1
Figure 6 fault code illustration example
© Envision Energy. All Rights Reserved. Page 7 of 7
