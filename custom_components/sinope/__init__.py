import os
import logging
import requests
import json
import struct
import binascii
import socket
import sys
import pytz
import time
from astral.sun import sun
from astral import LocationInfo
from . import crc8
from datetime import datetime, timedelta
from random import randint
import voluptuous as vol

from homeassistant.helpers import (
    config_validation as cv,
    discovery,
    entity_platform,
    service,
)

from homeassistant.const import (
    CONF_API_KEY,
    CONF_ID,
    CONF_SCAN_INTERVAL,
    CONF_TIME_ZONE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)

from homeassistant.util import Throttle
from .const import (
    DOMAIN,
    CONF_API_KEY_2,
    CONF_ID_2,
    CONF_SERVER,
    CONF_SERVER_2,
    CONF_MY_CITY,
)

#REQUIREMENTS = ['PY_Sinope==0.1.7']
REQUIREMENTS = ['crc8==0.2.1']
VERSION = '1.7.3'

DATA_DOMAIN = 'data_' + DOMAIN

_LOGGER = logging.getLogger(__name__)

#default values
SCAN_INTERVAL = timedelta(seconds=180)
MY_CITY = 'Montreal'
MY_TZ = 'America/Toronto'

REQUESTS_TIMEOUT = 30

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_ID): cv.string,
        vol.Required(CONF_SERVER): cv.string,
        vol.Optional(CONF_API_KEY_2): cv.string,
        vol.Optional(CONF_ID_2): cv.string,
        vol.Optional(CONF_SERVER_2): cv.string,
        vol.Optional(CONF_MY_CITY, default=MY_CITY): cv.string,
        vol.Optional(CONF_TIME_ZONE, default=MY_TZ): cv.time_zone,
        vol.Optional(CONF_SCAN_INTERVAL, default=SCAN_INTERVAL):
            cv.time_period
    })
}, extra=vol.ALLOW_EXTRA)

def setup(hass, hass_config) -> bool:
    """Setup sinope."""
    data = SinopeData(hass_config[DOMAIN])
    hass.data[DATA_DOMAIN] = data

    global CONFDIR
    CONFDIR = "/config/.storage/"
 
    _LOGGER.debug("Setting config location to: %s", CONFDIR)

    global SCAN_INTERVAL
    SCAN_INTERVAL = hass_config[DOMAIN].get(CONF_SCAN_INTERVAL)
    _LOGGER.debug("Setting scan interval to: %s", SCAN_INTERVAL)
    
    _LOGGER.debug("Setting time zone as: %s", hass_config[DOMAIN].get(CONF_TIME_ZONE))

    if len(hass_config[DOMAIN].get(CONF_ID)) != 16:
        _LOGGER.debug("Error in configuration parameters for id, the lenght is incorrect.")
    if len(hass_config[DOMAIN].get(CONF_API_KEY)) != 16:
        _LOGGER.debug("Error in configuration parameters for api_key, the lenght is incorrect.")
    if hass_config[DOMAIN].get(CONF_ID_2) is not None:
        if len(hass_config[DOMAIN].get(CONF_ID_2)) != 16:
            _LOGGER.debug("Error in configuration parameters for api_key2, the lenght is incorrect.")
        if len(hass_config[DOMAIN].get(CONF_ID_2)) != 16:
            _LOGGER.debug("Error in configuration parameters for id2, the lenght is incorrect.")

    discovery.load_platform(hass, 'climate', DOMAIN, {}, hass_config)
    discovery.load_platform(hass, 'light', DOMAIN, {}, hass_config)
    discovery.load_platform(hass, 'switch', DOMAIN, {}, hass_config)

    return True

class SinopeData:
    """Get the latest data and update the states."""

    def __init__(self, config):
        """Init the sinope data object."""
        api_key = config.get(CONF_API_KEY)
        api_id = config.get(CONF_ID)
        server = config.get(CONF_SERVER)
        api_key_2 = config.get(CONF_API_KEY_2)
        api_id_2 = config.get(CONF_ID_2)
        server_2 = config.get(CONF_SERVER_2)
        my_city = config.get(CONF_MY_CITY)
        tz = config.get(CONF_TIME_ZONE)
        self.sinope_client = SinopeClient(api_key, api_id, server, my_city, tz, api_key_2, api_id_2, server_2)

# According to HA:
# https://developers.home-assistant.io/docs/en/creating_component_code_review.html
# "All API specific code has to be part of a third party library hosted on PyPi.
# Home Assistant should only interact with objects and not make direct calls to the API."
# So all code below this line should eventually be integrated in a PyPi project.

class PySinopeError(Exception):
    pass

#import PY_Sinope

PORT = 4550

all_unit = "FFFFFFFF"
#sequential number to identify the current request. Could be any unique number that is different at each request
# could we use timestamp value ?
seq_num = 12345678 
seq = 0

# command type
data_read_command = "4002"
data_report_command = "4202"
data_write_command = "4402"

#thermostat data read
data_heat_level = "20020000" #0 to 100%
data_mode = "11020000" # off, manual, auto, bypass, away...
data_temperature = "03020000" #room temperature
data_setpoint = "08020000" #thermostat set point
data_away = "00070000"  #set device mode to away, 0=home, 2=away

