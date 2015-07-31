===============
Python-OpenEVSE
===============

This library helps communicating with OpenEVSE boards, using the RAPI protocol.

What is OpenEVSE ?
------------------

EVSE stands for Electrical Vehicle Supply Equipment. An EVSE is a charging
station for electrical vehicles.

OpenEVSE is an Open Hardware EVSE, allowing people to build their own EVSEs.

**OpenEVSE is not a finished product to be used by an end-user**.

What is RAPI ?
--------------

RAPI stands for "Remote API", allowing remote hardware to control the OpenEVSE
board using a serial port, with the FTDI/UART pins on the board.

The default baudrate is 115200, according to OpenEVSE sources (``open_evse.h``).

How to install this library ?
-----------------------------

::

    pip install python-openevse

How to use this library ?
-------------------------

See the inline documentation::

    >>> import openevse
    >>> help(openevse)

License
-------

`MIT <http://opensource.org/licenses/MIT>`_

Copyright (c) 2015 Sébastien Maccagnoni-Munch

In short : do what you want but keep my name in the resulting software.

Please, if you improve it, contribute back. Thanks ! :)

The low-level API
-----------------

Documentation on the RAPI protocol v1.0.3, from ``rapi_proc.h``::

     **** RAPI protocol ****
    
    Fx - function
    Sx - set parameter
    Gx - get parameter
    
    command formats
    1. with XOR checksum (recommended)
    $cc pp pp ...^xk\r
    2. with additive checksum (legacy)
    $cc pp pp ...*ck\r
    3. no checksum (FOR TESTING ONLY! DON'T USE FOR APPS)
    $cc pp pp ...\r
    
    \r = carriage return = 13d = 0x0D
    cc = 2-letter command
    pp = parameters
    xk = 2-hex-digit checksum - 8-bit XOR of all characters before '^'
    ck = 2-hex-digit checksum - 8-bit sum of all characters before '*'
    
    
    response format
    $OK [optional parameters]\r - success
    
    $NK [optional parameters]\r - failure
    
    asynchronous messages
    $ST state\r - EVSE state transition - sent whenever EVSE state changes
     state: EVSE_STATE_xxx
    
    commands
    
    FB color - set LCD backlight color
    colors:
     OFF 0
     RED 1
     YELLOW 3
     GREEN 2
     TEAL 6
     BLUE 4
     VIOLET 5
     WHITE 7 
    
     $FB 7*03 - set backlight to white
    FD - disable EVSE
     $FD*AE
    FE - enable EVSE
     $FE*AF
    FP x y text - print text on lcd display
    FR - reset EVSE
     $FR*BC
    FS - sleep EVSE
     $FS*BD
    
    S0 0|1 - set LCD type
     $S0 0*F7 = monochrome backlight
     $S0 1*F8 = RGB backlight
    S1 yr mo day hr min sec - set clock (RTC) yr=2-digit year
    S2 0|1 - disable/enable ammeter calibration mode - ammeter is read even when not charging
     $S2 0*F9
     $S2 1*FA
    S3 cnt - set charge time limit to cnt*15 minutes (0=disable, max=255)
    SA currentscalefactor currentoffset - set ammeter settings
    SC amps - set current capacity
    SD 0|1 - disable/enable diode check
     $SD 0*0B
     $SD 1*0C
    SE 0|1 - disable/enable command echo
     $SE 0*0C
     $SE 1*0D
     use this for interactive terminal sessions with RAPI.
     RAPI will echo back characters as they are typed, and add a <LF> character
     after its replies
    SF 0|1 - disable/enable GFI self test
     $SF 0*0D
     $SF 1*0E
    SG 0|1 - disable/enable ground check
     $SG 0*0E
     $SG 1*0F
    SH kWh - set cHarge limit to kWh
    SK - set accumulated Wh (v1.0.3+)
     $SK 0*12 - set accumulated Wh to 0
    SL 1|2|A  - set service level L1/L2/Auto
     $SL 1*14
     $SL 2*15
     $SL A*24
    SM voltscalefactor voltoffset - set voltMeter settings
    SR 0|1 - disable/enable stuck relay check
     $SR 0*19
     $SR 1*1A
    SS 0|1 - disable/enable GFI self-test
     $SS 0*1A
     $SS 1*1B
    ST starthr startmin endhr endmin - set timer
     $ST 0 0 0 0*0B - cancel timer
    SV 0|1 - disable/enable vent required
     $SV 0*1D
     $SV 1*1E
    
    G3 - get time limit
     response: OK cnt
     cnt*15 = minutes
            = 0 = no time limit
    GA - get ammeter settings
     response: OK currentscalefactor currentoffset
     $GA*AC
    GC - get current capacity range in amps
     response: OK minamps maxamps
     $GC*AE
    GE - get settings
     response: OK amps(decimal) flags(hex)
     $GE*B0
    GF - get fault counters
     response: OK gfitripcnt nogndtripcnt stuckrelaytripcnt (all values hex)
     $GF*B1
    GG - get charging current and voltage
     response: OK milliamps millivolts
     AMMETER must be defined in order to get amps, otherwise returns 0 amps
     VOLTMETER must be defined in order to get voltage, otherwise returns 0 volts
     $GG*B2
    GH - get cHarge limit
     response: OK kWh
     kWh = 0 = no charge limit
    GM - get voltMeter settings
     response: OK voltcalefactor voltoffset
     $GM^2E
    GP - get temPerature (v1.0.3+)
     $GP*BB
     response: OK ds3231temp mcp9808temp tmp007temp
     ds3231temp - temperature from DS3231 RTC
     mcp9808temp - temperature from MCP9808
     tmp007temp - temperature from TMP007
     all temperatures are in 10th's of a degree Celcius
     if any temperature sensor is not installed, its return value will be 0
    GS - get state
     response: OK state elapsed
     state: EVSE_STATE_xxx
     elapsed: elapsed charge time in seconds (valid only when in state C)
     $GS*BE
    GT - get time (RTC)
     response OK yr mo day hr min sec       yr=2-digit year
     $GT*BF
    GU - get energy usage (v1.0.3+)
     $GU*C0
     response OK Wattseconds Whacc
     Wattseconds - Watt-seconds used this charging session, note you'll divide Wattseconds by 3600 to get Wh
     Whacc - total Wh accumulated over all charging sessions, note you'll divide Wh by 1000 to get kWh
    GV - get version
     response: OK firmware_version protocol_version
     $GV*C1

Relation between low-level API commands and Python-OpenEVSE
-----------------------------------------------------------

* FB: ``lcd_backlight_color``
* FD: ``status``
* FE: ``status``
* FP: ``display_text``
* FR: ``reset``
* FS: ``status``
* S0: ``lcd_type``
* S1: ``time``
* S2: ``ammeter_calibration``
* S3: ``time_limit``
* SA: ``ammeter_settings``
* SC: ``current_capacity``
* SD: ``diode_check``
* SE: ``echo``
* SF: ``gfi_self_test``
* SG: ``ground_check``
* SH: ``charge_limit``
* SK: ``accumulated_wh``
* SL: ``service_level``
* SM: ``voltmeter_settings``
* SR: ``stuck_relay_check``
* SS: ``gfi_self_test`` (it is the same as SF)
* ST: ``timer``
* SV: ``vent_required``
* G3: ``time_limit``
* GA: ``ammeter_settings``
* GC: ``current_capacity_range``
* GE: ``current_capacity`` (1st field), see Flags class (2nd field)
* GF: ``fault_counters``
* GG: ``charging_current_and_voltage``
* GH: ``charge_limit``
* GM: ``voltmeter_settings``
* GP: ``temperature``
* GS: ``status``, ``elapsed``
* GT: ``time``
* GU: ``accumulated_wh``, ``elapsed``
* GV: ``version``
 

Some links to OpenEVSE
----------------------

* `OpenEVSE project <https://code.google.com/p/open-evse/>`_
* `Firmware source code <https://github.com/lincomatic/open_evse>`_
* `OpenEVSE store <http://store.openevse.com/>`_
