# The MIT License (MIT)
# 
# Copyright (c) 2015 Sebastien Maccagnoni-Munch <seb+pyopenevse@maccagnoni.eu>
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
"""Communicate with an OpenEVSE equipment, on the UART port

Initialization
--------------

If you are not sure the protocol is ready to be used by this Python module, you
may execute openevse.init(), which returns True if everything went well, False
otherwise.

For the moment, it only disables the echo ("$SE 0").

Exceptions
----------

If there is a problem communicating with the OpenEVSE (timeout on the serial
port), openevse.EvseTimeout is raised.

If there is another unidentified problem, openevse.EvseError is raised.

If a problem is identified, the corresponding exception is raised."""

import serial

_version = '0.1a2'

_param = {
    'port': '/dev/ttyAMA0',
    'baudrate': 115200,
    'timeout': 8
}

states = {
        0: 'unknown',
        1: 'not connected',
        2: 'connected',
        3: 'charging',
        4: 'vent required',
        5: 'diode check failed',
        6: 'gfci fault',
        7: 'no ground',
        8: 'stuck relay',
        9: 'gfci self-test failure',
        10: 'over temperature',
        254: 'sleeping',
        255: 'disabled'
}

class EvseTimeout(Exception):
    pass
class EvseError(Exception):
    pass
class UnknownColor(EvseError):
    pass
class UnknownStatus(EvseError):
    pass
class UnknownLcdType(EvseError):
    pass
class NoClock(EvseError):
    pass
class UnknownLevel(EvseError):
    pass
class NotCharging(Exception):
    pass

def _base_request(*args):
    command = '$' + ' '.join(args)
    checksum = 0
    for i in bytearray(command):
        checksum ^= i
    checksum = format(checksum, '02X')
    fullrequest = command+'^'+checksum+'\r'
    s = serial.Serial(**_param)
    s.open()
    s.write(fullrequest)
    response = ''
    while True:
        c = s.read()
        if c == '':
            raise EvseTimeout
        response += c
        if c == '\r':
            break
    s.close()
    response = response.split()
    return response[0], response[1:]

def _request_with_st_as_an_answer(*args):
    response, args = _base_request(*args)
    ok = True if response in ('ST', '$ST') else False
    return (ok, args)

def _request(*args):
    response, args = _base_request(*args)
    ok = True if response == '$OK' else False
    return (ok, args)

class Flags:
    """EVSE controller flags

    Specific values:
    * service_level: 1 or 2
    * lcd_type: 'monochrome' or 'rgb'

    True for enabled, False for disabled:
    * auto_service_level
    * diode_check
    * gfi_self_test
    * ground_check
    * stuck_relay_check
    * vent_required
    * auto_start
    * serial_debug

    """
    def __init__(self):
        done, data = _request('GE')
        if done: flags = int(data[1], 16)
        else: raise EvseError
        self.service_level = (flags & 0x0001) + 1
        self.diode_check = not flags & 0x0002
        self.vent_required = not flags & 0x0004
        self.ground_check = not flags & 0x0008
        self.stuck_relay_check = not flags & 0x0010
        self.auto_service_level = not flags & 0x0020
        self.auto_start = not flags & 0x0040
        self.serial_debug = not not flags & 0x0080
        self.lcd_type = 'monochrome' if flags & 0x0100 else 'rgb'
        self.gfi_self_test = not flags & 0x0200

def init(port=None):
    """Initialize the communication

    Arguments:
        * port: name of the port to connect to (default port is /dev/ttyAMA0,
                the serial port on the Raspberry Pi platform
    
    Returns True or False"""
    # TODO Test some API calls and make some functions inactive if the calls
    # are unavailable (no clock, no ammeter, no voltmeter...)
    if port:
        _param['port'] = port
    return echo(False)

def reset():
    """Reset the OpenEVSE
    
    Returns the EVSE state after the reset"""
    done, data = _request_with_st_as_an_answer('FR')
    if done: return states[int(data[0], 16)]
    raise EvseError

_lcd_colors = ['off','red','green','yellow','blue','violet','teal','white']
def lcd_backlight_color(color='off'):
    """Change the LCD backlight color
    
    Allowed colors:
      * off
      * red
      * green
      * yellow
      * blue
      * violet
      * teal
      * white

    Default: off (disable the backlight)"""
    try: colorcode = _lcd_colors.index(color)
    except ValueError: raise UnknownColor
    if _request('FB', str(colorcode))[0]: return True
    raise EvseError

_status_functions = {'disable':'FD', 'enable':'FE', 'sleep':'FS'}
def status(action=None):
    """Change the EVSE status.

    If an action is not specified, the status is requested

    Allowed actions:
      * enable
      * disable
      * sleep

    Default: no action, request the status
    
    Returns the status of the EVSE as a string"""
    if action:
        try: function = _status_functions[action]
        except KeyError: raise UnknownStatus
        done, data = _request(function)
        if done:
            if data: return states[int(data[0], 16)]
        else:
            raise EvseError
    done, data = _request('GS')
    if done: return states[int(data[0])]
    raise EvseError