#thermostat info read
data_display_format = "00090000" # 0 = celcius, 1 = fahrenheit
data_time_format = "01090000" # 0 = 24h, 1 = 12h
data_load = "000D0000" # 0-65519 watt, 1=1 watt, (2 bytes)
data_display2 = "30090000" # 0 = default setpoint, 1 = outdoor temp.
data_min_temp = "0A020000" # Minimum room setpoint, 5-30oC (2 bytes)
data_max_temp = "0B020000" # Maximum room setpoint, 5-30oC (2 bytes)
data_away_temp = "0C020000" # away room setpoint, 5-30oC (2 bytes)

# thermostat data report
data_outdoor_temperature = "04020000" #to show on thermostat, must be sent at least every hour
data_time = "00060000" #must be sent at least once a day or before write request for auto mode
data_date = "01060000"
data_sunrise = "20060000" #must be sent onece a day
data_sunset = "21060000" #must be sent onece a day

# thermostat data write
data_early_start = "60080000"  #0=disabled, 1=enabled
data_backlight = "0B090000" # variable  = intensity adjustable for thermostats
# values, 0 = always on, 1 = variable idle/on in use, 2 = off idle/variabe in use, 3 = always variable
data_backlight_idle = "09090000" # intensity when idle, 0 == off to 100 = always on

# light and dimmer
data_light_intensity = "00100000"  # 0 to 100, off to on, 101 = last level
data_light_mode = "09100000"  # 1=manual, 2=auto, 3=random or away, 130= bypass auto
data_light_event_timer = "000F0000"   # time in minutes the light event timer will stay on 0=off, 1--255 = on
data_light_event = "010F0000"  #0= no event sent, 1=timer active, 2= event sent for turn_on or turn_off
data_light_indicator_on = "10098001" # when light is on, 4 bytes: 0=intensity, 1=color red 0-255, 2=green 0-255, 3=blue 0-255
data_light_indicator_off = "10098000" # when light is off, 4 bytes: 0=intensity, 1=color red 0-255, 2=green 0-255, 3=blue 0-255

# Power control
data_power_intensity = "00100000"  # 0 to 100, off to on
data_power_mode = "09100000"  # 1=manual, 2=auto, 3=random or away, 130= bypass auto
data_power_connected = "000D0000" # actual load connected to the device
data_power_load = "020D0000" # load used by the device
data_power_event = "010F0000"  #0= no event sent, 1=timer active, 2= event sent for turn_on or turn_off
data_power_event_timer = "000F0000" # time in minutes the power event timer will stay on 0=off, 1--255 = on

# general
data_lock = "02090000" # 0 = unlock, 1 = lock, for keyboard device

def invert(id):
    """The Api_ID must be sent in reversed order"""
    k1 = id[14:16]
    k2 = id[12:14]
    k3 = id[10:12]
    k4 = id[8:10]
    k5 = id[6:8]
    k6 = id[4:6]
    k7 = id[2:4]
    k8 = id[0:2]
    return k1+k2+k3+k4+k5+k6+k7+k8

def crc_count(bufer):
    hash = crc8.crc8()
    hash.update(bufer)
    return hash.hexdigest()

def crc_check(bufer):
    hash = crc8.crc8()
    hash.update(bufer)
    if(hash.hexdigest() == "00"):
        return "00"
    return None

def get_dst(zone): # daylight saving time is on or not
    timezone = pytz.timezone(zone)
    localtime = datetime.now().astimezone(tz=timezone)
    if localtime.dst():
        return 128
    return 0

def set_date(zone):
    timezone = pytz.timezone(zone)
    now = datetime.now().astimezone(tz=timezone)
    day = int(now.strftime("%w"))-1
    if day == -1:
        day = 6
    w = bytearray(struct.pack('<i', day)[:1]).hex() #day of week, 0=monday converted to bytes
    d = bytearray(struct.pack('<i', int(now.strftime("%d")))[:1]).hex() #day of month converted to bytes
    m = bytearray(struct.pack('<i', int(now.strftime("%m")))[:1]).hex() #month converted to bytes
    y = bytearray(struct.pack('<i', int(now.strftime("%y")))[:1]).hex() #year converted to bytes
    date = '04'+w+d+m+y #xxwwddmmyy,  xx = length of data date = 04
    return date

def set_time(zone):
    timezone = pytz.timezone(zone)
    now = datetime.now().astimezone(tz=timezone)
    s = bytearray(struct.pack('<i', int(now.strftime("%S")))[:1]).hex() #second converted to bytes
    m = bytearray(struct.pack('<i', int(now.strftime("%M")))[:1]).hex() #minutes converted to bytes
    h = bytearray(struct.pack('<i', int(now.strftime("%H"))+get_dst(zone))[:1]).hex() #hours converted to bytes
    time = '03'+s+m+h #xxssmmhh  24hr, 16:09:00 pm, xx = length of data time = 03
    return time

def set_sun_time(city, zone, period): # period = sunrise or sunset
    cit = LocationInfo()
    cit.name = city
    cit.timezone = zone
    s = sun(cit.observer, date=datetime.now(), tzinfo=pytz.timezone(zone))
    if period == "sunrise":
        now = s['sunrise']
    else:
        now = s['sunset']
    s = bytearray(struct.pack('<i', int(now.strftime("%S")))[:1]).hex() #second converted to bytes
    m = bytearray(struct.pack('<i', int(now.strftime("%M")))[:1]).hex() #minutes converted to bytes
    h = bytearray(struct.pack('<i', int(now.strftime("%H"))+get_dst(zone))[:1]).hex() #hours converted to bytes
    time = '03'+s+m+h #xxssmmhh  24hr, 16:09:00 pm, xx = length of data time = 03
    return time

