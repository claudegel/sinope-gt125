"""
Support for Sinope light switch/dimmer.
type 102 = light switch SW2500RF
type 112 = light dimmer DM2500RF
For more details about this platform, please refer to the documentation at  
https://www.sinopetech.com/en/support/#api
"""
import json
import logging

import voluptuous as vol
import time

import custom_components.sinope as sinope
from . import (SCAN_INTERVAL, CONFDIR)
from homeassistant.components.light import (Light, ATTR_BRIGHTNESS,
    ATTR_BRIGHTNESS_PCT, SUPPORT_BRIGHTNESS)
from datetime import timedelta

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'sinope'

#STATE_AUTO = 'auto'
#STATE_MANUAL = 'manual'
#STATE_AWAY = 'away'
#STATE_STANDBY = 'bypass'
#SINOPE_TO_HA_STATE = {
#    1: STATE_MANUAL,
#    2: STATE_AUTO,
#    3: STATE_AWAY,
#    130: STATE_STANDBY
#}

DEVICE_TYPE_DIMMER = [112]
DEVICE_TYPE_LIGHT = [102]
IMPLEMENTED_DEVICE_TYPES = DEVICE_TYPE_LIGHT + DEVICE_TYPE_DIMMER

def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the sinope light."""
    data = hass.data[sinope.DATA_DOMAIN]
    CONF_file = CONFDIR + "sinope_devices.json"
    dev_list = []
    with open(CONF_file) as f:
        for line in f:
            dev_list.append(json.loads(line))         
    f.close()
    i = 2
    tot = len(dev_list)
    devices = []
    for a in dev_list:
        x = int(dev_list[i][2])
        if x in IMPLEMENTED_DEVICE_TYPES:
            device_name = '{} {} {}'.format(DEFAULT_NAME, 
                "dimmer" if x in DEVICE_TYPE_DIMMER 
                else "light", dev_list[i][1])
            device_id = "{}".format(dev_list[i][0])
            watt = "{}".format(dev_list[i][3])
            device_type = "{}".format(int(dev_list[i][2]))
            devices.append(SinopeLight(data, device_id, device_name, watt, device_type))
        if i == tot-1:
            break
        i = i + 1

    add_devices(devices, True)

def brightness_to_percentage(brightness):
    """Convert brightness from absolute 0..255 to percentage."""
    return int((brightness * 100.0) / 255.0)

def brightness_from_percentage(percent):
    """Convert percentage to absolute value 0..255."""
    return int((percent * 255.0) / 100.0)

class SinopeLight(Light):
    """Implementation of a Sinope light."""

    def __init__(self, data, device_id, name, wattage, device_type):
        """Initialize."""
        self._name = name
        self._type = int(device_type)
        self._client = data.sinope_client
        self._id = device_id
        self._wattage_override = wattage
        self._brightness_pct = None
        self._operation_mode = 1
        self._alarm = None
        self._rssi = None
        self._timer = 0
        self._is_dimmable = int(device_type) in DEVICE_TYPE_DIMMER
        _LOGGER.debug("Setting up %s: %s", self._name, self._id)
        
    def update(self):
        """Get the latest data from Sinope and update the state."""
        start = time.time()
        device_data = self._client.get_light_device_data(self._id)
        end = time.time()
        elapsed = round(end - start, 3)
        _LOGGER.debug("Updating %s (%s sec): %s",
            self._name, elapsed, device_data)
        self._brightness_pct = device_data["intensity"] if \
            device_data["intensity"] is not None else 0.0
        self._operation_mode = device_data["mode"] if \
            device_data["mode"] is not None else MODE_MANUAL
        self._alarm = device_data["alarm"]
        self._rssi = device_data["rssi"]
        device_info = self._client.get_light_device_info(self._id)
        self._timer = device_info["timer"] if \
            device_info["timer"] is not None else 0
        return
#        _LOGGER.warning("Cannot update %s: %s", self._name, device_data)

#    def update_info(self): 
#        device_info = self._client.get_light_device_info(self._id)
#        self._timer = device_info["timer"]
#        return  
#        _LOGGER.warning("Cannot update %s: %s", self._name, device_info)
        
    @property
    def supported_features(self):
        """Return the list of supported features."""
        if self._is_dimmable:
            return SUPPORT_BRIGHTNESS
        return 0
    
    @property
    def unique_id(self):
        """Return unique ID based on Sinope device ID."""
        return self._id

    @property
    def name(self):
        """Return the name of the light."""
        return self._name
    
    @property
    def brightness(self):
        """Return intensity of light"""
        return brightness_from_percentage(self._brightness_pct)

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._brightness_pct != 0

    # For the turn_on and turn_off functions, we would normally check if the
    # the requested state is different from the actual state to issue the 
    # command. But since we update the state every 5 minutes, there is good
    # chance that the current stored state doesn't match with real device 
    # state. So we force the set_brightness each time.
    def turn_on(self, **kwargs):
        """Turn the light on."""
        brightness_pct = 100
        if kwargs.get(ATTR_BRIGHTNESS):
            brightness_pct = \
                brightness_to_percentage(int(kwargs.get(ATTR_BRIGHTNESS)))
        elif self._is_dimmable:
            brightness_pct = 101 # Sets the light to last known brightness.
        self._client.set_brightness(self._id, brightness_pct)

    def turn_off(self, **kwargs):
        """Turn the light off."""
        self._client.set_brightness(self._id, 0)

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        data = {}
        if self._is_dimmable:
            data = {ATTR_BRIGHTNESS_PCT: self._brightness_pct}
        data.update({'alarm': self._alarm,
                     'operation_mode': self.operation_mode,
                     'rssi': self._rssi,
                     'wattage_override': self._wattage_override,
                     'id': self._id,
                     'timer': self._timer})
        return data
 
    @property
    def operation_mode(self):
        return self.to_hass_operation_mode(self._operation_mode)

    def to_hass_operation_mode(self, mode):
        """Translate sinope operation modes to hass operation modes."""
        if mode in SINOPE_TO_HA_STATE:
            return SINOPE_TO_HA_STATE[mode]
        _LOGGER.error("Operation mode %s could not be mapped to hass", mode)
        return None
