Envision  Energy  GFM  PCS  and  PPC

PSS/E User Defined Model

User Manual

Version 1.4a

2026/8/11

©Envision Energy. All Rights Reserved.

Doc. Title: Envision Energy GFM PCS and PPC PSS/E UDM User Manual_V1.4a

Disclaimer

While every precaution has been taken in the preparation of this document, Envision Energy
assumes  no  liability  with  respect  to  the  operation  or  use  of  Envision  Energy  products  and
documentation described herein, for any act or omission of Envision Energy concerning such
products  or  this  documentation,  for  any  interruption  of  service,  loss  or  interruption  of
business, loss of anticipatory profits, or for punitive, incidental or consequential damages in
connection  with  the  furnishing,  performance,  or  use  of  the  Envision  Energy  products  and
documentation  provided  herein.  Please  use  the  applicable  specifications  in  their  latest
versions.  Images  do  not  necessarily  reflect  the  exact  scope  of  supply.  The  actual  scope  of
supply can be subject to technical alterations at any time.

© Envision Energy. All Rights Reserved.                                                          Page  2  of 9

Doc. Title: Envision Energy GFM PCS and PPC PSS/E UDM User Manual_V1.4a

Contents

1  Overview ......................................................................................................................................... 4

2

Load Flow Model Setup .................................................................................................................. 4

3  Dynamic Model Configurations ...................................................................................................... 5

3.1

Dynamic Simulation Setup ................................................................................................... 5

3.2

PCS Model Configuration ..................................................................................................... 5

3.2.1

BESS System Rating and Overload ............................................................................ 5

3.2.2

Command Interface and Priority .............................................................................. 5

3.2.3

Voltage and Reactive Power Control ........................................................................ 6

3.2.4

Active Power Control ................................................................................................ 6

3.2.5

Primary Frequency Control ....................................................................................... 6

3.2.6

Protection ................................................................................................................. 6

3.3

PPC Model Configuration .................................................................................................... 6

3.3.1

PPC Model General Settings ..................................................................................... 6

3.3.2

Active Power Control and Frequency Response ...................................................... 7

3.3.3

Reactive Power/Voltage Control .............................................................................. 8

4  Diagnostic Flags and Internal Variables .......................................................... 错误!未定义书签。

© Envision Energy. All Rights Reserved.                                                          Page  3  of 9

Doc. Title: Envision Energy GFM PCS and PPC PSS/E UDM User Manual_V1.4a

1  Overview

This document provides user necessary information and guidance on using Envision Energy GFM PCS and PPC

PSS/E model. It is assumed that the user has a background of GFM PCS control and PSS/E simulation.

The  model  is  developed  as  a  user  defined model  in PSS/E  software  to  reflect  control  behavior of  Envision

Energy GFM PCS and PPC, it allows user to perform RMS dynamic simulation study in PSS/E power system

software.

The PCS model receives active power and voltage commands from PPC, or direct settings when there is no

PPC. Amounts measurements, control function and protection of the PCS are modelled.

With PPC model implemented, PCS plant active power control, reactive power control and frequency response

with different control modes can be realized. In case where Envision PPC is not used in the plant, please make

sure Envision PPC model is not included in the .dyr configuration and PCS interface is correctly configured.

However, due to platform limitation, EMT model like PSCAD is a better recommendation for transient study

such as fault ride through.

2  Load Flow Model Setup

As the first step in setting up simulations in PSS/E software, the user should prepare a solved load flow case in

which the PCS model or PCS aggregation has been properly created.

The PSS/E machine in load flow for each PCS or PCS aggregate should be configured as follows.

•



•

Control mode: Renewable: standard QT, QB limits

PGEN, QGEN: initial steady state active and reactive power delivered at the machine terminals as required.

PMAX, PMIN, QMAX, QMIN: the dynamic model does not make use of these values; however, it is good

practice to set these according to the capability limits of the Envision PCS unit being modelled. If it is desired

to constrain the reactive power to a specific value for the purposes of load flow, please set QMAX and QMIN

both equal to QGEN, the target value.

•  MBASE: nominal rating of the PCS unit or PCS aggregation. For user’s convenience this is based on the

nominal active power output: for example, 3.45MW. For a machine representing N identical PCS units, MBASE

is N times the MW rating of a single unit. This value is used in dynamic control so it must be set correctly.

•