def get_heat_level(data):
    sequence = data[12:20]
    deviceID = data[26:34]
    status = data[20:22]
    if status != "0a":
        _LOGGER.warning("Status code for device %s: (wrong answer ? %s), data:(%s)", deviceID, status, data)
        return None # device didn't answer, wrong device
    else:
        tc2 = data[46:48]
        return int(float.fromhex(tc2))

def set_temperature(temp_celcius):
    temp = int(temp_celcius*100)
    return "02"+bytearray(struct.pack('<i', temp)[:2]).hex()

def get_temperature(data):
    sequence = data[12:20]
    deviceID = data[26:34]
    status = data[20:22]
    if status != "0a":
        _LOGGER.warning("Status code: %s (device didn't answer, wrong device %s), Data:(%s)", status, deviceID, data)
        return None # device didn't answer, wrong device
    else:
        tc2 = data[46:48]
        tc4 = data[48:50]
        latemp = tc4+tc2
        if latemp == "7ffc" or latemp == "7ffa":
            _LOGGER.warning("Error code: %s (None or invalid value for %s), Data:(%s)", latemp, deviceID, data)
            return 0
        elif latemp == "7ff8" or latemp == "7fff":
            _LOGGER.warning("Error code: %s (Temperature higher than maximum range for %s)", latemp, deviceID)
            return 0
        elif latemp == "7ff9" or latemp == "8000" or latemp == "8001":
            _LOGGER.warning("Error code: %s (Temperature lower than minimum range for %s)", latemp, deviceID)
            return 0
        elif latemp == "7ff6" or latemp == "7ff7" or latemp == "7ffd" or latemp == "7ffe":
            _LOGGER.warning("Error code: %s (Defective device temperature sensor for %s), Data:(%s)", latemp, deviceID, data)
            return 0
        elif latemp == "7ffb":
            _LOGGER.warning("Error code: %s (Overload for %s)", latemp, deviceID)
            return 0
        elif latemp == "7ff5":
            _LOGGER.warning("Error code: %s (Internal error for %s), Data:(%s)", latemp, deviceID, data)
            return 0
        else:
            return round(float.fromhex(latemp)*0.01, 2)

def to_celcius(temp,unit): #unit = K for kelvin, C for celcius, F for farenheight
    if unit == "C":
        return round((temp-32)*0.5555, 2)
    else:
        return round((temp-273.15),2)

def from_celcius(temp):
    return round((temp+1.8)+32, 2)

def set_away(away): #0=home,2=away
    return "01"+bytearray(struct.pack('<i', away)[:1]).hex()

def get_away(data):
    sequence = data[12:20]
    deviceID = data[26:34]
    status = data[20:22]
    if status != "0a":
        _LOGGER.warning("Status code: %s (device didn't answer, wrong device %s) Data:(%s)", status, deviceID, data)
        return None # device didn't answer, wrong device
    else:
        tc2 = data[46:48]
        return int(float.fromhex(tc2))

def put_mode(mode): #0=off,1=freeze protect,2=manual,3=auto,5=away
    return "01"+bytearray(struct.pack('<i', mode)[:1]).hex()

def get_mode(data):
    sequence = data[12:20]
    deviceID = data[26:34]
    status = data[20:22]
    if status != "0a":
        _LOGGER.debug("Status code: %s (Wrong answer for: %s) Data:(%s)", status, deviceID, data)
        return None # device didn't answer, wrong device
    else:
        tc2 = data[46:48]
        return int(float.fromhex(tc2))

def set_intensity(num):
    return "01"+bytearray(struct.pack('<i', num)[:1]).hex()

def get_intensity(data):
    if data is not None:
        sequence = data[12:20]
        deviceID = data[26:34]
        status = data[20:22]
        if status != "0a":
            _LOGGER.debug("Status code: %s (Wrong answer for: %s) Data:(%s)", status, deviceID, data)
            return None # device didn't answer, wrong answer
        else:
            tc2 = data[46:48]
            return int(float.fromhex(tc2))
    else:
        _LOGGER.debug("No intensity received.")

def get_data_push(data): #will be used to send data pushed by GT125 when light is turned on or off directly to HA device
    deviceID = data[26:34]
    status = data[20:22]
    tc2 = data[46:48]
#    return int(float.fromhex(tc2))
    return None

def set_led_color(intensity, red, green, blue): #intensity (0-100), red, green. blue = RGB color (0-255)
    return "04"+bytearray(struct.pack('<i', intensity)[:1]).hex()+bytearray(struct.pack('<i', red)[:1]).hex()+bytearray(struct.pack('<i', green)[:1]).hex()+bytearray(struct.pack('<i', blue)[:1]).hex()

def set_lock(lock):
    return "01"+bytearray(struct.pack('<i', lock)[:1]).hex()

