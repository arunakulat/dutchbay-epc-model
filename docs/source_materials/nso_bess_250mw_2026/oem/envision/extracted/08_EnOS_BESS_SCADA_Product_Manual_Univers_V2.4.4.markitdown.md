Disclaimer
EnOSTM BESS SCADA
Product Manual
v2.4
1

Disclaimer
Disclaimer
For the purposes of this Document (“Document”), “Univers” shall collectively mean Univers
Pte. Ltd. and its Affiliates. “Affiliate” means in relation to Univers Pte Ltd, (i) any entity under
the control of Univers Pte Ltd, (ii) any entity controlling Univers Pte Ltd; and (iii) any other entity
under the control of controlling entity in (ii).
Confidentiality Statement
All information contained within this Document is provided in confidence and may only be used
by the recipient (“Recipient”) in accordance with a separate written agreement between
Univers and the Recipient. This Document shall not be used for any other purposes and shall
not be disclosed, copied, reproduced, modified, published, uploaded, posted, transmitted,
distributed, in whole or in part, without Univers's prior permission in writing, except that it may
be shared with the Recipient's employees for the purpose of evaluating Univers’s products and
software subject to such personnel similarly undertaking to maintain confidentiality of this
Document. This Document must be always held in safe custody. These obligations shall not
apply to information which is in the public domain or becomes known legitimately.
Revisions
Univers may, in its sole discretion, revise, update, change, modify, add to, supplement, or
delete certain terms in this Document, without notice to the Recipient, for security, legal, best
practice, or regulatory reasons, including to reflect the continuous improvement of Univers’s
products and software. Unless specified by Univers, this Document only applies to specific
software versions.
No Representations and Warranties
Except as specified otherwise by Univers, Univers does not make, and expressly disclaim, any
representations or warranties, express or implied, as to the completeness, accuracy, or
usefulness of the information contained in this Document. Univers does not warrant that use of
such information will not infringe any third-party rights, nor does Univers assume any liability
for damages or costs of any kind that may result from use of such information.
Any warranty terms, if applicable, shall be set out in the respective contract or agreement
signed by Univers and the recipient.
Third Party Products
This Document may contain information about the use of non-Univers products (“Third-party
Products”). Please note that information regarding Third-party Products is provided in good
2

Disclaimer
faith to the recipient for better user experience. Univers disclaims and any all liability, including
any express or implied warranties, whether oral or written, for such Third-party Products.
Intellectual Property Rights
The entire contents, design and proprietary information contained in this Document is the sole
and exclusive property of Univers, and all intellectual property (including but not limited to
patents, copyrights, trade secrets or trademarks) embodied in or in connection with this
Document (except as otherwise stated herein) is and shall remain the sole property of Univers.
Unless stated to the contrary, this Document in no way conveys any right, title(s), interest or
licence in any such intellectual property contained or embodied herein.
© Univers Pte Ltd 2025
3

Foreword
Foreword
About this document
This document is used to introduce the main functions, system performance, and software &
hardware environment required for system operation of the EnOSTM BESS SCADA system. It
is helpful for users to quickly understand the main functions and principles of the product for
decision making; it is helpful for solution personnel to evaluate and formulate appropriate
solutions; it is also helpful for project implementation personnel to reference for the acceptance
testing of product implementation results.
Disclaimer
The system graphic screens given in this manual are for reference only, which are subject to
project implementation and delivery. Due to continuous product improvement and upgrade, the
description of product functions in this manual is subject to change without notice.
4

Table of Contents
Table of Contents
Disclaimer .................................................................................................................................. 1
Foreword .................................................................................................................................... 4
Table of Contents ...................................................................................................................... 5
List of Figures ............................................................................................................................ 7
1 Overview ............................................................................................................................ 9
1.1 Terminology ........................................................................................................ 9
1.2 Target users ...................................................................................................... 10
1.3 Application scenarios ........................................................................................ 10
1.4 System features ................................................................................................ 11
2 Product Overview ............................................................................................................. 13
2.1 Hardware architecture ...................................................................................... 13
2.2 Functional framework ....................................................................................... 14
2.3 Function overview ............................................................................................. 15
3 Function introduction ........................................................................................................ 18
3.1 Monitoring ......................................................................................................... 18
3.1.1 Homepage ................................................................................................. 18
3.1.2 Subsystem of electrical topology............................................................... 19
3.1.3 Electrical topology ..................................................................................... 20
3.1.4 Device list .................................................................................................. 21
3.1.5 Token List .................................................................................................. 34
3.1.6 Favorite ..................................................................................................... 34
3.2 Alarm ................................................................................................................. 36
3.2.1 Real-time alarm ......................................................................................... 36
3.2.2 Historical alarm.......................................................................................... 38
3.3 Report ............................................................................................................... 39
3.3.1 Energy report............................................................................................. 39
5

Table of Contents
3.3.2 Operation report ........................................................................................ 39
3.3.3 TBA report ................................................................................................. 40
3.4 Analysis ............................................................................................................. 41
3.4.1 Trend analysis ........................................................................................... 41
3.4.2 Scatter analysis ......................................................................................... 43
3.4.3 Data export ................................................................................................ 44
3.5 Setting ............................................................................................................... 44
3.5.1 Operating parameters ............................................................................... 45
3.5.2 Password Modify ....................................................................................... 45
3.6 User management ............................................................................................ 46
4 System Performance ....................................................................................................... 49
4.1 Access capacity ................................................................................................ 49
4.2 Data storage ..................................................................................................... 49
4.3 Performance indicators ..................................................................................... 49
5 Deployment Requirements .............................................................................................. 51
5.1 Software environment ....................................................................................... 51
5.2 Hardware Requirement ..................................................................................... 51
5.3 System security................................................................................................. 51
5.3.1 Permission management .......................................................................... 51
5.3.2 Security audit............................................................................................. 52
5.3.3 Account security ........................................................................................ 52
5.3.4 Session management ............................................................................... 53
Appendix I Indicators Definition ............................................................................................... 54
Appendix II Service Ports ........................................................................................................ 58
Documentation • Support • Feedback ................................................................................. 64
6

List of Figures
List of Figures
Figure 1: Typical architecture diagram of SCADA system ............................................................ 14
Figure 2: Energy storage monitoring device-level topology .......................................................... 18
Figure 3: Homepage of energy storage site .................................................................................... 19
Figure 4: Electrical topology of energy storage subsystem ........................................................... 20
Figure 5: Electrical topology of energy storage station .................................................................. 21
Figure 6: Large card-based device list ............................................................................................. 22
Figure 7: Small card-based device list .............................................................................................. 22
Figure 8: List-based device list .......................................................................................................... 23
Figure 9: Single device details ........................................................................................................... 24
Figure 10: Subsystem device list ....................................................................................................... 25
Figure 11: Subsystem details ............................................................................................................. 26
Figure 12: Converter device list ......................................................................................................... 26
Figure 13: Converter details ............................................................................................................... 27
Figure 14: Battery array device list .................................................................................................... 27
Figure 15: Battery array details .......................................................................................................... 28
Figure 16: Battery cluster device list ................................................................................................. 28
Figure 17: Battery cluster details ....................................................................................................... 29
Figure 18: Air conditioner device list ................................................................................................. 30
Figure 19: Air conditioner details ....................................................................................................... 30
Figure 20: Protection and measuring-control device list ................................................................ 31
Figure 21: Protection and measuring-control device details ......................................................... 31
Figure 22: Liquid cooling device list .................................................................................................. 32
Figure 23: Liquid cooling device details ........................................................................................... 32
Figure 24: DC Converter device list .................................................................................................. 33
Figure 25: DC Converter device details ........................................................................................... 33
Figure 26: Other devices list .............................................................................................................. 34
Figure 27: Other devices details ........................................................................................................ 34
Figure 28: Token List........................................................................................................................... 34
Figure 29: Add favorite ........................................................................................................................ 35
7

List of Figures
Figure 30: Favorite list ......................................................................................................................... 35
Figure 31: Favorite setting .................................................................................................................. 35
Figure 32: Real-time alarms ............................................................................................................... 36
Figure 33: Alarm analysis ................................................................................................................... 37
Figure 34: Longitudinal analysis ........................................................................................................ 38
Figure 35: Horizontal analysis............................................................................................................ 38
Figure 36: Historical alarms................................................................................................................ 39
Figure 37: Energy report ..................................................................................................................... 39
Figure 38: Operation report ................................................................................................................ 40
Figure 39: TBA report .......................................................................................................................... 40
Figure 40: Downtime record ............................................................................................................... 41
Figure 41: Trend graph curve ............................................................................................................ 42
Figure 42: Template and display style editing ................................................................................. 42
Figure 43: Trend chart table ............................................................................................................... 42
Figure 44: Scatter analysis curve ...................................................................................................... 43
Figure 45: Scatter analysis table ....................................................................................................... 43
Figure 46: Data export ........................................................................................................................ 44
Figure 47: Export template editing .................................................................................................... 44
Figure 48: Alert template customization ........................................................................................... 45
Figure 49: Pop-up alarm mode settings ........................................................................................... 45
Figure 50: Modify the password ........................................................................................................ 46
Figure 51: User management ............................................................................................................ 47
Figure 52: User unlocking function .................................................................................................... 47
Figure 53: Role management ............................................................................................................ 48
8

