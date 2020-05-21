"""
Support for Sinope switch.
type 120 = load controller device, RM3250RF and RM3200RF
For more details about this platform, please refer to the documentation at  
https://www.sinopetech.com/en/support/#api
"""
import json
import logging

import voluptuous as vol
import time

import custom_components.sinope as sinope
from . import (SCAN_INTERVAL, CONFDIR)
from homeassistant.components.switch import (SwitchEntity, 
    ATTR_TODAY_ENERGY_KWH, ATTR_CURRENT_POWER_W)
from datetime import timedelta
from homeassistant.helpers.event import track_time_interval

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'sinope switch'

STATE_AUTO = 'auto'
STATE_MANUAL = 'manual'
STATE_AWAY = 'away'
STATE_STANDBY = 'bypass'
SINOPE_TO_HA_STATE = {
    1: STATE_MANUAL,
    2: STATE_AUTO,
    3: STATE_AWAY,
    130: STATE_STANDBY
}

IMPLEMENTED_DEVICE_TYPES = [120] #power control device

def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Sinope switch."""
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
            device_name = "{} {}".format(DEFAULT_NAME, dev_list[i][1])
            device_id = "{}".format(dev_list[i][0])
            device_type = "{}".format(int(dev_list[i][2]))
            devices.append(SinopeSwitch(data, device_id, device_name, device_type))
        if i == tot-1:
            break
        i = i + 1

    add_devices(devices, True)

class SinopeSwitch(SwitchEntity):
    """Implementation of a Sinope switch."""

    def __init__(self, data, device_id, name, device_type):
        """Initialize."""
        self._name = name
        self._type = device_type
        self._client = data.sinope_client
        self._id = device_id
        self._wattage = 0
        self._brightness = None
        self._operation_mode = 1
        self._alarm = None
        self._current_power_w = None
        self._rssi = None
        self._timer = 0
        _LOGGER.debug("Setting up %s: %s", self._name, self._id)

    def update(self):
        """Get the latest data from Sinope and update the state."""
        start = time.time()
        device_data = self._client.get_switch_device_data(self._id)
        end = time.time()
        elapsed = round(end - start, 3)
        _LOGGER.debug("Updating %s (%s sec): %s",
            self._name, elapsed, device_data)
        self._brightness = device_data["intensity"] if \
                device_data["intensity"] is not None else 0.0
        self._operation_mode = device_data["mode"] if \
                device_data["mode"] is not None else STATE_MANUAL
        self._alarm = device_data["alarm"]
        self._current_power_w = device_data["powerWatt"] if \
                device_data["powerWatt"] is not None else 0
        self._rssi = device_data["rssi"]
        device_info = self._client.get_switch_device_info(self._id)
        self._wattage = device_info["wattage"] if \
                device_info["wattage"] is not None else 0.0
        self._timer = device_info["timer"] if \
                device_info["timer"] is not None else 0
        return
#        _LOGGER.warning("Cannot update %s: %s", self._name, device_data)

#    def update_info(self): 
#        device_info = self._client.get_switch_device_info(self._id)
#        self._wattage = device_info["wattage"]
#        self._timer = device_info["timer"]
#        return  
#       _LOGGER.warning("Cannot update %s: %s", self._name, device_info)

    @property
    def unique_id(self):
        """Return unique ID based on Sinope device ID."""
        return self._id

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property  
    def is_on(self):
        """Return current operation i.e. ON, OFF """
        return self._brightness != 0

    def turn_on(self, **kwargs):
        """Turn the device on."""
        self._client.set_brightness(self._id, 100)
        
    def turn_off(self, **kwargs):
        """Turn the device off."""
        self._client.set_brightness(self._id, 0)

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {'alarm': self._alarm,
                'operation_mode': self.operation_mode,
                'rssi': self._rssi,
                'wattage': self._wattage,
                'id': self._id,
                'timer': self._timer}
       
    @property
    def operation_mode(self):
        return self.to_hass_operation_mode(self._operation_mode)

    @property
    def current_power_w(self):
        """Return the current power usage in W."""
        return self._current_power_w

#    @property
#    def today_energy_kwh(self):
#        """Return the today total energy usage in kWh."""
#        return self._today_energy_kwh
    
    @property
    def is_standby(self):
        """Return true if device is in standby."""
        return self._current_power_w == 0

    def to_hass_operation_mode(self, mode):
        """Translate Sinope operation modes to hass operation modes."""
        if mode in SINOPE_TO_HA_STATE:
            return SINOPE_TO_HA_STATE[mode]
        _LOGGER.error("Operation mode %s could not be mapped to hass", mode)
        return None