def get_lock(data):
    sequence = data[12:20]
    deviceID = data[26:34]
    status = data[20:22]
    if status != "0a":
        _LOGGER.debug("Status code: %s (Wrong answer for: %s) Data:(%s)", status, deviceID, data)
        return None # device didn't answer, wrong device
    else:
        tc2 = data[46:48]
        return int(float.fromhex(tc2))

def set_light_state(state): # 0,1,2,3
    return "01"+bytearray(struct.pack('<i', state)[:1]).hex()

def set_light_idle(level): # 0 to 100
    return "01"+bytearray(struct.pack('<i', level)[:1]).hex()

def set_indicator(level,red,green,blue): #use for led indicator when on or off
    b0 = bytearray(struct.pack('<i', level)[:1]).hex()
    b1 = bytearray(struct.pack('<i', red)[:1]).hex()
    b2 = bytearray(struct.pack('<i', green)[:1]).hex()
    b3 = bytearray(struct.pack('<i', blue)[:1]).hex()
    return b0+b1+b2+b3

def get_led(state,data):
    sequence = data[12:20]
    deviceID = data[26:34]
    status = data[20:22]
    if status != "0a":
        _LOGGER.debug("Status code: %s (Wrong answer for: %s) Data:(%s)", status, deviceID, data)
        my_led = {}
        if state == 1:
            my_led['intensity_on'] = 0
            my_led['red_on'] = 0
            my_led['green_on'] = 0
            my_led['blue_on'] = 0
        else:
            my_led['intensity_off'] = 0
            my_led['red_off'] = 0
            my_led['green_off'] = 0
            my_led['blue_off'] = 0
        return my_led
    else:
        tc0 = data[46:48]
        tc1 = data[48:50]
        tc2 = data[50:52]
        tc3 = data[52:54]
        my_led = {}
        if state == 1:
            my_led['intensity_on'] = str(int(float.fromhex(tc0)))
            my_led['red_on'] = str(int(float.fromhex(tc1)))
            my_led['green_on'] = str(int(float.fromhex(tc2)))
            my_led['blue_on'] = str(int(float.fromhex(tc3)))
        else:
            my_led['intensity_off'] = str(int(float.fromhex(tc0)))
            my_led['red_off'] = str(int(float.fromhex(tc1)))
            my_led['green_off'] = str(int(float.fromhex(tc2)))
            my_led['blue_off'] = str(int(float.fromhex(tc3)))
        return  my_led

def get_power_load(data): # get power in watt use by the device
    sequence = data[12:20]
    deviceID = data[26:34]
    status = data[20:22]
    if status != "0a":
        _LOGGER.debug("Status code: %s (Wrong answer ? %s) %s", status, deviceID, data)
        return None # device didn't answer, wrong device
    else:
        tc2 = data[46:48]
        tc4 = data[48:50]
        lepower = tc4+tc2
        return int(float.fromhex(lepower))

def set_light_event_on(num): #102 = light, 112 = dimmer
    b0 = "10"
    b1 = "00000000"
    b3 = "000000000000000000"
    if num == 102:
        b2 = "020200" #event on for light
    else:
        b2 = "020202" # event on for dimmer
    return b0+b1+b2+b3

def set_light_event_timer_on(num): #102 = light, 112 = dimmer
    b0 = "10"
    b1 = "00000000"
    b3 = "000000000000000000"
    if num == 102:
        b2 = "010100" #event on = timer start
    else:
        b2 = "010101" # event off = timer start (dimmer)
    return b0+b1+b2+b3

def set_light_event_off(num): #102 = light, 112 = dimmer
    b0 = "10"
    b1 = "00000000"
    b3 = "000000000000000000"
    if num == 102:
        b2 = "010100" #all event = off except timer subscription (default)
    else:
        b2 = "000001" # dimmer
    return b0+b1+b2+b3

def get_light_event_state(data): #received event from devices, 00100000
    sequence = data[12:20]
    deviceID = data[26:34]
    tc2 = data[54:60]
    return tc2 #int(float.fromhex(tc2))

def set_switch_event_on():
    b0 = "10"
    b1 = "0202"
    b2 = "0000000000000000000000000000"
    return b0+b1+b2

def set_switch_event_timer_on():
    b0 = "10"
    b1 = "0101"
    b2 = "0000000000000000000000000000"
    return b0+b1+b2

def set_switch_event_off():
    b0 = "10"
    b1 = "0000"
    b2 = "0000000000000000000000000000"
    return b0+b1+b2

def get_switch_event_state(data): #received event from devices,
    sequence = data[12:20]
    deviceID = data[26:34]
    tc2 = data[46:50]
    return  tc2 #int(float.fromhex(tc2))

def set_event_timer_length(num): # 0=desabled, 1 to 255 lenght on
    return "01"+bytearray(struct.pack('<i', num)[:1]).hex()

def get_event_timer_length(data): # 0=desabled, 1 to 255 lenght on
    sequence = data[12:20]
    deviceID = data[26:34]
    status = data[20:22]
    if status != "0a":
        _LOGGER.debug("Status code: %s (Wrong answer ? %s) %s", status, deviceID, data)
        return None # device didn't answer, wrong device
    else:
        tc2 = data[46:48]
        return int(float.fromhex(tc2))