Overview
1 Overview
The EnOSTM BESS SCADA system, developed by Univers, is grounded in the principles of
smart power, energy interconnection, and sustainable development. It operates on the
integrated EnOSTM SCADA platform, which overcomes the technical limitations of traditional
SCADA systems by spanning multiple domains, including wind power, solar energy, and energy
storage. This enables comprehensive power generation monitoring and energy management
to achieve multi-energy data access and interconnection within a unified platform.
Designed with second-level monitoring technology and power generation site models, the
system fully accesses data from energy storage devices. It facilitates operations management
and power generation control in smart sites through centralized monitoring, intelligent alarms,
and advanced data analysis and statistics.
For uplink communication, the system can collaborate with the power grid to relay important
device data as needed. For downlink communication, it interfaces with the local controller of
the energy storage subsystem to access various device data. This functionality supports
panoramic site monitoring, data analysis, intelligent alarms, and remote start/stop control,
enhancing the automatic safety management of energy storage sites. It enables a no-duty or
minimal-duty management mode, effectively reducing the operation and maintenance costs of
power stations.
1.1 Terminology
Abbreviation Full Name Description
Automatic Generation Refers to the automatic power generation
AGC
Control control system
Refers to the automatic voltage control
AVC Automatic Voltage Control
system
Used for monitoring battery voltage, current,
Battery Management
BMS temperature and other parameters as well as
System
managing and controlling the battery status
Energy Collaborative
ECC Energy Collaborative control module
Control
Refers to an energy management and
Energy Management dispatching system provided by Univers for
EMS
System active and reactive power control of wind
power, solar and energy storage.
Refers to a set of minimum energy storage
subsystem that consists of a single PCS and
ESS Energy Storage System
corresponding battery pack in the energy
storage power station
9

Overview
Refers to a system designed for the thorough
Local Comprehensive
LCRS recording of data or events within a specific
Recording System
local area.
Refers to the public connection point
Point of Common
PCC between the booster station in the power
Coupling
station and the power grid
Used in electrochemical energy storage
system to connect the battery and the grid to
PCS Power Conversion System
achieve bidirectional electrical energy
conversion
Primary Frequency Refers to a system for Primary Frequency
PFC
Control Control
Refers to the synchronous phasor
PMU Phasor Measurement Unit
measurement unit
PPC Power Plant Controller Power plant control for the whole station
Refers to the SCADA platform, which is a
comprehensive monitoring application
Supervisory Control and
SCADA software product for business scenarios such
Data Acquisition
as wind farms and energy storage developed
by Univers.
Millisecond-level sequential records of events
that occurs at each measurement point
SOE Sequence of Event (column) within the selected time range,
which are the most important basis for
device/system failure and abnormal analysis
TBA Time Based Availability Time-based availability.
1.2 Target users
This document is prepared mainly for the following readers for easing their related business.
⚫ Solutions
⚫ Sales team
⚫ Delivery team
⚫ Technical personnel for end customers
1.3 Application scenarios
The EnOSTM BESS SCADA system is mainly used for monitoring the devices at the site control
layer and the spacer layer.
⚫ By monitoring and controlling the devices in the energy storage site, including energy
storage subsystems, energy storage converters and energy storage batteries, it can
achieve the monitoring and management of the assets in the whole site.
10

Overview
⚫ The managers can understand the real-time and historical operating data of the wind farm
at any time through the PC devices.
⚫ The technicians can analyze alarms, power curves and other data through the system.
⚫ The maintenance personnel can use the remote diagnosis service provided by the system
for rapid response to device faults so as to timely monitor and online analyze faults and
reduce downtime.
⚫ The operators can conveniently view the operations of all the devices across the site
through the monitoring system.
1.4 System features
The EnOSTM BESS SCADA system is designed in accordance with key international and
regional standards to ensure compliance with communication protocols, power system
interoperability, cybersecurity.
It supports industry protocols such as IEC 60870-5-104, ModbusTCP,IEC61850,OPC_UA for
communication. To ensure system security, it adopts best practices aligned with IEC 62443 for
industrial cybersecurity and ISO/IEC 27001 for information security management.
Its development process follows a structured approach based on CMMI-DEV Level 3, ensuring
consistent quality, traceability, and continuous improvement.
These standards help ensure smooth integration with third-party systems and compliance with
utility and regulatory requirements across global markets.
Its main features include:
⚫ By monitoring and controlling the energy storage subsystems, box transformers, converters,
battery arrays, and cells in the energy storage site, it can achieve the intelligent monitoring
and management of the assets in the whole site.
⚫ The managers can understand the real-time and historical operating data of the energy
storage site at any time through the PC terminal.
⚫ The technicians can analyze device alarms, power curves and other data and failures
through the system.
⚫ The maintenance personnel can use the remote diagnosis service provided by the system
for rapid response to device faults so as to timely monitor and online analyze faults and
reduce downtime.
11

Overview
⚫ The operators can conveniently view the operations of all the devices across the site
through the monitoring system.
⚫ Highly configurable user interface. The monitoring interface can be customized according
to user needs to meet the monitoring requirements in different occasions and levels.
⚫ Reports can be customized to allow users to obtain the information they care about in a
timely manner.
⚫ Wide support for OPC, DNP, MODBUS, IEC-104, IEC-101 and other communication
protocols.
⚫ Provides real-time curve tool and historical data archive.
⚫ The complete user permission management function helps to distinguish and perform the
permission management for the alarm view, remote reset, start/stop machine and operating
parameters of the energy storage site.
⚫ It can provide a system interface based on the B/S architecture, and end users can access
it through the application screen or browser.
12

Product Overview
2 Product Overview
The EnOSTM BESS SCADA system is deployed at the site side of the energy storage site. It is
mainly used to display the important statuses of energy storage devices, and provides various
advanced application functions, such as panoramic automatic monitoring, data analysis, and
intelligent alarms of charging and discharging devices. For the uplink, it can cooperate with the
power grid to forward important device data or open data interfaces for third parties on demand;
for the downlink, it can communicate with the local controller of the energy storage subsystem
to access various device data of the energy storage subsystem and provide a data foundation
for advanced functions at the site side. The system is featured by stable overall operation, high
scalability and compatibility.
2.1 Hardware architecture
The system is designed with an open hierarchical distribution structure, and the devices at the
site control layer include application servers and workstations. As the center of data collection,
processing, storage and network management at the site control layer, the application server
works at the active/standby dual-network mode to ensure high availability. The workstation is
the main human-machine interface of the monitoring system, used for displaying graphs and
reports, recording events, displaying and querying alarm statuses, querying device statuses
and parameters, and issuing control command issuance. The device layer includes the
measurement & control device, the battery management system, the auxiliary control system,
and the local controller. The protection and measuring-control device provides state quantity
acquisition, AC sampling and measurement, and circuit breaker control. The battery
management system is used to monitor the statuses of the battery (including temperature,
voltage, current, and state of charge) to provide battery management and communication
interfaces. The auxiliary control system provides the data of air conditioning, fire protection, and
access control to realize the auxiliary protection of the system. The local controller is used for
the local data acquisition, storage and control of the energy storage subsystem, and is equipped
with voltage, SOC and other protection functions. The typical architecture and specific device
distribution of the EnOSTM BESS SCADA system are shown in the figure below.
13

Product Overview
Figure 1: Typical architecture diagram of SCADA system
2.2 Functional framework
The EnOSTM BESS SCADA system is mainly composed of data collection module, data bus,
data storage module and advanced application module. The system collects and parses
communication data messages, and then stores the device data to the database module and
some SCADA advanced applications through the data bus. The applications, including
monitoring modules, intelligent alarms and parameter settings, read data from the data storage
module for analysis.
⚫ Data collection: It supports the connection to multiple types of devices, and forwards data
to multiple third-party systems with multiple protocols. The forwarded data supports flexible
configuration.
⚫ Data bus: By using the message bus mode, it provides data transfer queues for front-end
systems, databases and applications.
⚫ Data storage: It supports multiple types of data storage methods such as files, memory and
databases, and can achieve the category-based data storage in multiple precisions.
⚫ Monitoring module: With this function, users can view the site-level and device-level local
monitoring information, obtain the real-time operating status of all the devices in the
monitored site as well as the parameters of each measurement point, and send remote
control commands to control the devices.
14

Product Overview
⚫ Smart alarm: It is used to confirm, filter and mute real-time alarm information, and it
supports the custom configuration of alarm templates, the double pop-up windows for fault
alarm and the query and export of historical alarm information.
⚫ Parameter setting: It is used to set various parameters and supports remote Web page
setting.
The overall system adopts a three-tier structure designed by standard software that covers the
data collection and communication, the data processing and storage, the interface display and
operations.
2.3 Function overview
The SCADA energy storage monitoring system is mainly developed for the business areas such
as intelligent monitoring and energy management, and provides advanced applications around
the site-side and local energy storage subsystems. The intelligent monitoring is intended to
solve the needs of customers in the power generation device monitoring and automation control,
the alarm monitoring and historical event query, and the device data statistics and core data
comparison and analysis.
The L1 functions of the system mainly include monitoring, alarming, reporting and operating
parameter tuning, and its detailed L2 functions and descriptions are shown in the table below.
Business L1 L2
Description
domain functions functions
Overall power station operation:
• Equipment status statistics and links to the
equipment list.
• Real-time station information.
• Operational trends.
Intelligent Monitoring Homepage
Subsystem geographical topology:
monitoring
• Drill down to detailed subsystem
topologies.
• Top-down monitoring and fault location
based on subsystem topology.
15

