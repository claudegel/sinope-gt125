"""
Support for Sinope thermostat.
family 10 = thermostat TH1120RF 3000W and 4000W
family 20 = thermostat TH1300RF 3600W floor, TH1500RF double pole thermostat
family 21 = thermostat TH1400RF low voltage
For more details about this platform, please refer to the documentation at
https://www.sinopetech.com/en/support/#api
"""
import json
import logging

import voluptuous as vol
import time

import custom_components.sinope as sinope
from . import (SCAN_INTERVAL, CONFDIR)
from homeassistant.components.climate import (ClimateEntity)
from homeassistant.components.climate.const import (HVAC_MODE_HEAT, 
    HVAC_MODE_OFF, HVAC_MODE_AUTO, SUPPORT_TARGET_TEMPERATURE, 
    SUPPORT_PRESET_MODE, PRESET_AWAY, PRESET_NONE, CURRENT_HVAC_HEAT, 
    CURRENT_HVAC_IDLE, CURRENT_HVAC_OFF)
from homeassistant.const import (TEMP_CELSIUS, TEMP_FAHRENHEIT, ATTR_TEMPERATURE)
from datetime import timedelta
from homeassistant.helpers.event import track_time_interval
from .const import (
    ATTR_OUTSIDE_TEMPERATURE,
    SUPPORT_OUTSIDE_TEMPERATURE,
    SERVICE_SET_OUTSIDE_TEMPERATURE,
)

_LOGGER = logging.getLogger(__name__)

SUPPORT_FLAGS = (SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE | SUPPORT_OUTSIDE_TEMPERATURE)

DEFAULT_NAME = "sinope climate"

SINOPE_MODE_OFF = 0
SINOPE_MODE_FREEZE_PROTECT = 1
SINOPE_MODE_MANUAL = 2
SINOPE_MODE_AUTO = 3
SINOPE_MODE_AWAY = 5

SINOPE_BYPASS_FLAG = 128
SINOPE_BYPASSABLE_MODES = [SINOPE_MODE_FREEZE_PROTECT,
                            SINOPE_MODE_AUTO,
                            SINOPE_MODE_AWAY]
SINOPE_MODE_AUTO_BYPASS = (SINOPE_MODE_AUTO | SINOPE_BYPASS_FLAG)

SUPPORTED_HVAC_MODES = [HVAC_MODE_OFF, HVAC_MODE_AUTO, HVAC_MODE_HEAT]

PRESET_BYPASS = 'temporary'
PRESET_MODES = [
    PRESET_NONE,
    PRESET_AWAY,
    PRESET_BYPASS
]