def get_result(data): # check if data write was successfull, return True or False
    sequence = data[12:20]
    deviceID = data[26:34]
    tc2 = data[20:22]
    if str(tc2) == "0a": #data read or write
        return True
    elif str(tc2) =="01": #data report
        return True
    else:
        _LOGGER.debug("Status code: %s (Wrong answer ? %s) %s", tc2, deviceID, data)
    return False

def error_info(bug,device):
    if bug == b'FF' or bug == b'ff':
        _LOGGER.debug("in request for %s : Request failed (%s).", device, bug)
    elif bug == b'02':
        _LOGGER.debug("in request for %s : Request aborted (%s).", device, bug)
    elif bug == b'FE' or bug == b'fe':
        _LOGGER.debug("in request for %s : Buffer full, retry later (%s).", device, bug)
    elif bug == b'FC' or bug == b'fc':
        _LOGGER.debug("in request for %s : Device not responding (%s), no more answer, request aborted.", device, bug)
    elif bug == b'FB' or bug == b'fb':
        _LOGGER.debug("in request for %s : Abort failed, request not found in queue (%s).", device, bug)
    elif bug == b'FA' or bug == b'fa':
        _LOGGER.debug("in request for %s : Unknown device or destination deviceID is invalid or not a member of this network (%s).", device, bug)
    elif bug == b'FD' or bug == b'fd':
        _LOGGER.debug("in request for %s : Error message reserved (%s), info not available.", device, bug)
    else:
        _LOGGER.debug("in request for %s : Unknown error (%s).", device, bug)

def send_request(self, serv, *arg): #data
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if serv == 1:
        server_address = (self._server, PORT)
    else:
        server_address = (self._server_2, PORT)
    while sock.connect_ex(server_address) != 0:
        _LOGGER.debug("Connect fail... waiting for socket connection...")
        time.sleep(1)
    try:
        if serv == 1:
            sock.sendall(login_request(self))
        else:
            sock.sendall(login_request_2(self))
        if bytearray(sock.recv(1024)).hex()[0:14] == "55000c00110100": #Login ok
#            _LOGGER.debug("Sinope login = ok")
            sock.sendall(arg[0])
            reply = sock.recv(1024)
            if crc_check(reply):  # receive acknowledge, check status and if we will receive more data
#                _LOGGER.debug("Reply et longueur du data = %s - %s", len(reply), binascii.hexlify(reply))
                deviceid = bytearray(reply).hex()[26:34]
                if len(reply) == 19:
                    seq_num = binascii.hexlify(reply)[12:20] #sequence id to link response to the correct request
                    status = binascii.hexlify(reply)[20:22]
                    more = binascii.hexlify(reply)[24:26] #check if we will receive other data
                    if status == b'00': # request status = ok for read and write, we go on (read=00, report=01, write=00)
                        if more == b'01': #GT125 is sending another data response
                            state = status
                            while state != b'0a':
                                datarec = sock.recv(1024)
#                                _LOGGER.debug("Reply2 received for device %s, %s", deviceid, binascii.hexlify(datarec))
                                state = binascii.hexlify(datarec)[20:22]
                                if state == b'00': # request has been queued, will receive another answer later
                                    _LOGGER.debug("Request queued for device %s, waiting...", deviceid)
                                elif state == b'0a': #we got an answer
                                    return datarec
                                    break
                                elif state == b'0b': # we receive a push notification
                                    get_data_push(datarec)
                                    break
                                else:
                                    _LOGGER.debug("Bad answer received, data: %s", binascii.hexlify(datarec))
                                    error_info(state,deviceid)
                                    return False
                                    break
                        else:
                            _LOGGER.debug("No more response...")
                            return False
                    elif status == b'01': #status ok for data report
                        return reply
                    else:
                        error_info(status,deviceid)
                        return False
                elif len(reply) > 19: # case data received with the acknowledge
                    datarec = reply[19:]
#                    _LOGGER.debug("Reply coupé = %s", binascii.hexlify(datarec))
                    state = binascii.hexlify(datarec)[20:22]
                    if state == b'00': # request has been queued, will receive another answer later
                        _LOGGER.debug("Request queued for device %s, waiting...", deviceID)
                    elif state == b'0a': #we got an answer
                        return datarec
                    elif state == b'0b': # we receive a push notification
                        get_data_push(datarec)
                    else:
                        _LOGGER.debug("Bad answer received, data: %s", binascii.hexlify(datarec))
                        error_info(state,deviceid)
                        return False
                else:
                    _LOGGER.debug("Bad response, Check data send request %s", binascii.hexlify(reply))
            else:
                _LOGGER.debug("Bad response, crc error...")
        else:
            _LOGGER.debug("Sinope login fail, check your Api_Key and Api_ID")
    finally:
        sock.close()

def login_request(self):
    login_data = "550012001001"+invert(self._api_id)+self._api_key
    login_crc = bytes.fromhex(crc_count(bytes.fromhex(login_data)))
    return bytes.fromhex(login_data)+login_crc

def login_request_2(self):
    login_data = "550012001001"+invert(self._api_id_2)+self._api_key_2
    login_crc = bytes.fromhex(crc_count(bytes.fromhex(login_data)))
    return bytes.fromhex(login_data)+login_crc

def get_seq(seq):
    sequence = ""
    for _ in range(4):
        value = randint(10, 99)
        sequence += str(value)
    return sequence

