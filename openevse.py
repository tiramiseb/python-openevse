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

Please note OpenEVSE object initialization disables the echo ("$SE 0").
"""

import datetime
import serial
import time

_version = '0.2+dev'

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
_lcd_colors = ['off','red','green','yellow','blue','violet','teal','white']
_status_functions = {'disable':'FD', 'enable':'FE', 'sleep':'FS'}
_lcd_types=['monochrome', 'rgb']
_service_levels=['A', '1', '2']

STANDARD_SERIAL_TIMEOUT = 0.5
RESET_SERIAL_TIMEOUT = 10
STATUS_SERIAL_TIMEOUT = 0

CORRECT_RESPONSE_PREFIXES = ('$OK', '$NK')

class EvseError(Exception):
    pass
class EvseTimeoutError(EvseError):
    pass
class NoClock(EvseError):
    pass
class NotCharging(Exception):
    pass

class OpenEVSE:
    """A connection to an OpenEVSE equipment through its RAPI serial protocol."""

    def __init__(self, port='/dev/ttyAMA0', baudrate=115200,
                 status_callback=None):
        """Initialize the OpenEVSE
        status_callback: a function to call if a "status change" line ($ST xx)
                         is received
        """
        self.new_status = None
        self.callback = status_callback
        self.s = serial.Serial(port=port, baudrate=baudrate,
                                timeout=STANDARD_SERIAL_TIMEOUT)
        # The first call may be wrong because other characters may have been
        # written on the serial port before initializing this class
        # That's why there is this "try" and this second "echo"
        try: self.echo(False)
        except EvseError:
            self.echo(False)

    def __del__(self):
        self.s.close()

    def _read_line(self):
        """Read a line from the serial port.
        
        Reimplementation was needed beause readline inherited from _IOBase does
        not allow \\r as an EOL character.
        """
        line = ''
        while True:
            c = self.s.read()
            if c == '':
                raise EvseTimeoutError
            line += c
            if c == '\r':
                break
        return line

    def _get_response(self):
        """Get the response of a command."""
        response = self._read_line()
        if response[:3] in CORRECT_RESPONSE_PREFIXES:
            response = response.split()
            return (response[0] == '$OK', response[1:])
        else:
            if response[:3] == '$ST':
                new_status = states[int(response.split()[1], 16)]
                if self.callback:
                    self.callback(new_status)
                self.new_status = new_status
            return self._get_response()

    def _silent_request(self, *args):
        """Send a request, do not read its response"""
        command = '$' + ' '.join(args)
        checksum = 0
        for i in bytearray(command):
            checksum ^= i
        checksum = format(checksum, '02X')
        request = command+'^'+checksum+'\r'
        self.s.write(request)
    
    def _request(self, *args):
        """Send a requests, wait for its response"""
        self._silent_request(*args)
        return self._get_response()


    def _flags(self):
        """Get EVSE controller flags

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
        done, data = self._request('GE')
        if done: flags = int(data[1], 16)
        else: raise EvseError
        return {
            'service_level': (flags & 0x0001) + 1,
            'diode_check': not flags & 0x0002,
            'vent_required': not flags & 0x0004,
            'ground_check': not flags & 0x0008,
            'stuck_relay_check': not flags & 0x0010,
            'auto_service_level': not flags & 0x0020,
            'auto_start': not flags & 0x0040,
            'serial_debug': not not flags & 0x0080,
            'lcd_type': 'monochrome' if flags & 0x0100 else 'rgb',
            'gfi_self_test': not flags & 0x0200
        }

    def get_status_change(self):
        """Get the new status if the status has changed
        
        If the status has not changed since the last test, None is returned.

        If the status has changed, the new status is returned as a string

        If the status has changed and status_callback has been defined,
        status_callback is called before returning the value."""
        self.s.timeout = STATUS_SERIAL_TIMEOUT
        try:
            # Wait to have read all status changes, only return the last one
            while True:
                self._get_response()
        except EvseTimeoutError:
            pass
        self.s.timeout = STANDARD_SERIAL_TIMEOUT
        # In fact, the callback is called by get_response...
        # Here we only deal with the value of self.new_status
        if not self.callback and self.new_status:
            status = self.new_status
            self.new_status = None
        else:
            status = None
        return status

    def reset(self):
        """Reset the OpenEVSE
        
        Returns the EVSE state after the reset
        
        Raises EvseTimeoutError if the OpenEVSE did not reboot within 10 seconds
        """
        self._silent_request('FR')
        # Give the OpenEVSE at most RESET_SERIAL_TIMEOUT seconds to reboot
        self.s.timeout = RESET_SERIAL_TIMEOUT
        # Read the next received line, which should start with "ST"
        line = self._read_line()
        self.s.timeout = STANDARD_SERIAL_TIMEOUT
        if line[:2] == 'ST':
            new_status = states[int(line.split()[1], 16)]
            if self.callback:
                self.callback(new_status)
            self.new_status = new_status
            time.sleep(1) # Let the OpenEVSE finish its boot sequence
                          # after the "ST" line is received
            return self.status()
        else:
            raise EvseError

    def lcd_backlight_color(self, color='off'):
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

        Default: off (disable the backlight)
        """
        colorcode = _lcd_colors.index(color)
        if self._request('FB', str(colorcode))[0]: return True
        raise EvseError

    def status(self, action=None):
        """Change the EVSE status.

        If an action is not specified, the status is requested

        Allowed actions:
          * enable
          * disable
          * sleep

        Default: no action, request the status
        
        Returns the status of the EVSE as a string
        """
        if action:
            function = _status_functions[action]
            done, data = self._request(function)
            if done:
                if data: return states[int(data[0], 16)]
            else:
                raise EvseError
        done, data = self._request('GS')
        if done: return states[int(data[0])]
        raise EvseError

    def display_text(self, x, y, text):
        """Display a given text on the LCD screen.

        Arguments:
          * x and y: cursor position
          * text: text to display
          """
        if self._request('FP', str(x), str(y), str(text))[0]: return True
        raise EvseError

    def lcd_type(self, lcdtype=None):
        """Change the LCD type

        Allowed types:
            * monochrome
            * rgb
        
        If lcdtype is not specified, the current type is returned
        
        Returns the LCD type ("monochrome" or "rgb")
        """
        if lcdtype:
            typecode = _lcd_types.index(lcdtype)
            if self._request('S0', str(typecode))[0]: return lcdtype
        else:
            return self._flags()['lcd_type']
        raise EvseError

    def time(self, the_datetime=None):
        """Set or get the RTC time
        
        Argument:
            * a datetime object
        
        If the datetime object is not specified, get the current OpenEVSE clock
        
        Returns a datetime object
        """
        if the_datetime:
            if self._request('S1',the_datetime.strftime('%y'), str(the_datetime.month),
                             str(the_datetime.day), str(the_datetime.hour),
                             str(the_datetime.minute), str(the_datetime.second))[0]:
                return the_datetime
        else:
            done, data = self._request('GT')
            if done:
                if data == ['165', '165', '165', '165', '165', '85']:
                    raise NoClock
                return datetime.datetime(year=int(data[0])+2000,
                                         month=int(data[1]),
                                         day=int(date[2]),
                                         hour=int(delta[3]),
                                         minute=int(delta[4]),
                                         second=int(delta[5]))
        raise EvseError

    def ammeter_calibration(self, enabled=True):
        """Enable or disable ammeter calibration mode"""
        if self._request('S2', str(int(enabled)))[0]: return True
        raise EvseError

    def time_limit(self, limit=None):
        """Get or set the charge time limit, in minutes.
        
        This time is rounded to the nearest quarter hour.

        The maximum value is 3825 minutes.
        
        Returns the limit
        """
        if limit is None:
            done, data = self._request('G3')
            if done: return int(data[0])*15
        else:
            limit = int(round(limit/15.0))
            if self._request('S3', str(limit))[0]: return limit
        raise EvseError

    def ammeter_settings(self, scalefactor=None, offset=None):
        """Set or get the ammeter settings

        If either of the arguments is None, get the values instead of setting them.

        Returns a (scalefactor, offset) tuple
        """
        if scalefactor is not None and offset is not None:
            if self._request('SA', str(scalefactor), str(offset))[0]:
                return (scalefactor, offset)
        else:
            done, data = self._request('GA')
            if done: return (int(data[0]), int(data[1]))
        raise EvseError

    def current_capacity(self, capacity=None):
        """Set or get the current capacity
        
        If capacity is None or 0, get the value
        
        Returns the capacity in amperes
        """
        if capacity:
            if self._request('SC', str(capacity))[0]: return capacity
        else:
            done, data = self._request('GE')
            if done: return int(data[0])
        raise EvseError

    def diode_check(self, enabled=None):
        """
        if enabled == True, enable the diode check
        if enabled == False, disable the diode check
        if enabled is not specified, request the diode check status
        
        Returns the diode check status
        """
        if enabled is None:
            return self._flags()['diode_check']
        if self._request('SD', str(int(enabled)))[0]: return enabled
        raise EvseError

    def echo(self, enabled=True):
        """Enable or disable echo

        THIS LIBRARY IS NOT MEANT TO BE USED WITH ECHO ENABLED
        """
        if self._request('SE', str(int(enabled)))[0]: return True
        raise EvseError

    def gfi_self_test(self, enabled=None):
        """
        if enabled == True, enable the GFI self test
        if enabled == False, disable the GFI self test
        if enabled is not specified, request the GFI self test status
        
        Returns the GFI self test status
        """
        if enabled is None:
            return self._flags()['gfi_self_test']
        if self._request('SF', str(int(enabled)))[0]: return enabled
        raise EvseError

    def ground_check(self, enabled=None):
        """
        if enabled == True, enable the ground check
        if enabled == False, disable the ground check
        if enabled is not specified, request the ground check status
        
        Returns the ground check status
        """
        if enabled is None:
            return self._flags()['ground_check']
        if self._request('SG', str(int(enabled)))[0]: return enabled
        raise EvseError

    def charge_limit(self, limit=None):
        """Get or set the charge limit (in kWh)
        
        Returns the limit in kWh
        """
        if limit is None:
            done, data = self._request('GH')
            if done: return int(data[0])
        else:
            if self._request('SH', str(int(limit)))[0]: return limit
        raise EvseError

    def accumulated_wh(self, wh=None):
        """Get or set the accumulated Wh

        Returns the accumulated value in Wh
        """
        if wh is None:
            done, data = self._request('GU')
            if done: return int(data[1])
        else:
            if self._request('SK', str(int(wh)))[0]: return wh
        raise EvseError

    def service_level(self, level=None):
        """Set the service level

        Allowed values:
            * 0: Auto
            * 1: Level 1, 120VAC 16A
            * 2: Level 2, 208-240VAC 80A

        If the level is not specified, the current level is returned
        
        Returns the current service level: 0 for auto, 1 or 2
        """
        if level is None:
            flags = self._flags()
            if flags.auto_service_level:
                return 0
            return flags.service_level
        else:
            levelcode = _service_levels[level]
            if self._request('SL', levelcode)[0]: return level
        raise EvseError

    def voltmeter_settings(self, scalefactor, offset):
        """Set or get the voltmeter settings

        If either of the arguments is None, get the values instead of setting them.

        Returns a (scalefactor, offset) tuple
        """
        if scalefactor is not None and offset is not None:
            if self._request('SM', str(scalefactor), str(offset))[0]:
                return (scalefactor, offset)
        else:
            done, data = self._request('GM')
            if done: return (int(data[0]), int(data[1]))
        raise EvseError

    def stuck_relay_check(self, enabled=True):
        """
        if enabled == True, enable the stuck relay check
        if enabled == False, disable the stuck relay check
        if enabled is not specified, request the stuck relay check status
        
        Returns the stuck relay check status
        """
        if enabled is None:
            return self._flags()['stuck_relay_check']
        if self._request('SR', str(int(enabled)))[0]: return enabled
        raise EvseError

    def timer(self, starthour=None, startminute=None, endhour=None, endminute=None):
        """Set or cancel the charge timer
        
        If any of the values is None, the timer is cancelled
        """
        if starthour is None or startminute is None or \
           endhour is None or endminute is None:
            done = self._request('ST', '0', '0', '0', '0')[0]
        else:
            done = self._request('ST', str(starthour), str(startminute),
                                  str(endhour), str(endminute))[0]
        if done: return True
        raise EvseError

    def vent_required(self, enabled=None):
        """
        if enabled == True, enable "ventilation required"
        if enabled == False, disable "ventilation required" 
        if enabled is not specified, request the "ventilation required" status
        
        Returns the "ventilation required" status
        """
        if enabled is None:
            return self._flags()['vent_required']
        if self._request('SV', str(int(enabled)))[0]: return enabled
        raise EvseError

    def current_capacity_range(self):
        """Get the current capacity range, in amperes

        (it depends on the service level)
        
        Returns a tuple of ints:
            (min_capacity, max_capacity)
        """
        done, data = self._request('GC')
        if done: return (int(data[0]), int(data[1]))
        raise EvseError

    def fault_counters(self):
        """Get the faults counters
        
        Returns a dictionary:
            {
                'GFI self test': X,
                'Ground': Y,
                'Stuck relay': Z
            }
        ... where X, Y and Z are ints
        """
        done, data = self._request('GF')
        if done:
            return {
                'GFI self test': int(data[0], 16),
                'Ground': int(data[1], 16),
                'Stuck relay': int(data[2], 16)
            }
        raise EvseError

    def charging_current_and_voltage(self):
        """Get the current charging current and voltage

        Returns a dictionary:
            {
                'amps': X,
                'volts': Y
            }
        ... where X and Y are floats
        """
        done, data = self._request('GG')
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

    def temperature(self):
        """Get the temperatures in degrees Celcius

        Returns a dictionary:
            {
                'ds3231temp': X,
                'mcp9808temp': Y,
                'tmp007temp': Z
            }
        ... where X, Y and Z are float
        
        If a sensor is not installed, the value is 0.0
        """
        done, data = self._request('GP')
        if done:
            return {
                'ds3231temp': float(data[0])/10,
                'mcp9808temp': float(data[1])/10,
                'tmp007temp': float(data[2])/10
            }
        raise EvseError

    def elapsed(self):
        """Get the elapsed time and energy used in the current charging session

        time is in seconds
        energy is in Watt-hour

        Returns a dictionary:
            {
                'seconds': X,
                'Wh': Y
        ... where X is an int and Y is a float

        If the charge state is not C (charging), raises NotCharging
        """
        done, data1 = self._request('GS')
        if done:
            if data1[0] != '3':
                raise NotCharging
            done, data2 = self._request('GU')
            if done:
                return {
                    'seconds':int(data1[1]),
                    'Wh':float(data2[0])/3600
                }
        raise EvseError

    def version(self):
        """Get the firmware and the protocol versions

        Returns a dictionary:
            {
                'firmware': X,
                'protocol': Y
            }
        ... where X and Y are strings
        """
        done, data = self._request('GV')
        if done:
            return {
                'firmware': data[0],
                'protocol': data[1]
            }
        raise EvseError