|           |     |     |     |     |     | Product Overview  |     |
| --------- | --- | --- | --- | --- | --- | ----------------- | --- |
| Business  | L1  | L2  |     |     |     |                   |     |
Description
| domain  | functions  | functions  |     |     |     |     |     |
| ------- | ---------- | ---------- | --- | --- | --- | --- | --- |
Used to display the composition and connection
|     |     | Subsystem   | relationships between feeders, box transformers,   |     |     |     |     |
| --- | --- | ----------- | -------------------------------------------------- | --- | --- | --- | --- |
|     |     | electrical  | and subsystems, as well as the status of switches  |     |     |     |     |
|     |     | topology    | and disconnectors, subsystem operational status,   |     |     |     |     |
and key operational data.
|     |     |     | Used  to  | display  a  | list  of  | various  | equipment,  |
| --- | --- | --- | --------- | ----------- | --------- | -------- | ----------- |
operational status, and key operational information.
Supports card, small icon, and table formats with
|     |     |              | customizable                                        | view  | order,  as  | well  | as  filtering,  |
| --- | --- | ------------ | --------------------------------------------------- | ----- | ----------- | ----- | --------------- |
|     |     | Device list  | tagging, and drilling down to individual equipment  |       |             |       |                 |
details. It mainly includes subsystems, converters,
|     |     |     | battery  packs,  | battery  | clusters,  | air  conditioning,  |     |
| --- | --- | --- | ---------------- | -------- | ---------- | ------------------- | --- |
monitoring and control, liquid cooling, and other
equipment.
Used to display all records of tagged monitoring
objects based on the equipment list or individual
Token list
equipment details within the station, with the option
to remove tags.
|     |     | Real-time  | Used for the real-time display of system operation  |     |     |     |     |
| --- | --- | ---------- | --------------------------------------------------- | --- | --- | --- | --- |
|     |     | alarm      | information and alarm information.                  |     |     |     |     |
Alarm
|     |     | Historical  | Used to search various alarm information that has  |                   |                   |              |              |
| --- | --- | ----------- | -------------------------------------------------- | ----------------- | ----------------- | ------------ | ------------ |
|     |     | alarm       | occurred.                                          |                   |                   |              |              |
|     |     |             | Support                                            | daily,  monthly,  | and               | yearly       | charge  and  |
|     |     | Energy      | discharge                                          | statistics,       | charge/discharge  |              | ratio        |
|     |     | Report      | statistics,                                        | and  report       | export            | for  energy  | storage      |
stations.
Report
Support custom report templates. Default templates
|     |     | Customized  | include subsystem hourly operation reports and  |          |       |                      |     |
| --- | --- | ----------- | ----------------------------------------------- | -------- | ----- | -------------------- | --- |
|     |     | Report      | battery  cluster                                | highest  | cell  | voltage/temperature  |     |
reports.
16

Product Overview
| Business  | L1  | L2  |     |     |     |     |     |     |     |
| --------- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
Description
| domain  | functions  | functions  |     |     |     |     |     |     |     |
| ------- | ---------- | ---------- | --- | --- | --- | --- | --- | --- | --- |
Reflect the changing trends of AI, DI, and PI in the
form of tables and curves.
|     |     |     |     | •  Support  | custom  |     | queries  | and  | save  |
| --- | --- | --- | --- | ----------- | ------- | --- | -------- | ---- | ----- |
templates based on device type and model,
|     |     |     |     | such                    | as  | battery  | pack                | voltage  |     |
| --- | --- | --- | --- | ----------------------- | --- | -------- | ------------------- | -------- | --- |
|     |     |     |     | difference/temperature  |     |          | difference/current  |          |     |
Trend
analysis, and battery cluster cell voltage
analysis
difference/temperature difference analysis.
|     |     |     |     | •  Support  |     | maximum/minimum/average  |     |     |     |
| --- | --- | --- | --- | ----------- | --- | ------------------------ | --- | --- | --- |
Analytics
statistics of the queried data.
|     |     |     |     | •  Support  |     | data  | comparison  |     | by  |
| --- | --- | --- | --- | ----------- | --- | ----- | ----------- | --- | --- |
day/week/month/year.
|     |     | Scatter   | Reflects the change trend of the telemetry value in  |     |     |     |     |     |     |
| --- | --- | --------- | ---------------------------------------------------- | --- | --- | --- | --- | --- | --- |
|     |     | analysis  | the form of tables and curves.                       |     |     |     |     |     |     |
Support custom export templates based on device
|     |     | Data       | type and model. For example, support exporting  |          |              |     |        |          |          |
| --- | --- | ---------- | ----------------------------------------------- | -------- | ------------ | --- | ------ | -------- | -------- |
|     |     | analytics  | battery                                         | cluster  | temperature  |     | data,  | battery  | cluster  |
voltage data, and battery pack current data.
|     | Modify password  |     | Modify the password of the current account.  |      |       |             |     |      |       |
| --- | ---------------- | --- | -------------------------------------------- | ---- | ----- | ----------- | --- | ---- | ----- |
|     |                  |     | Covers                                       | the  | user  | management  |     | and  | role  |
User management
management.
Alert  template  Customize the real-time alarm templates and set
Settings
|     | configuration  |     | the pop-up alarm mode.  |     |     |     |     |     |     |
| --- | -------------- | --- | ----------------------- | --- | --- | --- | --- | --- | --- |
Corresponding to the permissions and roles in user
management, it is used to configure the device
System configuration
|     |     |     | operation  | and  | data  | browsing  | permissions  |     | of  |
| --- | --- | --- | ---------- | ---- | ----- | --------- | ------------ | --- | --- |
different roles.
|     |     |     |     |     |     |     |     |     |     |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
17

Function introduction
3 Function introduction
3.1 Monitoring
The monitoring function mainly refers to centralized monitoring and control of energy storage
sites. The EnOSTM BESS SCADA system provides the different types of sites with the
monitoring pages that support different business needs. See the figure below for the overall
monitoring device-level topology of the energy storage system. At the site level, the site
homepage is provided for overall overview monitoring; at the subsystem level, the electrical
topology of subsystem is provided to monitor the composition and connection relationships
among devices; at the device level, the system provides both the list-based and detailed
monitoring information of subsystems, converters, battery arrays, battery clusters, air
conditioners, and measurement and control devices.
Figure 2: Energy storage monitoring device-level topology
3.1.1 Homepage
The homepage of energy storage site displays the real-time operating information of the
site in the form of figures and curves. It provides a unified monitoring platform, which is
convenient for users to understand the operation status of energy storage site in time and
improve the site monitoring efficiency. The homepage of the energy storage site is shown
in Figure 3.
18

Function introduction
Figure 3: Homepage of energy storage site
The main functions are as follows:
⚫ Station information overview, including the installed capacity of the station, the proportion
of faults of various types of equipment, and supporting to click on the device name to drill
down to the equipment list for fault screening and positioning.
⚫ Real-time data overview, which provides an overview of real-time data to help users
intuitively understand the overall operation of the site.
⚫ Status monitoring statistics, which counts the number of subsystems in different states,
and you can directly click on each status statistics to drill down to the device list to view
details.
⚫ Curve-based display, which provides the trend curves of important measurement points of
the site under different time granularity; the time granularity is customizable and the
measurement points can be selected within a certain range.
⚫ Subsystem distribution, which shows the relative distribution positions of all subsystems
under the site; you can hover the mouse over important measurement points and status
of each subsystem for monitoring, and click a "Subsystem Number" to jump to the electrical
topology page of the energy storage subsystem. Click Edit to enter the editing mode,
where you can drag and drop the distribution position of each subsystem and edit the
display number of the subsystem.
3.1.2 Subsystem of electrical topology
The electrical topology of energy storage subsystem is used to display the connection
relationship between the feeder, box transformer and subsystem, the state of the switch, the
operation status of the subsystem and the key operation data.
19

Function introduction
The main functions are as follows:
⚫ Subsystem information overview, including real-time operation status of subsystems and
statistics of devices under the subsystem. When the number of faults is greater than 0,
it will be displayed in red, and click the corresponding device name to drill down to the
device list for fault filtering and locating;
⚫ Electrical topology of subsystem, which is used to monitor the connection relationships
among devices, the switch status, and the device operation status. With the topology,
users can intuitively view the connection relationships among devices and judge the switch
status and the device operation status through the color (the connection interruption is
preferred, and the operation status is displayed if the communication is normal). You can
click the device to drill down to the device details for each device to locate the problem.
⚫ Device information monitoring, including the key operation information of important
devices, such as protection and measuring-control devices, converters, and battery
clusters in the subsystem.
Figure 4: Electrical topology of energy storage subsystem
3.1.3 Electrical topology
The electrical topology of the station displays the connection status of electrical equipment, the
state of the switch and the status of the subsystem in the form of wiring diagrams, and provides
the monitoring of important measurement points of the box transformers and the subsystems.
It is convenient for users to monitor and control the important measurement points of the switch
and box transformer of the station, and the electrical topology is shown in the following figure:
20