ZR, ZX: these values are not used directly in the dynamic model and do not directly affect behaviour, but

their values can influence the numerical performance of the PSS/E simulation engine. The values ZR = 0, ZX =

999pu are recommended.

•

•

RTRAN, XTRAN: must be zero.

GENTAP: must be 1.

© Envision Energy. All Rights Reserved.                                                          Page  4  of 9

Doc. Title: Envision Energy GFM PCS and PPC PSS/E UDM User Manual_V1.4a

Other parameters may be left as default values.

3  Dynamic Model Configurations

3.1  Dynamic Simulation Setup

With .dll and .dyr files imported, Envision Energy PCS and PPC models are reflected as:

•

ENGFMxx: represents the Envision GFM PCS controller model and is written as a ‘renewable model’. It

receives commands from PPC or interface settings. Amounts measurement, steady state operation, transient

state control and protection have been modelled.

•

BNPPC_GFMVx: represents the power plant controller (PPC) model and is written as an ‘other model’. It

issues active power and voltage commands to individual PCS units or aggregates in order to regulate active

power, frequency and/or reactive power or voltage at the plant point of connection.

The  PSS/E  software  uses  a  modified  load  flow  engine  to  calculate  quasi-static  network  solutions  during  a

dynamic  simulation.  This  engine  generally  performs  well  but  is  sometimes  limited  by  its  ability  to  solve

networks with low short-circuit ratios and high transient power flows.

When using the Envision dynamic model with generators whose power output is large compared with the

short-circuit fault level at the point of connection, slight modification of PSS/E’s solution parameters may assist

with obtaining reliable network solutions when simulating the response to solid three-phase faults close to

the point of connection. Suggested modifications include reduction of the ‘acceleration factor’ to 0.5 or 0.3

from its default value of 1.0, and an increase in the maximum iteration count to 100 or 200 from its default

value of 25.

With certain networks, similar modifications to the solution parameters may be necessary when simulating

system response to severe faults, or to faults remote from the PCS terminals.

3.2  PCS Model Configuration

3.2.1  BESS System Rating

Parameters in the table below define the rating and overload of the BESS system based on generator Mbase.

3.2.2  Command Interface and Priority

The PCS model can receive commands from either PPC or direct interfaces, via settings ICON(M+3). Details on

the configurable parameter and command interface are given in Table 2 below.

Table 1 PCS model PQ control configurable settings

ICON(M+3)

Command Sent From

Command Interface

Unit

0

1

PPC

‘WPCMND’ and ‘VREF’

p.u. (power on generator
Mbase)

Local control

Var(L) and V(L+2)

p.u.

© Envision Energy. All Rights Reserved.                                                          Page  5  of 9

Doc. Title: Envision Energy GFM PCS and PPC PSS/E UDM User Manual_V1.4a

3.2.3  Voltage and Reactive Power Control

The  PCS  controls  reactive  power  by  adjusting  its  own  output  voltage  magnitude,  thereby  supporting  the

voltage at the point of connection. The PCS controls via Q-V droop control: when the voltage is low, the PCS

increases  reactive  power  output  in  response;  when  voltage  becomes  high,  the  reactive  power  is  adjusted

according to the droop characteristic.

3.2.4  Active Power Control

The PCS controls active power by adjusting its output frequency and phase angle, thereby providing frequency

support.

3.2.5  Primary Frequency Control

In the model provided by default, the primary frequency control function is disabled. With the local primary

frequency  control  function  enabled,  incremental  active  power  command  is  calculated  using  a  frequency

control droop coefficient based on PCS terminal frequency and base frequency value; the incremental active

power command is then added into the active power control loop as described in Section 3.2.3.

Relevant control parameters for primary frequency control are as shown in Table 2 below.

Table 2 Primary Frequency Control Settings

ICON/CON

CON Name

Description

CON(J+12)

pKdroop

Droop coefficient for primary f control

CON(J+30)

CON(J+31)

Wdb+

Wdb-

Positive deadband for primary f control

Negative deadband for primary f control

Unit

N/A

p.u.

p.u.

3.2.6  Protection

With ICON(M+6) set as 0, protection function is enabled. Voltage and frequency protections are implemented,

and user could adjust CON(J+65) to CON(J+100) for low frequency protection, high frequency protection, low

voltage protection and high voltage protection. The protection function operates on a conventional ‘threshold