IMPLEMENTED_DEVICE_TYPES = [10, 20, 21]
   
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the sinope thermostats."""
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
            devices.append(SinopeThermostat(data, device_id, device_name, device_type))
        if i == tot-1:
            break
        i = i + 1
    
    add_devices(devices, True)

def setup_entry(hass, config, add_entities):
    """Set up the set_outside_temperature service."""
    platform = entity_platform.current_platform.get()
    # This will call Entity.set_outside_temperature(outside_temperature=VALUE)
    platform.register_entity_service(
        SERVICE_SET_OUTSIDE_TEMPERATURE,
        {
            vol.Required(ATTR_OUTSIDE_TEMPERATURE): vol.All(
                vol.Coerce(float), vol.Range(min=-40, max=40)
            )
        },
        "set_outside_temperature",
    )

class SinopeThermostat(ClimateEntity):
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
        _LOGGER.debug("Setting up %s: %s", self._name, self._id)

    def update(self):
        """Get the latest data from Sinope and update the state."""
        start = time.time()
        device_data = self._client.get_climate_device_data(self._id)
        end = time.time()
        elapsed = round(end - start, 3)
        _LOGGER.debug("Updating %s (%s sec): %s",
            self._name, elapsed, device_data)

        self._cur_temp = float(device_data["temperature"]) if \
            device_data["temperature"] is not None else 0.0
        self._target_temp = float(device_data["setpoint"]) if \
            device_data["setpoint"] is not None else 0.0
        self._heat_level = device_data["heatLevel"] if \
            device_data["heatLevel"] is not None else 0
        self._alarm = device_data["alarm"]
        self._rssi = device_data["rssi"]
        self._operation_mode = device_data["mode"] if \
            device_data["mode"] is not None else SINOPE_MODE_MANUAL

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
    def hvac_mode(self):
        """Return current operation"""
        if self._operation_mode == SINOPE_MODE_OFF:
            return HVAC_MODE_OFF
        elif self._operation_mode in [SINOPE_MODE_AUTO, 
                                      SINOPE_MODE_AUTO_BYPASS]:
            return HVAC_MODE_AUTO
        else:
            return HVAC_MODE_HEAT

    @property
    def hvac_modes(self):
        """Return the list of available operation modes."""
        return SUPPORTED_HVAC_MODES

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._cur_temp
    
    @property
    def target_temperature (self):
        """Return the temperature we try to reach."""
        return self._target_temp

    @property
    def outside_temperature (self):
        """Return the outside temperature we try to set."""
        return self._outside_temperature
    
    @property
    def preset_modes(self):
        """Return available preset modes."""
        return PRESET_MODES
      
    @property
    def preset_mode(self):
        """Return current preset mode."""
        if self._operation_mode & SINOPE_BYPASS_FLAG == SINOPE_BYPASS_FLAG:
            return PRESET_BYPASS
        elif self._operation_mode == SINOPE_MODE_AWAY:
            return PRESET_AWAY
        else:
            return PRESET_NONE

    @property
    def hvac_action(self):
        """Return current HVAC action."""
        if self._operation_mode == SINOPE_MODE_OFF:
            return CURRENT_HVAC_OFF
        elif self._heat_level == 0:
            return CURRENT_HVAC_IDLE
        else:
            return CURRENT_HVAC_HEAT

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        self._client.set_temperature(self._id, temperature)
        self._target_temp = temperature

    def set_outside_temperature(self, outside_temperature):
        """Send command to set new outside temperature."""
        if outside_temperature is None:
            return
        self._client.set_hourly_report(self._id, outside_temperature)
        self._outside_temperature = outside_temperature

    async def async_set_outside_temperature(self, outside_temperature):
        """Send command to set new outside temperature."""
        await self._client.set_hourly_report(
            self._id, outside_temperature)
        self._outside_temperature = outside_temperature

    def set_hvac_mode(self, hvac_mode):
        """Set new hvac mode."""
        self._client.send_time(self._id)
        if hvac_mode == HVAC_MODE_OFF:
            self._client.set_mode(self._id, self._type, SINOPE_MODE_OFF)
        elif hvac_mode == HVAC_MODE_HEAT:
            self._client.set_mode(self._id, self._type, SINOPE_MODE_MANUAL)
        elif hvac_mode == HVAC_MODE_AUTO:
            self._client.set_mode(self._id, self._type, SINOPE_MODE_AUTO)
        else:
            _LOGGER.error("Unable to set hvac mode: %s.", hvac_mode)

    def set_preset_mode(self, preset_mode):
        """Activate a preset."""
        if preset_mode == self.preset_mode:
            return

        if preset_mode == PRESET_AWAY:
            """Set away mode on device, away_on = 2 away_off =0"""
            self._client.set_away_mode(self._id, 2)
        elif preset_mode == PRESET_BYPASS:
            if self._operation_mode in SINOPE_BYPASSABLE_MODES:
                self._client.set_away_mode(self._id, 0)      
                self._client.set_mode(self._id, self._type, self._operation_mode | 
                SINOPE_BYPASS_FLAG)
        elif preset_mode == PRESET_NONE:
            # Re-apply current hvac_mode without any preset
            self._client.set_away_mode(self._id, 0)
            self.set_hvac_mode(self.hvac_mode)
        else:
            _LOGGER.error("Unable to set preset mode: %s.", preset_mode)