def count_data(data):
    size = int(len(data)/2)
    return bytearray(struct.pack('<i', size)[:1]).hex()

def count_data_frame(data):
    size = int(len(data)/2)
    return bytearray(struct.pack('<i', size)[:2]).hex()

def data_read_request(*arg): # command,unit_id,data_app
    head = "5500"
#    data_command = arg[0]
    data_seq = get_seq(seq)
    data_type = "00"
    data_res = "000000000000"
    app_data_size = "04"
    size = count_data_frame(arg[0]+data_seq+data_type+data_res+arg[1]+app_data_size+arg[2])
    data_frame = head+size+arg[0]+data_seq+data_type+data_res+arg[1]+app_data_size+arg[2]
    read_crc = bytes.fromhex(crc_count(bytes.fromhex(data_frame)))
    return bytes.fromhex(data_frame)+read_crc

def data_report_request(*arg): # data = size+time or size+temperature (command,unit_id,data_app,data)
    head = "5500"
#    data_command = arg[0]
    data_seq = get_seq(seq)
    data_type = "00"
    data_res = "000000000000"
    app_data_size = count_data(arg[2]+arg[3])
    size = count_data_frame(arg[0]+data_seq+data_type+data_res+arg[1]+app_data_size+arg[2]+arg[3])
    data_frame = head+size+arg[0]+data_seq+data_type+data_res+arg[1]+app_data_size+arg[2]+arg[3]
    read_crc = bytes.fromhex(crc_count(bytes.fromhex(data_frame)))
    return bytes.fromhex(data_frame)+read_crc

def data_write_request(*arg): # data = size+data to send (command,unit_id,data_app,data)
    head = "5500"
#    data_command = arg[0]
    data_seq = get_seq(seq)
    data_type = "00"
    data_res = "000000000000"
    app_data_size = count_data(arg[2]+arg[3])
    size = count_data_frame(arg[0]+data_seq+data_type+data_res+arg[1]+app_data_size+arg[2]+arg[3])
    data_frame = head+size+arg[0]+data_seq+data_type+data_res+arg[1]+app_data_size+arg[2]+arg[3]
#    _LOGGER.debug("Data write request %s", data_frame)
    read_crc = bytes.fromhex(crc_count(bytes.fromhex(data_frame)))
    return bytes.fromhex(data_frame)+read_crc

class SinopeClient(object):

    def __init__(self, api_key, api_id, server, my_city, tz, api_key_2, api_id_2, server_2, timeout=REQUESTS_TIMEOUT):
        """Initialize the client object."""
        self._api_key = api_key
        self._api_id = api_id
        self._server = server
        self._api_key_2 = api_key_2
        self._api_id_2 = api_id_2
        self._server_2 = server_2
        self._my_city = my_city
        self._tz = tz
        self.device_data = {}
        self.device_info = {}

# retreive data from devices

    def get_climate_device_data(self, server, device_id):
        """Get device data."""
        # send requests
        try:
            temperature = get_temperature(bytearray(send_request(self, server, data_read_request(data_read_command,device_id,data_temperature))).hex())
            setpoint = get_temperature(bytearray(send_request(self, server, data_read_request(data_read_command,device_id,data_setpoint))).hex())
            heatlevel = get_heat_level(bytearray(send_request(self, server, data_read_request(data_read_command,device_id,data_heat_level))).hex())
            mode = get_mode(bytearray(send_request(self, server, data_read_request(data_read_command,device_id,data_mode))).hex())
            away = get_away(bytearray(send_request(self, server, data_read_request(data_read_command,device_id,data_away))).hex())
        except OSError:
            raise PySinopeError("Cannot get climate data")
        # Prepare data
        self._device_data = {'setpoint': setpoint, 'mode': mode, 'alarm': 0, 'rssi': 0, 'temperature': temperature, 'heatLevel': heatlevel, 'away': away}
        return self._device_data

    def get_light_device_data(self, server, device_id):
        """Get device data."""
        # Prepare return
        data = {}
        # send requests
        try:
            intensity = get_intensity(bytearray(send_request(self, server, data_read_request(data_read_command,device_id,data_light_intensity))).hex())
            mode = get_mode(bytearray(send_request(self, server, data_read_request(data_read_command,device_id,data_light_mode))).hex())
        except OSError:
            raise PySinopeError("Cannot get light data")
        # Prepare data
        self._device_data = {'intensity': intensity, 'mode': mode, 'alarm': 0, 'rssi': 0}
        return self._device_data

    def get_switch_device_data(self, server, device_id):
        """Get device data."""
        # send requests
        try:
            intensity = get_intensity(bytearray(send_request(self, server, data_read_request(data_read_command,device_id,data_power_intensity))).hex())
            mode = get_mode(bytearray(send_request(self, server, data_read_request(data_read_command,device_id,data_power_mode))).hex())
            powerwatt = get_power_load(bytearray(send_request(self, server, data_read_request(data_read_command,device_id,data_power_load))).hex())
        except OSError:
            raise PySinopeError("Cannot get switch data")
        # Prepare data
        self._device_data = {'intensity': intensity, 'mode': mode, 'powerWatt': powerwatt, 'alarm': 0, 'rssi': 0}
        return self._device_data

    def get_climate_device_info(self, server, device_id):
        """Get information for this device."""
        # send requests
        try:
            tempmax = get_temperature(bytearray(send_request(self, server, data_read_request(data_read_command,device_id,data_max_temp))).hex())
            tempmin = get_temperature(bytearray(send_request(self, server, data_read_request(data_read_command,device_id,data_min_temp))).hex())
            wattload = get_power_load(bytearray(send_request(self, server, data_read_request(data_read_command,device_id,data_load))).hex())
            wattoveride = get_power_load(bytearray(send_request(self, server, data_read_request(data_read_command,device_id,data_power_connected))).hex())
            keyboard = get_lock(bytearray(send_request(self, server, data_read_request(data_read_command,device_id,data_lock))).hex())
            display2 = get_mode(bytearray(send_request(self, server, data_read_request(data_read_command,device_id,data_display2))).hex())