def display_text(x, y, text):
    """Display a given text on the LCD screen.

    Arguments:
      * x and y: cursor position
      * text: text to display"""
    if _request('FP', str(x), str(y), str(text))[0]: return True
    raise EvseError

_lcd_types=['monochrome', 'rgb']
def lcd_type(lcdtype=None):
    """Change the LCD type

    Allowed types:
        * monochrome
        * rgb
    
    If lcdtype is not specified, the current type is returned
    
    Returns the LCD type ("monochrome" or "rgb")"""
    if lcdtype:
        try: typecode = _lcd_types.index(lcdtype)
        except ValueError: raise UnknownLcdType
        if _request('S0', str(typecode))[0]: return lcdtype
    else:
        return Flags().lcd_type
    raise EvseError

def time(the_datetime=None):
    """Set or get the RTC time
    
    Argument:
        * a datetime object
    
    If the datetime object is not specified, get the current OpenEVSE clock
    
    Returns a datetime object"""
    if the_datetime:
        if _request('S1',the_datetime.strftime('%y'), str(the_datetime.month),
                         str(the_datetime.day), str(the_datetime.hour),
                         str(the_datetime.minute), str(the_datetime.second))[0]:
            return the_datetime
    else:
        done, data = _request('GT')
        if done:
            if data == ['165', '165', '165', '165', '165', '85']:
                raise NoClock
            import datetime
            return datetime.datetime(year=int(data[0])+2000,
                                     month=int(data[1]),
                                     day=int(date[2]),
                                     hour=int(delta[3]),
                                     minute=int(delta[4]),
                                     second=int(delta[5]))
    raise EvseError

def ammeter_calibration(enabled=True):
    """Enable or disable ammeter calibration mode"""
    if _request('S2', str(int(enabled)))[0]: return True
    raise EvseError

def time_limit(limit=None):
    """Get or set the charge time limit, in minutes.
    
    This time is rounded to the nearest quarter hour.

    The maximum value is 3825 minutes.
    
    Returns the limit"""
    if limit is None:
        done, data = _request('G3')
        if done: return int(data[0])*15
    else:
        limit = int(round(limit/15.0))
        if _request('S3', str(limit))[0]: return limit
    raise EvseError

def ammeter_settings(scalefactor=None, offset=None):
    """Set or get the ammeter settings

    If either of the arguments is None, get the values instead of setting them.

    Returns a (scalefactor, offset) tuple"""
    if scalefactor is not None and offset is not None:
        if _request('SA', str(scalefactor), str(offset))[0]:
            return (scalefactor, offset)
    else:
        done, data = _request('GA')
        if done: return (int(data[0]), int(data[1]))
    raise EvseError

def current_capacity(capacity=None):
    """Set or get the current capacity
    
    If capacity is None or 0, get the value
    
    Returns the capacity in amperes"""
    if capacity:
        if _request('SC', str(capacity))[0]: return capacity
    else:
        done, data = _request('GE')
        if done: return int(data[0])
    raise EvseError

def diode_check(enabled=None):
    """
    if enabled == True, enable the diode check
    if enabled == False, disable the diode check
    if enabled is not specified, request the diode check status
    
    Returns the diode check status"""
    if enabled is None:
        return Flags().diode_check
    if _request('SD', str(int(enabled)))[0]: return enabled
    raise EvseError

def echo(enabled=True):
    """Enable or disable echo

    THIS LIBRARY IS NOT MEANT TO BE USED WITH ECHO ENABLED"""
    if _request('SE', str(int(enabled)))[0]: return True
    raise EvseError

def gfi_self_test(enabled=None):
    """
    if enabled == True, enable the GFI self test
    if enabled == False, disable the GFI self test
    if enabled is not specified, request the GFI self test status
    
    Returns the GFI self test status"""
    if enabled is None:
        return Flags().gfi_self_test
    if _request('SF', str(int(enabled)))[0]: return enabled
    raise EvseError

def ground_check(enabled=None):
    """
    if enabled == True, enable the ground check
    if enabled == False, disable the ground check
    if enabled is not specified, request the ground check status
    
    Returns the ground check status"""
    if enabled is None:
        return Flags().ground_check
    if _request('SG', str(int(enabled)))[0]: return enabled
    raise EvseError

def charge_limit(limit=None):
    """Get or set the charge limit (in kWh)
    
    Returns the limit in kWh"""
    if limit is None:
        done, data = _request('GH')
        if done: return int(data[0])
    else:
        if _request('SH', str(int(limit)))[0]: return limit
    raise EvseError

def accumulated_wh(wh=None):
    """Get or set the accumulated Wh

    Returns the accumulated value in Wh"""
    if wh is None:
        done, data = _request('GU')
        if done: return int(data[1])
    else:
        if _request('SK', str(int(wh)))[0]: return wh
    raise EvseError