Function introduction
Figure 5: Electrical topology of energy storage station
The main functions are as follows:
⚫ The wiring diagram of the station, including the connection status of each box transformer
and related electrical equipment, etc.
⚫ Real-time data overview, providing monitoring of all box transformers and important
measurement points of subsystems of the power station, helping users intuitively
understand the overall operation of the station.
⚫ Support switch name modification to meet the needs of different users for switch definition.
⚫ Measurement point configuration: Support the configuration of different monitoring
measurement points and customized display styles to meet the monitoring needs of
different users.
3.1.4 Device list
The device list page can be switched through the tabs to display the device lists of different
access devices. This page displays the monitoring information of various devices under the site
through three ways: large card, small card and list, and you can switch among them through 3
different icons in the upper right corner of different pages. Each mode covers the device status
statistics. Also, you can click the configuration button in the upper right corner of the page
for filter configuration, card configuration, and table configuration. The display content and
styles can be flexibly adjusted, changed and saved to adapt to the diversity of screen needs.
The right side of the filter bar displays the number statistics of each listed object by default and
supports filtering, and you can click the name of each device to perform the listing operation.
21

Function introduction
With the large card-based mode, you can intuitively understand the operating status and key
operating indicators of devices, quickly locate abnormal devices, and check the overview of all
the operation and statistical information of devices. You can adjust the information to be
displayed through the "Card Configuration".
Figure 6: Large card-based device list
The small card-based mode is suitable for scenarios with a large number of devices, such as
battery clusters, so as to provide an overview of as many devices as possible and facilitate the
timely detection of abnormal operations. The icon color and style are consistent with those
configured in the large card-based mode.
Figure 7: Small card-based device list
The list-based mode supports the display of all devices and their key operating indicators. You
can freely sort the status details, active power, reactive power, health, and communication
status. You can adjust the information to be displayed through the "table Configuration". Also,
it supports setting of benchmarking devices, and benchmarking devices are always on top.
22

Function introduction
Figure 8: List-based device list
The main functions are described as follows:
⚫ Displays the types of devices connected to the site; you can click each tab to view the
list of different types of devices.
⚫ Provides the quick overview of device status, where the devices of different states will
be marked with different colors and filter labels for you to quickly filter and locate faulty
device.
⚫ Supports the status statistics of each device, which is convenient for users to quickly
understand the running status of each device.
⚫ Supports quick search of target device based on device name.
⚫ You can switch among three modes: large card, small card, and list, and zooming is
supported for large card-based and small card-based modes.
⚫ You can click to edit device indicators, icon color, and style displayed in the device
list.
⚫ The large and small card mode supports the token operation of each device, as well as
the number of attached device objects to count and filter.
⚫ You can click a device card to enter the corresponding single device monitoring page.
3.1.4.1 Single device monitoring
The single device monitoring mainly covers subsystems, converters, battery arrays, battery
clusters, air conditioners, protection measuring-control and liquid cooling devices, which are
automatically displayed according to the actual type of device connected to the site. The details
of a single device are generally distributed as follows:
23

Function introduction
Figure 9: Single device details
The main functions are described as follows:
⚫ You can click "List" to return to the device list page.
⚫ You can click to quickly switch to the previous or next device to improve inspection
efficiency, or you can directly click the device name to appear in the asset tree to quickly
switch between any device.
⚫ Displays important information of devices, such as real-time running status, health status,
and communication status.
⚫ Supports remote start and stop operations of some devices.
⚫ Supports the token operation, the device will automatically block the alarms with the token.
⚫ Displays the operation information. You can click " " to set the displayed measurement
points and the display style; Click " " to pop up the window to enlarge the display box,
and you can view more real-time data of measurement points. “All Data” support the
search function.
⚫ Display the light signs, you can click the icon to "update flashing", "return to hide" and "top
level" configuration, etc.
⚫ Supports the display of important measurement point curves with different time granularity,
such as active power, reactive power, subsystem charging and discharging. Also, the color,
style, range and other attributes of curves are customizable.
24

Function introduction
⚫ Displays the real-time alarm information, and supports the filtration by alarm type and
alarm level.
Some devices will display personalized functions according to the needs of actual monitoring.
The following is the detailed introduction to various devices.
3.1.4.2 Subsystem
The subsystem list displays all the subsystems at the site and their key operating indicators.
Also, you can click a card or a list line to enter the corresponding subsystem detail page.
Figure 10: Subsystem device list
The main functions are described as follows:
⚫ Displays the operating status, the health status and the quantity statistics of various
states for all subsystems. By default, the filter bar displays the operating status, including
fault shutdown, user shutdown, maintenance and repair, discharge operation, charging
operation, equipment standby and connection interruption status. The health status is
displayed in the upper left corner of each card below, including normal, alarm, and fault.
⚫ You can click any card or list line to enter its corresponding detail page. The detail page
shows the operating status and real-time running data of the device.
25

Function introduction
Figure 11: Subsystem details
3.1.4.3 Converter
The converter list displays all the converters at the site and their key operating indicators. Also,
you can click a card or a list line to enter the corresponding converter detail page.
Figure 12: Converter device list
The main functions are described as follows:
⚫ Displays the operating status, the health status and the quantity statistics of various
states for all converters. By default, the filter bar displays the operating status, including
fault shutdown, user shutdown, maintenance and repair, discharge operation, charging
operation, equipment standby and connection interruption status. The health status is
displayed in the upper left corner of each card below, including normal, alarm, and fault.
26

Function introduction
⚫ You can click any card or list line to enter its corresponding detail page. The detail page
shows the operating status and real-time running data of the device.
Figure 13: Converter details
3.1.4.4 Battery Array
The Battery Array list displays all the battery arrays at the site and their key operating indicators.
Also, you can click a card or a list line to enter the corresponding battery array detail page.
Figure 14: Battery array device list
The main functions are described as follows:
⚫ Displays the operating status, the health status and the quantity statistics of various
states for all battery arrays. By default, the filter bar displays the operating status,
including fault shutdown, user shutdown, maintenance and repair, discharge operation,
27

Function introduction
charging operation, equipment standby and connection interruption status. The health
status is displayed in the upper left corner of each card below, including normal, alarm,
and fault.
⚫ You can click any card or list line to enter its corresponding detail page. The detail page
shows the operating status and real-time running data of the device.
Figure 15: Battery array details
3.1.4.5 Battery Cluster
The Battery Cluster list displays all the battery clusters at the site and their key operating
indicators. Also, you can click a card or a list line to enter the corresponding battery cluster
detail page.
Figure 16: Battery cluster device list
The main functions are described as follows:
28

Function introduction
⚫ Displays the operating status, the health status and the quantity statistics of various
states for all battery clusters. By default, the filter bar displays the operating status,
including fault shutdown, user shutdown, maintenance and repair, discharge operation,
charging operation, equipment standby and connection interruption status. The health
status is displayed in the upper left corner of each card below, including normal, alarm,
and fault.
⚫ You can click any card or list line to enter its corresponding detail page. The detail page
shows the operating status and real-time running data of the device.
Figure 17: Battery cluster details
The personalized functions of the battery cluster detail page are described as follows:
⚫ Supports the visual display of full cell voltage and temperature under a battery cluster,
where the cell voltage and temperature values are distinguished according to different
colors, and the position of the highest/lowest cell temperature/voltage can be located.
3.1.4.6 Air Conditioner
The Air Conditioner list displays all the air conditioners at the site and their key operating
indicators. Also, you can click a card or a list line to enter the corresponding air conditioner
detail page.
29

Function introduction
Figure 18: Air conditioner device list
The main functions are described as follows:
⚫ Displays the operating status, the health status and the quantity statistics of various
states for all air conditioners. By default, the filter bar displays the operating status,
including fault shutdown, user shutdown, maintenance and repair, running, and
connection interruption status. The health status is displayed in the upper left corner of
each card below, including normal, alarm, and fault.
⚫ You can click any card or list line to enter its corresponding detail page. The detail page
shows the operating status and real-time running data of the device.
Figure 19: Air conditioner details
30

Function introduction
3.1.4.7 Protection and Measuring-control Devices
The Protection and Measuring-control Devices device list displays all the measurement and
control devices at the site and their key operating indicators. Also, you can click a card or a list
line to enter the corresponding protection and measuring-control devices detail page.
Figure 20: Protection and measuring-control device list
The main functions are described as follows:
⚫ Displays the operating status, the health status and the quantity statistics of various
states for all protection and measuring-control devices. By default, the filter bar displays
the operating status, including fault shutdown, user shutdown, maintenance and repair,
running, standby and connection interruption status. The health status is displayed in the
upper left corner of each card below, including normal, alarm, and fault.
⚫ You can click any card or list line to enter its corresponding detail page. The detail page
shows the operating status and real-time running data of the device.
Figure 21: Protection and measuring-control device details
The personalized functions of the protection and measuring-control device detail page are
described as follows:
31

Function introduction
⚫ Supports the display of the primary wiring diagrams of the protection and measuring-
control devices, support editing and displaying the device numbers such as switches and
circuit breakers.
3.1.4.8 Liquid cooling
The liquid cooling device list displays all the DC liquid cooling devices at the site and their key
operating indicators. Also, you can click a card or a list line to enter the corresponding DC liquid
cooling devices detail page.
Figure 22: Liquid cooling device list
The main functions are described as follows:
⚫ Displays the operating status, the health status and the quantity statistics of various
states for all protection and measuring-control devices. By default, the filter bar displays
the operating status, including fault shutdown, user shutdown, maintenance and repair,
cooling running, heater running, circulation running and connection interruption status.
The health status is displayed in the upper left corner of each card below, including
normal, alarm, and fault.
⚫ You can click any card or list line to enter its corresponding detail page. The detail page
shows the operating status and real-time running data of the device.
Figure 23: Liquid cooling device details
32