#            backlight_state = get_mode(bytearray(send_request(self, server, data_read_request(data_read_command,device_id,data_backlight))).hex())
            backlight_idle = get_mode(bytearray(send_request(self, server, data_read_request(data_read_command,device_id,data_backlight_idle))).hex())
        except OSError:
            raise PySinopeError("Cannot get climate info")
        # Prepare data
        self._device_info = {'active': 1, 'tempMax': tempmax, 'tempMin': tempmin, 'wattage': wattload, 'wattageOverride': wattoveride, 'keypad': keyboard, 'display2': display2, 'backlight_state': None, 'backlight_idle': backlight_idle}
        return self._device_info

    def get_light_device_info(self, server, device_id):
        """Get information for this device."""
        # send requests
        try:
            timer = get_event_timer_length(bytearray(send_request(self, server, data_read_request(data_read_command,device_id,data_light_event_timer))).hex())
            keyboard = get_lock(bytearray(send_request(self, server, data_read_request(data_read_command,device_id,data_lock))).hex())
            led_on = get_led(1,bytearray(send_request(self, server, data_read_request(data_read_command,device_id,data_light_indicator_on))).hex())
            led_off = get_led(0,bytearray(send_request(self, server, data_read_request(data_read_command,device_id,data_light_indicator_off))).hex())
        except OSError:
            raise PySinopeError("Cannot get light info")
        # Prepare data
        result = []
        result.append({'active': 1, 'timer': timer, 'keypad': keyboard})
        result.append(led_on)
        result.append(led_off)
        return result

    def get_switch_device_info(self, server, device_id):
        """Get information for this device."""
        # send requests
        try:
            wattload = get_power_load(bytearray(send_request(self, server, data_read_request(data_read_command,device_id,data_power_connected))).hex())
            timer = get_event_timer_length(bytearray(send_request(self, server, data_read_request(data_read_command,device_id,data_power_event_timer))).hex())
            keyboard = get_lock(bytearray(send_request(self, server, data_read_request(data_read_command,device_id,data_lock))).hex())
        except OSError:
            raise PySinopeError("Cannot get switch info")
        # Prepare data
        self._device_info = {'active': 1, 'wattage': wattload, 'timer': timer, 'keypad': keyboard}
        return self._device_info

    def set_brightness(self, server, device_id, brightness):
        """Set device intensity."""
        try:
            response = get_result(bytearray(send_request(self, server, data_write_request(data_write_command,device_id,data_light_intensity,set_intensity(brightness)))).hex())
        except OSError:
            raise PySinopeError("Cannot set device brightness")
        return response

    def send_time(self, server, device_id):
        """Send current time to device. it is required to set device mode to auto"""
        try:
            response = get_result(bytearray(send_request(self, server, data_write_request(data_write_command,device_id,data_time,set_time(self._tz)))).hex())
        except OSError:
            raise PySinopeError("Cannot send current time to device")
        return response

    def set_mode(self, server, device_id, device_type, mode):
        """Set device operation mode."""
        # prepare data
        try:
            if int(device_type) < 100:
                response = get_result(bytearray(send_request(self, server, data_write_request(data_write_command,device_id,data_mode,put_mode(mode)))).hex())
            else:
                response = get_result(bytearray(send_request(self, server, data_write_request(data_write_command,device_id,data_light_mode,put_mode(mode)))).hex())
        except OSError:
            raise PySinopeError("Cannot set device operation mode")
        return response

    def set_away_mode(self, server, device_id, away):
        """Set device away mode. We need to send time before sending new away mode."""
        try:
            if device_id == "all":
                device_id = "FFFFFFFF"
                result = get_result(bytearray(send_request(self, server, data_report_request(data_report_command,device_id,data_time,set_time(self._tz)))).hex())
                response = get_result(bytearray(send_request(self, server, data_report_request(data_report_command,device_id,data_away,set_away(away)))).hex())
            else:
                result = get_result(bytearray(send_request(self, server, data_report_request(data_report_command,device_id,data_time,set_time(self._tz)))).hex())
                response = get_result(bytearray(send_request(self, server, data_write_request(data_write_command,device_id,data_away,set_away(away)))).hex())
        except OSError:
            raise PySinopeError("Cannot set device away")
        return response 

    def set_temperature(self, server, device_id, temperature):
        """Set device temperature."""
        try:
            response = get_result(bytearray(send_request(self, server, data_write_request(data_write_command,device_id,data_setpoint,set_temperature(temperature)))).hex())
        except OSError:
            raise PySinopeError("Cannot set device setpoint temperature")
        return response

    def set_temperature_min(self, server, device_id, temperature):
        """Set device minimum setpoint temperature."""
        try:
            response = get_result(bytearray(send_request(self, server, data_write_request(data_write_command,device_id,data_min_temp,set_temperature(temperature)))).hex())
        except OSError:
            raise PySinopeError("Cannot set device minimum setpoint temperature")
        return response

    def set_temperature_max(self, server, device_id, temperature):
        """Set device maximum setpoint temperature."""
        try:
            response = get_result(bytearray(send_request(self, server, data_write_request(data_write_command,device_id,data_max_temp,set_temperature(temperature)))).hex())
        except OSError:
            raise PySinopeError("Cannot set device maximum setpoint temperature")
        return response

    def set_event_timer(self, server, device_id, time):
        """Set device timer length."""
        try:
            response = get_result(bytearray(send_request(self, server, data_write_request(data_write_command,device_id,data_light_event_timer,set_event_timer_length(time)))).hex())
        except OSError:
            raise PySinopeError("Cannot set device event timer length")
        return response

    def set_all_away(self, server, away):
        """Set all devices to away mode 0=home, 2=away"""
        try:
            response = get_result(bytearray(send_request(self, server, data_report_request(data_report_command,all_unit,data_away,set_away(away)))).hex())
        except OSError:
            raise PySinopeError("Cannot set all devices to away or home mode")
        return response

    def set_keyboard_lock(self, server, device_id, lock):
        """lock/unlock device keyboard, unlock=0, lock=1"""
        try:
            response = get_result(bytearray(send_request(self, server, data_write_request(data_write_command,device_id,data_lock,set_lock(lock)))).hex())
        except OSError:
            raise PySinopeError("Cannot change lock device state")
        return response

    def set_second_display(self, server, device_id, display):
        """Set second display to: outdoor = 1, setpoint = 0"""
        _LOGGER.debug("Parameter server=%s, id=%s, display=%s", server, device_id, display)
        try:
            response = get_result(bytearray(send_request(self, server, data_write_request(data_write_command,device_id,data_display2,put_mode(display)))).hex())
        except OSError:
            raise PySinopeError("Cannot change second display state")
        return response

    def set_backlight_state(self, server, device_id, state):
        """set backlight state, 0 = full intensity, 1 = variable intensity when idle, 2 = off when idle, 3 = always variable intensity """
        _LOGGER.debug("Parameter server=%s, id=%s, state=%s", server, device_id, state)
        try:
            response = get_result(bytearray(send_request(self, server, data_write_request(data_write_command,device_id,data_backlight,set_light_state(state)))).hex())
        except OSError:
            raise PySinopeError("Cannot change backlight device state")
        return response

    def set_backlight_idle(self, server, device_id, level):
        """Set backlight intensity when idle, 0 off to 100 full"""
        _LOGGER.debug("Parameter server=%s, id=%s, level=%s", server, device_id, level)
        try:
            response = get_result(bytearray(send_request(self, server, data_write_request(data_write_command,device_id,data_backlight_idle,set_light_idle(level)))).hex())
        except OSError:
            raise PySinopeError("Cannot change device backlight level")
        return response

    def set_led_indicator(self, server, device_id, state, intensity, red, green, blue):
        """Set backlight intensity when idle, 0 off to 100 full"""
        if state == 0:
            data_light = data_light_indicator_off
        else:
            data_light = data_light_indicator_on
        try:
            response = get_result(bytearray(send_request(self, server, data_write_request(data_write_command,device_id,data_light,set_led_color(intensity, red, green, blue)))).hex())
        except OSError:
            raise PySinopeError("Cannot change device backlight level")
        return response

    def set_daily_report(self, server):
        """Set report to send data to each devices once a day. Needed to get proper auto mode operation"""
        _LOGGER.debug("Parameter server=%s", server)
        try:
            result = get_result(bytearray(send_request(self, server, data_report_request(data_report_command,all_unit,data_time,set_time(self._tz)))).hex())
            result = get_result(bytearray(send_request(self, server, data_report_request(data_report_command,all_unit,data_date,set_date(self._tz)))).hex())
            result = get_result(bytearray(send_request(self, server, data_report_request(data_report_command,all_unit,data_sunrise,set_sun_time(self._my_city, self._tz, "sunrise")))).hex())
            result = get_result(bytearray(send_request(self, server, data_report_request(data_report_command,all_unit,data_sunset,set_sun_time(self._my_city, self._tz, "sunset")))).hex())
        except OSError:
            raise PySinopeError("Cannot send daily report to each devices")
        return result

    def set_hourly_report(self, server, device_id, outside_temperature):
        """we need to send temperature once per hour if we want it to be displayed on second thermostat display line"""
        """We also need to send command to switch from setpoint temperature to outside temperature on second thermostat display"""
        """Display setting is done once for each thermostat"""
        try:
            if device_id == "all": #broadcasted to all devices
                device_id = "FFFFFFFF"
            result = get_result(bytearray(send_request(self, server, data_report_request(data_report_command,device_id,data_outdoor_temperature,set_temperature(outside_temperature)))).hex())
        except OSError:
            raise PySinopeError("Cannot send outside temperature report to each devices")
        return result
