"""
Support for Sinope thermostat.
type 10 = thermostat TH1120RF 3000W and 4000W
type 20 = thermostat TH1300RF 3600W floor, TH1500RF double pole thermostat
type 21 = thermostat TH1400RF low voltage
For more details about this platform, please refer to the documentation at  
https://www.sinopetech.com/en/support/#api
"""
import json
import logging

import voluptuous as vol
import time

import custom_components.sinope as sinope
from . import (SCAN_INTERVAL)
from homeassistant.components.climate import (ClimateDevice, ATTR_TEMPERATURE,
    ATTR_AWAY_MODE, ATTR_OPERATION_MODE, ATTR_OPERATION_LIST, ATTR_CURRENT_TEMPERATURE)
from homeassistant.components.climate.const import (STATE_HEAT, 
    STATE_IDLE, STATE_AUTO, STATE_MANUAL, SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_OPERATION_MODE, SUPPORT_AWAY_MODE, SUPPORT_ON_OFF)
from homeassistant.const import (TEMP_CELSIUS, TEMP_FAHRENHEIT, STATE_OFF)
from datetime import timedelta
from homeassistant.helpers.event import track_time_interval

_LOGGER = logging.getLogger(__name__)

SUPPORT_FLAGS = (SUPPORT_TARGET_TEMPERATURE | SUPPORT_OPERATION_MODE |
    SUPPORT_AWAY_MODE | SUPPORT_ON_OFF)

DEFAULT_NAME = "sinope climate"

STATE_STANDBY = 'bypass'
STATE_AWAY = 'away'
SINOPE_STATE_AWAY = 5
SINOPE_STATE_OFF = 0
SINOPE_TO_HA_STATE = {
    0: STATE_OFF,
    2: STATE_MANUAL,
    3: STATE_AUTO,
    5: STATE_AWAY,
    129: STATE_STANDBY,
    131: STATE_STANDBY,
    133: STATE_STANDBY
}
HA_TO_SINOPE_STATE = {
    value: key for key, value in SINOPE_TO_HA_STATE.items()
}
OPERATION_LIST = [STATE_OFF, STATE_MANUAL, STATE_AUTO, STATE_AWAY, STATE_STANDBY]

IMPLEMENTED_DEVICE_TYPES = [10, 20, 21]

def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the sinope thermostats."""
    data = hass.data[sinope.DATA_DOMAIN]
    dev_list = []
    with open('/home/homeassistant/.homeassistant/.storage/sinope_devices.json') as f:
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
            devices.append(SinopeThermostat(data, device_id, device_name, device_type))
        if i == tot-1:
            break
        i = i + 1
    
    add_devices(devices, True)

class SinopeThermostat(ClimateDevice):
    """Implementation of a Sinope thermostat."""

    def __init__(self, data, device_id, name, device_type):
        """Initialize."""
        self._name = name
        self._type = device_type
        self._client = data.sinope_client
        self._id = device_id
        self._wattage = None
        self._wattage_override = None
        self._min_temp = None
        self._max_temp = None
        self._target_temp = None
        self._cur_temp = None
        self._rssi = None
        self._alarm = None
        self._operation_mode = 2
        self._heat_level = None
        self._is_away = False
        _LOGGER.debug("Setting up %s: %s", self._name, self._id)

    def update(self):
        """Get the latest data from Sinope and update the state."""
        start = time.time()
        device_data = self._client.get_climate_device_data(self._id)
        end = time.time()
        elapsed = round(end - start, 3)
        _LOGGER.debug("Updating %s (%s sec): %s",
            self._name, elapsed, device_data)

        self._cur_temp = float(device_data["temperature"])
        self._target_temp = float(device_data["setpoint"]) if \
            device_data["setpoint"] is not None else 0.0
        self._heat_level = device_data["heatLevel"] if \
            device_data["heatLevel"] is not None else 0
        self._alarm = device_data["alarm"]
        self._rssi = device_data["rssi"]
        self._operation_mode = device_data["mode"]
        if device_data["mode"] != SINOPE_STATE_AWAY:
            self._is_away = False
        else:
            self._is_away = True
        device_info = self._client.get_climate_device_info(self._id)
        self._wattage = device_info["wattage"]
        self._wattage_override = device_info["wattageOverride"]
        self._min_temp = device_info["tempMin"]
        self._max_temp = device_info["tempMax"]
        return
#            _LOGGER.warning("Cannot update %s: %s", self._name, device_data)

#    def update_info(self): 
#        device_info = self._client.get_climate_device_info(self._id)
#        self._wattage = device_info["wattage"]
#        self._wattage_override = device_info["wattageOverride"]
#        self._min_temp = device_info["tempMin"]
#        self._max_temp = device_info["tempMax"]
#        return  
#       _LOGGER.warning("Cannot update %s: %s", self._name, device_info)

    @property
    def unique_id(self):
        """Return unique ID based on Sinope device ID."""
        return self._id

    @property
    def name(self):
        """Return the name of the thermostat."""
        return self._name

    @property
    def state(self):
        """Return current state i.e. heat, off, idle."""
        if self.is_on:
            return STATE_HEAT
        if self._operation_mode == SINOPE_STATE_OFF:
            return STATE_OFF
        return STATE_IDLE

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {'alarm': self._alarm,
                'heat_level': self._heat_level,
                'rssi': self._rssi,
                'wattage': self._wattage,
                'wattage_override': self._wattage_override,
                'id': self._id}

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def min_temp(self):
        """Return the min temperature."""
        return self._min_temp

    @property
    def max_temp(self):
        """Return the max temperature."""
        return self._max_temp

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def current_operation(self):
        """Return current operation i.e. off, auto, manual."""
        return self.to_hass_operation_mode(self._operation_mode)

    @property
    def operation_list(self):
        """Return the list of available operation modes."""
        return OPERATION_LIST

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._cur_temp
    
    @property
    def target_temperature (self):
        """Return the temperature we try to reach."""
        return self._target_temp

    @property
    def is_away_mode_on(self):
        return self._is_away

    @property
    def is_on(self):
        if self._heat_level == None:
            return False
        return self._heat_level > 0

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        self._client.set_temperature(self._id, temperature)
        self._target_temp = temperature

    def set_operation_mode(self, operation_mode):
        """Set new operation mode."""
        mode = self.to_sinope_operation_mode(operation_mode)
        if mode == 3: #auto mode
            self._client.send_time(self._id)
        self._client.set_mode(self._id, self._type, mode)

    def to_sinope_operation_mode(self, mode):
        """Translate hass operation modes to sinope modes."""
        if mode in HA_TO_SINOPE_STATE:
            return HA_TO_SINOPE_STATE[mode]
        _LOGGER.error("Operation mode %s could not be mapped to sinope", mode)
        return None
        
    def to_hass_operation_mode(self, mode):
        """Translate sinope operation modes to hass operation modes."""
        if mode in SINOPE_TO_HA_STATE:
            return SINOPE_TO_HA_STATE[mode]
        _LOGGER.error("Operation mode %s could not be mapped to hass", mode)
        return None
    
    def turn_away_mode_on(self):
        """Turn away mode on."""
        self._client.set_away_mode(self._id, 2)
        self._is_away = True

    def turn_away_mode_off(self):
        """Turn away mode off."""
        self._client.set_away_mode(self._id, 0)
        self._is_away = False
        
    def turn_off(self):
        """Turn device off."""
        self._client.set_mode(self._id, self._type, SINOPE_STATE_OFF)

    def turn_on(self):
        """Turn device on (auto mode)."""
        self._client.send_time(self._id)
        self._client.set_mode(self._id, self._type, 3)