and timer’ basis; when either of the voltage/frequency level and time duration sets is met, the protection will

be triggered and it will trip the PCS model.

In case for testing purpose, setting ICON(M+6) being 1 can disable the protection function.

It  needs  to  be  noticed  that  the  extreme  low  frequency  protection  is  only  valid  for  discharging  model;  the

extreme high frequency protection is only valid for charging model. Please refer to PCS product specification

for details.

3.3  PPC Model Configuration

3.3.1  PPC Model General Settings

The Envision PPC model is written as a Bus Type Model, which can be attached to any existing bus; its variable

index can be get by psspy.cctmind_buso( ).

For different controlled models, the dynamic configuration must be changed accordingly, specifically as below:

© Envision Energy. All Rights Reserved.                                                          Page  6  of 9

Doc. Title: Envision Energy GFM PCS and PPC PSS/E UDM User Manual_V1.4a





Power Flow and Controlled Bus: the power flow from bus ICON(M+8) to bus ICON(M+9), and the voltage

at bus ICON(M+6) will be controlled for voltage control mode, and frequency at bus ICON(M+7) will be

controlled for frequency response.

Setting for Controlling Multiple Generators: Envision PPC model can support up to 300 generators (or

aggregates, one generator could be one aggregate, same below) in total, as in up to 6 groups. ICOM(M+21)

to ICON(M+38) defines the settings of 6 groups separately. Settings of the first group is introduced below

and the same way for the other groups.
-  When there is only 1 generator in each group, set ICON(M+39) as 0 and ICON(M+22) as ID of the

generator.  Alternatively,  the  setting  approach  for  more  groups  can  also  be  adopted  if  all  the

generators share the same ID.

-  When there are more than 1 generators in one of the groups, the ID of all generators must be the

same  and  the  generator  attached  bus  number  in  each  group  must  be  in  sequence  (eg:  71000,

71001….). Set ICON(M+39) as 1, ID of the generators is set in ICON(M+20). For Group 1 for example,

the  starting  generator  bus  number  is  set  by  ICON(M+21)  and  ICON(M+22)  is  number  of  the

generators in the group.

  Generator Type Setting: Different types of generators can be controlled by the PPC. However, in each

group, the generators must share the same type and reactive power command limitation. ICON(M+23)

defines type of the generator being controlled in the first group for example, setting description can be

found in the table below. PPC command limitation is in reactive power format in p.u. based on Mbase

setting unless otherwise stated. And same for the other groups. Table 6 below describes the setting for

ICON(M+23).

Table 3 ICON(M+23) generator type setting description

ICON(M+23)

Description

0

1

2

3

4

WTG is controlled and PPC command limitation is in power factor Cos value format

WTG is controlled and PPC command limitation is in reactive power format in p.u.

based on Mbase

BESS PCS is controlled

Machine type STATCOM is controlled

FACTS type STATCOM is controlled; and the STATCOM command input VAR index

number should be set by ICON(M+40)

3.3.2  Active Power Control and Frequency Response

In regards to active power and frequency control, the PPC model can provide AGC active power control, inertia

response and frequency control of different control modes. Control mode can be defined via ICON(M+1) as

described in Table 7. Control logics of each function and each control mode are detailed below.

Table 4 ICOM(M+1) Active power control mode selection

ICOM(M+1)

Control mode

0

No P control or f response

© Envision Energy. All Rights Reserved.                                                          Page  7  of 9

Doc. Title: Envision Energy GFM PCS and PPC PSS/E UDM User Manual_V1.4a

ICOM(M+1)

Control mode

1

2

P control AGC function enabled

Primary frequency response function is enabled, with AGC enabled; active power regulation result

is the summation of AGC and frequency response

Under AGC active power control, the plant active power reference can be given via interface Var(L+3), in per

unit on generator Mbase.

Under frequency control, the plant active power regulation amount calculation follows the formula below:

𝑑𝑟𝑜𝑜𝑝(%) = 100  ×

∆𝑓 𝑓𝑛𝑜𝑚⁄
∆𝑃 𝑃𝑛⁄

Where:

∆𝑓  is the measured frequency deviation beyond deadband, in Hz;

∆𝑃  is the active power change amount, in MW;

𝑓𝑛𝑜𝑚  is the nominal frequency 50 or 60, in Hz;

𝑃𝑛  is the controlled rated power of the PPC, in MW;