Function introduction
3.1.4.9 DC Converter
The DC Converter device list displays all the DC Converter devices at the site and their key
operating indicators. Also, you can click a card or a list line to enter the corresponding DC
Converter devices detail page.
Figure 24: DC Converter device list
The main functions are described as follows:
⚫ Displays the health status, total fault and real-time running data. The health status is
displayed in the upper left corner of each card below, including normal, alarm, and fault.
⚫ You can click any card or list line to enter its corresponding detail page. The detail page
shows the operating status and real-time running data of the device.
Figure 25: DC Converter device details
3.1.4.10 Other Devices
The list of other devices displays all other non-standard equipment that is not of particular
concern under the station, such as dehumidifiers, etc., to realize the monitoring of all connected
devices under the station. You can click on the card to jump to the corresponding device details
screen.
33

Function introduction
Figure 26: Other devices list
The details page shows the real-time operating data and alarm of the device:
Figure 27: Other devices details
3.1.5 Token List
The token list table page displays all the records of the monitoring object in the station based
on the pages of the device list or single device detail, and the tokens can be carried out. Click
on the device object to drill down to the details page of the corresponding single device, view
the relevant operation information, and confirm the corresponding listing operation.
Figure 28: Token List
3.1.6 Favorite
When the on-duty personnel monitor the system, they may pay attention to multiple monitoring
pages. At present, most users rely on multiple monitoring screens to solve the problem. In order
34

Function introduction
to improve the convenience of switching back and forth in the case of more monitoring screens,
the system provides the favorite and rotate functions, and the pages in the favorite can
automatically redirect in turn to improve the efficiency of user monitoring. The main functions
are:
⚫ Click " Favorite" in the upper right corner, customize the page tag name and save, that
can be added the current page to the favorite list.
Figure 29: Add favorite
⚫ Display all the page tags that have been added to the favorites bar at the top of the page,
and you can click the page tag to quickly jump to the corresponding page. On the right,
you can start/pause the page rotation and set the page labels.
Figure 30: Favorite list
⚫ Click the settings button on the right to modify the name, delete, whether to rotate, and
set the rotation duration of the tags that have been added to the favorite page.
Figure 31: Favorite setting
35

Function introduction
3.2 Alarm
3.2.1 Real-time alarm
The site control system operating and alarm information is displayed in real time on the real-
time alarm page. The display style of alarm information in the page can be customized by the
user on the alarm template configuration page. After the settings are completed, the real-time
alarm interface will display the alarm information according to the set template. On the real-
time alarm page, users can filter, sort and confirm the alarm information, and can filter the alarm
information by confirmation status, alarm type, alarm level, field, application and activity. The
alarm types supported by the system include: remote signal displacement, remote signal SOE,
telemetry limit violation, working condition information, manual operation, remote control and
remote adjustment, protection events, etc. For remote signal displacement and fault (SC) types
of alarms, users can configure and modify records on the interface. For the real-time alarms,
the alarms at levels below the interval are given by application.
If the frequency of a specific type of alarm from a specific device exceeds a predefined threshold
within a certain time window, the historical alarms will be removed from the database to reduce
storage load, while still retaining full traceability via the archived CSV files.
Once the alarm frequency exceeds the configured threshold, the system will also generate a
summarized archival alarm, such as:
“[Alarm Type] occurred [X] times from [Start Time] to [End Time] at [Object].”
This helps operators quickly understand the context and volume of repetitive alarm events
without reviewing each instance individually.
Figure 32: Real-time alarms
You can configure the pop-up alarm configuration on the page according to the alarm template,
and pop up a single pop-up window or a double pop-up window (the fault pop-up window and
the alarm pop-up window appear separately and independently).
36

Function introduction
Based on historical alarm data, the system supports more advanced alarm analysis functions.
You can click the button with "Analyse" in the "Operate" column to enter the corresponding
analysis function interface. At present, the energy storage station supports the frequency
analysis function.
Figure 33: Alarm analysis
3.2.1.1 Frequency analysis
Frequency analysis mainly includes longitudinal analysis and horizontal analysis. Based on the
analysis results, you can perform operations such as not alarming, modifying the alarm level,
and disabling voice. The main functions are:
⚫ Longitudinal analysis: You can analyze the frequency of alarms every day in the past
week. Analyze the number of alarms of the same type on the same device to reflect the
running status of the device.
37

Function introduction
Figure 34: Longitudinal analysis
⚫ Horizontal analysis: Supports selecting alarms for the same type of devices at the same
time. By analyzing the number of alarms of different devices of the same type, the
differences in operation between devices of the same type are reflected.
Figure 35: Horizontal analysis
3.2.2 Historical alarm
The historical alarm function is mainly used to search various alarm information that has
occurred. Users can filter and query alarms by alarm type, device, alarm time, and alarm level.
The user can save the query conditions as a query template to facilitate the next query for the
same type and level of alarm information. The query results can be exported into CSV, XLS,
PDF and other formats and saved to the specified path.
38

Function introduction
Figure 36: Historical alarms
3.3 Report
3.3.1 Energy report
The site control system module provides the energy reports in the field of energy storage. The
statistics of daily, monthly and annual energy are made from two dimensions, i.e. energy
storage site and energy storage subsystems, including active and reactive discharge/discharge
power and energy conversion efficiency. Users can also export and save the data of energy
storage power report as CSV, XLS or PDF files according to actual needs.
Figure 37: Energy report
3.3.2 Operation report
From the dimensions of energy storage stations and energy storage subsystems, electricity
statistics can be carried out in the time dimensions of day/week/month/year/total respectively,
and the data include the total charging and discharging Energy, service factor, service hours,
charging/discharging/stanby hours, charging and discharging times, charging and discharging
depth, utilization factor, charging and discharging utilization hours, etc. Users can also export
and save the data from running reports as CSV, XLS, or PDF files according to their actual
needs. The definitions of each indicator are detailed in Appendix I.
39

Function introduction
Figure 38: Operation report
3.3.3 TBA report
The station control system module provides a utilization report in the field of energy storage.
Supports daily, weekly, monthly, and annual statistics for stations and subsystems within a
specified time range. At the same time, it provides the function of editing the shutdown record
for external reasons for the device type to solve the problem that the availability of the
equipment itself and the external cause is lower than the actual utilization rate.
3.3.3.1 TBA
You can query and export the availability of a site/subsystem within a specified time range,
such as daily, weekly, monthly, or yearly.
Figure 39: TBA report
3.3.3.2 Downtime record
You can query subsystem-oriented downtime records, edit downtime and reason, and export
downtime record data within a specified time range. At the same time, it supports the export of
1min-level reporting reports, power supply network data reporting, and other needs.
40

Function introduction
Figure 40: Downtime record
Click the button next to the end time to quickly split the shutdown record. In addition, you
can check multiple shutdown records, click the "Batch Edit" button to edit the availability and
reason of the shutdown record subsystem, and explain the situation in the remarks.
3.4 Analysis
3.4.1 Trend analysis
The trend analysis tool can reflect the change trend of the telemetry value, the remote signal
value and the electrical measurement in the form of tables and curves. Users can compare the
historical values of measurement points in the form of curves or tables, and can query the
maximum and minimum historical values of telemetry points. The system supports
simultaneous display and selective cross-comparison of the curves of different colors for
multiple measurement points as well as the zooming-in/zooming-out of curves. The searched
records can be exported to the specified path in CSV, XLS, PDF and other formats. The main
functions are as follows:
⚫ Customization of consistency analysis templates based on device type and model is
supported. For example, it supports battery pack differential pressure analysis,
temperature differential analysis, and current analysis by default; Cell pressure difference
analysis, temperature difference analysis, etc., you can directly select the corresponding
template for query and analysis within the time range needed.
⚫ The maximum, minimum, and average statistics of the queried data can be performed.
⚫ Data can be queried by day, week, month, year, or custom time range.
⚫ Supports year-on-year and month-on-month analysis in the corresponding time
dimension.
41

Function introduction
Figure 41: Trend graph curve
Figure 42: Template and display style editing
Figure 43: Trend chart table
42

Function introduction
3.4.2 Scatter analysis
The scatter analysis can reflect the change trend of the telemetry value in the form of tables
and curves. Users can compare the historical values of measurement points in the form of
curves or tables. The system supports display and selective cross-comparison for multiple
measurement points as well as the zooming-in/zooming-out of curves. The searched records
can be exported to the specified path in CSV, XLS, PDF and other formats.
Figure 44: Scatter analysis curve
Figure 45: Scatter analysis table
43

Function introduction
3.4.3 Data export
The data export function supports on-demand export of measurement point data and historical
alarms, and supports multi-dimensional customized export such as device type, sampling
granularity, asset selection, measurement point selection, time range selection, etc., and
downloads or deletes. At the same time, this function supports saving export conditions as
templates.
Figure 46: Data export
Figure 47: Export template editing
3.5 Setting
The system settings mainly covers three modules: operation parameters, alarm template
configuration, and password modification.
⚫ Operating parameters: set the parameters of energy storage operation.
44