_service_levels=['A', '1', '2']
def service_level(level=None):
    """Set the service level

    Allowed values:
        * 0: Auto
        * 1: Level 1, 120VAC 16A
        * 2: Level 2, 208-240VAC 80A

    If the level is not specified, the current level is returned
    
    Returns the current service level: 0 for auto, 1 or 2"""
    if level is None:
        flags = Flags()
        if flags.auto_service_level:
            return 0
        return flags.service_level
    else:
        try: levelcode = _service_levels[level]
        except IndexError: raise UnknownLevel
        if _request('SL', levelcode)[0]: return level
    raise EvseError

def voltmeter_settings(scalefactor, offset):
    """Set or get the voltmeter settings

    If either of the arguments is None, get the values instead of setting them.

    Returns a (scalefactor, offset) tuple"""
    if scalefactor is not None and offset is not None:
        if _request('SM', str(scalefactor), str(offset))[0]:
            return (scalefactor, offset)
    else:
        done, data = _request('GM')
        if done: return (int(data[0]), int(data[1]))
    raise EvseError

def stuck_relay_check(enabled=True):
    """
    if enabled == True, enable the stuck relay check
    if enabled == False, disable the stuck relay check
    if enabled is not specified, request the stuck relay check status
    
    Returns the stuck relay check status"""
    if enabled is None:
        return Flags().stuck_relay_check
    if _request('SR', str(int(enabled)))[0]: return enabled
    raise EvseError

def timer(starthour=None, startminute=None, endhour=None, endminute=None):
    """Set or cancel the charge timer
    
    If any of the values is None, the timer is cancelled"""
    if starthour is None or startminute is None or \
       endhour is None or endminute is None:
        done = _request('ST', '0', '0', '0', '0')[0]
    else:
        done = _request('ST', str(starthour), str(startminute),
                              str(endhour), str(endminute))[0]
    if done: return True
    raise EvseError

def vent_required(enabled=None):
    """
    if enabled == True, enable "ventilation required"
    if enabled == False, disable "ventilation required" 
    if enabled is not specified, request the "ventilation required" status
    
    Returns the "ventilation required" status"""
    if enabled is None:
        return Flags().vent_required
    if _request('SV', str(int(enabled)))[0]: return enabled
    raise EvseError

def current_capacity_range():
    """Get the current capacity range, in amperes

    (it depends on the service level)
    
    Returns a tuple of ints:
        (min_capacity, max_capacity)"""
    done, data = _request('GC')
    if done: return (int(data[0]), int(data[1]))
    raise EvseError

def fault_counters():
    """Get the faults counters
    
    Returns a dictionary:
        {
            'GFI self test': X,
            'Ground': Y,
            'Stuck relay': Z
        }
    ... where X, Y and Z are ints"""
    done, data = _request('GF')
    if done:
        return {
            'GFI self test': data[0],
            'Ground': data[1],
            'Stuck relay': data[2]
        }
    raise EvseError

def charging_current_and_voltage():
    """Get the current charging current and voltage

    Returns a dictionary:
        {
            'amps': X,
            'volts': Y
        }
    ... where X and Y are floats"""
    done, data = _request('GG')
    if done:
        milliamps = float(data[0])
        millivolts = float(data[1])
        amps = float(milliamps)/1000 if milliamps > 0 else 0.0
        volts = float(millivolts)/1000 if millivolts > 0 else 0.0
        return {
            'amps': amps,
            'volts': volts
        }
    raise EvseError

def temperature():
    """Get the temperatures in degrees Celcius

    Returns a dictionary:
        {
            'ds3231temp': X,
            'mcp9808temp': Y,
            'tmp007temp': Z
        }
    ... where X, Y and Z are float
    
    If a sensor is not installed, the value is 0.0"""
    done, data = _request('GP')
    if done:
        return {
            'ds3231temp': float(data[0])/10,
            'mcp9808temp': float(data[1])/10,
            'tmp007temp': float(data[2])/10
        }
    raise EvseError

def elapsed():
    """Get the elapsed time and energy used in the current charging session

    time is in seconds
    energy is in Watt-hour

    Returns a dictionary:
        {
            'seconds': X,
            'Wh': Y
    ... where X is an int and Y is a float

    If the charge state is not C (charging), raises NotCharging"""
    done, data1 = _request('GS')
    if done:
        if data1[0] != '3':
            raise NotCharging
        done, data2 = _request('GU')
        if done:
            return {
                'seconds':int(data1[1]),
                'Wh':float(data2[0])/3600
            }
    raise EvseError

def version():
    """Get the firmware and the protocol versions

    Returns a dictionary:
        {
            'firmware': X,
            'protocol': Y
        }
    ... where X and Y are strings"""
    done, data = _request('GV')
    if done:
        return {
            'firmware': data[0],
            'protocol': data[1]
        }
    raise EvseError

# GU this charging session