𝑑𝑟𝑜𝑜𝑝  is the adjustable droop setting and can be adjusted via CON(J+15), in %.

Deadband  can  be  set  via  CON(J+32)  and  CON(J+33),  limitation  on  active  power  regulation  amount  can  be

adjusted via CON(J+40) and CON(J+41).

A few other functions and settings for active power and frequency control are detailed below:

Active power limit: Plant active power output can be limited via CON(J+30).

PPC freezing when frequency deviates: When POC frequency deviation gets above CON(J+82), the PPC will

freeze active power command sent to the PCS units, until frequency recovers. When POC frequency deviation

gets  higher  than  CON(J+83),  the  PPC  P  control  PI  controller  output  will  stop  increasing  if  the  frequency

deviation is positive or stop decreasing when the frequency deviation is negative.

3.3.3  Reactive Power/Voltage Control

In regards to  reactive  power  control, the PPC model can provide  four different control modes  that can  be

defined via ICON(M) as described in Table 8 below.

Table 5 ICOM(M) Reactive power control mode selection

ICOM(M+1)

Control mode

Setpoint interface

0

1

2

3

4

PPC Q control is disabled

/

Reactive power control

Qref  input  from  Var(L)  in  p.u.  on  sum  of  Mbase  of  all  active

generators and Qmax of STATCOMs (if there is any)

power factor control mode

PFref input from Var(L+1) in cos value

voltage droop control mode

Vref input from Var(L+2) in p.u.

direct voltage control mode

Vref input from Var(L+2) in p.u.

© Envision Energy. All Rights Reserved.                                                          Page  8  of 9

Doc. Title: Envision Energy GFM PCS and PPC PSS/E UDM User Manual_V1.4a



Reactive power control mode and power factor control mode

In reactive power control mode, the PPC targets to regulate control point Q to setpoint value via a PI control

loop; in power factor control mode, the PPC calculates Qref from power factor setpoint and plant active power

and uses the Q control loop to achieve Qref. In these two modes, PI parameters can be adjusted via CON(J+24)

and CON(J+25).



Voltage droop control mode

In voltage droop control mode, PPC calculates Qref as per the droop formula below, and Qref goes into a PI

control loop, the PPC targets to regulate control point Q to the dynamically calculated Qref value.

𝑄𝑟𝑒𝑓_𝑀𝑉𝐴𝑟 = 𝑑𝑟𝑜𝑜𝑝  ×   (𝑉𝑟𝑒𝑓_𝑝𝑢 −   𝑉𝑚𝑒𝑎𝑠_𝑝𝑢) × 𝐵𝑎𝑠𝑒

Where:

𝑉𝑟𝑒𝑓_𝑝𝑢  is the voltage setpoint received via Var(L+2), in p.u.;

𝑉𝑚𝑒𝑎𝑠_𝑝𝑢  is the measured voltage at control point, in p.u.;

𝑑𝑟𝑜𝑜𝑝  is the adjustable droop setting and can be adjusted via CON(J+16) and CON(J+17);

𝐵𝑎𝑠𝑒  is an adjustable setting and can be set via CON(J+29), if it is set as 0 then the controlled generator Mbase

will be used.

Voltage control deadband can be set via CON(J+20) and CON(J+21), PI parameters can be set via CON(J+22)

and CON(J+23).



Direct voltage control mode

In direct voltage control mode, PPC targets to regulate control point V to setpoint value via a PI control loop.

Voltage control deadband can be set via CON(J+20) and CON(J+21), PI parameters can be set via CON(J+68)

and CON(J+69).

A few other functions and settings for reactive power are detailed below

Reactive power limitation: Generator Q command limitation can be set in CON(J+50) to CON(J+61) in p.u. for

each generator group. The plant reactive power capability is limited by CON(J+18) and CON(J+19) in p.u.

PPC freezing when voltage deviates: When POC voltage gets lower than CON(J+11) or higher than CON(J+12),

the PPC will freeze active power and voltage commands sent to the PCS units, until voltage recovers. When

POC voltage gets higher than CON(J+64), the PPC Q command in Q control mode or the value calculated in

power  factor  control mode  will  stop  increasing;  when  POC voltage  gets  lower than  CON(J+65),  it  will  stop

decreasing.

© Envision Energy. All Rights Reserved.                                                          Page  9  of 9