Function introduction
⚫ Alert template configuration: used to customize the real-time alarm template and set the
pop-up alarm mode.
⚫ Password modification: used to reset the password of the current login account;
3.5.1 Operating parameters
The alarm template configuration is mainly to provide users with the role of super user with the
function of real-time alarm template customization and the function of pop-up alarm mode
setting.
Figure 48: Alert template customization
Figure 49: Pop-up alarm mode settings
3.5.2 Password Modify
This part is mainly used to reset the password of the current login account.
45

Function introduction
Figure 50: Modify the password
3.6 User management
The user management covers two categories: account management and role management.
Only administrators have user management permission.
The account management function mainly refers to the addition, deletion and modification of
users, the setting of login homepage, password and LOGO, and the association of account and
role permissions. In addition, the super user has the permission to unlock any locked user. If
the user name or password is entered incorrectly three times in a row when a user logs into the
system, the account will be locked. At this time, the super user can unlock the account through
the user unlocking function so that the user can log into the system immediately.
46

Function introduction
Figure 51: User management
Figure 52: User unlocking function
The role management function is mainly to establish corresponding job roles according to
business needs. At the same time, these positions can be cross-configured with business fields,
which means strong role establishment flexibility.
For example, if the roles of system administrator, duty officer, duty leader are established, the
roles of wind farm duty officer, solar duty leader and booster station visitor can be formed by
combining with wind, solar and hydropower, just to name a few. The final role will match the
screens of business field, that is, the solar duty leader can only access the corresponding
screens of solar site, and cannot access the screens of hydro site or booster station; the booster
47

Function introduction
station visitor can only access the booster station screens and does not have the operation
permissions. The functions of adding roles, modifying role permissions and deleting roles are
shown in the figure below.
Figure 53: Role management
48

System Performance
4  System Performance
4.1  Access capacity
Based on real-time databases, timing databases and general commercial relational databases,
the EnOSTM BESS SCADA system is designed with a distributed scheme to organize massive
data, create data models, establish data relationships, collect real-time data, and quickly access
the historical data. A single node supports a maximum access scale of 200,000 points.
4.2  Data storage
The historical data storage mainly covers 1-min data, event information and report data. The 1-
min data and 10-min data are acquired through sampling, and the cycle selected on the data
collection device can be used as the shortest storage cycle without the restriction on the number
of sampling points. The event information is completely recorded in the historical database to
ensure traceability and benchmarking. In addition, the system provides the report data that
reflects the operating status of different devices, and stores it in the historical database.
The historical data storage capacity is calculated according to the following table:
Type  Storage period  Capacity increment  Required capacity
(for every 100K points)
| Historical  | 10 years  | 5 GB/100K points/year  | 50 GB  |
| ----------- | --------- | ---------------------- | ------ |
report
| 1-min data  | 2 years  | 5 GB/100K points/year  | 800 GB  |
| ----------- | -------- | ---------------------- | ------- |
| Event       | 2 years  | 5 GB/100K points/year  | 200 GB  |
information
4.3  Performance indicators
⚫  System redundancy indicators
| Hot standby switching time   |     |     | ≤ 3s    |
| ---------------------------- | --- | --- | ------- |
| Cold standby switching time  |     |     | ≤1 min  |
⚫  System computer resource load rate indicators
| Average CPU load rate (within any 5 minutes)   |     |     | ≤40%           |
| ---------------------------------------------- | --- | --- | -------------- |
| Standby space (root zone)                      |     |     | ≥20% (or 10G)  |
⚫  SCADA indicators
49

System Performance
Number of accessible points per distributed front-end ≤ 100000 points
group
Number of accessible points for a single site control ≤ 200000 points
node
Real-time data change update delay ≤1 s
Accessible points for remote control ≥30000
Master site remote output delay ≤1 s
Event recording resolution ≤1 ms
Remote signal displacement transmission time ≤2 s
One-hour data export ≤5 min
Daily report calculation ≤5 min
Raw data storage ≤2 years
50

Deployment Requirements
5 Deployment Requirements
5.1 Software environment
The software environment for the system is described as follows:
Software Version
OS Linx v6/Ubuntu 22(containerization)
MySQL v5.7
Chrome V90.0+
5.2 Hardware Requirement
Processor (CPU): Quad-core processor,2.1 GHz or higher
Memory (RAM): 32 GB
Storage:7.2 T
5.3 System security
In order to improve its security, the system has been enhanced for its security protection
capabilities from four aspects: permission management, security audit, account security and
session management.
5.3.1 Permission management
In order to improve the system security, three independent management roles, including system
administrator, audit administrator, and business configurator, are set for the system. Different
roles have independent management permissions and management scope.
The role of audit administrator only has the permissions to monitor the operation tracks of other
types of users and to manage, monitor and operate & maintain audit records. The audit records
mainly cover events, user names, user IPs, audit event types, event levels, and event
categories. The audit event types mainly include: manual remote signaling lockout, manual
telemetry lockout, manual remote control, manual remote adjustment, manual card placement,
user event login, user login/logout, and early warning in audit log. The event levels include hints,
alarms and failures. The event categories cover business level and system level, where the
system-level events include user event login, user login/logout, and early warning in audit log
while the business-level events include manual remote signaling lockout, manual telemetry
lockout, manual remote control, manual remote adjustment, and manual card placement.
51

Deployment Requirements
The role of system administrator only has system management permissions, including user
management, role management, permission management and configuration customization.
The role of business configurator only has the permissions for basic configuration of various
parameters, master data and functions.
The business operators are the end business users of the system, and have no management
permissions. Also, the permissions of mutually exclusive services cannot be granted to the
same business user.
5.3.2 Security audit
The system performs the security audit on important user behaviors and security events of the
operating system and database systems. Such audit covers all the users and the audit records
include the event date and time, user, event type, and other audit-related information.
⚫ The system regularly backs up the audit records of the operating systems and database
systems, and the audit records cannot be tampered with;
⚫ The application audit records of the system can be exported, classified, sorted, inquired
and statistically analyzed
5.3.3 Account security
In order to achieve account security, the system increases constraints on the password
complexity and the number of logins.
⚫ Login verification
When a user logs into the system, the system will judge and determine whether the password
strength verification is required, whether it is the first login for the user, whether the password
has expired and has not been changed, and whether the user is locked after three failed logins.
⚫ Password complexity verification
When a user changes the password on the password modification page, the system will verify
the password complexity, requiring a combination of uppercase and lowercase letters, symbols
and numbers, which should be no less than 8 characters and should not as the same as the
user name.
⚫ Ciphertext transfer
The system uses AES symmetric encryption for encryption and decryption to ensure the
confidentiality of data transfer.
52

Deployment Requirements
5.3.4 Session management
⚫ The system has a session termination mechanism. When the user does not respond within
30 minutes, the server will automatically end the session;
⚫ The system will automatically end the session when the user logs off or closes the client.
⚫ The system can limit the maximum number of concurrent sessions and prohibit the same
user from logging into the system repeatedly.
53

|     |     |     |     | Appendix I Indicators Definition  |     |     |
| --- | --- | --- | --- | --------------------------------- | --- | --- |
Appendix I Indicators Definition
➢  Energy report
| Name  | Description  |     | Statistical  | Time       | Data sources  |     |
| ----- | ------------ | --- | ------------ | ---------- | ------------- | --- |
|       |              |     | level        | hierarchy  |               |     |
Active  The sum of the positive  Station/subsy Day/Week/M Active  Power
Power  active power on the AC  stem  onth/Year/To Production  of
|     | side  of  | the  energy  |     | tal  | subsystem  |     |
| --- | --------- | ------------ | --- | ---- | ---------- | --- |
Production
storage unit.
Active  The sum of the reverse  Station/subsy Day/Week/M Active  Power
Power  active power on the AC  stem  onth/Year/To Consumed  of
|     | side  of  | the  energy  |     | tal  | subsystem  |     |
| --- | --------- | ------------ | --- | ---- | ---------- | --- |
Consumed
storage unit.
Reactive  The sum of the positive  Station/subsy Day/Week/M Reactive  Power
Power  reactive power on the  stem  onth/Year/To Production  of
| Production  | AC side of the energy  |     |     | tal  | subsystem  |     |
| ----------- | ---------------------- | --- | --- | ---- | ---------- | --- |
storage unit.
Reactive  The sum of the reverse  Station/subsy Day/Week/M Reactive  Power
Power  reactive power on the  stem  onth/Year/To Consumed  of
|     | AC side of the energy  |     |     | tal  | subsystem  |     |
| --- | ---------------------- | --- | --- | ---- | ---------- | --- |
Consumed
storage unit.
Energy  The ratio of the amount  Station/subsy Day/Week/M Active Power and
Conversion  of active discharge to  stem  onth/Year/To Reactive  Power
| Efficiency  | the  amount  | of  active  |     | tal  | Production  | of  |
| ----------- | ------------ | ----------- | --- | ---- | ----------- | --- |
|             | charge       |             |     |      | subsystem   |     |

|     |     |     |     |     |     |     |
| --- | --- | --- | --- | --- | --- | --- |
54

Appendix I Indicators Definition
➢  Operation report
| Name  | Description  |     | Statistica | Time  | Data sources  |
| ----- | ------------ | --- | ---------- | ----- | ------------- |
l level  hierarchy
Dischar The total discharge of PCS at the  Station/su Day/Week/M Active  Power
ged  energy storage station  bsystem  onth/Year/To Production  of
| Energy  |     |     |     | tal  | PCS  |
| ------- | --- | --- | --- | ---- | ---- |
@PCS
Charged  The total charging capacity of the  Station/su Day/Week/M Active  Power
Energy  PCS of the energy storage station  bsystem  onth/Year/To Consumed  of
| @PCS  |     |     |     | tal  | PCS  |
| ----- | --- | --- | --- | ---- | ---- |
Service  The ratio of the operating hours of  Station/su Day/Week/M Service hours
| Factor  | the energy storage power station  |     | bsystem  | onth/Year/To |     |
| ------- | --------------------------------- | --- | -------- | ------------ | --- |
|         | to the statistical time.          |     |          | tal          |     |
Service  The  operating  time  of  the  Station/su Day/Week/M Subsystem
Hours  station/energy  storage  unit  (the  bsystem  onth/Year/To operating
|     | sum  of      | charging  | hours  and  | tal  | status  |
| --- | ------------ | --------- | ----------- | ---- | ------- |
|     | discharging  | hours)    | and  the    |      |         |
Subsystem
|     | weighted  | average  of  | the  rated  |     |     |
| --- | --------- | ------------ | ----------- | --- | --- |
rated power
power of each energy storage unit
Charged  The number of hours when the  Station/su Day/Week/M Subsystem
Hours  energy storage power station is in  bsystem  onth/Year/To operating
|     | the  charging  | state,          | and  the     | tal  | status  |
| --- | -------------- | --------------- | ------------ | ---- | ------- |
|     | charging       | hours  of       | the  energy  |      |         |
|     | storage        | power  station  | are          |      |         |
weighted according to the rated
|     | capacity  | of  the  energy  | storage  |     |     |
| --- | --------- | ---------------- | -------- | --- | --- |
unit.
Dischar The  number  of  hours  that  the  Station/su Day/Week/M Subsystem
ged  energy storage power station is in  bsystem  onth/Year/To rated power
| Hours  | the  discharge  | state,          | and  the     | tal  |     |
| ------ | --------------- | --------------- | ------------ | ---- | --- |
|        | discharge       | hours  of       | the  energy  |      |     |
|        | storage         | power  station  | are          |      |     |
weighted according to the rated
55

|     |           |                  |          | Appendix I Indicators Definition  |     |
| --- | --------- | ---------------- | -------- | --------------------------------- | --- |
|     | capacity  | of  the  energy  | storage  |                                   |     |
unit.
Standby  The  number  of  hours  that  the  Station/su Day/Week/M Subsystem
Hours  energy storage power station is in  bsystem  onth/Year/To operating
|     | standby mode, and the standby  |                  |           | tal  | status  |
| --- | ------------------------------ | ---------------- | --------- | ---- | ------- |
|     | hours                          | of  the  energy  | storage   |      |         |
|     | power                          | station  are     | weighted  |      |         |
according to the rated capacity of
the energy storage unit.
Charged  A charge should meet: the full- Station/su Day/Week/M Subsystem/st
Times  field  charging  power  is  greater  bsystem  onth/Year/To ation  active
|     | than 5% of the rated power of the  |     |     | tal  | power  |
| --- | ---------------------------------- | --- | --- | ---- | ------ |
station, and the duration is greater
Subsystem/st
than 15 minutes (the duration of a
ation  rated
grid dispatching period), and the
power
default 5% is configurable
Dischar The primary discharge should be  Station/su Day/Week/M Subsystem/st
ged  satisfied: the full-field  discharge  bsystem  onth/Year/To ation  active
| Times  | power is greater than 5% of the  |     |     | tal  | power  |
| ------ | -------------------------------- | --- | --- | ---- | ------ |
rated power of the station, and the
Subsystem/st
|     | duration  | is  greater  | than  15  |     |     |
| --- | --------- | ------------ | --------- | --- | --- |
ation  rated
|     | minutes  | (the  length  | of  a  grid  |     |     |
| --- | -------- | ------------- | ------------ | --- | --- |
power
|     | dispatching  | period),  | and  the  |     |     |
| --- | ------------ | --------- | --------- | --- | --- |
default 5% is configurable
Depth of  The  weighted  average  Station/su Day/Week/M Subsystem/st
discharg charge/discharge  depth  of  the  bsystem  onth/Year/To ation SOC
| e   | energy storage power station is  |     |     | tal  |     |
| --- | -------------------------------- | --- | --- | ---- | --- |
Subsystem/st
|     | comprehensively  | calculated  | by  |     |     |
| --- | ---------------- | ----------- | --- | --- | --- |
ation  active
using the daily charge-discharge
power
|     | state  (SOC)  | extreme  | difference  |     |     |
| --- | ------------- | -------- | ----------- | --- | --- |
production
|     | and  the  | daily  discharge  | as  the  |     |     |
| --- | --------- | ----------------- | -------- | --- | --- |
weight of the extreme on the basis
of the total discharge.
56

Appendix I Indicators Definition
Utilizatio The ratio of the utilization hours of  Station/su Day/Week/M Utilization
n Factor  the energy storage power station  bsystem  onth/Year/To hours
|     | to the statistical hours.  |     |     | tal  |
| --- | -------------------------- | --- | --- | ---- |
Utilizatio The sum of the actual amount of  Station/su Day/Week/M Active  Power
n Hours  electricity  (including  the  actual  bsystem  onth/Year/To Production
|     | discharge and actual charging) of  |     |     | tal  |
| --- | ---------------------------------- | --- | --- | ---- |
Active  Power
|     | all  energy  | storage  | units  in  the  |     |
| --- | ------------ | -------- | --------------- | --- |
Consumed
|     | energy  | storage  power  | station,  |     |
| --- | ------- | --------------- | --------- | --- |
Rated
|     | divided  | by  the  rated  | capacity  |     |
| --- | -------- | --------------- | --------- | --- |
capacity
(kWh) of the station.
Charged  The number of hours obtained by  Station/su Day/Week/M Active  Power
Utilizatio dividing  the  total  charging  bsystem  onth/Year/To Consumed
| n Hours  | capacity  | of  all  energy  | storage  | tal  |
| -------- | --------- | ---------------- | -------- | ---- |
Rated
units in the energy storage plant
capacity
by the rated capacity (kWh) of the
station.
Dischar The number of hours obtained by  Station/su Day/Week/M Active  Power
ge  dividing the total discharge of all  bsystem  onth/Year/To Production
| Utilizatio | energy storage units in the energy  |     |     | tal  |
| ---------- | ----------------------------------- | --- | --- | ---- |
Rated
| n Hours  | storage power station by the rated  |     |     |     |
| -------- | ----------------------------------- | --- | --- | --- |
capacity
capacity (kWh) of the station.

|     |     |     |     |     |
| --- | --- | --- | --- | --- |
57

|     |     |     |     | Appendix II Service Ports  |
| --- | --- | --- | --- | -------------------------- |
Appendix II Service Ports
| Port  | Port type  | Service Name  |     | Remarks              |
| ----- | ---------- | ------------- | --- | -------------------- |
| 22    | TCP        | sshd          |     | Host                 |
| 123   | UDP        | ntp           |     | /                    |
| 3306  | TCP        | mysql         |     | Univers docker/Host  |
6500/6504- TCP  USCADA_upgrade_svr(vsftp)  Univers docker/Host
6510
| 4005  | TCP  | USCADA_webservice_svr   |     | Univers docker/Host  |
| ----- | ---- | ----------------------- | --- | -------------------- |
| 4006  | TCP  | USCADA_cgn_webservice_s |     | Univers docker       |
vr
| 4506       | TCP  | USCADA_fc_webservice      |     | Univers docker/Host  |
| ---------- | ---- | ------------------------- | --- | -------------------- |
| 4508-4509  | TCP  | Forecast                  |     | Univers docker       |
| 6870       | TCP  | USCADA_data_sync_client   |     | Univers docker       |
| 6871       | TCP  | USCADA_data_sync_client_r |     | Univers docker       |
ealtime
| 6872  | TCP  | USCADA_data_sync_server  |     | Univers docker  |
| ----- | ---- | ------------------------ | --- | --------------- |
| 6873  | TCP  | USCADA_data_sync_server  |     | Univers docker  |
_realtime
| 6888/6886  | TCP/UDP  | USCADA_msgbus_svr       |     | Univers docker       |
| ---------- | -------- | ----------------------- | --- | -------------------- |
| 7777/6872  | TCP      | USCADA_monitor          |     | Univers docker       |
| 8701       | TCP      | USCADA_tomcat7/scada_we |     | Univers docker/Host  |
b_gateway
| 8702  | TCP  | USCADA_tomcat7_2       |     | Univers docker  |
| ----- | ---- | ---------------------- | --- | --------------- |
| 8292  | TCP  | USCADA_WFPCConfigServi |     | Univers docker  |
ceHost
| 8890  | TCP  | USCADA_data_repair_servic |     | Univers docker  |
| ----- | ---- | ------------------------- | --- | --------------- |
e
58

Appendix II Service Ports
| 8892  | TCP  | USCADA_config_center_ser | Univers docker/Host  |
| ----- | ---- | ------------------------ | -------------------- |
vice
| 9100  | TCP  | USCADA_agc_bat_ctrl/USC | Univers docker  |
| ----- | ---- | ----------------------- | --------------- |
ADA_agc_ipower
| 9300         | TCP  | USCADA_db_login_service   | Univers docker/Host  |
| ------------ | ---- | ------------------------- | -------------------- |
| 15000        | TCP  | USCADA_tenmindata_wssvr   | Univers docker       |
| 15001        | TCP  | USCADA_alarmoption_wssvr  | Univers docker/Host  |
| 2401-2408    | TCP  | USCADA_iec104             | Univers docker       |
| 3000-3009    | TCP  | USCADA_iec102_zf          | Univers docker       |
|  3000-3099   | UDP  | USCADA_C_Net              | Univers docker       |
| 3100         | UDP  | USCADA_ForwardGapMQ       | Univers docker       |
| 4880         | TCP  | USCADA_opc ua server      | Univers docker       |
| 5020-5023    | TCP  | USCADA_MODBUS             | Univers docker       |
| 8079         | TCP  | USCADA_opc xml-da server  | Univers docker       |
| 20001-20200  | TCP  | USCADA_AdsProxy           | Univers docker       |
| 22221/22222  | UDP  | USCADA_fe_switch          | Univers docker       |
| 6501-6503    | TCP  | DMC                       | Univers docker       |
| 177          | UDP  | Xmanager                  | /                    |
| 6000-6010    | TCP  | Xmanager                  | /                    |
| 5901-5910    | TCP  | VNC                       | /                    |
| 443          | TCP  | nginx https               | Univers docker       |
| 6379         | TCP  | redis                     | Univers docker/Host  |
| 2501-2510    | TCP  | USCADA_NetGapFTP          | Univers docker       |
| 5560-5569    | TCP  | USCADA_NetGapFTP          | Univers docker/Host  |
| 6660-6669    | UDP  | USCADA_NetGapFTP代理        | Univers docker       |
| 6670-6719    | TCP  | USCADA_BackwardGapAge     | Univers docker       |
nt-C
59

|        |      |                          |     | Appendix II Service Ports  |
| ------ | ---- | ------------------------ | --- | -------------------------- |
| 61616  | TCP  | USCADA_MQ                |     | Univers docker/Host        |
| 1883   | TCP  | USCADA_scada_mqtt_svr    |     | Univers docker/Host        |
| 8161   | TCP  | USCADA_MQ_web            |     | Univers docker/Host        |
| 15005  | TCP  | USCADA_alarm_wssvr       |     | Univers docker             |
| 6511   | TCP  | USCADA_dataquality       |     | Univers docker             |
| 6512   | TCP  | USCADA_dataquality       |     | Univers docker             |
| 6513   | TCP  | USCADA_dataquality       |     | Univers docker             |
| 6514   | TCP  | USCADA_cfg_cntr_ssl_svr  |     | Univers docker             |
| 6515   | TCP  | USCADA_cfg_load_svr      |     | Univers docker             |
| 6516   | TCP  | USCADA_ukey-plugin.jar   |     | Univers docker             |
| 6517   | TCP  | USCADA_ukey-auth.jar     |     | Univers docker             |
| 6518   | TCP  | USCADA_dataset_svr       |     | Univers docker/Host        |
| 6519   | TCP  | USCADA_noise_ctrl_svr    |     | Univers docker             |
| 6520   | TCP  | USCADA_Analysis_Forecast |     | Univers docker             |
_Module
| 6521  | TCP  | /                        |     | /               |
| ----- | ---- | ------------------------ | --- | --------------- |
| 6526  | TCP  | USCADA_IT_monitor-agent  |     | Univers docker  |
| 6527  | TCP  | USCADA_IT_monitor-       |     | Univers docker  |
transfer
| 6528  | TCP  | USCADA_IT_monitor-web.jar  |     | Univers docker  |
| ----- | ---- | -------------------------- | --- | --------------- |
| 6522  | TCP  | USCADA_data_cascade_pro    |     | Univers docker  |
ducer
| 6524  | TCP  | USCADA_dataset_center_sv |     | Univers docker  |
| ----- | ---- | ------------------------ | --- | --------------- |
r
| 6523  | TCP  | USCADA_record_history_svr  |     | Univers docker  |
| ----- | ---- | -------------------------- | --- | --------------- |
| 6525  | TCP  | USCADA_auto-check-client   |     | Univers docker  |
| 6529  | TCP  | USCADA_proManSvr           |     | Univers docker  |
60

Appendix II Service Ports
| 6530  | TCP  | USCADA_secdata_query_sv | Univers docker  |
| ----- | ---- | ----------------------- | --------------- |
r
| 6531  | TCP  | emc                | Univers docker  |
| ----- | ---- | ------------------ | --------------- |
| 6532  | TCP  | USCADA_tensorflow- | Univers docker  |
detection
| 6533  | TCP  | USCADA_db_config_proxy_ | Univers docker  |
| ----- | ---- | ----------------------- | --------------- |
svr
| 6534  | TCP  | sshd                     | Host                 |
| ----- | ---- | ------------------------ | -------------------- |
| 6535  | TCP  | USCADA_fdb_remote_servic | Univers docker/Host  |
e
| 6536       | TCP  | USCADA_svc_fp_proxy  | Univers docker       |
| ---------- | ---- | -------------------- | -------------------- |
| 6537       | TCP  | USCADA_sc_service    | Univers docker       |
| 6538       | TCP  | model_service        | Univers docker/Host  |
| 6539       | TCP  | scada_web_service    | Univers docker/Host  |
| 6540       | TCP  | update_proxy_svr     | Univers docker/Host  |
| 6541       | TCP  | wave_task_mgr(PMS)   | Univers docker       |
| 6542       | TCP  | wave_task_mgr(FR)    | Univers docker       |
| 6543       | TCP  | wave_task_mgr(LOS)   | Univers docker       |
| 6544       | TCP  | tomcat7              | Univers docker       |
| 6545       | TCP  | Alarm                | Univers docker       |
| 6546       | TCP  | Alarm                | Univers docker       |
| 6547       | TCP  | New custom reports   |                      |
| 6544-6549  | TCP  | Reserved             | Univers docker       |
| 6550-6552  | TCP  | PMS                  | Univers docker       |
| 6553       | TCP  | USCADA_IMA           | /                    |
| 6554       | TCP  | emc-web              | /                    |
| 6555       | TCP  | emc-novnc            | /                    |
61

|            |      |                      |     | Appendix II Service Ports  |
| ---------- | ---- | -------------------- | --- | -------------------------- |
| 6556       | TCP  | emc-novnc            |     | /                          |
| 5500       | UDP  | emc-center           |     | /                          |
| 6600       | TCP  | emc-agent            |     | /                          |
| 7766       | TCP  | emc-center           |     | /                          |
| 6557-6599  | TCP  | Reserved Host        |     |                            |
| 6601-6659  |      | Reserved             |     |                            |
| 8088       | TCP  | FC/PMS               |     | Univers docker             |
| 8090       | TCP  | FC                   |     | Univers docker             |
| 7086       | TCP  | USCADA_influxdb      |     | influxdb docker            |
| 7088       | TCP  | USCADA_influxdb(app  |     | influxdb docker            |
docker)
| 7089  | UDP  | USCADA_influxdb(app  |     | influxdb docker  |
| ----- | ---- | -------------------- | --- | ---------------- |
docker)
| 5506  | TCP  | USCADA_GSP  |     | Univers docker       |
| ----- | ---- | ----------- | --- | -------------------- |
| 5507  | TCP  | USCADA_GSP  |     | Univers docker/Host  |
| 5508  | TCP  | USCADA_GSP  |     | Univers docker       |
| 5509  | TCP  | USCADA_GSP  |     | Univers docker       |
Active  The  sum  of  Station/subsystem  Day/Week/Month/Year/To
| Power  | the  reverse  |     |     | tal  |
| ------ | ------------- | --- | --- | ---- |
active  power
Consumed
|     | on  the  AC    |     |     |     |
| --- | -------------- | --- | --- | --- |
|     | side  of  the  |     |     |     |
energy
storage unit.
Reactive  The  sum  of  Station/subsystem  Day/Week/Month/Year/To
| Power       | the  positive  |     |     | tal  |
| ----------- | -------------- | --- | --- | ---- |
| Production  | reactive       |     |     |      |
power on the
|     | AC  side  | of  |     |     |
| --- | --------- | --- | --- | --- |
62

Appendix II Service Ports
the energy
storage unit.
Reactive The sum of Station/subsystem Day/Week/Month/Year/To
Power the reverse tal
reactive
Consumed
power on the
AC side of
the energy
storage unit.
Energy The ratio of Station/subsystem Day/Week/Month/Year/To
Conversion the amount of tal
Efficiency active
discharge to
the amount of
active charge
63

Documentation • Support • Feedback
Documentation • Support • Feedback
Document Services
High-quality product documentation is essential to our solution. Please contact
your Univers sales representative for the latest product documentation to
maximize your purchase.
Technical support
For professional guidance and assistance, access the online ticketing system
at any time to report an issue or raise a request by opening a ticket in an easy
and quick way.
Self-serving Online Ticketing System: https://support.univers.com/csm
User feedback
We welcome your comments and suggestions regarding the product or
documentation to help us improve continuously.
Email: support.global@univers.com
64
